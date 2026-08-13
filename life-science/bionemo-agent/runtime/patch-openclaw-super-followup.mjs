import { createHash } from "node:crypto";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

export const PINNED_OPENCLAW_SUPER_FOLLOWUP_HASH = "82712e39d2863f055210df3a33f4a725872bcbf3dfef1b7ba181dba882f60edc";
const PATCH_MARKER = "openclaw.bionemo.super-followup.v1";
export function bionemoSuperShouldFinalizeWithoutTools(model, context) {
  const superModel = "nvidia/nemotron-3-super-120b-a12b";
  const wrappers = new Set([
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
  ]);
  const catalogTool = "clawbio_models__models_list";
  if (String(model?.provider || "").toLowerCase() !== "tokenfactory"
    || String(model?.id || "").toLowerCase() !== superModel) return false;
  const messages = Array.isArray(context?.messages) ? context.messages : [];
  const result = messages.at(-1);
  const assistant = messages.at(-2);
  if (result?.role !== "toolResult" || assistant?.role !== "assistant") return false;
  const calls = Array.isArray(assistant.content)
    ? assistant.content.filter((block) => block?.type === "toolCall")
    : [];
  if (calls.length !== 1 || !calls[0].id || calls[0].id !== result.toolCallId || calls[0].name !== result.toolName) return false;
  const call = calls[0];
  let target = call.name;
  if (target === "tool_call") {
    let args = call.arguments;
    if (typeof args === "string") {
      try { args = JSON.parse(args); } catch { return false; }
    }
    if (!args || typeof args !== "object" || Array.isArray(args) || typeof args.id !== "string") return false;
    target = args.id.startsWith("openclaw:bionemo-agent-toolkit:")
      ? args.id.slice("openclaw:bionemo-agent-toolkit:".length)
      : args.id === "mcp:bundle-mcp:clawbio_models__models_list" ? catalogTool : args.id;
  }
  if (wrappers.has(target)) return true;
  return target === catalogTool && result.isError !== true;
}

const HELPER_ANCHOR = "function buildOpenAICompletionsParams(model, context, options) {";
const PAYLOAD_ANCHOR = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {`;
const PAYLOAD_REPLACEMENT = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (bionemoSuperShouldFinalizeWithoutTools(model, context)) {\n\t\t\t\t\tdelete params.tools;\n\t\t\t\t\tparams.tool_choice = "none";\n\t\t\t\t}\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {`;

function replaceExactlyOnce(source, anchor, replacement, label) {
  const first = source.indexOf(anchor);
  if (first < 0 || source.indexOf(anchor, first + anchor.length) >= 0) {
    throw new Error(`Pinned OpenClaw Super compatibility check failed for ${label}`);
  }
  return `${source.slice(0, first)}${replacement}${source.slice(first + anchor.length)}`;
}

export async function patchOpenClawSuperFollowup(distRoot) {
  const names = (await readdir(distRoot)).filter((name) => name.startsWith("openai-transport-stream-") && name.endsWith(".js"));
  if (names.length !== 1) throw new Error(`Expected exactly one pinned OpenClaw completions transport chunk, found ${names.length}`);
  const filePath = path.join(distRoot, names[0]);
  const original = await readFile(filePath, "utf8");
  if (original.includes(PATCH_MARKER)) return { changed: false, path: filePath };
  const actual = createHash("sha256").update(original).digest("hex");
  if (actual !== PINNED_OPENCLAW_SUPER_FOLLOWUP_HASH) {
    throw new Error(`Pinned OpenClaw Super compatibility hash mismatch: ${actual}`);
  }
  let source = replaceExactlyOnce(
    original,
    HELPER_ANCHOR,
    `/* ${PATCH_MARKER} */\n${bionemoSuperShouldFinalizeWithoutTools.toString()}\n${HELPER_ANCHOR}`,
    "helper insertion",
  );
  source = replaceExactlyOnce(source, PAYLOAD_ANCHOR, PAYLOAD_REPLACEMENT, "post-payload tool guard");
  const temporary = `${filePath}.bionemo-${process.pid}.tmp`;
  await writeFile(temporary, source, { encoding: "utf8", mode: 0o644, flag: "wx" });
  await rename(temporary, filePath);
  return { changed: true, path: filePath };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  patchOpenClawSuperFollowup(process.argv[2]).catch((error) => {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  });
}
