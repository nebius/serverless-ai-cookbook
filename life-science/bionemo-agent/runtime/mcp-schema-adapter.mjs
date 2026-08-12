import crypto from "node:crypto";
import http from "node:http";
import { Readable } from "node:stream";

const DEFAULT_MAX_REQUEST_BYTES = 2_500_000;
const DEFAULT_MAX_RESPONSE_BYTES = 25_000_000;
const ACKNOWLEDGEMENT_FIELDS = Object.freeze([
  "research_only",
  "non_clinical",
  "non_commercial",
  "aup_accepted",
  "biosafety_review_required",
  "no_safety_or_therapeutic_claims",
]);

// These requirements are part of the public clawbio_models_list contract. They
// are deliberately model-facing: the adapter never fabricates user consent.
const REQUIRED_ACKNOWLEDGEMENTS = Object.freeze({
  clawbio_boltz2_predict: ["research_only", "non_clinical"],
  clawbio_diffdock_dock: ["research_only", "no_safety_or_therapeutic_claims"],
  clawbio_evo2_generate: ["research_only", "non_clinical", "biosafety_review_required"],
  clawbio_genmol_generate: ["research_only", "no_safety_or_therapeutic_claims"],
  clawbio_molmim_optimize: ["research_only", "no_safety_or_therapeutic_claims"],
  clawbio_msa_search: ["research_only", "non_clinical"],
  clawbio_openfold2_predict: ["research_only", "non_clinical"],
  clawbio_openfold3_predict: ["research_only", "non_clinical"],
  clawbio_proteinmpnn_design: ["research_only", "non_clinical", "biosafety_review_required"],
  clawbio_rfdiffusion_generate: ["research_only", "non_clinical", "biosafety_review_required"],
  clawbio_cellpose_segment: ["research_only", "non_clinical"],
  clawbio_esm2_embed: ["research_only", "non_clinical"],
  clawbio_esmc_analyze: ["research_only", "non_clinical", "aup_accepted"],
  clawbio_scvi_fit_transform: ["research_only", "non_clinical"],
  clawbio_scanvi_fit_transform: ["research_only", "non_clinical"],
  clawbio_deepvariant_call: ["research_only", "non_clinical"],
  clawbio_alphagenome_predict: ["research_only", "non_clinical", "non_commercial"],
});

const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

export class McpAdapterInputError extends Error {
  constructor(message) {
    super(message);
    this.name = "McpAdapterInputError";
  }
}

function plainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function clone(value) {
  return structuredClone(value);
}

function decodeJsonPointerToken(value) {
  return value.replaceAll("~1", "/").replaceAll("~0", "~");
}

function localReference(root, reference) {
  if (typeof reference !== "string" || !reference.startsWith("#/")) {
    throw new McpAdapterInputError(`unsupported MCP schema reference: ${String(reference)}`);
  }
  let value = root;
  for (const token of reference.slice(2).split("/").map(decodeJsonPointerToken)) {
    if (!plainObject(value) || !Object.hasOwn(value, token)) {
      throw new McpAdapterInputError(`unresolved MCP schema reference: ${reference}`);
    }
    value = value[token];
  }
  return value;
}

function dereferenceSchema(value, root, stack = [], depth = 0) {
  if (depth > 48) throw new McpAdapterInputError("MCP schema reference nesting is too deep");
  if (Array.isArray(value)) return value.map((item) => dereferenceSchema(item, root, stack, depth + 1));
  if (!plainObject(value)) return value;
  if (typeof value.$ref === "string") {
    if (stack.includes(value.$ref)) throw new McpAdapterInputError(`cyclic MCP schema reference: ${value.$ref}`);
    const target = localReference(root, value.$ref);
    const siblings = Object.fromEntries(Object.entries(value).filter(([key]) => key !== "$ref"));
    return dereferenceSchema({ ...clone(target), ...siblings }, root, [...stack, value.$ref], depth + 1);
  }
  return Object.fromEntries(Object.entries(value)
    .filter(([key]) => key !== "$defs" && key !== "definitions")
    .map(([key, item]) => [key, dereferenceSchema(item, root, stack, depth + 1)]));
}

