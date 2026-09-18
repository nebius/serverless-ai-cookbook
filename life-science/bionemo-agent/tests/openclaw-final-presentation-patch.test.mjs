import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  patchOpenClawFinalPresentation,
  PINNED_OPENCLAW_FINAL_PRESENTATION_HASHES,
} from "../runtime/patch-openclaw-final-presentation.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";

async function pinnedDist(t) {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-final-presentation-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const { stdout } = await execFileAsync("docker", ["create", PINNED_IMAGE]);
  const containerId = stdout.trim();
  let removed = false;
  t.after(() => removed ? undefined : execFileAsync("docker", ["rm", "-f", containerId]).catch(() => {}));
  await execFileAsync("docker", ["cp", `${containerId}:/app/dist`, path.join(root, "dist")]);
  await execFileAsync("docker", ["rm", containerId]);
  removed = true;
  return path.join(root, "dist");
}

async function chunk(distRoot, prefix, marker) {
  const { readdir } = await import("node:fs/promises");
  const names = await readdir(distRoot);
  const matches = [];
  for (const name of names.filter((value) => value.startsWith(prefix) && value.endsWith(".js"))) {
    const source = await readFile(path.join(distRoot, name), "utf8");
    if (source.includes(marker)) matches.push({ name, source });
  }
  assert.equal(matches.length, 1);
  return matches[0];
}

