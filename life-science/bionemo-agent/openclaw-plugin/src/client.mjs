import { NVIDIA_HOST, NVIDIA_ORIGIN, SKILLS } from "./catalog.mjs";
import { InputError, VendorError, redactText } from "./errors.mjs";
import { LIMITS, VALIDATORS } from "./validation.mjs";

const RETRYABLE_STATUS = new Set([429, 502, 503, 504]);

function requireNvidiaKey(env) {
  const key = env.NVIDIA_API_KEY || env.NGC_API_KEY;
  if (!key || typeof key !== "string") {
    throw new VendorError(
      "NVIDIA_API_KEY or NGC_API_KEY is not configured through the endpoint secret environment",
      { status: 401, code: "missing_nvidia_key" },
    );
  }
  return key;
}

function buildAllowedUrl(route) {
  const url = new URL(route, NVIDIA_ORIGIN);
  if (url.protocol !== "https:" || url.hostname !== NVIDIA_HOST || url.port || !url.pathname.startsWith("/v1/biology/")) {
    throw new InputError("adapter attempted a route outside the pinned NVIDIA hosted allowlist");
  }
  return url;
}

async function readBodyLimited(response, limit = LIMITS.responseBytes) {
  const advertised = Number(response.headers?.get?.("content-length") || 0);
  if (advertised > limit) throw new VendorError(`NVIDIA response exceeds ${limit} bytes`, { status: 502, code: "response_too_large" });

  if (!response.body?.getReader) {
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.length > limit) throw new VendorError(`NVIDIA response exceeds ${limit} bytes`, { status: 502, code: "response_too_large" });
    return buffer.toString("utf8");
  }

  const chunks = [];
  let total = 0;
  const reader = response.body.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > limit) {
        await reader.cancel("response limit exceeded");
        throw new VendorError(`NVIDIA response exceeds ${limit} bytes`, { status: 502, code: "response_too_large" });
      }
      chunks.push(Buffer.from(value));
    }
  } finally {
    reader.releaseLock();
  }
  return Buffer.concat(chunks, total).toString("utf8");
}

function parseVendorBody(text, status) {
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    if (status >= 400) return { detail: redactText(text) };
    throw new VendorError("NVIDIA returned a non-JSON success response", { status: 502, code: "invalid_vendor_response" });
  }
}

function vendorMessage(body, status) {
  const candidate = body?.detail || body?.message || body?.error?.message || body?.error;
  return redactText(typeof candidate === "string" ? candidate : `NVIDIA hosted NIM returned HTTP ${status}`);
}

function retryDelay(response, attempt) {
  const retryAfter = Number(response?.headers?.get?.("retry-after") || 0);
  if (Number.isFinite(retryAfter) && retryAfter > 0) return Math.min(retryAfter * 1_000, 5_000);
  return Math.min(250 * 2 ** attempt, 2_000);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function vendorPayload(skillId, payload) {
  if (skillId === "openfold2") {
    const { relax: relax_prediction, ...request } = payload;
    return {
      ...request,
      ...(relax_prediction !== undefined ? { relax_prediction } : {}),
    };
  }
  if (skillId !== "molmim") return payload;
  const { num_iterations: iterations, radius: scaled_radius, ...request } = payload;
  return {
    ...request,
    ...(iterations !== undefined ? { iterations } : {}),
    ...(scaled_radius !== undefined ? { scaled_radius } : {}),
  };
}

export class NimClient {
  constructor({ fetchImpl = globalThis.fetch, env = process.env, logger = console, retries = 2 } = {}) {
    if (typeof fetchImpl !== "function") throw new TypeError("fetch implementation is required");
    this.fetchImpl = fetchImpl;
    this.env = env;
    this.logger = logger;
    this.retries = Math.max(0, Math.min(Number(retries) || 0, 2));
  }

  async call(skillId, input) {
    const definition = SKILLS[skillId];
    const validator = VALIDATORS[skillId];
    if (!definition || !validator) throw new InputError(`unsupported NIM skill: ${skillId}`);
    const payload = validator(input);
    const route = skillId === "msa_search" && payload.sequences ? definition.pairedRoute : definition.route;
    const url = buildAllowedUrl(route);
    const key = requireNvidiaKey(this.env);
    const request = vendorPayload(skillId, payload);
    const requestBytes = Buffer.byteLength(JSON.stringify(request), "utf8");

    for (let attempt = 0; attempt <= this.retries; attempt += 1) {
      const started = performance.now();
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), definition.timeoutMs);
      let response;
      try {
        response = await this.fetchImpl(url, {
          method: "POST",
          headers: {
            Accept: "application/json",
            Authorization: `Bearer ${key}`,
            "Content-Type": "application/json",
            "User-Agent": "nebius-bionemo-agent/3.3.1",
          },
          body: JSON.stringify(request),
          redirect: "error",
          signal: controller.signal,
        });
        const text = await readBodyLimited(response);
        const body = parseVendorBody(text, response.status);
        const elapsedMs = Math.round(performance.now() - started);
        if (response.ok) {
          if (!body || typeof body !== "object") throw new VendorError("NVIDIA returned an invalid response object", { status: 502, code: "invalid_vendor_response" });
          this.logger.info?.(`BioNeMo NIM ${skillId} completed (${elapsedMs} ms, ${requestBytes} request bytes)`);
          return {
            skillId,
            route: url.pathname,
            elapsedMs,
            requestBytes,
            requestId: response.headers?.get?.("nvcf-reqid") || response.headers?.get?.("x-request-id") || null,
            data: body,
          };
        }

        const retryable = RETRYABLE_STATUS.has(response.status);
        if (retryable && attempt < this.retries) {
          await sleep(retryDelay(response, attempt));
          continue;
        }
        throw new VendorError(vendorMessage(body, response.status), {
          status: response.status,
          code: "nvidia_http_error",
          retryable,
        });
      } catch (error) {
        if (error?.name === "AbortError") {
          throw new VendorError("NVIDIA hosted NIM request timed out", { status: 408, code: "vendor_timeout", retryable: true });
        }
        if (error instanceof InputError || error instanceof VendorError) throw error;
        if (attempt < this.retries) {
          await sleep(retryDelay(response, attempt));
          continue;
        }
        throw new VendorError(`NVIDIA hosted NIM network error: ${redactText(error?.message)}`, {
          status: 502,
          code: "vendor_network_error",
          retryable: true,
        });
      } finally {
        clearTimeout(timer);
      }
    }
    throw new VendorError("NVIDIA request exhausted retry budget", { status: 502, retryable: true });
  }
}

export const __test = { buildAllowedUrl, readBodyLimited, requireNvidiaKey, vendorPayload };
