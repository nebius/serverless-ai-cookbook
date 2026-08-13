import { createHash } from "node:crypto";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

// Exact amd64 chunks in the OpenClaw 2026.7.1-2 image pinned by Dockerfile.
// The alternate selection hash is the same chunk after the separately tested
// bundle-MCP turn-context patch has run first.
export const PINNED_OPENCLAW_FINAL_PRESENTATION_HASHES = Object.freeze({
  hookRunner: Object.freeze(["c066170e97a2355603f0bdd3079a687bf835632856a741fa9a92683d7d4b2750"]),
  lifecycle: Object.freeze(["1d0675b25b4e5a9c89e1f8946701f123950853aa06bd443c2fcad4a37712baef"]),
  selection: Object.freeze([
    "ccff13111aa60369ac9d88b526a58a7df1f733f1d99d205c01c6186036957e66",
    "37b112232440dd297e914077543824baf61849d74ad06cd0f9e7adfa7deafa00",
  ]),
});

const PATCH_MARKER = "openclaw.bionemo.final-presentation.v1";

const MERGE_START_ANCHOR = `\tconst mergeBeforeAgentFinalize = (acc, next) => {
\t\tconst normalizeRetry = (retry) => {`;
const MERGE_START_REPLACEMENT = `\tconst mergeBeforeAgentFinalize = (acc, next) => {
\t\tconst appendFinalAssistantText = concatOptionalTextSegments({
\t\t\tleft: acc?.appendFinalAssistantText,
\t\t\tright: next.appendFinalAssistantText
\t\t});
\t\tconst withFinalPresentation = (result) => appendFinalAssistantText ? { ...result, appendFinalAssistantText } : result;
\t\tconst normalizeRetry = (retry) => {`;
const MERGE_ACC_FINALIZE_ANCHOR = `\t\tif (acc?.action === "finalize") return acc;`;
const MERGE_ACC_FINALIZE_REPLACEMENT = `\t\tif (acc?.action === "finalize") return withFinalPresentation(acc);`;
const MERGE_FINALIZE_ANCHOR = `\t\tif (next.action === "finalize") return {
\t\t\taction: "finalize",
\t\t\treason: next.reason
\t\t};`;
const MERGE_FINALIZE_REPLACEMENT = `\t\tif (next.action === "finalize") return withFinalPresentation({
\t\t\taction: "finalize",
\t\t\treason: next.reason
\t\t});`;
const MERGE_BOTH_REVISE_ANCHOR = `\t\t\treturn attachRetryCandidates({
\t\t\t\taction: "revise",
\t\t\t\treason: concatOptionalTextSegments({
\t\t\t\t\tleft: acc.reason,
\t\t\t\t\tright: next.reason
\t\t\t\t}),
\t\t\t\t...retry ? { retry } : {}
\t\t\t}, retryCandidates);`;
const MERGE_BOTH_REVISE_REPLACEMENT = `\t\t\treturn withFinalPresentation(attachRetryCandidates({
\t\t\t\taction: "revise",
\t\t\t\treason: concatOptionalTextSegments({
\t\t\t\t\tleft: acc.reason,
\t\t\t\t\tright: next.reason
\t\t\t\t}),
\t\t\t\t...retry ? { retry } : {}
\t\t\t}, retryCandidates));`;
const MERGE_ACC_REVISE_ANCHOR = `\t\tif (acc?.action === "revise") return acc;`;
const MERGE_ACC_REVISE_REPLACEMENT = `\t\tif (acc?.action === "revise") return withFinalPresentation(acc);`;
const MERGE_NEXT_REVISE_ANCHOR = `\t\tif (next.action === "revise") {
\t\t\tconst retry = normalizeRetry(next.retry);
\t\t\treturn {
\t\t\t\taction: "revise",
\t\t\t\treason: next.reason,
\t\t\t\t...retry ? { retry } : {}
\t\t\t};
\t\t}`;
const MERGE_NEXT_REVISE_REPLACEMENT = `\t\tif (next.action === "revise") {
\t\t\tconst retry = normalizeRetry(next.retry);
\t\t\treturn withFinalPresentation({
\t\t\t\taction: "revise",
\t\t\t\treason: next.reason,
\t\t\t\t...retry ? { retry } : {}
\t\t\t});
\t\t}`;
const MERGE_CONTINUE_ANCHOR = `\t\treturn next.action === "continue" ? {
\t\t\taction: "continue",
\t\t\treason: next.reason
\t\t} : acc ?? next;`;
const MERGE_CONTINUE_REPLACEMENT = `\t\treturn withFinalPresentation(next.action === "continue" ? {
\t\t\taction: "continue",
\t\t\treason: next.reason
\t\t} : acc ?? next);`;