function schemaType(schema) {
  if (!plainObject(schema)) return null;
  if (typeof schema.type === "string") return schema.type;
  if (Array.isArray(schema.type) && schema.type.length === 1) return schema.type[0];
  return null;
}

function annotateStructuredValues(schema) {
  if (Array.isArray(schema)) return schema.map(annotateStructuredValues);
  if (!plainObject(schema)) return schema;
  const next = Object.fromEntries(Object.entries(schema).map(([key, value]) => [key, annotateStructuredValues(value)]));
  if (["array", "object"].includes(schemaType(next))) {
    const guidance = "Pass this as a native JSON value, never as a quoted or stringified JSON value.";
    next.description = next.description ? `${next.description} ${guidance}` : guidance;
  }
  return next;
}

function acknowledgementProperty(field) {
  return {
    type: "boolean",
    const: true,
    description: `Required user acknowledgement: set true only after the user has explicitly accepted ${field.replaceAll("_", " ")}.`,
  };
}

function requestSchemaVariants(inputSchema) {
  const requestProperty = inputSchema?.properties?.request;
  if (!plainObject(requestProperty)) return null;
  const resolved = dereferenceSchema(requestProperty, inputSchema);
  if (schemaType(resolved) === "object" && plainObject(resolved.properties)) {
    return { variants: [resolved], discriminatorProperty: null };
  }
  if (Array.isArray(resolved.oneOf) && resolved.oneOf.length > 0) {
    const variants = resolved.oneOf.filter((item) => schemaType(item) === "object" && plainObject(item.properties));
    if (variants.length === resolved.oneOf.length) {
      const discriminatorProperty = typeof resolved.discriminator?.propertyName === "string" ? resolved.discriminator.propertyName : null;
      return { variants, discriminatorProperty };
    }
  }
  return null;
}

function toolDescription(description) {
  const prefix = typeof description === "string" && description.trim() ? `${description.trim()} ` : "";
  return `${prefix}Arguments use one flat JSON object. Arrays and objects must be native JSON values, not strings. The local adapter supplies the upstream request envelope and idempotency key.`;
}

export function adaptMcpToolDefinition(tool) {
  if (!plainObject(tool) || typeof tool.name !== "string" || !plainObject(tool.inputSchema)) {
    return { tool: clone(tool), mapping: null };
  }
  const requestDefinition = requestSchemaVariants(tool.inputSchema);
  const requiredAcknowledgements = REQUIRED_ACKNOWLEDGEMENTS[tool.name];
  if (!requestDefinition || !requiredAcknowledgements) {
    const next = clone(tool);
    next.inputSchema = annotateStructuredValues(dereferenceSchema(tool.inputSchema, tool.inputSchema));
    return { tool: next, mapping: null };
  }

  const acknowledgementProperties = Object.fromEntries(requiredAcknowledgements.map((field) => [`ack_${field}`, acknowledgementProperty(field)]));
  const flatVariants = requestDefinition.variants.map((requestSchema) => ({
    type: "object",
    additionalProperties: false,
    properties: { ...annotateStructuredValues(requestSchema.properties), ...acknowledgementProperties },
    required: [...new Set([
      ...(Array.isArray(requestSchema.required) ? requestSchema.required : []),
      ...requiredAcknowledgements.map((field) => `ack_${field}`),
    ])],
  }));
  const next = clone(tool);
  next.description = toolDescription(tool.description);
  next.inputSchema = flatVariants.length === 1
    ? { ...flatVariants[0], title: `${tool.name}Arguments` }
    : { type: "object", oneOf: flatVariants, title: `${tool.name}Arguments` };
  return {
    tool: next,
    mapping: {
      mode: "flat-request",
      requestSchemas: requestDefinition.variants,
      requestKeys: [...new Set(requestDefinition.variants.flatMap((schema) => Object.keys(schema.properties)))],
      discriminatorProperty: requestDefinition.discriminatorProperty,
      requiredAcknowledgements: [...requiredAcknowledgements],
    },
  };
}

