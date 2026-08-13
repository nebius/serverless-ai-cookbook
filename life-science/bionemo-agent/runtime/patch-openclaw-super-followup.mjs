import { createHash } from "node:crypto";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";

export const PINNED_OPENCLAW_SUPER_FOLLOWUP_HASH = "82712e39d2863f055210df3a33f4a725872bcbf3dfef1b7ba181dba882f60edc";
const PATCH_MARKER = "openclaw.bionemo.super-followup.v2";
export const BIONEMO_SUPER_CATALOG_PROMPT = "Call exactly clawbio_models__models_list once with no arguments. Do not call any other tool. After it succeeds, call no more tools and briefly summarize which BioNeMo models are available.";
const NOTEBOOK_WORKFLOW_IDS = Object.freeze({
  "egfr-research-drug-demo": "research_drug_demo",
  "compare-protein-structures": "compare_protein_structures",
  "optimize-ligand-complex": "optimize_ligand_complex",
  "bulk-openfold2-five-proteins": "batch_fold_demo",
});
const ACKS = Object.freeze({
  ack_research_only: true,
  ack_non_clinical: true,
  ack_non_commercial: true,
  ack_aup_accepted: true,
  ack_no_safety_or_therapeutic_claims: true,
});
export const BIONEMO_SUPER_NOTEBOOK_TURNS = Object.freeze(NOTEBOOK_CATALOG.map((entry) => {
  const workflowId = NOTEBOOK_WORKFLOW_IDS[entry.slug];
  const params = {
    ...ACKS,
    ...(workflowId === "research_drug_demo" ? { use_tavily: true } : {}),
    ...(workflowId === "batch_fold_demo" ? { input_file: "notebooks/data/five-proteins.fasta" } : {}),
  };
  return Object.freeze({
    prompt: entry.prompt,
    name: `bionemo_${workflowId}`,
    params: Object.freeze(params),
  });
}));
export const BIONEMO_SUPER_INITIAL_TURNS = Object.freeze([
  ...BIONEMO_SUPER_NOTEBOOK_TURNS,
  Object.freeze({ prompt: BIONEMO_SUPER_CATALOG_PROMPT, name: "clawbio_models__models_list", params: Object.freeze({}) }),
]);

export function bionemoSuperInitialNotebookTool(model, context) {
  const superModel = "nvidia/nemotron-3-super-120b-a12b";
  if (String(model?.provider || "").toLowerCase() !== "tokenfactory"
    || String(model?.id || "").toLowerCase() !== superModel) return undefined;
  const messages = Array.isArray(context?.messages) ? context.messages : [];
  let userIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") { userIndex = index; break; }
  }
  if (userIndex < 0 || messages.slice(userIndex + 1).some((message) => message?.role === "toolResult")) return undefined;
  const content = messages[userIndex]?.content;
  const prompt = typeof content === "string" ? content : Array.isArray(content)
    ? content.filter((block) => block?.type === "text" && typeof block.text === "string").map((block) => block.text).join("")
    : "";
  const match = BIONEMO_SUPER_INITIAL_TURNS.find((entry) => entry.prompt === prompt);
  return match ? { name: match.name, params: { ...match.params } } : undefined;
}
export function bionemoSuperCompletedToolTarget(model, context) {
  const superModel = "nvidia/nemotron-3-super-120b-a12b";
  const wrappers = new Set([
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
  ]);
  const catalogTool = "clawbio_models__models_list";
  if (String(model?.provider || "").toLowerCase() !== "tokenfactory"
    || String(model?.id || "").toLowerCase() !== superModel) return undefined;
  const messages = Array.isArray(context?.messages) ? context.messages : [];
  const result = messages.at(-1);
  const assistant = messages.at(-2);
  if (result?.role !== "toolResult" || assistant?.role !== "assistant") return undefined;
  const calls = Array.isArray(assistant.content)
    ? assistant.content.filter((block) => block?.type === "toolCall")
    : [];
  if (calls.length !== 1 || !calls[0].id || calls[0].id !== result.toolCallId || calls[0].name !== result.toolName) return undefined;
  const call = calls[0];
  let target = call.name;
  if (target === "tool_call") {
    let args = call.arguments;
    if (typeof args === "string") {
      try { args = JSON.parse(args); } catch { return undefined; }
    }
    if (!args || typeof args !== "object" || Array.isArray(args) || typeof args.id !== "string") return undefined;
    target = args.id.startsWith("openclaw:bionemo-agent-toolkit:")
      ? args.id.slice("openclaw:bionemo-agent-toolkit:".length)
      : args.id === "mcp:bundle-mcp:clawbio_models__models_list" ? catalogTool : args.id;
  }
  const failed = result.isError === true
    || (result.error !== undefined && result.error !== null && result.error !== false && result.error !== "");
  if (failed) return undefined;
  if (wrappers.has(target)) return target;
  return target === catalogTool ? target : undefined;
}

