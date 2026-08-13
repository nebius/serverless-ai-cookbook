import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import {
  bionemoSuperShouldFinalizeWithoutTools,
  patchOpenClawSuperFollowup,
} from "../runtime/patch-openclaw-super-followup.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";
const superModel = { provider: "tokenfactory", id: "nvidia/nemotron-3-super-120b-a12b" };

function turn(name, { id = name, isError = false, arguments: args = {} } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: "done" }] },
  ] };
}

test("Super finalizes after atomic wrappers and successful catalog lookup only", () => {
  for (const name of ["bionemo_research_drug_demo", "bionemo_compare_protein_structures", "bionemo_optimize_ligand_complex", "bionemo_batch_fold_demo"]) {
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name)), true);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name, { isError: true })), true);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("tool_call", { id: `openclaw:bionemo-agent-toolkit:${name}` })), true);
  }
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_models__models_list")), true);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_models__models_list", { isError: true })), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("tool_call", { id: "mcp:bundle-mcp:clawbio_models__models_list" })), true);
});

test("Super guard leaves initial, other-model, mismatched, and compute/status chains untouched", () => {
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, { messages: [{ role: "user", content: [] }] }), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...superModel, id: "deepseek-ai/DeepSeek-V4-Pro" }, turn("bionemo_batch_fold_demo")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_openfold2_predict")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn("clawbio_job_status")), false);
  const mismatch = structuredClone(turn("bionemo_batch_fold_demo"));
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, mismatch), false);
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
  assert.match(source, /openclaw\.bionemo\.super-followup\.v1/u);
  const callback = source.indexOf("if (nextParams !== void 0) params = nextParams;");
  const guard = source.indexOf("if (bionemoSuperShouldFinalizeWithoutTools(model, context))");
  const request = source.indexOf("client.chat.completions.create(params");
  assert.ok(callback >= 0 && callback < guard && guard < request);
  assert.match(source, /delete params\.tools;\s*params\.tool_choice = "none";/su);
  await execFileAsync(process.execPath, ["--check", path.join(distRoot, file)]);
});
