import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";
import {
  McpAdapterInputError,
  adaptMcpToolDefinition,
  adaptToolCallPayload,
  adaptToolsListPayload,
  startMcpSchemaAdapter,
} from "../runtime/mcp-schema-adapter.mjs";

const ACKNOWLEDGEMENTS = {
  additionalProperties: false,
  properties: {
    research_only: { type: "boolean", default: false },
    non_clinical: { type: "boolean", default: false },
    non_commercial: { type: "boolean", default: false },
    aup_accepted: { type: "boolean", default: false },
    biosafety_review_required: { type: "boolean", default: false },
    no_safety_or_therapeutic_claims: { type: "boolean", default: false },
  },
  type: "object",
};

function wrappedTool(name, requestName, requestSchema) {
  return {
    name,
    description: `Test ${name}`,
    inputSchema: {
      type: "object",
      properties: {
        request: { $ref: `#/$defs/${requestName}` },
        acknowledgements: { $ref: "#/$defs/Acknowledgements" },
        idempotency_key: { type: "string" },
      },
      required: ["request", "acknowledgements", "idempotency_key"],
      $defs: { Acknowledgements: ACKNOWLEDGEMENTS, [requestName]: requestSchema },
    },
  };
}

const OPENFOLD2 = wrappedTool("clawbio_openfold2_predict", "OpenFold2Request", {
  type: "object",
  additionalProperties: false,
  properties: {
    sequence: { type: "string", minLength: 1, maxLength: 512 },
    selected_models: { type: "array", minItems: 1, maxItems: 1, items: { type: "integer" } },
  },
  required: ["sequence"],
});

const ESM2 = wrappedTool("clawbio_esm2_embed", "ESM2Request", {
  type: "object",
  additionalProperties: false,
  properties: {
    sequences: { type: "array", minItems: 1, maxItems: 32, items: { type: "string" } },
    format: { type: "string", const: "npz", default: "npz" },
  },
  required: ["sequences"],
});

const TOOLS_LIST = { jsonrpc: "2.0", id: 1, result: { tools: [OPENFOLD2, ESM2] } };

test("Cerebrium wrapper schemas become flat, dereferenced model-facing schemas", () => {
  const catalog = new Map();
  const adapted = adaptToolsListPayload(TOOLS_LIST, catalog);
  const [openfold2, esm2] = adapted.result.tools;

  assert.deepEqual(openfold2.inputSchema.required, ["sequence", "ack_research_only", "ack_non_clinical"]);
  assert.deepEqual(Object.keys(openfold2.inputSchema.properties), ["sequence", "selected_models", "ack_research_only", "ack_non_clinical"]);
  assert.equal(openfold2.inputSchema.properties.ack_research_only.const, true);
  assert.equal(JSON.stringify(openfold2).includes("$ref"), false);
  assert.equal(JSON.stringify(openfold2).includes("$defs"), false);
  assert.match(openfold2.description, /flat JSON object/u);
  assert.match(openfold2.inputSchema.properties.selected_models.description, /never as a quoted or stringified JSON/u);

  assert.equal(esm2.inputSchema.properties.sequences.type, "array");
  assert.equal(esm2.inputSchema.properties.sequences.items.type, "string");
  assert.deepEqual(esm2.inputSchema.required, ["sequences", "ack_research_only", "ack_non_clinical"]);
  assert.equal(catalog.size, 2);
});

test("the exact stringified ESM2 failure shape is canonicalized before upstream forwarding", () => {
  const catalog = new Map();
  adaptToolsListPayload(TOOLS_LIST, catalog);
  const payload = {
    jsonrpc: "2.0",
    id: 42,
    method: "tools/call",
    params: {
      name: "clawbio_esm2_embed",
      arguments: {
        sequences: "[{\"id\": \"test_seq\", \"sequence\": \"MKTIIALSYIFCLVFADALKL\"}]",
        ack_research_only: true,
        ack_non_clinical: true,
      },
    },
  };
  const adapted = adaptToolCallPayload(payload, catalog, { idempotencyKeyFactory: () => "generated-test-key" });
  assert.deepEqual(adapted.params.arguments.request, { sequences: ["MKTIIALSYIFCLVFADALKL"] });
  assert.equal(adapted.params.arguments.acknowledgements.research_only, true);
  assert.equal(adapted.params.arguments.acknowledgements.non_clinical, true);
  assert.equal(adapted.params.arguments.acknowledgements.aup_accepted, false);
  assert.equal(adapted.params.arguments.idempotency_key, "generated-test-key");
  assert.equal("sequences" in adapted.params.arguments, false);

  assert.throws(() => adaptToolCallPayload({
    ...payload,
    params: {
      ...payload.params,
      arguments: { ...payload.params.arguments, sequences: "[{\"sequence\":\"MKTII\",\"unexpected\":true}]" },
    },
  }, catalog), /must contain only string id and sequence fields/u);
});