export function bionemoSuperShouldFinalizeWithoutTools(model, context) {
  return Boolean(bionemoSuperCompletedToolTarget(model, context));
}

export function bionemoSuperBoundedResultSummary(model, context) {
  if (!bionemoSuperCompletedToolTarget(model, context)) return "";
  const result = Array.isArray(context?.messages) ? context.messages.at(-1) : undefined;
  let structured = result?.structuredContent;
  if (!structured || typeof structured !== "object" || Array.isArray(structured)) {
    const text = Array.isArray(result?.content)
      ? result.content.find((block) => block?.type === "text" && typeof block.text === "string")?.text
      : undefined;
    if (text) {
      try { structured = JSON.parse(text); } catch { structured = undefined; }
    }
  }
  const summary = structured?.summary;
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) return "";
  let serialized;
  try { serialized = JSON.stringify(summary, null, 2); } catch { return ""; }
  if (serialized.length > 6_000) serialized = `${serialized.slice(0, 6_000)}\n… (summary bounded)`;
  return serialized.replace(/([?&]access=)[A-Za-z0-9_-]+/gu, "$1[redacted]");
}

export function bionemoSuperDeterministicFinalText(model, context) {
  const target = bionemoSuperCompletedToolTarget(model, context);
  const text = {
    bionemo_research_drug_demo: "The Tavily, OpenFold2, MolMIM, and OpenFold3 research workflow returned a terminal result. Review the cited evidence, model confidence, selected candidate, and attached structures. This is research-only, non-clinical output that requires independent computational and wet-lab validation.",
    bionemo_compare_protein_structures: "The OpenFold2 and OpenFold3 structure-comparison workflow returned a terminal result. Review the returned scalar confidence summaries and attached structures. Neither prediction is experimental ground truth; this research-only output requires independent computational and wet-lab validation.",
    bionemo_optimize_ligand_complex: "The MolMIM and OpenFold3 ligand-complex workflow returned a terminal result. Review both candidates, the deterministic selection, returned score, confidence, and attached structure. It makes no binding, safety, efficacy, or clinical claim and requires independent validation.",
    bionemo_batch_fold_demo: "The bounded five-protein OpenFold2 workflow returned a terminal result. Review each record status, confidence summary, and attached structure. These research-only predictions require independent computational and experimental validation.",
    clawbio_models__models_list: "The read-only BioNeMo model catalog lookup completed. Review the returned catalog entries above.",
  };
  if (!target) return undefined;
  const summary = bionemoSuperBoundedResultSummary(model, context);
  return summary ? `${text[target]}\n\nReturned workflow summary:\n${summary}` : text[target];
}

