const SECRET_KEY_PATTERN = /(?:authorization|api[-_]?key|token|secret|password|credential)/iu;
const BEARER_PATTERN = /Bearer\s+[A-Za-z0-9._~+\/=\-]{8,}/giu;
const NVIDIA_KEY_PATTERN = /nvapi-[A-Za-z0-9_\-]{8,}/giu;

export class InputError extends Error {
  constructor(message) {
    super(message);
    this.name = "InputError";
    this.code = "invalid_input";
  }
}

export class VendorError extends Error {
  constructor(message, { status = 502, code = "vendor_error", retryable = false } = {}) {
    super(message);
    this.name = "VendorError";
    this.status = status;
    this.code = code;
    this.retryable = retryable;
  }
}

export function redactText(value) {
  return String(value ?? "")
    .replace(BEARER_PATTERN, "Bearer [redacted]")
    .replace(NVIDIA_KEY_PATTERN, "[redacted-nvidia-key]")
    .slice(0, 4_096);
}

export function redactSecrets(value, depth = 0) {
  if (depth > 12) return "[depth-limited]";
  if (Array.isArray(value)) return value.slice(0, 2_000).map((item) => redactSecrets(item, depth + 1));
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        SECRET_KEY_PATTERN.test(key) ? "[redacted]" : redactSecrets(item, depth + 1),
      ]),
    );
  }
  return typeof value === "string" ? redactText(value) : value;
}

export function publicError(error) {
  const status = Number(error?.status || 0);
  let message = redactText(error?.message || "Unexpected BioNeMo adapter error");
  let code = error?.code || "internal_error";

  if (status === 401 || status === 403) {
    code = "nvidia_auth_or_entitlement";
    message = "NVIDIA rejected the request. Verify the participant NVIDIA API key and NIM entitlement.";
  } else if (status === 404) {
    code = "hosted_route_unavailable";
    message = "The pinned NVIDIA hosted NIM route is unavailable. No fallback model was substituted.";
  } else if (status === 408 || error?.name === "AbortError") {
    code = "vendor_timeout";
    message = "The hosted NIM request exceeded its bounded timeout. Retry with a smaller event-sized input.";
  } else if (status === 429) {
    code = "vendor_rate_limit";
    message = "NVIDIA rate-limited the request. Wait briefly, then retry the same bounded request.";
  }

  return { code, message, status: status || 500, retryable: Boolean(error?.retryable) };
}