const NORMALIZE_START_ANCHOR = `function normalizeBeforeAgentFinalizeResult(result, event) {
\tif (result?.action === "finalize") {`;
const NORMALIZE_START_REPLACEMENT = `function normalizeBeforeAgentFinalizeResult(result, event) {
\tconst appendFinalAssistantText = normalizeOptionalString(result?.appendFinalAssistantText);
\tconst withFinalPresentation = (normalized) => appendFinalAssistantText ? { ...normalized, appendFinalAssistantText } : normalized;
\tif (result?.action === "finalize") {`;
const NORMALIZE_FINALIZE_ANCHOR = `\t\treturn reason ? {
\t\t\taction: "finalize",
\t\t\treason
\t\t} : { action: "finalize" };`;
const NORMALIZE_FINALIZE_REPLACEMENT = `\t\tconst normalized = reason ? {
\t\t\taction: "finalize",
\t\t\treason
\t\t} : { action: "finalize" };
\t\treturn withFinalPresentation(normalized);`;
const NORMALIZE_RETRY_REVISE_ANCHOR = `\t\t\t\treturn {
\t\t\t\t\taction: "revise",
\t\t\t\t\treason: reason && reason.includes(retryInstruction) ? reason : [reason, retryInstruction].filter(Boolean).join("\\n\\n")
\t\t\t\t};`;
const NORMALIZE_RETRY_REVISE_REPLACEMENT = `\t\t\t\treturn withFinalPresentation({
\t\t\t\t\taction: "revise",
\t\t\t\t\treason: reason && reason.includes(retryInstruction) ? reason : [reason, retryInstruction].filter(Boolean).join("\\n\\n")
\t\t\t\t});`;
const NORMALIZE_EXHAUSTED_ANCHOR = `\t\t\treturn { action: "continue" };
\t\t}`;
const NORMALIZE_EXHAUSTED_REPLACEMENT = `\t\t\treturn withFinalPresentation({ action: "continue" });
\t\t}`;
const NORMALIZE_SIMPLE_REVISE_ANCHOR = `\t\treturn reason ? {
\t\t\taction: "revise",
\t\t\treason
\t\t} : { action: "continue" };
\t}`;
const NORMALIZE_SIMPLE_REVISE_REPLACEMENT = `\t\treturn withFinalPresentation(reason ? {
\t\t\taction: "revise",
\t\t\treason
\t\t} : { action: "continue" });
\t}`;
const NORMALIZE_CONTINUE_ANCHOR = `\treturn { action: "continue" };
}`;
const NORMALIZE_CONTINUE_REPLACEMENT = `\treturn withFinalPresentation({ action: "continue" });
}`;