test("pinned OpenClaw final presentation patch is fail-closed, phase-safe, and idempotent", { timeout: 120_000 }, async (t) => {
  const distRoot = await pinnedDist(t);
  const first = await patchOpenClawFinalPresentation(distRoot);
  assert.equal(first.changed, true);
  const second = await patchOpenClawFinalPresentation(distRoot);
  assert.equal(second.changed, false);

  const hookRunner = await chunk(distRoot, "hook-runner-global-", "const mergeBeforeAgentFinalize");
  const lifecycle = await chunk(distRoot, "lifecycle-hook-helpers-", "function normalizeBeforeAgentFinalizeResult");
  const selection = await chunk(distRoot, "selection-", "function handleAgentEnd(ctx, evt)");
  for (const candidate of [hookRunner, lifecycle, selection]) {
    assert.match(candidate.source, /openclaw\.bionemo\.final-presentation\.v2/u);
    await execFileAsync(process.execPath, ["--check", path.join(distRoot, candidate.name)]);
  }
  assert.match(hookRunner.source, /concatOptionalTextSegments\(\{\s*left: acc\?\.appendFinalAssistantText,\s*right: next\.appendFinalAssistantText/su);
  assert.match(lifecycle.source, /normalizeOptionalString\(result\?\.appendFinalAssistantText\)/u);
  assert.match(selection.source, /textSignature: JSON\.stringify\(\{ v: 1, phase: "final_answer" \}\)/u);
  assert.match(selection.source, /rewriteTranscriptEntriesInSessionManager/u);
  assert.match(selection.source, /activeSession\.agent\.state\.messages = activeSessionManager\.buildSessionContext\(\)\.messages/u);
  assert.match(selection.source, /ctx\.state\.assistantTexts\[index\] = rawReplacement/u);
  assert.match(selection.source, /parseReplyDirectives\(splitTrailingDirective\(rawReplacement\.trim\(\), \{ final: true \}\)\.text\)/u);
  assert.match(selection.source, /resolveSendableOutboundReplyParts\(parsedReplacement\)/u);
  assert.match(selection.source, /text: cleanedReplacement,\s*delta: "",\s*replace: true,\s*mediaUrls,\s*phase: "final_answer"/su);
  const asyncTerminal = selection.source.match(/\.then\(\(decision\) => \{[\s\S]*?return deliverTerminalWithLifecycleErrorFallback\(\);\n\t\}\);/u)?.[0];
  assert.ok(asyncTerminal);
  assert.ok(asyncTerminal.indexOf("applyFinalPresentation(decision)") < asyncTerminal.indexOf("return deliverTerminalWithLifecycleErrorFallback();"));
});

test("final presentation live replacement uses native directive delivery while preserving raw transcript text", { timeout: 120_000 }, async (t) => {
  const distRoot = await pinnedDist(t);
  await patchOpenClawFinalPresentation(distRoot);
  const selection = await chunk(distRoot, "selection-", "function handleAgentEnd(ctx, evt)");
  const directives = await chunk(distRoot, "payloads-", "function parseReplyDirectives");
  const replyPayload = await chunk(distRoot, "reply-payload-", "function resolveSendableOutboundReplyParts");
  const applySource = selection.source.match(/\tconst applyFinalPresentation = \(decision\) => \{[\s\S]*?\n\t\};\n\tconst deliverTerminal/u)?.[0]
    ?.replace(/\n\tconst deliverTerminal$/u, "");
  assert.ok(applySource, "patched live presentation helper must be extractable");

  const rawReplacement = "Normalized answer.\n\nMEDIA:/tmp/native-structure.cif";
  const coreScript = [
    `import { f as parseReplyDirectives } from ${JSON.stringify(`file:///app/dist/${directives.name}`)};`,
    `import { m as resolveSendableOutboundReplyParts } from ${JSON.stringify(`file:///app/dist/${replyPayload.name}`)};`,
    `const parsed = parseReplyDirectives(${JSON.stringify(rawReplacement)});`,
    "process.stdout.write(JSON.stringify({ parsed, sendable: resolveSendableOutboundReplyParts(parsed) }));",
  ].join("\n");
  const { stdout: coreStdout } = await execFileAsync("docker", [
    "run", "--rm", "--network", "none", "--entrypoint", "node", PINNED_IMAGE,
    "--input-type=module", "--eval", coreScript,
  ]);
  const core = JSON.parse(coreStdout);
  assert.equal(core.parsed.text, "Normalized answer.");
  assert.deepEqual(core.sendable.mediaUrls, ["/tmp/native-structure.cif"]);
  assert.equal(core.sendable.hasMedia, true);

  const emitted = [];
  const ctx = {
    state: { assistantTexts: ["Provider answer."] },
    emitAssistantStreamData: (data) => emitted.push(data),
  };
  const calls = [];
  const applyFinalPresentation = Function(
    "ctx",
    "splitTrailingDirective",
    "parseReplyDirectives",
    "resolveSendableOutboundReplyParts",
    "buildAssistantStreamData",
    `"use strict";\n${applySource}\nreturn applyFinalPresentation;`,
  )(
    ctx,
    (text, options) => {
      calls.push(["split", text, options]);
      return { text, tail: "" };
    },
    (text) => {
      calls.push(["parse", text]);
      return core.parsed;
    },
    (payload) => {
      calls.push(["resolve", payload]);
      return core.sendable;
    },
    (payload) => ({
      text: payload.text ?? "",
      delta: payload.delta ?? "",
      replace: payload.replace ? true : undefined,
      mediaUrls: payload.mediaUrls?.length ? payload.mediaUrls : undefined,
      phase: payload.phase,
    }),
  );

  const decision = { replacementAssistantText: rawReplacement };
  assert.equal(applyFinalPresentation(decision), decision);
  assert.equal(ctx.state.assistantTexts[0], rawReplacement, "assistantTexts must retain raw MEDIA for persistence");
  assert.deepEqual(calls[0], ["split", rawReplacement, { final: true }]);
  assert.deepEqual(emitted, [{
    text: "Normalized answer.",
    delta: "",
    replace: true,
    mediaUrls: ["/tmp/native-structure.cif"],
    phase: "final_answer",
  }]);
});

test("final presentation patch rejects a drifted pinned chunk before writing", async (t) => {
  const root = await mkdtemp(path.join(os.tmpdir(), "bionemo-final-presentation-drift-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(root, "hook-runner-global-fixture.js"), "const mergeBeforeAgentFinalize = (acc, next) => {};\n");
  await writeFile(path.join(root, "lifecycle-hook-helpers-fixture.js"), "function normalizeBeforeAgentFinalizeResult(result, event) {}\n");
  await writeFile(path.join(root, "selection-fixture.js"), "/**\n* Repairs persisted signed-thinking replay state after provider-confirmed rejection.\n*/\nfunction repairRejectedThinkingReplayInSessionManager(params) {}\nfunction handleAgentEnd(ctx, evt) {}\n");
  await assert.rejects(
    () => patchOpenClawFinalPresentation(root, { expectedHashes: PINNED_OPENCLAW_FINAL_PRESENTATION_HASHES }),
    /compatibility hash mismatch/u,
  );
  assert.doesNotMatch(await readFile(path.join(root, "hook-runner-global-fixture.js"), "utf8"), /openclaw\.bionemo/u);
});

test("final presentation patch rejects a partially patched runtime", async (t) => {
  const distRoot = await pinnedDist(t);
  const hookRunner = await chunk(distRoot, "hook-runner-global-", "const mergeBeforeAgentFinalize");
  const hookPath = path.join(distRoot, hookRunner.name);
  await writeFile(hookPath, `/* openclaw.bionemo.final-presentation.v2 */\n${hookRunner.source}`);
  await assert.rejects(() => patchOpenClawFinalPresentation(distRoot), /partially patched/u);
});
