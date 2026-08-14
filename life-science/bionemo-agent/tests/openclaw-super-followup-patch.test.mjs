import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  BIONEMO_SUPER_INITIAL_TURNS,
  BIONEMO_SUPER_NOTEBOOK_TURNS,
  bionemoNormalizeStrictOpenClawPrompt,
  bionemoSuperBoundedResultSummary,
  bionemoSuperCompletedToolTarget,
  bionemoSuperDeterministicFinalText,
  bionemoSuperInitialNotebookTool,
  bionemoSuperLocalCompletionText,
  bionemoSuperShouldFinalizeWithoutTools,
  patchOpenClawSuperFollowup,
} from "../runtime/patch-openclaw-super-followup.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";
const superModel = { provider: "tokenfactory", id: "nvidia/nemotron-3-super-120b-a12b" };
const deepSeekModel = { provider: "tokenfactory", id: "deepseek-ai/DeepSeek-V4-Pro" };

function turn(name, { id = name, isError = false, arguments: args = {}, status = "completed" } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: JSON.stringify({ status, summary: { skill: name } }) }] },
  ] };
}

const tavilyInitial = BIONEMO_SUPER_INITIAL_TURNS.find(({ name }) => name === "tavily_web__tavily_search");

function tavilyTurn() {
  return { messages: [
    { role: "user", content: [{ type: "text", text: tavilyInitial.prompt }] },
    { role: "assistant", content: [{
      type: "toolCall",
      id: "tavily-call-1",
      name: tavilyInitial.name,
      arguments: structuredClone(tavilyInitial.params),
    }] },
    {
      role: "toolResult",
      toolCallId: "tavily-call-1",
      toolName: tavilyInitial.name,
      isError: false,
      content: [{ type: "text", text: "structuredContent:\n{bounded Tavily result}" }],
      details: {
        mcpServer: "tavily_web",
        mcpTool: "tavily_search",
        structuredContent: {
          query: tavilyInitial.params.query,
          results: [
            { title: "RCSB PDB documentation", url: "https://www.rcsb.org/docs/" },
            { title: "UniProt documentation", url: "https://www.uniprot.org/help/" },
          ],
        },
      },
    },
  ] };
}

const EPHEMERAL_TAVILY_CALL_ID = "callbionemosuper0123456789ab4cde8f012345";

function ephemeralTavilyTurn() {
  const persisted = tavilyTurn();
  const structured = persisted.messages[2].details.structuredContent;
  return { messages: [
    {
      role: "user",
      content: `[Fri 2026-08-14 18:06 UTC] ${tavilyInitial.prompt}`,
    },
    {
      role: "assistant",
      stopReason: "toolUse",
      content: [{
        type: "toolCall",
        id: EPHEMERAL_TAVILY_CALL_ID,
        name: tavilyInitial.name,
        arguments: structuredClone(tavilyInitial.params),
        partialArgs: JSON.stringify(tavilyInitial.params),
      }],
    },
    {
      role: "toolResult",
      toolCallId: EPHEMERAL_TAVILY_CALL_ID,
      toolName: tavilyInitial.name,
      isError: false,
      content: [{ type: "text", text: `structuredContent:\n${JSON.stringify(structured, null, 2)}` }],
    },
  ] };
}

test("Token Factory Super and DeepSeek finalize after successful atomic wrappers only", () => {
  for (const name of [
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
    "bionemo_molmim",
    "bionemo_openfold2",
    "bionemo_openfold3",
  ]) {
    for (const model of [superModel, deepSeekModel]) {
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn(name)), true);
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn(name, { isError: true })), false);
      assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, turn("tool_call", { id: `openclaw:bionemo-agent-toolkit:${name}` })), true);
      assert.equal(bionemoSuperCompletedToolTarget(model, turn(name)), name);
      assert.match(bionemoSuperDeterministicFinalText(model, turn(name)), /returned a terminal result/u);
    }
  }
  const errored = structuredClone(turn("bionemo_compare_protein_structures"));
  errored.messages.at(-1).error = { code: "failed" };
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, errored), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, errored), false);
});

test("host-local completion is limited to exact completed Token Factory Super tool boundaries", () => {
  const completed = turn("bionemo_molmim");
  assert.match(bionemoSuperLocalCompletionText(superModel, completed), /MolMIM optimization returned a terminal result/u);
  const structured = structuredClone(completed);
  structured.messages.at(-1).content = [{ type: "text", text: "not-json" }];
  structured.messages.at(-1).structuredContent = { status: "completed", summary: { skill: "MolMIM" } };
  assert.match(bionemoSuperLocalCompletionText(superModel, structured), /MolMIM optimization returned a terminal result/u);
  assert.equal(bionemoSuperLocalCompletionText(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { status: "running" })), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { status: null })), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("bionemo_molmim", { isError: true })), undefined);
  const ambiguous = structuredClone(completed);
  delete ambiguous.messages.at(-1).isError;
  assert.equal(bionemoSuperLocalCompletionText(superModel, ambiguous), undefined);
  assert.equal(bionemoSuperLocalCompletionText(superModel, turn("tavily_search")), undefined);
  const mismatch = structuredClone(completed);
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperLocalCompletionText(superModel, mismatch), undefined);
});