const SELECTION_HELPER_ANCHOR = "/**\n* Repairs persisted signed-thinking replay state after provider-confirmed rejection.\n*/\nfunction repairRejectedThinkingReplayInSessionManager(params) {";
const SELECTION_HELPER_REPLACEMENT = `/** BioNeMo: append deterministic final presentation without mutating provider-signed text. */
function bionemoAppendFinalAssistantText(message, appendText) {
\tif (message?.role !== "assistant" || message.stopReason !== "stop" || typeof appendText !== "string" || !appendText.trim()) return;
\tif (typeof message.content === "string") return {
\t\t...message,
\t\tcontent: message.content ? \`${"${message.content.trimEnd()}"}\\n\\n${"${appendText}"}\` : appendText
\t};
\tif (!Array.isArray(message.content)) return;
\tconst hasExplicitPhase = message.content.some((block) => {
\t\tif (!block || typeof block !== "object" || block.type !== "text") return false;
\t\treturn Boolean(parseAssistantTextSignature(block.textSignature)?.phase);
\t});
\treturn {
\t\t...message,
\t\tcontent: [...message.content, {
\t\t\ttype: "text",
\t\t\ttext: appendText,
\t\t\t...hasExplicitPhase ? { textSignature: JSON.stringify({ v: 1, phase: "final_answer" }) } : {}
\t\t}]
\t};
}
function bionemoRewriteFinalAssistant(params) {
\tconst branch = params.sessionManager.getBranch();
\tconst entry = branch.slice().reverse().find((candidate) => candidate.type === "message" && candidate.message?.role === "assistant");
\tif (!entry) return;
\tconst message = bionemoAppendFinalAssistantText(entry.message, params.appendText);
\tif (!message) return;
\tconst visibleText = resolveFinalAssistantVisibleText(message);
\tif (!visibleText) return;
\tconst result = rewriteTranscriptEntriesInSessionManager({
\t\tsessionManager: params.sessionManager,
\t\treplacements: [{ entryId: entry.id, message }]
\t});
\tif (!result.changed) return;
\tif (params.sessionFile) emitSessionTranscriptUpdate({
\t\tsessionFile: params.sessionFile,
\t\tsessionKey: params.sessionKey,
\t\t...params.agentId ? { agentId: params.agentId } : {}
\t});
\treturn { message, visibleText };
}
${SELECTION_HELPER_ANCHOR}`;

const FINALIZE_OUTCOME_ANCHOR = `\t\t\t\t});
\t\t\t\tif (outcome.action !== "revise") return;
\t\t\t\tif (event.hadDeterministicSideEffect) {`;
const FINALIZE_OUTCOME_REPLACEMENT = `\t\t\t\t});
\t\t\t\tconst willRevise = outcome.action === "revise" && !event.hadDeterministicSideEffect;
\t\t\t\tif (!willRevise && outcome.appendFinalAssistantText) {
\t\t\t\t\tconst presentation = bionemoRewriteFinalAssistant({
\t\t\t\t\t\tsessionManager: activeSessionManager,
\t\t\t\t\t\tsessionFile: params.sessionFile,
\t\t\t\t\t\tsessionKey: params.sessionKey,
\t\t\t\t\t\tagentId: hookAgentId,
\t\t\t\t\t\tappendText: outcome.appendFinalAssistantText
\t\t\t\t\t});
\t\t\t\t\tif (presentation) {
\t\t\t\t\t\tactiveSession.agent.state.messages = activeSessionManager.buildSessionContext().messages;
\t\t\t\t\t\treturn { replacementAssistantText: presentation.visibleText };
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (outcome.action !== "revise") return;
\t\t\t\tif (event.hadDeterministicSideEffect) {`;