const HELPER_ANCHOR = "function buildOpenAICompletionsParams(model, context, options) {";
const PAYLOAD_ANCHOR = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {\n\t\t\t\t\tenforceCodeModeResponsesToolSurface(params);\n\t\t\t\t\tassertCodeModeResponsesToolSurface(params);\n\t\t\t\t}`;
const PAYLOAD_REPLACEMENT = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {\n\t\t\t\t\tenforceCodeModeResponsesToolSurface(params);\n\t\t\t\t\tassertCodeModeResponsesToolSurface(params);\n\t\t\t\t}\n\t\t\t\tlet bionemoSuperInitialTool = bionemoSuperInitialNotebookTool(model, context);\n\t\t\t\tif (bionemoSuperInitialTool && Array.isArray(params.tools) && params.tools.some((tool) => tool?.function?.name === bionemoSuperInitialTool.name)) {\n\t\t\t\t\tparams.tool_choice = { type: "function", function: { name: bionemoSuperInitialTool.name } };\n\t\t\t\t} else bionemoSuperInitialTool = undefined;\n\t\t\t\tif (bionemoSuperShouldFinalizeWithoutTools(model, context)) {\n\t\t\t\t\tdelete params.tools;\n\t\t\t\t\tparams.tool_choice = "none";\n\t\t\t\t}`;
const STREAM_OPTIONS_ANCHOR = `\t\t\t\tawait processOpenAICompletionsStream(responseStream, output, model, stream, {\n\t\t\t\t\tsignal: options?.signal,\n\t\t\t\t\temitReasoning,`;
const STREAM_OPTIONS_REPLACEMENT = `\t\t\t\tawait processOpenAICompletionsStream(responseStream, output, model, stream, {\n\t\t\t\t\tsignal: options?.signal,\n\t\t\t\t\tbionemoSuperInitialTool,\n\t\t\t\t\tbionemoSuperFinalText: bionemoSuperDeterministicFinalText(model, context),\n\t\t\t\t\temitReasoning,`;
const STREAM_INIT_ANCHOR = `\tconst emitReasoning = options?.emitReasoning ?? true;\n\tconst compat = getCompat(model);`;
const STREAM_INIT_REPLACEMENT = `\tconst emitReasoning = options?.emitReasoning ?? true;\n\tconst bionemoSuperInitialTool = options?.bionemoSuperInitialTool && typeof options.bionemoSuperInitialTool === "object" ? options.bionemoSuperInitialTool : undefined;\n\tconst bionemoSuperFinalText = typeof options?.bionemoSuperFinalText === "string" ? options.bionemoSuperFinalText : "";\n\tconst compat = getCompat(model);`;
const TOOL_CALL_ANCHOR = `\t\tif (choiceDelta.tool_calls && choiceDelta.tool_calls.length > 0) {`;
const TOOL_CALL_REPLACEMENT = `\t\tif (!bionemoSuperFinalText && !bionemoSuperInitialTool && choiceDelta.tool_calls && choiceDelta.tool_calls.length > 0) {`;
const FALLBACK_ANCHOR = `\tconst hasToolCalls = output.content.some((block) => block.type === "toolCall");\n\tconst hasVisibleText = output.content.some((block) => block.type === "text" && typeof block.text === "string" && block.text.trim().length > 0);`;
const FALLBACK_REPLACEMENT = `\tconst hasToolCalls = output.content.some((block) => block.type === "toolCall");\n\tlet hasVisibleText = output.content.some((block) => block.type === "text" && typeof block.text === "string" && block.text.trim().length > 0);\n\tif (bionemoSuperFinalText && !hasVisibleText) {\n\t\tappendTextDelta(bionemoSuperFinalText);\n\t\thasVisibleText = true;\n\t}`;
const INITIAL_REPAIR_ANCHOR = `\tfinishAllToolCallBlocks();\n\tcurrentBlock = null;`;
const INITIAL_REPAIR_REPLACEMENT = `\tfinishAllToolCallBlocks();\n\tif (bionemoSuperInitialTool) {\n\t\toutput.content = output.content.filter((item) => item?.type !== "toolCall");\n\t\tconst block = { type: "toolCall", id: \`call_bionemo_super_\${randomUUID()}\`, name: bionemoSuperInitialTool.name, arguments: { ...bionemoSuperInitialTool.params }, partialArgs: JSON.stringify(bionemoSuperInitialTool.params) };\n\t\toutput.content.push(block);\n\t\ttoolCallBlockIndices.set(block, output.content.length - 1);\n\t\tpushStreamEvent({ type: "toolcall_start", contentIndex: output.content.length - 1, partial: output });\n\t\tpushStreamEvent({ type: "toolcall_delta", contentIndex: output.content.length - 1, delta: block.partialArgs, partial: output });\n\t\toutput.stopReason = "toolUse";\n\t}\n\tcurrentBlock = null;`;

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
    `/* ${PATCH_MARKER} */\nconst BIONEMO_SUPER_INITIAL_TURNS = ${JSON.stringify(BIONEMO_SUPER_INITIAL_TURNS)};\n${bionemoSuperInitialNotebookTool.toString()}\n${bionemoSuperCompletedToolTarget.toString()}\n${bionemoSuperShouldFinalizeWithoutTools.toString()}\n${bionemoSuperBoundedResultSummary.toString()}\n${bionemoSuperDeterministicFinalText.toString()}\n${HELPER_ANCHOR}`,
    "helper insertion",
  );
  source = replaceExactlyOnce(source, PAYLOAD_ANCHOR, PAYLOAD_REPLACEMENT, "post-payload tool guard");
  source = replaceExactlyOnce(source, STREAM_OPTIONS_ANCHOR, STREAM_OPTIONS_REPLACEMENT, "final-only stream option");
  source = replaceExactlyOnce(source, STREAM_INIT_ANCHOR, STREAM_INIT_REPLACEMENT, "final-only stream state");
  source = replaceExactlyOnce(source, TOOL_CALL_ANCHOR, TOOL_CALL_REPLACEMENT, "final-only tool suppression");
  source = replaceExactlyOnce(source, INITIAL_REPAIR_ANCHOR, INITIAL_REPAIR_REPLACEMENT, "initial notebook tool repair");
  source = replaceExactlyOnce(source, FALLBACK_ANCHOR, FALLBACK_REPLACEMENT, "deterministic final fallback");
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