export function adaptToolsListPayload(payload, catalog = new Map()) {
  if (Array.isArray(payload)) return payload.map((item) => adaptToolsListPayload(item, catalog));
  if (!plainObject(payload) || !Array.isArray(payload.result?.tools)) return clone(payload);
  const next = clone(payload);
  next.result.tools = payload.result.tools.map((tool) => {
    const adapted = adaptMcpToolDefinition(tool);
    if (adapted.mapping) catalog.set(tool.name, adapted.mapping);
    return adapted.tool;
  });
  return next;
}

function maybeParseStructuredString(value, schema, label) {
  const expected = schemaType(schema);
  if (typeof value !== "string" || !["array", "object"].includes(expected)) return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  try {
    const parsed = JSON.parse(trimmed);
    if ((expected === "array" && Array.isArray(parsed)) || (expected === "object" && plainObject(parsed))) return parsed;
  } catch {}
  throw new McpAdapterInputError(`${label} must be a native JSON ${expected}, not a string`);
}

function coerceStructuredValue(value, schema, label, toolName) {
  const wasSerialized = typeof value === "string";
  const parsed = maybeParseStructuredString(value, schema, label);
  if (Array.isArray(parsed)) {
    let items = parsed;
    if (wasSerialized && toolName === "clawbio_esm2_embed" && label === "sequences" && schemaType(schema?.items) === "string") {
      items = parsed.map((item, index) => {
        if (typeof item === "string") return item;
        if (plainObject(item) && typeof item.sequence === "string") {
          const unknown = Object.keys(item).filter((key) => !["id", "sequence"].includes(key));
          if (unknown.length || (item.id !== undefined && typeof item.id !== "string")) {
            throw new McpAdapterInputError(`sequences[${index}] must contain only string id and sequence fields`);
          }
          return item.sequence;
        }
        throw new McpAdapterInputError(`sequences[${index}] must be a protein sequence string`);
      });
    }
    return items.map((item, index) => coerceStructuredValue(item, schema?.items, `${label}[${index}]`, toolName));
  }
  if (plainObject(parsed) && plainObject(schema?.properties)) {
    return Object.fromEntries(Object.entries(parsed).map(([key, item]) => [
      key,
      coerceStructuredValue(item, schema.properties[key], `${label}.${key}`, toolName),
    ]));
  }
  return parsed;
}

function generatedIdempotencyKey(toolName, jsonRpcId, argumentsValue, namespace = "") {
  const digest = crypto.createHash("sha256")
    .update(JSON.stringify([namespace, toolName, jsonRpcId ?? null, argumentsValue]))
    .digest("hex")
    .slice(0, 32);
  return `bionemo-agent-${digest}`;
}