const APPLY_LIVE_ANCHOR = `\tconst deliverTerminal = () => {
\t\tctx.state.deferBlockReplyDelivery = false;`;
const APPLY_LIVE_REPLACEMENT = `\tconst applyFinalPresentation = (decision) => {
\t\tconst replacement = decision?.replacementAssistantText;
\t\tif (typeof replacement !== "string" || !replacement.trim()) return decision;
\t\tconst index = ctx.state.assistantTexts.length - 1;
\t\tif (index >= 0) ctx.state.assistantTexts[index] = replacement;
\t\telse ctx.state.assistantTexts.push(replacement);
\t\tctx.emitAssistantStreamData(buildAssistantStreamData({
\t\t\ttext: replacement,
\t\t\tdelta: "",
\t\t\treplace: true,
\t\t\tphase: "final_answer"
\t\t}));
\t\treturn decision;
\t};
\tconst deliverTerminal = () => {
\t\tctx.state.deferBlockReplyDelivery = false;`;
const APPLY_ASYNC_ANCHOR = `\t}).then((decision) => {
\t\tif (decision?.suppressTerminalDelivery === true) {`;
const APPLY_ASYNC_REPLACEMENT = `\t}).then((decision) => {
\t\tapplyFinalPresentation(decision);
\t\tif (decision?.suppressTerminalDelivery === true) {`;
const APPLY_SYNC_ANCHOR = `\tif (beforeTerminalDelivery?.suppressTerminalDelivery === true) {`;
const APPLY_SYNC_REPLACEMENT = `\tapplyFinalPresentation(beforeTerminalDelivery);
\tif (beforeTerminalDelivery?.suppressTerminalDelivery === true) {`;

function sha256(source) {
  return createHash("sha256").update(source).digest("hex");
}

function replaceExactlyOnce(source, anchor, replacement, label) {
  const first = source.indexOf(anchor);
  if (first < 0 || source.indexOf(anchor, first + anchor.length) >= 0) {
    throw new Error(`Pinned OpenClaw compatibility check failed for ${label}`);
  }
  return `${source.slice(0, first)}${replacement}${source.slice(first + anchor.length)}`;
}

async function findChunk(distRoot, prefix, marker) {
  const names = (await readdir(distRoot)).filter((name) => name.startsWith(prefix) && name.endsWith(".js"));
  const matches = [];
  for (const name of names) {
    const filePath = path.join(distRoot, name);
    const source = await readFile(filePath, "utf8");
    if (source.includes(marker)) matches.push({ filePath, source });
  }
  if (matches.length !== 1) throw new Error(`Expected exactly one pinned OpenClaw ${prefix} chunk, found ${matches.length}`);
  return matches[0];
}

async function atomicRewrite(filePath, source) {
  const temporary = `${filePath}.bionemo-${process.pid}.tmp`;
  await writeFile(temporary, source, { encoding: "utf8", mode: 0o644, flag: "wx" });
  await rename(temporary, filePath);
}

function assertPinnedHash(source, allowed, label) {
  const actual = sha256(source);
  if (!allowed.includes(actual)) throw new Error(`Pinned OpenClaw compatibility hash mismatch for ${label}: ${actual}`);
}