test("the adapter never fabricates required user acknowledgements", () => {
  const catalog = new Map();
  adaptToolsListPayload(TOOLS_LIST, catalog);
  assert.throws(() => adaptToolCallPayload({
    jsonrpc: "2.0",
    id: 43,
    method: "tools/call",
    params: { name: "clawbio_esm2_embed", arguments: { sequences: ["MKTIIALSYIFCLVFADALKL"] } },
  }, catalog), (error) => error instanceof McpAdapterInputError && /ack_research_only=true/u.test(error.message));
});

test("union request schemas also become a consistent flat top-level contract", () => {
  const union = {
    name: "clawbio_esmc_analyze",
    inputSchema: {
      type: "object",
      properties: {
        request: { discriminator: { propertyName: "operation" }, oneOf: [{ $ref: "#/$defs/Embedding" }, { $ref: "#/$defs/Logits" }] },
        acknowledgements: { $ref: "#/$defs/Acknowledgements" },
        idempotency_key: { type: "string" },
      },
      required: ["request", "acknowledgements", "idempotency_key"],
      $defs: {
        Acknowledgements: ACKNOWLEDGEMENTS,
        Embedding: { type: "object", properties: { operation: { const: "embeddings" } }, required: ["operation"] },
        Logits: { type: "object", properties: { operation: { const: "logits" } }, required: ["operation"] },
      },
    },
  };
  const adapted = adaptMcpToolDefinition(union);
  assert.equal(adapted.mapping.mode, "flat-request");
  assert.equal(JSON.stringify(adapted.tool).includes("$ref"), false);
  assert.equal(JSON.stringify(adapted.tool).includes("$defs"), false);
  assert.equal(adapted.tool.inputSchema.oneOf.length, 2);
  assert.equal(adapted.tool.inputSchema.oneOf.every((branch) => !Object.hasOwn(branch.properties, "request")), true);
  assert.deepEqual(adapted.tool.inputSchema.oneOf[0].required, ["operation", "ack_research_only", "ack_non_clinical", "ack_aup_accepted"]);

  const catalog = new Map([[union.name, adapted.mapping]]);
  const call = adaptToolCallPayload({
    jsonrpc: "2.0",
    id: 9,
    method: "tools/call",
    params: {
      name: union.name,
      arguments: { operation: "logits", ack_research_only: true, ack_non_clinical: true, ack_aup_accepted: true },
    },
  }, catalog, { idempotencyKeyFactory: () => "union-key" });
  assert.deepEqual(call.params.arguments.request, { operation: "logits" });
  assert.equal(call.params.arguments.idempotency_key, "union-key");
});

test("loopback adapter forwards auth privately and rewrites list/call payloads", async (t) => {
  const secret = "mcp-test-secret-never-return";
  const upstreamCalls = [];
  const upstream = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    upstreamCalls.push({ authorization: req.headers.authorization, payload });
    const response = payload.method === "tools/list"
      ? { ...TOOLS_LIST, id: payload.id }
      : { jsonrpc: "2.0", id: payload.id, result: { content: [{ type: "text", text: "queued" }] } };
    res.writeHead(200, { "Content-Type": "application/json", "Mcp-Session-Id": "test-session" });
    res.end(JSON.stringify(response));
  });
  await new Promise((resolve, reject) => {
    upstream.once("error", reject);
    upstream.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => upstream.close());
  const upstreamUrl = `http://127.0.0.1:${upstream.address().port}/mcp`;
  const adapter = await startMcpSchemaAdapter({ upstreamUrl, apiKey: secret, port: 0 });
  t.after(() => adapter.server.close());
  assert.equal(adapter.server.listenerCount("error"), 0, "startup rejection listener must be removed after listen succeeds");

  const listResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
  });
  const listed = await listResponse.json();
  assert.deepEqual(listed.result.tools[1].inputSchema.required, ["sequences", "ack_research_only", "ack_non_clinical"]);
  assert.equal(listResponse.headers.get("mcp-session-id"), "test-session");

  const callResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "Mcp-Session-Id": "test-session" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: { sequences: ["MKTIIALSYIFCLVFADALKL"], ack_research_only: true, ack_non_clinical: true },
      },
    }),
  });
  assert.equal(callResponse.status, 200);
  assert.equal(upstreamCalls.length, 2);
  assert.equal(upstreamCalls.every((call) => call.authorization === `Bearer ${secret}`), true);
  assert.deepEqual(upstreamCalls[1].payload.params.arguments.request.sequences, ["MKTIIALSYIFCLVFADALKL"]);
  assert.equal(upstreamCalls[1].payload.params.arguments.acknowledgements.research_only, true);
  assert.match(upstreamCalls[1].payload.params.arguments.idempotency_key, /^bionemo-agent-[a-f0-9]{32}$/u);
  assert.equal(JSON.stringify(await callResponse.json()).includes(secret), false);

  const secondSessionResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "Mcp-Session-Id": "another-session" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: { sequences: ["MKTIIALSYIFCLVFADALKL"], ack_research_only: true, ack_non_clinical: true },
      },
    }),
  });
  await secondSessionResponse.json();
  assert.notEqual(
    upstreamCalls[1].payload.params.arguments.idempotency_key,
    upstreamCalls[2].payload.params.arguments.idempotency_key,
    "idempotency keys must not collide across MCP sessions",
  );
});