export function adaptToolCallPayload(payload, catalog, { idempotencyKeyFactory = generatedIdempotencyKey } = {}) {
  if (Array.isArray(payload)) return payload.map((item) => adaptToolCallPayload(item, catalog, { idempotencyKeyFactory }));
  if (!plainObject(payload) || payload.method !== "tools/call" || !plainObject(payload.params)) return clone(payload);
  const toolName = payload.params.name;
  const mapping = catalog.get(toolName);
  if (!mapping || mapping.mode !== "flat-request") return clone(payload);
  const supplied = plainObject(payload.params.arguments) ? payload.params.arguments : {};
  let requestSchema;
  if (mapping.requestSchemas.length === 1) requestSchema = mapping.requestSchemas[0];
  else if (mapping.discriminatorProperty) {
    const discriminatorValue = supplied[mapping.discriminatorProperty];
    requestSchema = mapping.requestSchemas.find((schema) => schema.properties?.[mapping.discriminatorProperty]?.const === discriminatorValue);
    if (!requestSchema) {
      const choices = mapping.requestSchemas.map((schema) => schema.properties?.[mapping.discriminatorProperty]?.const).filter(Boolean);
      throw new McpAdapterInputError(`${toolName}.${mapping.discriminatorProperty} must be one of: ${choices.join(", ")}`);
    }
  } else {
    requestSchema = mapping.requestSchemas.find((schema) => (schema.required || []).every((key) => Object.hasOwn(supplied, key)));
    if (!requestSchema) throw new McpAdapterInputError(`${toolName} does not match any supported request variant`);
  }
  const requestKeys = Object.keys(requestSchema.properties);
  const allowed = new Set([...requestKeys, ...mapping.requiredAcknowledgements.map((field) => `ack_${field}`)]);
  const unknown = Object.keys(supplied).filter((key) => !allowed.has(key));
  if (unknown.length) throw new McpAdapterInputError(`${toolName} contains unsupported fields: ${unknown.join(", ")}`);

  const request = {};
  for (const key of requestKeys) {
    if (!Object.hasOwn(supplied, key)) continue;
    request[key] = coerceStructuredValue(supplied[key], requestSchema.properties[key], key, toolName);
  }
  for (const key of requestSchema.required || []) {
    if (!Object.hasOwn(request, key)) throw new McpAdapterInputError(`${toolName} is missing required field: ${key}`);
  }
  const acknowledgements = {};
  for (const field of ACKNOWLEDGEMENT_FIELDS) acknowledgements[field] = false;
  for (const field of mapping.requiredAcknowledgements) {
    if (supplied[`ack_${field}`] !== true) {
      throw new McpAdapterInputError(`${toolName} requires explicit ack_${field}=true`);
    }
    acknowledgements[field] = true;
  }

  const next = clone(payload);
  next.params.arguments = {
    request,
    acknowledgements,
    idempotency_key: idempotencyKeyFactory(toolName, payload.id, supplied),
  };
  return next;
}

function jsonRpcInvalidParams(payload, message) {
  return {
    jsonrpc: "2.0",
    id: plainObject(payload) && Object.hasOwn(payload, "id") ? payload.id : null,
    error: { code: -32602, message },
  };
}

function requestHeaders(req, apiKey) {
  const headers = new Headers();
  for (const [key, rawValue] of Object.entries(req.headers)) {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase()) || key.toLowerCase() === "authorization") continue;
    if (Array.isArray(rawValue)) rawValue.forEach((value) => headers.append(key, value));
    else if (rawValue !== undefined) headers.set(key, rawValue);
  }
  headers.set("Authorization", `Bearer ${apiKey}`);
  return headers;
}

function responseHeaders(upstream, transformed) {
  const headers = {};
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) return;
    headers[key] = value;
  });
  if (transformed) delete headers["content-encoding"];
  return headers;
}