export async function patchOpenClawFinalPresentation(distRoot, { expectedHashes = PINNED_OPENCLAW_FINAL_PRESENTATION_HASHES } = {}) {
  if (!distRoot) throw new Error("OpenClaw dist root is required");
  const hookRunner = await findChunk(distRoot, "hook-runner-global-", "const mergeBeforeAgentFinalize = (acc, next) =>");
  const lifecycle = await findChunk(distRoot, "lifecycle-hook-helpers-", "function normalizeBeforeAgentFinalizeResult(result, event)");
  const selection = await findChunk(distRoot, "selection-", SELECTION_HELPER_ANCHOR);
  const files = [hookRunner, lifecycle, selection];
  const fullyPatched = files.every(({ source }) => source.includes(PATCH_MARKER));
  if (fullyPatched) return { changed: false, paths: files.map(({ filePath }) => filePath) };
  if (files.some(({ source }) => source.includes(PATCH_MARKER))) throw new Error("Refusing to modify a partially patched OpenClaw final-presentation runtime");

  assertPinnedHash(hookRunner.source, expectedHashes.hookRunner, "hook runner");
  assertPinnedHash(lifecycle.source, expectedHashes.lifecycle, "lifecycle helper");
  assertPinnedHash(selection.source, expectedHashes.selection, "embedded selection");

  let hookRunnerSource = replaceExactlyOnce(hookRunner.source, MERGE_START_ANCHOR, MERGE_START_REPLACEMENT, "finalize result merge setup");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_ACC_FINALIZE_ANCHOR, MERGE_ACC_FINALIZE_REPLACEMENT, "prior forced finalize merge");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_FINALIZE_ANCHOR, MERGE_FINALIZE_REPLACEMENT, "forced finalize merge");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_BOTH_REVISE_ANCHOR, MERGE_BOTH_REVISE_REPLACEMENT, "combined revision merge");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_ACC_REVISE_ANCHOR, MERGE_ACC_REVISE_REPLACEMENT, "prior revision merge");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_NEXT_REVISE_ANCHOR, MERGE_NEXT_REVISE_REPLACEMENT, "next revision merge");
  hookRunnerSource = replaceExactlyOnce(hookRunnerSource, MERGE_CONTINUE_ANCHOR, MERGE_CONTINUE_REPLACEMENT, "continue merge");
  hookRunnerSource = `/* ${PATCH_MARKER} */\n${hookRunnerSource}`;

  let lifecycleSource = replaceExactlyOnce(lifecycle.source, NORMALIZE_START_ANCHOR, NORMALIZE_START_REPLACEMENT, "finalize normalization start");
  lifecycleSource = replaceExactlyOnce(lifecycleSource, NORMALIZE_FINALIZE_ANCHOR, NORMALIZE_FINALIZE_REPLACEMENT, "finalize normalization result");
  lifecycleSource = replaceExactlyOnce(lifecycleSource, NORMALIZE_RETRY_REVISE_ANCHOR, NORMALIZE_RETRY_REVISE_REPLACEMENT, "retry revision normalization");
  lifecycleSource = replaceExactlyOnce(lifecycleSource, NORMALIZE_EXHAUSTED_ANCHOR, NORMALIZE_EXHAUSTED_REPLACEMENT, "exhausted revision normalization");
  lifecycleSource = replaceExactlyOnce(lifecycleSource, NORMALIZE_SIMPLE_REVISE_ANCHOR, NORMALIZE_SIMPLE_REVISE_REPLACEMENT, "simple revision normalization");
  lifecycleSource = replaceExactlyOnce(lifecycleSource, NORMALIZE_CONTINUE_ANCHOR, NORMALIZE_CONTINUE_REPLACEMENT, "continue normalization result");
  lifecycleSource = `/* ${PATCH_MARKER} */\n${lifecycleSource}`;

  let selectionSource = replaceExactlyOnce(selection.source, SELECTION_HELPER_ANCHOR, SELECTION_HELPER_REPLACEMENT, "phase-safe transcript append");
  selectionSource = replaceExactlyOnce(selectionSource, FINALIZE_OUTCOME_ANCHOR, FINALIZE_OUTCOME_REPLACEMENT, "finalize transcript rewrite");
  selectionSource = replaceExactlyOnce(selectionSource, APPLY_LIVE_ANCHOR, APPLY_LIVE_REPLACEMENT, "live replacement helper");
  selectionSource = replaceExactlyOnce(selectionSource, APPLY_ASYNC_ANCHOR, APPLY_ASYNC_REPLACEMENT, "async terminal replacement");
  selectionSource = replaceExactlyOnce(selectionSource, APPLY_SYNC_ANCHOR, APPLY_SYNC_REPLACEMENT, "sync terminal replacement");
  selectionSource = `/* ${PATCH_MARKER} */\n${selectionSource}`;

  await atomicRewrite(hookRunner.filePath, hookRunnerSource);
  await atomicRewrite(lifecycle.filePath, lifecycleSource);
  await atomicRewrite(selection.filePath, selectionSource);
  return { changed: true, paths: files.map(({ filePath }) => filePath) };
}

async function main() {
  const [distRoot] = process.argv.slice(2);
  const result = await patchOpenClawFinalPresentation(distRoot);
  process.stdout.write(`BioNeMo OpenClaw final-presentation patch: ${result.changed ? "applied" : "already applied"}.\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    process.stderr.write(`BioNeMo OpenClaw final-presentation compatibility patch failed: ${error.message}\n`);
    process.exitCode = 1;
  });
}
