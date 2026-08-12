import assert from "node:assert/strict";
import http from "node:http";
import test from "node:test";
import {
  McpAdapterInputError,
  __test as adapterTest,
  adaptMcpToolDefinition,
  adaptToolCallPayload,
  adaptToolsListPayload,
  startMcpSchemaAdapter,
} from "../runtime/mcp-schema-adapter.mjs";
import { MCP_TURN_ID_FIELD } from "../runtime/mcp-submission-policy.mjs";

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
  assert.match(openfold2.description, /call it at most once per user request/u);
  assert.match(openfold2.description, /poll only clawbio_job_status for that exact ID, at most four times/u);
  assert.match(openfold2.inputSchema.properties.selected_models.description, /never as a quoted or stringified JSON/u);

  assert.equal(esm2.inputSchema.properties.sequences.type, "array");
  assert.equal(esm2.inputSchema.properties.sequences.items.type, "string");
  assert.deepEqual(esm2.inputSchema.required, ["sequences", "ack_research_only", "ack_non_clinical"]);
  assert.equal(catalog.size, 2);
});

test("semantic retries dedupe within one turn but identical later turns stay independent", () => {
  const turnA = "turn-aaaaaaaa-1111";
  const turnB = "turn-bbbbbbbb-2222";
  const first = adapterTest.generatedIdempotencyKey(
    "clawbio_esm2_embed",
    41,
    { sequences: ["MKTII"], format: "npz", ack_research_only: true, ack_non_clinical: true },
    { turnId: turnA, fallbackNamespace: "adapter-a:session-a" },
  );
  const retry = adapterTest.generatedIdempotencyKey(
    "clawbio_esm2_embed",
    99,
    { ack_non_clinical: true, format: "npz", ack_research_only: true, sequences: ["MKTII"] },
    { turnId: turnA, fallbackNamespace: "adapter-b:reconnected-session" },
  );
  const laterTurn = adapterTest.generatedIdempotencyKey(
    "clawbio_esm2_embed",
    99,
    { sequences: ["MKTII"], format: "npz", ack_research_only: true, ack_non_clinical: true },
    { turnId: turnB, fallbackNamespace: "adapter-a:session-a" },
  );
  const unmarkedFirst = adapterTest.generatedIdempotencyKey("clawbio_esm2_embed", 1, { sequences: ["MKTII"] }, { fallbackNamespace: "session-a" });
  const unmarkedSecond = adapterTest.generatedIdempotencyKey("clawbio_esm2_embed", 2, { sequences: ["MKTII"] }, { fallbackNamespace: "session-a" });
  assert.equal(retry, first, "one turn must survive transport RPC changes, reconnects, and adapter restarts");
  assert.notEqual(laterTurn, first, "a later user turn must be able to submit the same biological input again");
  assert.notEqual(unmarkedSecond, unmarkedFirst, "unmarked calls must never acquire a long-lived semantic dedupe scope");
});