test("host-local Tavily completion requires the exact source-owned turn and trusted result provenance", () => {
  const completed = tavilyTurn();
  assert.equal(bionemoSuperCompletedToolTarget(superModel, completed), tavilyInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, completed), true);
  const final = bionemoSuperLocalCompletionText(superModel, completed);
  assert.match(final, /RCSB PDB/u);
  assert.match(final, /UniProt/u);
  assert.match(final, /Source claims:/u);
  assert.match(final, /Source-owned comparison/iu);
  assert.match(final, /source titles and canonical URLs appended below/iu);

  const timestamped = structuredClone(completed);
  timestamped.messages[0].content[0].text = `[Fri 2026-08-14 18:06 UTC] ${tavilyInitial.prompt}`;
  assert.equal(bionemoSuperCompletedToolTarget(superModel, timestamped), tavilyInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, timestamped), true);
  assert.equal(bionemoSuperLocalCompletionText(superModel, timestamped), final);

  const rejected = [];
  const wrongPrompt = structuredClone(completed);
  wrongPrompt.messages[0].content[0].text += " ";
  rejected.push(wrongPrompt);
  const doubleTimestamp = structuredClone(timestamped);
  doubleTimestamp.messages[0].content[0].text = `[Fri 2026-08-14 18:06 UTC] ${doubleTimestamp.messages[0].content[0].text}`;
  rejected.push(doubleTimestamp);
  const wrongArgs = structuredClone(completed);
  wrongArgs.messages[1].content[0].arguments.max_results = 4;
  rejected.push(wrongArgs);
  const extraArg = structuredClone(completed);
  extraArg.messages[1].content[0].arguments.topic = "general";
  rejected.push(extraArg);
  const mismatchedCall = structuredClone(completed);
  mismatchedCall.messages[2].toolCallId = "other-call";
  rejected.push(mismatchedCall);
  const duplicateCall = structuredClone(completed);
  duplicateCall.messages[1].content.push(structuredClone(duplicateCall.messages[1].content[0]));
  rejected.push(duplicateCall);
  const earlierTool = structuredClone(completed);
  earlierTool.messages.splice(1, 0,
    { role: "assistant", content: [{ type: "toolCall", id: "earlier-call", name: "bionemo_models_list", arguments: {} }] },
    { role: "toolResult", toolCallId: "earlier-call", toolName: "bionemo_models_list", isError: false, content: [] },
  );
  rejected.push(earlierTool);
  const ambiguousSuccess = structuredClone(completed);
  delete ambiguousSuccess.messages[2].isError;
  rejected.push(ambiguousSuccess);
  const errored = structuredClone(completed);
  errored.messages[2].isError = true;
  rejected.push(errored);
  const reportedError = structuredClone(completed);
  reportedError.messages[2].error = { code: "rate_limited" };
  rejected.push(reportedError);
  const wrongServer = structuredClone(completed);
  wrongServer.messages[2].details.mcpServer = "other";
  rejected.push(wrongServer);
  const topLevelStructured = structuredClone(completed);
  topLevelStructured.messages[2].structuredContent = topLevelStructured.messages[2].details.structuredContent;
  rejected.push(topLevelStructured);
  const emptyResults = structuredClone(completed);
  emptyResults.messages[2].details.structuredContent.results = [];
  rejected.push(emptyResults);
  const unsafeUrl = structuredClone(completed);
  unsafeUrl.messages[2].details.structuredContent.results[0].url = "file:///tmp/result";
  rejected.push(unsafeUrl);
  const unrequestedDomain = structuredClone(completed);
  unrequestedDomain.messages[2].details.structuredContent.results[0].url = "https://evil.example/";
  rejected.push(unrequestedDomain);
  const insecureDomain = structuredClone(completed);
  insecureDomain.messages[2].details.structuredContent.results[0].url = "http://www.rcsb.org/docs/";
  rejected.push(insecureDomain);
  const controlTitle = structuredClone(completed);
  controlTitle.messages[2].details.structuredContent.results[0].title = "RCSB\nPDB";
  rejected.push(controlTitle);
  for (const boundary of rejected) {
    assert.equal(bionemoSuperCompletedToolTarget(superModel, boundary), undefined);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, boundary), false);
    assert.equal(bionemoSuperLocalCompletionText(superModel, boundary), undefined);
  }
  assert.equal(bionemoSuperCompletedToolTarget(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperLocalCompletionText(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperCompletedToolTarget({ ...superModel, provider: "nvidia" }, completed), undefined);
});