async function readRequestBody(req, maxBytes) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of req) {
    bytes += chunk.length;
    if (bytes > maxBytes) throw new McpAdapterInputError(`MCP request exceeds ${maxBytes} bytes`);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

async function readResponseBody(response, maxBytes) {
  const declared = Number(response.headers.get("content-length") || 0);
  if (declared > maxBytes) throw new Error(`MCP response exceeds ${maxBytes} bytes`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > maxBytes) throw new Error(`MCP response exceeds ${maxBytes} bytes`);
  return bytes;
}

function transformEventStream(body, catalog) {
  return body.replace(/(^|\n)data: ([^\n]+)(?=\n|$)/gu, (line, prefix, encoded) => {
    try {
      return `${prefix}data: ${JSON.stringify(adaptToolsListPayload(JSON.parse(encoded), catalog))}`;
    } catch {
      return line;
    }
  });
}

export function startMcpSchemaAdapter({
  upstreamUrl,
  apiKey,
  port = 18791,
  host = "127.0.0.1",
  fetchImpl = globalThis.fetch,
  maxRequestBytes = DEFAULT_MAX_REQUEST_BYTES,
  maxResponseBytes = DEFAULT_MAX_RESPONSE_BYTES,
} = {}) {
  if (!upstreamUrl) throw new Error("MCP schema adapter requires upstreamUrl");
  if (!apiKey) throw new Error("MCP schema adapter requires apiKey");
  const target = new URL(upstreamUrl);
  const catalog = new Map();
  const adapterInstanceId = crypto.randomBytes(16).toString("hex");
  const server = http.createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end('{"status":"ok"}\n');
      return;
    }
    if (req.url !== "/mcp" || !["GET", "POST", "DELETE"].includes(req.method || "")) {
      res.writeHead(404, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end('{"error":"not found"}\n');
      return;
    }

    let requestPayload = null;
    let requestBody;
    try {
      requestBody = req.method === "POST" ? await readRequestBody(req, maxRequestBytes) : undefined;
      if (requestBody?.length) {
        requestPayload = JSON.parse(requestBody.toString("utf8"));
        const sessionId = Array.isArray(req.headers["mcp-session-id"])
          ? req.headers["mcp-session-id"][0]
          : req.headers["mcp-session-id"];
        requestPayload = adaptToolCallPayload(requestPayload, catalog, {
          idempotencyKeyFactory: (toolName, jsonRpcId, argumentsValue) => generatedIdempotencyKey(
            toolName,
            jsonRpcId,
            argumentsValue,
            `${adapterInstanceId}:${sessionId || "no-session"}`,
          ),
        });
        requestBody = Buffer.from(JSON.stringify(requestPayload));
      }
    } catch (error) {
      const status = error instanceof McpAdapterInputError ? 200 : 400;
      const response = jsonRpcInvalidParams(requestPayload, error instanceof Error ? error.message : "invalid MCP request");
      res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(`${JSON.stringify(response)}\n`);
      return;
    }

    try {
      const upstream = await fetchImpl(target, {
        method: req.method,
        headers: requestHeaders(req, apiKey),
        body: requestBody,
        redirect: "error",
      });
      const contentType = upstream.headers.get("content-type") || "";
      if (req.method !== "POST" || (!contentType.includes("application/json") && !contentType.includes("text/event-stream"))) {
        res.writeHead(upstream.status, responseHeaders(upstream, false));
        if (upstream.body) Readable.fromWeb(upstream.body).pipe(res);
        else res.end();
        return;
      }
      const body = await readResponseBody(upstream, maxResponseBytes);
      let transformed;
      if (contentType.includes("application/json")) {
        transformed = Buffer.from(JSON.stringify(adaptToolsListPayload(JSON.parse(body.toString("utf8")), catalog)));
      } else {
        transformed = Buffer.from(transformEventStream(body.toString("utf8"), catalog));
      }
      res.writeHead(upstream.status, {
        ...responseHeaders(upstream, true),
        "Content-Length": String(transformed.length),
      });
      res.end(transformed);
    } catch {
      res.writeHead(502, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end(`${JSON.stringify(jsonRpcInvalidParams(requestPayload, "BioNeMo MCP gateway is temporarily unavailable"))}\n`);
    }
  });

  return new Promise((resolve, reject) => {
    const onStartupError = (error) => reject(error);
    server.once("error", onStartupError);
    server.listen(port, host, () => {
      server.off("error", onStartupError);
      resolve({
        server,
        catalog,
        url: `http://${host}:${server.address().port}/mcp`,
      });
    });
  });
}

export const __test = {
  ACKNOWLEDGEMENT_FIELDS,
  REQUIRED_ACKNOWLEDGEMENTS,
  dereferenceSchema,
  generatedIdempotencyKey,
};