test("schema defaults and internal turn identity normalize before hashing and forwarding", () => {
  const catalog = new Map();
  adaptToolsListPayload(TOOLS_LIST, catalog);
  const base = {
    jsonrpc: "2.0",
    method: "tools/call",
    params: {
      name: "clawbio_esm2_embed",
      arguments: {
        sequences: ["MKTII"],
        ack_research_only: true,
        ack_non_clinical: true,
        [MCP_TURN_ID_FIELD]: "turn-defaults-12345678",
      },
    },
  };
  const omitted = adaptToolCallPayload({ ...base, id: 10 }, catalog);
  const explicit = adaptToolCallPayload({
    ...base,
    id: 11,
    params: { ...base.params, arguments: { ...base.params.arguments, format: "npz" } },
  }, catalog);
  assert.deepEqual(omitted.params.arguments.request, { sequences: ["MKTII"], format: "npz" });
  assert.deepEqual(explicit.params.arguments.request, omitted.params.arguments.request);
  assert.equal(explicit.params.arguments.idempotency_key, omitted.params.arguments.idempotency_key);
  assert.equal(MCP_TURN_ID_FIELD in omitted.params.arguments, false);
  assert.equal(JSON.stringify(omitted).includes("turn-defaults-12345678"), false);

  assert.throws(() => adaptToolCallPayload({
    ...base,
    id: 12,
    params: { ...base.params, arguments: { ...base.params.arguments, [MCP_TURN_ID_FIELD]: "bad value with spaces" } },
  }, catalog), /__bionemo_agent_run_id is invalid/u);
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
  assert.deepEqual(adapted.params.arguments.request, { sequences: ["MKTIIALSYIFCLVFADALKL"], format: "npz" });
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

test("JSON-RPC batches forward valid members and return invalid-params per rejected member", async (t) => {
  const upstreamPayloads = [];
  const upstream = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    upstreamPayloads.push(payload);
    const response = Array.isArray(payload)
      ? payload.filter((member) => Object.hasOwn(member, "id")).map((member) => ({
        jsonrpc: "2.0",
        id: member.id,
        result: { content: [{ type: "text", text: "queued" }] },
      }))
      : payload.method === "tools/list"
        ? { ...TOOLS_LIST, id: payload.id }
        : { jsonrpc: "2.0", id: payload.id, result: {} };
    res.writeHead(200, { "Content-Type": "application/json", "Mcp-Session-Id": "batch-session" });
    res.end(JSON.stringify(response));
  });
  await new Promise((resolve, reject) => {
    upstream.once("error", reject);
    upstream.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => upstream.close());
  const adapter = await startMcpSchemaAdapter({
    upstreamUrl: `http://127.0.0.1:${upstream.address().port}/mcp`,
    apiKey: "batch-secret",
    port: 0,
  });
  t.after(() => adapter.server.close());

  await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
  });
  const batch = [
    {
      jsonrpc: "2.0",
      id: 20,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: {
          sequences: ["MKTII"],
          ack_research_only: true,
          ack_non_clinical: true,
          [MCP_TURN_ID_FIELD]: "turn-batch-valid-12345678",
        },
      },
    },
    {
      jsonrpc: "2.0",
      id: 21,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: { sequences: ["MISSINGACK"] },
      },
    },
  ];
  const response = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Mcp-Session-Id": "batch-session" },
    body: JSON.stringify(batch),
  });
  assert.equal(response.status, 200);
  const members = await response.json();
  assert.deepEqual(members.map(({ id }) => id).sort((a, b) => a - b), [20, 21]);
  assert.equal(members.find(({ id }) => id === 21).error.code, -32602);
  assert.match(members.find(({ id }) => id === 21).error.message, /ack_research_only=true/u);
  assert.equal(upstreamPayloads.length, 2);
  assert.equal(upstreamPayloads[1].length, 1, "the invalid member must never reach Cerebrium");
  assert.equal(upstreamPayloads[1][0].id, 20);

  const allInvalidResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Mcp-Session-Id": "batch-session" },
    body: JSON.stringify([batch[1], { ...batch[1], id: 22 }]),
  });
  assert.equal(allInvalidResponse.status, 200);
  assert.deepEqual((await allInvalidResponse.json()).map(({ id }) => id), [21, 22]);
  assert.equal(upstreamPayloads.length, 2, "an all-invalid batch must be answered locally");
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
    if (payload.method === "notifications/initialized") {
      res.writeHead(202, { "Content-Type": "application/json", "Content-Length": "0" });
      res.end();
      return;
    }
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
        arguments: {
          sequences: ["MKTIIALSYIFCLVFADALKL"],
          ack_research_only: true,
          ack_non_clinical: true,
          [MCP_TURN_ID_FIELD]: "turn-loopback-11111111",
        },
      },
    }),
  });
  assert.equal(callResponse.status, 200);
  assert.equal(upstreamCalls.length, 2);
  assert.equal(upstreamCalls.every((call) => call.authorization === `Bearer ${secret}`), true);
  assert.deepEqual(upstreamCalls[1].payload.params.arguments.request, { sequences: ["MKTIIALSYIFCLVFADALKL"], format: "npz" });
  assert.equal(upstreamCalls[1].payload.params.arguments.acknowledgements.research_only, true);
  assert.equal(MCP_TURN_ID_FIELD in upstreamCalls[1].payload.params.arguments, false);
  assert.match(upstreamCalls[1].payload.params.arguments.idempotency_key, /^bionemo-agent-[a-f0-9]{32}$/u);
  assert.equal(JSON.stringify(await callResponse.json()).includes(secret), false);

  const retryResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "Mcp-Session-Id": "test-session" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 200,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: {
          ack_non_clinical: true,
          sequences: "[\"MKTIIALSYIFCLVFADALKL\"]",
          ack_research_only: true,
          [MCP_TURN_ID_FIELD]: "turn-loopback-11111111",
        },
      },
    }),
  });
  await retryResponse.json();
  assert.equal(
    upstreamCalls[2].payload.params.arguments.idempotency_key,
    upstreamCalls[1].payload.params.arguments.idempotency_key,
    "same-session retries with a new JSON-RPC ID or legacy serialized array must reuse the upstream job key",
  );

  const secondSessionResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "Mcp-Session-Id": "another-session" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: {
          sequences: ["MKTIIALSYIFCLVFADALKL"],
          format: "npz",
          ack_research_only: true,
          ack_non_clinical: true,
          [MCP_TURN_ID_FIELD]: "turn-loopback-11111111",
        },
      },
    }),
  });
  await secondSessionResponse.json();
  assert.equal(
    upstreamCalls[1].payload.params.arguments.idempotency_key,
    upstreamCalls[3].payload.params.arguments.idempotency_key,
    "one turn must retain request identity across an MCP reconnect",
  );

  const laterTurnResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", "Mcp-Session-Id": "test-session" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: 201,
      method: "tools/call",
      params: {
        name: "clawbio_esm2_embed",
        arguments: {
          sequences: ["MKTIIALSYIFCLVFADALKL"],
          ack_research_only: true,
          ack_non_clinical: true,
          [MCP_TURN_ID_FIELD]: "turn-loopback-22222222",
        },
      },
    }),
  });
  await laterTurnResponse.json();
  assert.notEqual(
    upstreamCalls[1].payload.params.arguments.idempotency_key,
    upstreamCalls[4].payload.params.arguments.idempotency_key,
    "the same request in a later user turn must create a fresh upstream job",
  );

  const notificationResponse = await fetch(adapter.url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  });
  assert.equal(notificationResponse.status, 202);
  assert.equal(notificationResponse.headers.get("content-length"), "0");
  assert.equal(await notificationResponse.text(), "");
});