test("host-local Tavily completion accepts only the exact stripped ephemeral LLM boundary", () => {
  const completed = ephemeralTavilyTurn();
  assert.equal(EPHEMERAL_TAVILY_CALL_ID.length, 40);
  assert.equal(EPHEMERAL_TAVILY_CALL_ID.startsWith("call_bionemo_super_"), false);
  assert.match(EPHEMERAL_TAVILY_CALL_ID, /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u);
  assert.equal(bionemoSuperCompletedToolTarget(superModel, completed), tavilyInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, completed), true);
  assert.match(bionemoSuperLocalCompletionText(superModel, completed), /RCSB PDB/u);

  const rejected = [];
  const bareJson = structuredClone(completed);
  bareJson.messages[2].content[0].text = bareJson.messages[2].content[0].text.slice("structuredContent:\n".length);
  rejected.push(bareJson);
  const providerProse = structuredClone(completed);
  providerProse.messages[2].content[0].text = "Provider normal path.";
  rejected.push(providerProse);
  const wrongPrompt = structuredClone(completed);
  wrongPrompt.messages[0].content += " ";
  rejected.push(wrongPrompt);
  const projectedUserBlocks = structuredClone(completed);
  projectedUserBlocks.messages[0].content = [{ type: "text", text: projectedUserBlocks.messages[0].content }];
  rejected.push(projectedUserBlocks);
  const prefixed = structuredClone(completed);
  prefixed.messages[2].content[0].text = `prefix:${prefixed.messages[2].content[0].text}`;
  rejected.push(prefixed);
  const suffixed = structuredClone(completed);
  suffixed.messages[2].content[0].text += " trailing provider prose";
  rejected.push(suffixed);
  const trailingWhitespace = structuredClone(completed);
  trailingWhitespace.messages[2].content[0].text += "\n";
  rejected.push(trailingWhitespace);
  const compactJson = structuredClone(completed);
  const compactStructured = JSON.parse(compactJson.messages[2].content[0].text.slice("structuredContent:\n".length));
  compactJson.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(compactStructured)}`;
  rejected.push(compactJson);
  const duplicateKey = structuredClone(completed);
  duplicateKey.messages[2].content[0].text = duplicateKey.messages[2].content[0].text.replace(
    "{\n",
    `{\n  "query": ${JSON.stringify(tavilyInitial.params.query)},\n`,
  );
  rejected.push(duplicateKey);
  const oversized = structuredClone(completed);
  const oversizedStructured = JSON.parse(oversized.messages[2].content[0].text.slice("structuredContent:\n".length));
  oversizedStructured.padding = "x".repeat(65_536);
  oversized.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(oversizedStructured, null, 2)}`;
  assert.ok(oversized.messages[2].content[0].text.length > 65_536);
  rejected.push(oversized);
  const extraBlock = structuredClone(completed);
  extraBlock.messages[2].content.push({ type: "text", text: "extra" });
  rejected.push(extraBlock);
  const extraResultField = structuredClone(completed);
  extraResultField.messages[2].content[0].metadata = {};
  rejected.push(extraResultField);
  const extraAssistantBlock = structuredClone(completed);
  extraAssistantBlock.messages[1].content.push({ type: "text", text: "extra" });
  rejected.push(extraAssistantBlock);
  const wrongStopReason = structuredClone(completed);
  wrongStopReason.messages[1].stopReason = "stop";
  rejected.push(wrongStopReason);
  for (const alternateType of ["toolUse", "functionCall"]) {
    const wrongCallType = structuredClone(completed);
    wrongCallType.messages[1].content[0].type = alternateType;
    rejected.push(wrongCallType);
  }
  const alteredPartialArgs = structuredClone(completed);
  alteredPartialArgs.messages[1].content[0].partialArgs = "{}";
  rejected.push(alteredPartialArgs);
  const missingPartialArgs = structuredClone(completed);
  delete missingPartialArgs.messages[1].content[0].partialArgs;
  rejected.push(missingPartialArgs);
  const mismatchedId = structuredClone(completed);
  mismatchedId.messages[2].toolCallId = "fedcba9876543210fedcba9876543210fedcba98";
  rejected.push(mismatchedId);
  const emptyId = structuredClone(completed);
  emptyId.messages[1].content[0].id = "";
  emptyId.messages[2].toolCallId = "";
  rejected.push(emptyId);
  const nonStringId = structuredClone(completed);
  nonStringId.messages[1].content[0].id = 42;
  nonStringId.messages[2].toolCallId = 42;
  rejected.push(nonStringId);
  for (const invalidId of [
    "0123456789abcdef0123456789abcdef01234567",
    "call_bionemo_super_0123456789ab4cde8f012345",
    EPHEMERAL_TAVILY_CALL_ID.replace("4cde8", "5cde8"),
    EPHEMERAL_TAVILY_CALL_ID.replace("4cde8", "4cde7"),
  ]) {
    const invalidProjectedId = structuredClone(completed);
    invalidProjectedId.messages[1].content[0].id = invalidId;
    invalidProjectedId.messages[2].toolCallId = invalidId;
    rejected.push(invalidProjectedId);
  }
  const badArgs = structuredClone(completed);
  badArgs.messages[1].content[0].arguments.max_results = 4;
  rejected.push(badArgs);
  const badHost = structuredClone(completed);
  const badHostStructured = JSON.parse(badHost.messages[2].content[0].text.slice("structuredContent:\n".length));
  badHostStructured.results[0].url = "https://evil.example/docs/";
  badHost.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(badHostStructured, null, 2)}`;
  rejected.push(badHost);
  const credentialedUrl = structuredClone(completed);
  const credentialedStructured = JSON.parse(credentialedUrl.messages[2].content[0].text.slice("structuredContent:\n".length));
  credentialedStructured.results[0].url = "https://user:pass@www.rcsb.org/docs/";
  credentialedUrl.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(credentialedStructured, null, 2)}`;
  rejected.push(credentialedUrl);
  const explicitPort = structuredClone(completed);
  const portStructured = JSON.parse(explicitPort.messages[2].content[0].text.slice("structuredContent:\n".length));
  portStructured.results[0].url = "https://www.rcsb.org:8443/docs/";
  explicitPort.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(portStructured, null, 2)}`;
  rejected.push(explicitPort);
  const unsafeTitle = structuredClone(completed);
  const titleStructured = JSON.parse(unsafeTitle.messages[2].content[0].text.slice("structuredContent:\n".length));
  titleStructured.results[0].title = "RCSB\nPDB";
  unsafeTitle.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(titleStructured, null, 2)}`;
  rejected.push(unsafeTitle);
  const tooManyResults = structuredClone(completed);
  const tooManyStructured = JSON.parse(tooManyResults.messages[2].content[0].text.slice("structuredContent:\n".length));
  tooManyStructured.results = Array.from({ length: 6 }, (_, index) => ({ title: `RCSB ${index}`, url: `https://www.rcsb.org/docs/${index}` }));
  tooManyResults.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(tooManyStructured, null, 2)}`;
  rejected.push(tooManyResults);
  const badQuery = structuredClone(completed);
  const badQueryStructured = JSON.parse(badQuery.messages[2].content[0].text.slice("structuredContent:\n".length));
  badQueryStructured.query = "different query";
  badQuery.messages[2].content[0].text = `structuredContent:\n${JSON.stringify(badQueryStructured, null, 2)}`;
  rejected.push(badQuery);
  const missingSuccess = structuredClone(completed);
  delete missingSuccess.messages[2].isError;
  rejected.push(missingSuccess);
  const errored = structuredClone(completed);
  errored.messages[2].isError = true;
  rejected.push(errored);
  const stringSuccess = structuredClone(completed);
  stringSuccess.messages[2].isError = "false";
  rejected.push(stringSuccess);
  const reportedError = structuredClone(completed);
  reportedError.messages[2].error = { code: "provider_error" };
  rejected.push(reportedError);
  const ambiguousError = structuredClone(completed);
  ambiguousError.messages[2].error = null;
  rejected.push(ambiguousError);
  const ownUndefinedError = structuredClone(completed);
  ownUndefinedError.messages[2].error = undefined;
  rejected.push(ownUndefinedError);
  const ambiguousDetails = structuredClone(completed);
  ambiguousDetails.messages[2].details = {};
  rejected.push(ambiguousDetails);
  const ownUndefinedDetails = structuredClone(completed);
  ownUndefinedDetails.messages[2].details = undefined;
  rejected.push(ownUndefinedDetails);
  const ambiguousStructured = structuredClone(completed);
  ambiguousStructured.messages[2].structuredContent = null;
  rejected.push(ambiguousStructured);
  const ownUndefinedStructured = structuredClone(completed);
  ownUndefinedStructured.messages[2].structuredContent = undefined;
  rejected.push(ownUndefinedStructured);
  const duplicateResult = structuredClone(completed);
  duplicateResult.messages.splice(-1, 0, structuredClone(duplicateResult.messages[2]));
  rejected.push(duplicateResult);

  for (const boundary of rejected) {
    assert.equal(bionemoSuperCompletedToolTarget(superModel, boundary), undefined);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, boundary), false);
    assert.equal(bionemoSuperLocalCompletionText(superModel, boundary), undefined);
  }
  assert.equal(bionemoSuperCompletedToolTarget(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperCompletedToolTarget({ ...superModel, provider: "nvidia" }, completed), undefined);
});

test("Super initial calls are source-owned only for exact reviewed prompts", () => {
  assert.equal(BIONEMO_SUPER_NOTEBOOK_TURNS.length, 4);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS.length, 6);
  assert.deepEqual(BIONEMO_SUPER_INITIAL_TURNS.slice(0, 4), BIONEMO_SUPER_NOTEBOOK_TURNS);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS[4].name, "bionemo_molmim");
  assert.deepEqual(BIONEMO_SUPER_INITIAL_TURNS[4].params, {
    smi: "COC1=C(C=C2C(=C1)N=CN=C2NC3=CC(=C(C=C3)F)Cl)OCCCN4CCOCC4",
    algorithm: "CMA-ES",
    num_molecules: 2,
    num_iterations: 2,
    property_name: "QED",
    particles: 2,
    minimize: false,
    min_similarity: 0.7,
    radius: 1,
    ack_research_only: true,
    ack_no_safety_or_therapeutic_claims: true,
  });
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS[5], tavilyInitial);
  assert.deepEqual(tavilyInitial.params, {
    query: "RCSB PDB UniProt protein structure research contributions",
    include_domains: ["rcsb.org", "uniprot.org"],
    search_depth: "basic",
    max_results: 5,
    include_raw_content: false,
    include_images: false,
  });
  for (const expected of BIONEMO_SUPER_INITIAL_TURNS) {
    const actual = bionemoSuperInitialNotebookTool(superModel, {
      messages: [{ role: "user", content: [{ type: "text", text: expected.prompt }] }],
    });
    assert.deepEqual(actual, { name: expected.name, params: { ...expected.params } });
    assert.deepEqual(
      bionemoSuperInitialNotebookTool(superModel, { prompt: expected.prompt, messages: [] }),
      { name: expected.name, params: { ...expected.params } },
    );
    assert.deepEqual(
      bionemoSuperInitialNotebookTool(superModel, {
        messages: [{ role: "user", content: `[Fri 2026-08-14 18:06 UTC] ${expected.prompt}` }],
      }),
      { name: expected.name, params: { ...expected.params } },
    );
  }
  const [first] = BIONEMO_SUPER_NOTEBOOK_TURNS;
  const strictEnvelope = "[Fri 2026-08-14 18:06 UTC] ";
  assert.equal(bionemoNormalizeStrictOpenClawPrompt(first.prompt), first.prompt);
  assert.equal(bionemoNormalizeStrictOpenClawPrompt(`${strictEnvelope}${first.prompt}`), first.prompt);
  assert.equal(bionemoNormalizeStrictOpenClawPrompt(`${strictEnvelope}${strictEnvelope}${first.prompt}`), `${strictEnvelope}${first.prompt}`);
  assert.equal(bionemoSuperInitialNotebookTool(deepSeekModel, { messages: [{ role: "user", content: first.prompt }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [{ role: "user", content: `${first.prompt} ` }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool({ ...superModel, provider: "nvidia" }, { messages: [{ role: "user", content: first.prompt }] }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [{ role: "user", content: "List all available BioNeMo models." }] }), undefined);
  for (const role of ["toolResult", "tool", "function"]) {
    assert.equal(bionemoSuperInitialNotebookTool(superModel, { messages: [
      { role: "user", content: first.prompt },
      { role, toolName: first.name },
    ] }), undefined);
  }
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    prompt: first.prompt,
    messages: [{ role: "user", content: "Continue from the previous tool call." }],
  }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    prompt: first.prompt,
    messages: [{ role: "toolResult", toolName: first.name }],
  }), undefined);
  for (const malformed of [
    `[Fri 2026-8-14 18:06 UTC] ${first.prompt}`,
    `[Fri 2026-08-14 18:06 UTC] [Fri 2026-08-14 18:06 UTC] ${first.prompt}`,
    `prefix [Fri 2026-08-14 18:06 UTC] ${first.prompt}`,
    `[Fri 2026-08-14 18:06 UTC] ${first.prompt} `,
  ]) {
    assert.equal(bionemoSuperInitialNotebookTool(superModel, {
      messages: [{ role: "user", content: malformed }],
    }), undefined);
  }
});

test("Super fallback includes only a bounded workflow summary", () => {
  const context = turn("bionemo_compare_protein_structures");
  context.messages.at(-1).content = [{ type: "text", text: JSON.stringify({
    summary: { predictions: { openfold2: { confidence: { ptm_score: 0.81 } }, openfold3: { confidence: { ptm_score: 0.87 } } }, note: "safe" },
    artifacts: [{ viewerMarkdown: "access=must-not-appear" }],
  }) }];
  const summary = bionemoSuperBoundedResultSummary(superModel, context);
  assert.match(summary, /ptm_score/u);
  assert.doesNotMatch(summary, /must-not-appear/u);
  assert.match(bionemoSuperDeterministicFinalText(superModel, context), /Returned workflow summary/u);
});

test("post-success guard leaves initial, unrelated tools/models, errors, and mismatched chains untouched", () => {
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, { messages: [{ role: "user", content: [] }] }), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...superModel, id: "meta/llama-3.3-70b-instruct" }, turn("bionemo_batch_fold_demo")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...deepSeekModel, provider: "nvidia" }, turn("bionemo_batch_fold_demo")), false);
  for (const name of ["openfold2_predict", "job_status", "clawbio__run_skill", "clawbio_run_skill", "tavily_search", "web_search"]) {
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name)), false);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, turn(name)), false);
  }
  const mismatch = structuredClone(turn("bionemo_batch_fold_demo"));
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, mismatch), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, mismatch), false);
  const multipleCalls = structuredClone(turn("bionemo_batch_fold_demo"));
  multipleCalls.messages.at(-2).content.push({ type: "toolCall", id: "call-2", name: "bionemo_batch_fold_demo", arguments: {} });
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, multipleCalls), false);
  const notImmediate = structuredClone(turn("bionemo_batch_fold_demo"));
  notImmediate.messages.splice(-1, 0, { role: "assistant", content: [{ type: "text", text: "intervening" }] });
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, notImmediate), false);
});

test("pinned transport patch is hash-gated, idempotent, and runs after payload callbacks", { timeout: 120_000 }, async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-super-followup-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const { stdout } = await execFileAsync("docker", ["create", PINNED_IMAGE]);
  const container = stdout.trim();
  t.after(() => execFileAsync("docker", ["rm", "-f", container]).catch(() => {}));
  await execFileAsync("docker", ["cp", `${container}:/app/dist`, path.join(root, "dist")]);
  await execFileAsync("docker", ["rm", container]);
  const distRoot = path.join(root, "dist");
  assert.equal((await patchOpenClawSuperFollowup(distRoot)).changed, true);
  assert.equal((await patchOpenClawSuperFollowup(distRoot)).changed, false);
  const names = (await import("node:fs/promises")).readdir(distRoot);
  const file = (await names).find((name) => name.startsWith("openai-transport-stream-") && name.endsWith(".js"));
  const source = await readFile(path.join(distRoot, file), "utf8");
  assert.match(source, /openclaw\.bionemo\.super-followup\.v14/u);
  const callback = source.indexOf("if (nextParams !== void 0) params = nextParams;");
  const codeMode = source.indexOf("if (options?.openclawCodeModeToolSurface === true)", callback);
  const guard = source.indexOf("if (bionemoSuperFinalText)");
  const request = source.indexOf("client.chat.completions.create(params");
  assert.ok(callback >= 0 && callback < codeMode && codeMode < guard && guard < request);
  assert.match(source, /delete params\.tools;\s*params\.tool_choice = "none";/su);
  assert.match(source, /const bionemoSuperLocalFinalText = bionemoSuperLocalCompletionText\(model, context\)/u);
  assert.match(source, /const client = bionemoSuperLocalFinalText \? undefined : createOpenAICompletionsClient/u);
  assert.equal(source.match(/bionemoNormalizeStrictOpenClawPrompt\(/gu)?.length, 4);
  assert.match(source, /bionemoSuperInitialTool && Array\.isArray\(params\.tools\)\s*&& params\.tools\.some\(\(tool\) => tool\?\.function\?\.name === bionemoSuperInitialTool\.name\)/su);
  assert.doesNotMatch(source, /bionemoSuperContextTavilyTool|mcp:bundle-mcp:tavily_web__tavily_search/u);
  assert.equal(source.includes(["BIONEMO", "TEMP", "TAVILY", "POST", "RESULT", "TRANSPORT", "DIAGNOSTIC"].join("_")), false);
  assert.doesNotMatch(source, /bionemoEmitTempTavily/u);
  assert.equal(source.includes(["bionemo", "super", "initial", "diagnostic"].join("-")), false);
  assert.match(source, /const responseStream = bionemoSuperLocalResponse\s*\? \(async function\* bionemoSuperCompletedStream\(\) \{\s*yield \{ id: "bionemo-local-completion", choices:/su);
  assert.match(source, /const bionemoSuperLocalResponse = bionemoSuperLocalFinalText \|\| Boolean\(bionemoSuperInitialTool\)/u);
  assert.doesNotMatch(source, /bionemoSuperInitialTool\?\.name === "tavily_web__tavily_search"/u);
  assert.match(source, /bionemoSuperFinalText,/u);
  assert.match(source, /if \(!bionemoSuperFinalText && !bionemoSuperInitialTool && choiceDelta\.tool_calls/u);
  assert.match(source, /if \(choiceDelta\.content && !bionemoSuperFinalText && !bionemoSuperInitialTool\)/u);
  assert.match(source, /appendTextDelta\(bionemoSuperFinalText\)/u);
  assert.match(source, /params\.tool_choice = \{ type: "function", function: \{ name: bionemoSuperInitialTool\.name \} \}/u);
  await execFileAsync(process.execPath, ["--check", path.join(distRoot, file)]);

  let testingSource = source.replace(
    "export { ",
    "export { createOpenAICompletionsTransportStreamFn as __bionemoCreateOpenAICompletionsTransportStreamFn, processOpenAICompletionsStream as __bionemoProcessOpenAICompletionsStream, bionemoSuperDeterministicFinalText as __bionemoSuperDeterministicFinalText, bionemoSuperLocalCompletionText as __bionemoSuperLocalCompletionText, bionemoSuperShouldFinalizeWithoutTools as __bionemoSuperShouldFinalizeWithoutTools, ",
  );
  assert.notEqual(testingSource, source);
  testingSource = testingSource.replaceAll(
    "fetch: buildGuardedModelFetch(model),",
    "fetch: globalThis.__bionemoTestFetch ?? buildGuardedModelFetch(model),",
  );
  assert.match(testingSource, /globalThis\.__bionemoTestFetch \?\? buildGuardedModelFetch/u);
  await writeFile(path.join(distRoot, file), testingSource);
  const expectedInitial = BIONEMO_SUPER_NOTEBOOK_TURNS[1];
  const expectedTavilyInitial = tavilyInitial;
  const integrationScript = `
    import assert from "node:assert/strict";
    const patched = await import("file:///app/dist/${file}?test=" + Date.now());
    const model = ${JSON.stringify({ ...superModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const deepSeekModel = ${JSON.stringify({ ...deepSeekModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 1_048_576, maxTokens: 8_192 })};
    const expectedInitial = ${JSON.stringify({ name: expectedInitial.name, params: { ...expectedInitial.params } })};
    const expectedTavilyInitial = ${JSON.stringify({ name: expectedTavilyInitial.name, params: { ...expectedTavilyInitial.params } })};
    const expectedInitialTurns = ${JSON.stringify(BIONEMO_SUPER_INITIAL_TURNS.map(({ prompt, name, params }) => ({ prompt, name, params: { ...params } })))};
    const output = () => ({ role: "assistant", content: [], api: model.api, provider: model.provider, model: model.id, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0, cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 } }, stopReason: "stop", timestamp: Date.now() });
    const chunks = () => (async function* providerChunks() { yield { id: "response-1", choices: [{ index: 0, delta: { content: "<tool_call><function=read><parameter=path>artifact.pdb</parameter></function></tool_call>", tool_calls: [{ index: 0, id: "provider-call", type: "function", function: { name: "babel", arguments: "{}" } }] }, finish_reason: "tool_calls" }] }; }());
    const initialOutput = output();
    const initialEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), initialOutput, model, { push: (event) => initialEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperInitialTool: expectedInitial });
    assert.equal(initialOutput.stopReason, "toolUse");
    assert.deepEqual(initialOutput.content.filter(({ type }) => type === "toolCall").map(({ name, arguments: args }) => ({ name, args })), [{ name: expectedInitial.name, args: expectedInitial.params }]);
    assert.equal(initialOutput.content.some(({ type }) => type === "text"), false);
    assert.deepEqual(initialEvents.filter(({ type }) => type === "toolcall_start").map(({ partial }) => partial.content.at(-1).name), [expectedInitial.name]);
    assert.equal(initialEvents.filter(({ type }) => type === "toolcall_delta").length, 1);
    const wrongTavilyOutput = output();
    const wrongTavilyEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), wrongTavilyOutput, model, { push: (event) => wrongTavilyEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperInitialTool: expectedTavilyInitial });
    assert.equal(wrongTavilyOutput.stopReason, "toolUse");
    assert.deepEqual(wrongTavilyOutput.content, [{
      type: "toolCall",
      id: wrongTavilyOutput.content[0].id,
      name: "tavily_web__tavily_search",
      arguments: expectedTavilyInitial.params,
      partialArgs: JSON.stringify(expectedTavilyInitial.params),
    }]);
    assert.deepEqual(wrongTavilyEvents.filter(({ type }) => type === "toolcall_start").map(({ partial }) => partial.content.at(-1).name), [expectedTavilyInitial.name]);
    const noToolChunks = () => (async function* providerChunks() {
      yield { id: "response-no-tool", choices: [{ index: 0, delta: { content: "I will not call a tool." }, finish_reason: "stop" }] };
    }());
    const missingTavilyOutput = output();
    await patched.__bionemoProcessOpenAICompletionsStream(noToolChunks(), missingTavilyOutput, model, { push: () => {} }, { emitReasoning: false, bionemoSuperInitialTool: expectedTavilyInitial });
    assert.equal(missingTavilyOutput.stopReason, "toolUse");
    assert.deepEqual(missingTavilyOutput.content.filter(({ type }) => type === "toolCall").map(({ name, arguments: args }) => ({ name, args })), [{ name: expectedTavilyInitial.name, args: expectedTavilyInitial.params }]);
    assert.equal(missingTavilyOutput.content.some(({ type }) => type === "text"), false);
    const finalOutput = output();
    const finalEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), finalOutput, model, { push: (event) => finalEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperFinalText: "Deterministic completed result." });
    assert.equal(finalOutput.stopReason, "stop");
    assert.equal(finalOutput.content.some(({ type }) => type === "toolCall"), false);
    assert.equal(finalOutput.content.filter(({ type }) => type === "text").map(({ text }) => text).join(""), "Deterministic completed result.");
    assert.equal(JSON.stringify(finalOutput).includes("<tool_call>"), false);
    assert.equal(finalEvents.some(({ type }) => type.startsWith("toolcall_")), false);

    const successfulBoundary = ${JSON.stringify(turn("bionemo_batch_fold_demo"))};
    const successfulTavilyBoundary = ${JSON.stringify(tavilyTurn())};
    const successfulEphemeralTavilyBoundary = ${JSON.stringify(ephemeralTavilyTurn())};
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, successfulBoundary), true);
    const sourceOwnedFinal = patched.__bionemoSuperDeterministicFinalText(deepSeekModel, successfulBoundary);
    assert.match(sourceOwnedFinal, /five-protein OpenFold2 workflow returned a terminal result/u);
    const superLocalFinal = patched.__bionemoSuperLocalCompletionText(model, successfulBoundary);
    assert.match(superLocalFinal, /five-protein OpenFold2 workflow returned a terminal result/u);
    assert.equal(patched.__bionemoSuperLocalCompletionText(deepSeekModel, successfulBoundary), undefined);

    const collectEvents = async (eventStream) => {
      const events = [];
      for await (const event of eventStream) events.push(event);
      return events;
    };
    const within = async (promise, timeoutMs) => {
      let timer;
      try {
        return await Promise.race([
          promise,
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("transport did not finish locally")), timeoutMs); }),
        ]);
      } finally {
        clearTimeout(timer);
      }
    };
    const transport = patched.__bionemoCreateOpenAICompletionsTransportStreamFn();
    let providerFetchCalls = 0;
    globalThis.__bionemoTestFetch = async () => {
      providerFetchCalls += 1;
      return await new Promise(() => {});
    };
    for (const expected of expectedInitialTurns) {
      const exactInitialContext = { messages: [{ role: "user", content: "[Fri 2026-08-14 18:06 UTC] " + expected.prompt }] };
      const initialEvents = await within(collectEvents(transport(model, exactInitialContext, {
        apiKey: "test-key",
        emitReasoning: false,
        signal: AbortSignal.timeout(500),
        onPayload(params) {
          return { ...params, tools: [{ type: "function", function: { name: expected.name, description: "bounded test", parameters: { type: "object" } } }] };
        },
      })), 750);
      assert.equal(providerFetchCalls, 0, expected.name + " must not start a zero-byte provider request");
      assert.equal(initialEvents.some(({ type }) => type === "error"), false, JSON.stringify(initialEvents));
      assert.equal(initialEvents.at(0).type, "start");
      assert.equal(initialEvents.at(-1).type, "done");
      assert.equal(initialEvents.at(-1).message.stopReason, "toolUse");
      assert.deepEqual(initialEvents.at(-1).message.content, [{
        type: "toolCall",
        id: initialEvents.at(-1).message.content[0].id,
        name: expected.name,
        arguments: expected.params,
        partialArgs: JSON.stringify(expected.params),
      }]);
      assert.equal(initialEvents.at(-1).message.content[0].id.startsWith("call_bionemo_super_"), true);
    }
    const expectedScienceInitial = expectedInitialTurns[0];
    const exactScienceInitialContext = { messages: [{ role: "user", content: "[Fri 2026-08-14 18:06 UTC] " + expectedScienceInitial.prompt }] };
    const localEvents = await within(collectEvents(transport(model, successfulBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "completed Super boundary must not start the zero-byte provider follow-up");
    assert.equal(localEvents.some(({ type }) => type === "error"), false, JSON.stringify(localEvents));
    assert.equal(localEvents.at(0).type, "start");
    assert.equal(localEvents.at(-1).type, "done");
    assert.equal(localEvents.some(({ type }) => type === "text_start"), true);
    assert.equal(localEvents.some(({ type }) => type === "text_delta"), true);
    assert.deepEqual(localEvents.at(-1).message.content, [{ type: "text", text: superLocalFinal }]);
    assert.equal(localEvents.at(-1).message.stopReason, "stop");

    const timestampedSuccessfulTavilyBoundary = structuredClone(successfulTavilyBoundary);
    timestampedSuccessfulTavilyBoundary.messages[0].content[0].text = "[Fri 2026-08-14 18:06 UTC] "
      + timestampedSuccessfulTavilyBoundary.messages[0].content[0].text;
    const tavilyLocalFinal = patched.__bionemoSuperLocalCompletionText(model, timestampedSuccessfulTavilyBoundary);
    assert.match(tavilyLocalFinal, /RCSB PDB/u);
    assert.match(tavilyLocalFinal, /UniProt/u);
    const tavilyLocalEvents = await within(collectEvents(transport(model, timestampedSuccessfulTavilyBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "timestamp-prefixed successful Tavily boundary must not start a zero-byte provider follow-up");
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "error"), false, JSON.stringify(tavilyLocalEvents));
    assert.equal(tavilyLocalEvents.at(0).type, "start");
    assert.equal(tavilyLocalEvents.at(-1).type, "done");
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "text_start"), true);
    assert.equal(tavilyLocalEvents.some(({ type }) => type === "text_delta"), true);
    assert.deepEqual(tavilyLocalEvents.at(-1).message.content, [{ type: "text", text: tavilyLocalFinal }]);
    assert.equal(tavilyLocalEvents.at(-1).message.stopReason, "stop");

    assert.equal(successfulEphemeralTavilyBoundary.messages[1].content[0].id.length, 40);
    assert.equal(successfulEphemeralTavilyBoundary.messages[1].content[0].id.startsWith("call_bionemo_super_"), false);
    assert.match(successfulEphemeralTavilyBoundary.messages[1].content[0].id, /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u);
    const ephemeralTavilyLocalFinal = patched.__bionemoSuperLocalCompletionText(model, successfulEphemeralTavilyBoundary);
    assert.match(ephemeralTavilyLocalFinal, /RCSB PDB/u);
    assert.match(ephemeralTavilyLocalFinal, /UniProt/u);
    const ephemeralTavilyLocalEvents = await within(collectEvents(transport(model, successfulEphemeralTavilyBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "exact stripped ephemeral Tavily boundary must not start a provider request");
    assert.equal(ephemeralTavilyLocalEvents.some(({ type }) => type === "error"), false, JSON.stringify(ephemeralTavilyLocalEvents));
    assert.equal(ephemeralTavilyLocalEvents.at(0).type, "start");
    assert.equal(ephemeralTavilyLocalEvents.at(-1).type, "done");
    assert.deepEqual(ephemeralTavilyLocalEvents.at(-1).message.content, [{ type: "text", text: ephemeralTavilyLocalFinal }]);
    assert.equal(ephemeralTavilyLocalEvents.at(-1).message.stopReason, "stop");

    const providerBody = 'data: {"id":"normal-response","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"Provider normal path."},"finish_reason":"stop"}]}\\n\\ndata: [DONE]\\n\\n';
    globalThis.__bionemoTestFetch = async () => {
      providerFetchCalls += 1;
      return new Response(providerBody, { status: 200, headers: { "content-type": "text/event-stream" } });
    };
    const ephemeralRejected = [];
    const bareJsonBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    bareJsonBoundary.messages[2].content[0].text = bareJsonBoundary.messages[2].content[0].text.slice("structuredContent:\\n".length);
    ephemeralRejected.push(["bare JSON", bareJsonBoundary]);
    const providerProseBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    providerProseBoundary.messages[2].content[0].text = "Provider normal path.";
    ephemeralRejected.push(["provider prose", providerProseBoundary]);
    const wrongPromptBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    wrongPromptBoundary.messages[0].content += " ";
    ephemeralRejected.push(["wrong source prompt", wrongPromptBoundary]);
    const userBlocksBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    userBlocksBoundary.messages[0].content = [{ type: "text", text: userBlocksBoundary.messages[0].content }];
    ephemeralRejected.push(["non-string user projection", userBlocksBoundary]);
    const prefixedBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    prefixedBoundary.messages[2].content[0].text = "prefix:" + prefixedBoundary.messages[2].content[0].text;
    ephemeralRejected.push(["extra prefix", prefixedBoundary]);
    const suffixedBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    suffixedBoundary.messages[2].content[0].text += " trailing provider prose";
    ephemeralRejected.push(["extra suffix", suffixedBoundary]);
    const trailingWhitespaceBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    trailingWhitespaceBoundary.messages[2].content[0].text += "\\n";
    ephemeralRejected.push(["trailing JSON whitespace", trailingWhitespaceBoundary]);
    const compactJsonBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    const compactStructured = JSON.parse(compactJsonBoundary.messages[2].content[0].text.slice("structuredContent:\\n".length));
    compactJsonBoundary.messages[2].content[0].text = "structuredContent:\\n" + JSON.stringify(compactStructured);
    ephemeralRejected.push(["compact JSON", compactJsonBoundary]);
    const duplicateKeyBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    duplicateKeyBoundary.messages[2].content[0].text = duplicateKeyBoundary.messages[2].content[0].text.replace(
      "{\\n",
      "{\\n  \\"query\\": " + JSON.stringify(expectedTavilyInitial.params.query) + ",\\n",
    );
    ephemeralRejected.push(["duplicate JSON key", duplicateKeyBoundary]);
    const oversizedBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    const oversizedStructured = JSON.parse(oversizedBoundary.messages[2].content[0].text.slice("structuredContent:\\n".length));
    oversizedStructured.padding = "x".repeat(65_536);
    oversizedBoundary.messages[2].content[0].text = "structuredContent:\\n" + JSON.stringify(oversizedStructured, null, 2);
    assert.ok(oversizedBoundary.messages[2].content[0].text.length > 65_536);
    ephemeralRejected.push(["oversized result text", oversizedBoundary]);
    const extraBlockBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    extraBlockBoundary.messages[2].content.push({ type: "text", text: "extra" });
    ephemeralRejected.push(["extra result block", extraBlockBoundary]);
    const extraResultFieldBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    extraResultFieldBoundary.messages[2].content[0].metadata = {};
    ephemeralRejected.push(["extra result content field", extraResultFieldBoundary]);
    const extraAssistantBlockBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    extraAssistantBlockBoundary.messages[1].content.push({ type: "text", text: "extra" });
    ephemeralRejected.push(["extra assistant block", extraAssistantBlockBoundary]);
    const wrongStopReasonBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    wrongStopReasonBoundary.messages[1].stopReason = "stop";
    ephemeralRejected.push(["wrong assistant stop reason", wrongStopReasonBoundary]);
    for (const alternateType of ["toolUse", "functionCall"]) {
      const wrongCallTypeBoundary = structuredClone(successfulEphemeralTavilyBoundary);
      wrongCallTypeBoundary.messages[1].content[0].type = alternateType;
      ephemeralRejected.push(["wrong call type " + alternateType, wrongCallTypeBoundary]);
    }
    const alteredPartialArgsBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    alteredPartialArgsBoundary.messages[1].content[0].partialArgs = "{}";
    ephemeralRejected.push(["altered partial args", alteredPartialArgsBoundary]);
    const missingPartialArgsBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    delete missingPartialArgsBoundary.messages[1].content[0].partialArgs;
    ephemeralRejected.push(["missing partial args", missingPartialArgsBoundary]);
    const mismatchedIdBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    mismatchedIdBoundary.messages[2].toolCallId = "fedcba9876543210fedcba9876543210fedcba98";
    ephemeralRejected.push(["mismatched ID", mismatchedIdBoundary]);
    const emptyIdBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    emptyIdBoundary.messages[1].content[0].id = "";
    emptyIdBoundary.messages[2].toolCallId = "";
    ephemeralRejected.push(["empty ID", emptyIdBoundary]);
    for (const [label, invalidId] of [
      ["arbitrary 40-hex ID", "0123456789abcdef0123456789abcdef01234567"],
      ["raw underscore ID", "call_bionemo_super_0123456789ab4cde8f012345"],
      ["wrong UUID version", successfulEphemeralTavilyBoundary.messages[1].content[0].id.replace("4cde8", "5cde8")],
      ["wrong UUID variant", successfulEphemeralTavilyBoundary.messages[1].content[0].id.replace("4cde8", "4cde7")],
    ]) {
      const invalidProjectedIdBoundary = structuredClone(successfulEphemeralTavilyBoundary);
      invalidProjectedIdBoundary.messages[1].content[0].id = invalidId;
      invalidProjectedIdBoundary.messages[2].toolCallId = invalidId;
      ephemeralRejected.push([label, invalidProjectedIdBoundary]);
    }
    const badArgsBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    badArgsBoundary.messages[1].content[0].arguments.max_results = 4;
    ephemeralRejected.push(["bad args", badArgsBoundary]);
    const badHostBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    const badHostStructured = JSON.parse(badHostBoundary.messages[2].content[0].text.slice("structuredContent:\\n".length));
    badHostStructured.results[0].url = "https://evil.example/docs/";
    badHostBoundary.messages[2].content[0].text = "structuredContent:\\n" + JSON.stringify(badHostStructured, null, 2);
    ephemeralRejected.push(["bad host", badHostBoundary]);
    const badQueryBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    const badQueryStructured = JSON.parse(badQueryBoundary.messages[2].content[0].text.slice("structuredContent:\\n".length));
    badQueryStructured.query = "different query";
    badQueryBoundary.messages[2].content[0].text = "structuredContent:\\n" + JSON.stringify(badQueryStructured, null, 2);
    ephemeralRejected.push(["bad query", badQueryBoundary]);
    const missingSuccessBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    delete missingSuccessBoundary.messages[2].isError;
    ephemeralRejected.push(["missing explicit success", missingSuccessBoundary]);
    const erroredEphemeralBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    erroredEphemeralBoundary.messages[2].isError = true;
    ephemeralRejected.push(["errored result", erroredEphemeralBoundary]);
    const reportedErrorBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    reportedErrorBoundary.messages[2].error = { code: "provider_error" };
    ephemeralRejected.push(["reported error", reportedErrorBoundary]);
    const ambiguousErrorBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    ambiguousErrorBoundary.messages[2].error = null;
    ephemeralRejected.push(["ambiguous error field", ambiguousErrorBoundary]);
    const undefinedErrorBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    undefinedErrorBoundary.messages[2].error = undefined;
    ephemeralRejected.push(["own undefined error", undefinedErrorBoundary]);
    const ambiguousDetailsBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    ambiguousDetailsBoundary.messages[2].details = {};
    ephemeralRejected.push(["ambiguous details", ambiguousDetailsBoundary]);
    const undefinedDetailsBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    undefinedDetailsBoundary.messages[2].details = undefined;
    ephemeralRejected.push(["own undefined details", undefinedDetailsBoundary]);
    const ambiguousStructuredBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    ambiguousStructuredBoundary.messages[2].structuredContent = null;
    ephemeralRejected.push(["ambiguous top-level structured content", ambiguousStructuredBoundary]);
    const undefinedStructuredBoundary = structuredClone(successfulEphemeralTavilyBoundary);
    undefinedStructuredBoundary.messages[2].structuredContent = undefined;
    ephemeralRejected.push(["own undefined structured content", undefinedStructuredBoundary]);
    for (const [label, boundary] of ephemeralRejected) {
      assert.equal(patched.__bionemoSuperLocalCompletionText(model, boundary), undefined, label);
      const events = await within(collectEvents(transport(model, boundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
      assert.equal(events.at(-1).type, "done", label);
      assert.deepEqual(events.at(-1).message.content, [{ type: "text", text: "Provider normal path." }], label);
    }
    assert.equal(providerFetchCalls, ephemeralRejected.length, "every rejected ephemeral shape must retain the provider transport");
    const providerBaseline = providerFetchCalls;
    const malformedTimestampContext = { messages: [{ role: "user", content: "[Fri 2026-8-14 18:06 UTC] " + expectedScienceInitial.prompt }] };
    const malformedTimestampEvents = await within(collectEvents(transport(model, malformedTimestampContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: expectedScienceInitial.name, description: "bounded test", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 1, "a malformed timestamp envelope must retain the provider transport");
    assert.equal(malformedTimestampEvents.at(-1).type, "done");
    assert.deepEqual(malformedTimestampEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const missingSurfaceEvents = await within(collectEvents(transport(model, exactScienceInitialContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: "other_tool", description: "other", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 2, "a missing projected source-owned tool must retain the provider transport");
    assert.equal(missingSurfaceEvents.at(-1).type, "done");
    assert.deepEqual(missingSurfaceEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const wrongProviderModel = { ...model, provider: "nvidia" };
    const wrongProviderEvents = await within(collectEvents(transport(wrongProviderModel, exactScienceInitialContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: expectedScienceInitial.name, description: "bounded test", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 3, "the exact timestamped prompt on another provider must retain the provider transport");
    assert.equal(wrongProviderEvents.at(-1).type, "done");
    assert.deepEqual(wrongProviderEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const malformedTavilyBoundary = structuredClone(successfulTavilyBoundary);
    malformedTavilyBoundary.messages.at(-1).details.mcpServer = "untrusted-server";
    assert.equal(patched.__bionemoSuperLocalCompletionText(model, malformedTavilyBoundary), undefined);
    const malformedTavilyEvents = await within(collectEvents(transport(model, malformedTavilyBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 4, "malformed Tavily provenance retains the provider transport");
    assert.equal(malformedTavilyEvents.at(-1).type, "done");
    assert.deepEqual(malformedTavilyEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const erroredBoundaryForTransport = ${JSON.stringify(turn("bionemo_batch_fold_demo", { isError: true }))};
    const erroredEvents = await within(collectEvents(transport(model, erroredBoundaryForTransport, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 5, "errored Super boundary retains the provider transport");
    assert.equal(erroredEvents.at(-1).type, "done");
    assert.deepEqual(erroredEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const deepSeekEvents = await within(collectEvents(transport(deepSeekModel, successfulBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 6, "other models retain the provider transport");
    assert.equal(deepSeekEvents.at(-1).type, "done");
    assert.deepEqual(deepSeekEvents.at(-1).message.content, [{ type: "text", text: sourceOwnedFinal }]);

    const repeatedProviderChunks = () => (async function* providerChunks() {
      for (let index = 0; index < 3; index += 1) {
        yield { id: \`response-deepseek-\${index}\`, choices: [{ index: 0, delta: {
          content: "<tool_call><function=bionemo_batch_fold_demo><parameter=repeat>true</parameter></function></tool_call>",
          tool_calls: [{ index: 0, id: \`provider-repeat-\${index}\`, type: "function", function: {
            name: index === 1 ? "tool_call" : "bionemo_batch_fold_demo",
            arguments: index === 1 ? JSON.stringify({ id: "openclaw:bionemo-agent-toolkit:bionemo_batch_fold_demo" }) : "{}",
          } }],
        }, finish_reason: "tool_calls" }] };
      }
    }());
    const deepSeekFinalOutput = output();
    deepSeekFinalOutput.model = deepSeekModel.id;
    const deepSeekFinalEvents = [];
    await patched.__bionemoProcessOpenAICompletionsStream(repeatedProviderChunks(), deepSeekFinalOutput, deepSeekModel, { push: (event) => deepSeekFinalEvents.push(structuredClone(event)) }, { emitReasoning: false, bionemoSuperFinalText: sourceOwnedFinal });
    assert.equal(deepSeekFinalOutput.stopReason, "stop");
    assert.deepEqual(deepSeekFinalOutput.content, [{ type: "text", text: sourceOwnedFinal }]);
    assert.equal(JSON.stringify(deepSeekFinalOutput).includes("provider-repeat"), false);
    assert.equal(JSON.stringify(deepSeekFinalOutput).includes("<tool_call>"), false);
    assert.equal(deepSeekFinalEvents.some(({ type }) => type.startsWith("toolcall_")), false);
    const persisted = [...successfulBoundary.messages, deepSeekFinalOutput];
    assert.equal(persisted.filter((message) => message.role === "toolResult" && message.toolName === "bionemo_batch_fold_demo").length, 1);
    assert.equal(persisted.flatMap((message) => Array.isArray(message.content) ? message.content : []).filter((block) => block?.type === "toolCall" && block.name === "bionemo_batch_fold_demo").length, 1);

    const erroredBoundary = ${JSON.stringify(turn("bionemo_batch_fold_demo", { isError: true }))};
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, erroredBoundary), false);
    assert.equal(patched.__bionemoSuperDeterministicFinalText(deepSeekModel, erroredBoundary), undefined);
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, ${JSON.stringify(turn("tavily_search"))}), false);
    assert.equal(patched.__bionemoSuperShouldFinalizeWithoutTools(${JSON.stringify({ ...deepSeekModel, id: "other/model" })}, successfulBoundary), false);
    const passThroughOutput = output();
    passThroughOutput.model = deepSeekModel.id;
    await patched.__bionemoProcessOpenAICompletionsStream(chunks(), passThroughOutput, deepSeekModel, { push: () => {} }, { emitReasoning: false, bionemoSuperFinalText: patched.__bionemoSuperDeterministicFinalText(deepSeekModel, erroredBoundary) });
    assert.equal(passThroughOutput.content.some(({ type }) => type === "toolCall"), true);
  `;
  await execFileAsync("docker", [
    "run", "--rm", "--network", "none", "--entrypoint", "node",
    "--mount", `type=bind,src=${path.join(distRoot, file)},dst=/app/dist/${file},readonly`,
    PINNED_IMAGE, "--input-type=module", "-e", integrationScript,
  ]);
});
