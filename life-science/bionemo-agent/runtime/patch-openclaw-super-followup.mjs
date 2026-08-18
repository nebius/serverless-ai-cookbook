import { createHash } from "node:crypto";
import { readdir, readFile, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";
import { WORKBENCH_EXAMPLE_SESSIONS } from "./example-session-catalog.mjs";

export const PINNED_OPENCLAW_SUPER_FOLLOWUP_HASH = "82712e39d2863f055210df3a33f4a725872bcbf3dfef1b7ba181dba882f60edc";
const PATCH_MARKER = "openclaw.bionemo.super-followup.v17";
const SOURCE_OWNED_TOKEN_FACTORY_MODELS = Object.freeze([
  "nvidia/nemotron-3-super-120b-a12b",
  "zai-org/glm-5.2",
]);
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
  Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "molmim-direct-mcp").prompt,
    name: "bionemo_molmim",
    params: Object.freeze({
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
    }),
  }),
  Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "tavily-public-research").prompt,
    name: "tavily_web__tavily_search",
    params: Object.freeze({
      query: "RCSB PDB UniProt protein structure research contributions",
      include_domains: Object.freeze(["rcsb.org", "uniprot.org"]),
      search_depth: "basic",
      max_results: 5,
      include_raw_content: false,
      include_images: false,
    }),
  }),
  Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "bionemo-model-inventory").prompt,
    name: "bionemo_models_list",
    params: Object.freeze({}),
  }),
]);

const GWAS_LIST_NAMES = Object.freeze([
  "ancestry-risk-profiler",
  "clinical-trial-finder",
  "fine-mapping",
  "gwas-catalog-region-fetch",
  "gwas-lookup",
  "gwas-pipeline",
  "gwas-prs",
  "locuscompare-region-render",
  "mendelian-randomisation",
  "wgs-prs",
]);
const GWAS_CONTRACT_SHA256 = "1add53f8a0b331d7a5d09eb97003f679438b623102514a101d1df159f5fe8316";
const GUIDED_FAILURE_TEXT = "I could not validate the packaged example result, so I stopped without running anything else. Start a fresh example session to try again; no additional tool or scientific job was submitted.";
const WORKBENCH_TOUR_TEXT = `This workspace combines a reasoning assistant with scientific models and packaged multi-step workflows. I can help frame a research question, choose an appropriate model or workflow, check inputs, coordinate requested steps, monitor progress, and explain the returned evidence and limitations.

Packaged biology skills provide task-specific guidance, while notebooks offer guided, reproducible examples. Uploads are staged when a workflow needs file input. Long-running work appears as jobs whose progress can be checked; previous jobs remain available through job history, and generated reports, tables, molecular structures, and other artifacts are saved with the result.

A service being available or ready means it is configured to accept work. It does not mean a particular result is scientifically valid, experimentally confirmed, safe, or clinically meaningful. Outputs are research-only and nonclinical and require independent computational and experimental validation. This orientation did not start a scientific job or probe an external service.`;
const SKILL_GUIDANCE_TEXT = `Packaged skills are task-specific operating guides. They help the assistant use the right sequence, inputs, safety boundaries, and interpretation rules for a task; they are not additional compute by themselves.

For biology catalogs, guidance explains how to discover and inspect a capability and its readiness. For public-source research, it defines source selection, citation, and evidence-versus-synthesis rules. For a multi-step scientific workflow, it describes how model calls, jobs, outputs, and validation should be coordinated.

Learning about a capability means reading its catalog entry or contract; running it means executing tools and possibly creating jobs or files. Workspace-specific rules take precedence over generic packaged guidance. A capability may remain documented even when optional software, data, credentials, or a service is not installed or configured, so documentation alone is not proof of availability.

This is nonclinical, research-use guidance. Nothing was executed.`;
const GWAS_CATALOG_TEXT = `The packaged workflow is GWAS Lookup (\`gwas-lookup\`, alias \`gwas\`). Its pinned catalog entry is runnable, CI-validated, and its bundled example is ready in this image.

It accepts one public dbSNP rsID such as \`rs3798220\`. It covers Ensembl/VEP variant resolution; association evidence from GWAS Catalog and Open Targets; PheWAS results from UKB-TOPMed, FinnGen, and Biobank Japan; expression evidence from GTEx and the EBI eQTL Catalogue; and Open Targets fine-mapping credible sets.

Its output layout contains \`report.md\`, CSV tables for GWAS, the three PheWAS collections, eQTL associations and credible sets, figures for GWAS traits and population allele frequencies, \`raw_results.json\`, and a reproducibility directory containing \`commands.sh\` and \`api_versions.json\`.

This was a read-only catalog and contract review. The lookup was not run and no clinical recommendation was made. Any eventual output is research-only and requires expert review and independent validation.`;
export const BIONEMO_GUIDED_STARTER_TURNS = Object.freeze({
  tour: Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "openclaw-workbench-tour").prompt,
    finalText: WORKBENCH_TOUR_TEXT,
  }),
  skills: Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "openclaw-skill-guidance").prompt,
    finalText: SKILL_GUIDANCE_TEXT,
  }),
  catalog: Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "clawbio-readonly-catalog").prompt,
    steps: Object.freeze([
      Object.freeze({ name: "clawbio__list_skills", params: Object.freeze({ query: "gwas" }) }),
      Object.freeze({ name: "clawbio__describe_skill", params: Object.freeze({ name: "gwas-lookup" }) }),
    ]),
    finalText: GWAS_CATALOG_TEXT,
  }),
  demo: Object.freeze({
    prompt: WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "clawbio-gwas-demo").prompt,
    steps: Object.freeze([
      Object.freeze({ name: "clawbio__describe_skill", params: Object.freeze({ name: "gwas-lookup" }) }),
      Object.freeze({ name: "clawbio__run_skill", params: Object.freeze({ skill: "gwas-lookup", demo: true }) }),
    ]),
  }),
});

export function bionemoIsSourceOwnedTokenFactoryModel(model) {
  return String(model?.provider || "").toLowerCase() === "tokenfactory"
    && SOURCE_OWNED_TOKEN_FACTORY_MODELS.includes(String(model?.id || "").toLowerCase());
}

export function bionemoNormalizeStrictOpenClawPrompt(prompt) {
  return typeof prompt === "string"
    ? prompt.replace(/^\[[A-Z][a-z]{2} \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\] /u, "")
    : "";
}

export function bionemoStrictCurrentUserTurn(context) {
  const messages = Array.isArray(context?.messages) ? context.messages : [];
  let userIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") { userIndex = index; break; }
  }
  if (userIndex < 0) {
    if (messages.length !== 0 || typeof context?.prompt !== "string") return undefined;
    return { prompt: bionemoNormalizeStrictOpenClawPrompt(context.prompt), currentTurn: [] };
  }
  const content = messages[userIndex]?.content;
  let prompt;
  if (typeof content === "string") prompt = content;
  else if (Array.isArray(content) && content.length === 1
    && content[0]?.type === "text" && typeof content[0].text === "string") prompt = content[0].text;
  else return undefined;
  return {
    prompt: bionemoNormalizeStrictOpenClawPrompt(prompt),
    currentTurn: messages.slice(userIndex + 1),
  };
}

function bionemoStrictArgsEqual(actual, expected) {
  if (!actual || typeof actual !== "object" || Array.isArray(actual)) return false;
  const actualKeys = Object.keys(actual);
  const expectedKeys = Object.keys(expected);
  return actualKeys.length === expectedKeys.length
    && actualKeys.every((key, index) => key === expectedKeys[index] && actual[key] === expected[key]);
}

function bionemoStrictProjectedCallId(value) {
  return typeof value === "string" && (
    /^call_bionemo_super_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(value)
    || /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u.test(value)
  );
}

function bionemoStrictSha256(value) {
  if (typeof sha256Hex === "function") return sha256Hex(value);
  if (typeof createHash === "function") return createHash("sha256").update(value).digest("hex");
  return "";
}

export function bionemoValidatedClawBioStep(pair, expected) {
  if (!Array.isArray(pair) || pair.length !== 2) return undefined;
  const [assistant, result] = pair;
  if (assistant?.role !== "assistant" || assistant.stopReason !== "toolUse"
    || !Array.isArray(assistant.content) || assistant.content.length !== 1
    || result?.role !== "toolResult" || result.toolName !== expected.name
    || result.isError !== false || Object.hasOwn(result, "error")
    || !Array.isArray(result.content) || result.content.length !== 1) return undefined;
  const call = assistant.content[0];
  if (call?.type !== "toolCall" || call.name !== expected.name
    || !bionemoStrictProjectedCallId(call.id) || call.id !== result.toolCallId
    || !bionemoStrictArgsEqual(call.arguments, expected.params)
    || call.partialArgs !== JSON.stringify(expected.params)) return undefined;
  const details = result.details;
  if (!details || typeof details !== "object" || Array.isArray(details)
    || details.mcpServer !== "clawbio"
    || details.mcpTool !== expected.name.slice("clawbio__".length)
    || !details.structuredContent || typeof details.structuredContent !== "object"
    || Array.isArray(details.structuredContent)) return undefined;
  const block = result.content[0];
  if (!block || typeof block !== "object" || Array.isArray(block)
    || Object.keys(block).sort().join(",") !== "text,type"
    || block.type !== "text" || typeof block.text !== "string" || block.text.length > 131_072) return undefined;
  let canonical;
  try { canonical = `structuredContent:\n${JSON.stringify(details.structuredContent, null, 2)}`; } catch { return undefined; }
  return block.text === canonical ? details.structuredContent : undefined;
}

export function bionemoValidatedGwasList(structured) {
  const entries = structured?.result;
  if (!Array.isArray(entries) || entries.length !== GWAS_LIST_NAMES.length) return false;
  const names = new Set();
  const expectedKeys = [
    "cli_alias", "demo_command", "demo_runnable_in_image", "description", "has_demo",
    "maturity_tier", "name", "runnable", "status", "tags",
  ];
  for (let index = 0; index < entries.length; index += 1) {
    const entry = entries[index];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)
      || Object.keys(entry).sort().some((key, keyIndex) => key !== expectedKeys[keyIndex])
      || Object.keys(entry).length !== expectedKeys.length
      || entry.name !== GWAS_LIST_NAMES[index] || names.has(entry.name)
      || !(entry.cli_alias === null || (typeof entry.cli_alias === "string" && entry.cli_alias.length <= 64))
      || typeof entry.demo_command !== "string" || entry.demo_command.length > 256
      || typeof entry.description !== "string" || !entry.description || entry.description.length > 1_024
      || typeof entry.has_demo !== "boolean" || typeof entry.runnable !== "boolean"
      || typeof entry.demo_runnable_in_image !== "boolean"
      || typeof entry.maturity_tier !== "string" || entry.maturity_tier.length > 64
      || typeof entry.status !== "string" || entry.status.length > 64
      || !Array.isArray(entry.tags) || entry.tags.length > 32
      || entry.tags.some((tag) => typeof tag !== "string" || tag.length > 64)) return false;
    names.add(entry.name);
  }
  const gwas = entries[4];
  return gwas.cli_alias === "gwas" && gwas.status === "mvp"
    && gwas.maturity_tier === "ci-validated" && gwas.has_demo === true
    && gwas.runnable === true && gwas.demo_runnable_in_image === true;
}

export function bionemoValidatedGwasContract(structured) {
  const expectedKeys = [
    "chaining_partners", "cli_alias", "data_license", "demo_command", "demo_runnable_in_image",
    "dependencies", "description", "has_demo", "has_script", "has_tests", "license",
    "maturity_evidence", "maturity_tier", "model_license", "name", "spec", "status", "tags",
    "trigger_keywords", "version",
  ];
  if (!structured || typeof structured !== "object" || Array.isArray(structured)
    || Object.keys(structured).length !== expectedKeys.length
    || Object.keys(structured).sort().some((key, index) => key !== expectedKeys[index])
    || structured.name !== "gwas-lookup" || structured.cli_alias !== "gwas"
    || structured.status !== "mvp" || structured.maturity_tier !== "ci-validated"
    || structured.has_demo !== true || structured.has_script !== true || structured.has_tests !== true
    || structured.demo_runnable_in_image !== true || structured.license !== "MIT"
    || typeof structured.description !== "string" || structured.description.length > 1_024
    || typeof structured.spec !== "string" || structured.spec.length > 32_768
    || bionemoStrictSha256(structured.spec) !== GWAS_CONTRACT_SHA256) return false;
  return Array.isArray(structured.dependencies) && Array.isArray(structured.chaining_partners)
    && Array.isArray(structured.tags) && Array.isArray(structured.trigger_keywords)
    && structured.trigger_keywords.includes("rsID") && structured.spec.includes("## Output Structure");
}

export function bionemoValidatedGwasDemo(structured) {
  if (!structured || typeof structured !== "object" || Array.isArray(structured)
    || Object.keys(structured).sort().join(",") !== "demo,exit_code,skill,stderr,stdout,success"
    || structured.skill !== "gwas-lookup" || structured.demo !== true
    || structured.success !== true || structured.exit_code !== 0 || structured.stderr !== ""
    || typeof structured.stdout !== "string" || structured.stdout.length > 16_384) return undefined;
  const reportMatch = structured.stdout.match(/  Report: (\/workspace\/agent\/artifacts\/clawbio\/output\/gwas_[0-9]{8}_[0-9]{6})\/report\.md\n/u);
  const fullMatch = structured.stdout.match(/  Full output: (\/workspace\/agent\/artifacts\/clawbio\/output\/gwas_[0-9]{8}_[0-9]{6})\/\n/u);
  if (!reportMatch || !fullMatch || reportMatch[1] !== fullMatch[1]) return undefined;
  const root = reportMatch[1];
  const normalized = structured.stdout.replaceAll(root, "<ROOT>");
  const expected = `GWAS Lookup: rs3798220
============================================================

  Demo mode: loading demo_rs3798220.json

  Using pre-fetched demo data for rs3798220
  Resolved: chr6:160540105 (T/C)
  Consequence: missense_variant

  Loaded 8 pre-fetched API results

  Merging and normalising results...
    GWAS: 11 associations (11 GWS)
    PheWAS: UKB=5, FinnGen=3, BBJ=1
    eQTLs: 5
    Credible sets: 3

  Writing report...
  Writing CSV tables...
  Generating figures...
  Writing reproducibility bundle...
  Writing result.json...

  Report: <ROOT>/report.md
  Full output: <ROOT>/

  ClawBio is a research and educational tool. It is not a medical device and does not provide clinical diagnoses. Consult a healthcare professional before making any medical decisions.
`;
  return normalized === expected ? { root, reportPath: `${root}/report.md` } : undefined;
}

function bionemoGwasDemoFinalText(validated) {
  const { root, reportPath } = validated;
  return `The bundled offline GWAS lookup completed using public, pre-fetched reference data for \`rs3798220\`. The variant resolved to GRCh38 \`chr6:160540105\`, alleles T/C, with a missense consequence in LPA.

The bundled report contains 11 merged GWAS associations, all marked genome-wide significant; PheWAS results from UKB (5), FinnGen (3), and Biobank Japan (1); five eQTL associations including LPA expression findings; and three Open Targets fine-mapping credible sets.

Generated files:

- Report: \`${reportPath}\`
- Tables: \`${root}/tables/\` — \`gwas_associations.csv\`, \`phewas_ukb.csv\`, \`phewas_finngen.csv\`, \`phewas_bbj.csv\`, \`eqtl_associations.csv\`, and \`credible_sets.csv\`
- Figures: \`${root}/figures/\` — \`gwas_traits_dotplot.png\` and \`allele_freq_populations.png\`
- Raw results: \`${root}/raw_results.json\`
- Reproducibility: \`${root}/reproducibility/commands.sh\` and \`${root}/reproducibility/api_versions.json\`
- Machine-readable result: \`${root}/result.json\`
- Full output root: \`${root}/\`

The input is public and the output is research-only. It is not a diagnosis, personal-risk prediction, or treatment recommendation.`;
}

export function bionemoGuidedStarterAction(model, context) {
  if (!bionemoIsSourceOwnedTokenFactoryModel(model)) return undefined;
  const turn = bionemoStrictCurrentUserTurn(context);
  if (!turn) return undefined;
  const entry = Object.values(BIONEMO_GUIDED_STARTER_TURNS).find(({ prompt }) => prompt === turn.prompt);
  if (!entry) return undefined;
  if (!entry.steps) return turn.currentTurn.length === 0
    ? { type: "final", text: entry.finalText }
    : { type: "final", text: GUIDED_FAILURE_TEXT };
  if (turn.currentTurn.length === 0) return { type: "tool", ...entry.steps[0] };
  const first = bionemoValidatedClawBioStep(turn.currentTurn.slice(0, 2), entry.steps[0]);
  const firstValid = entry === BIONEMO_GUIDED_STARTER_TURNS.catalog
    ? bionemoValidatedGwasList(first)
    : bionemoValidatedGwasContract(first);
  if (!firstValid) return { type: "final", text: GUIDED_FAILURE_TEXT };
  if (turn.currentTurn.length === 2) return { type: "tool", ...entry.steps[1] };
  if (turn.currentTurn.length !== 4) return { type: "final", text: GUIDED_FAILURE_TEXT };
  const second = bionemoValidatedClawBioStep(turn.currentTurn.slice(2, 4), entry.steps[1]);
  if (entry === BIONEMO_GUIDED_STARTER_TURNS.catalog) {
    return bionemoValidatedGwasContract(second)
      ? { type: "final", text: entry.finalText }
      : { type: "final", text: GUIDED_FAILURE_TEXT };
  }
  const demo = bionemoValidatedGwasDemo(second);
  return demo
    ? { type: "final", text: bionemoGwasDemoFinalText(demo) }
    : { type: "final", text: GUIDED_FAILURE_TEXT };
}

export function bionemoSuperInitialNotebookTool(model, context) {
  const guided = bionemoGuidedStarterAction(model, context);
  if (guided?.type === "tool") return { name: guided.name, params: { ...guided.params } };
  if (guided) return undefined;
  if (!bionemoIsSourceOwnedTokenFactoryModel(model)) return undefined;
  const turn = bionemoStrictCurrentUserTurn(context);
  if (!turn || turn.currentTurn.length !== 0) return undefined;
  const match = BIONEMO_SUPER_INITIAL_TURNS.find((entry) => entry.prompt === turn.prompt);
  return match ? { name: match.name, params: { ...match.params } } : undefined;
}

export function bionemoSuperValidatedModelInventory(model, context) {
  const inventoryTool = "bionemo_models_list";
  if (!bionemoIsSourceOwnedTokenFactoryModel(model)) return undefined;
  const expected = BIONEMO_SUPER_INITIAL_TURNS.find((entry) => entry.name === inventoryTool);
  if (!expected || Object.keys(expected.params).length !== 0) return undefined;

  const messages = Array.isArray(context?.messages) ? context.messages : [];
  let userIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") { userIndex = index; break; }
  }
  if (userIndex < 0) return undefined;
  const userContent = messages[userIndex]?.content;
  if (typeof userContent !== "string"
    || bionemoNormalizeStrictOpenClawPrompt(userContent) !== expected.prompt) return undefined;
  const currentTurn = messages.slice(userIndex + 1);
  if (currentTurn.length !== 2) return undefined;
  const assistant = currentTurn[0];
  const result = currentTurn[1];
  if (assistant?.role !== "assistant" || result?.role !== "toolResult"
    || !Array.isArray(assistant.content) || assistant.content.length !== 1) return undefined;
  const call = assistant.content[0];
  const projectedCallId = /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u;
  if (assistant.stopReason !== "toolUse"
    || call?.type !== "toolCall" || call.name !== inventoryTool
    || result.toolName !== inventoryTool
    || typeof call.id !== "string" || !projectedCallId.test(call.id)
    || typeof result.toolCallId !== "string" || !projectedCallId.test(result.toolCallId)
    || call.id !== result.toolCallId
    || !call.arguments || typeof call.arguments !== "object" || Array.isArray(call.arguments)
    || Object.keys(call.arguments).length !== 0 || call.partialArgs !== JSON.stringify(expected.params)
    || !Object.hasOwn(result, "isError") || result.isError !== false
    || Object.hasOwn(result, "error") || result.error !== undefined
    || Object.hasOwn(result, "details") || result.details !== undefined
    || Object.hasOwn(result, "structuredContent") || result.structuredContent !== undefined
    || !Array.isArray(result.content) || result.content.length !== 1) return undefined;
  const contentBlock = result.content[0];
  const contentKeys = contentBlock && typeof contentBlock === "object" && !Array.isArray(contentBlock)
    ? Object.keys(contentBlock).sort()
    : [];
  if (contentKeys.length !== 2 || contentKeys[0] !== "text" || contentKeys[1] !== "type"
    || contentBlock.type !== "text" || typeof contentBlock.text !== "string"
    || contentBlock.text.length > 65_536) return undefined;

  let structured;
  try { structured = JSON.parse(contentBlock.text); } catch { return undefined; }
  let canonical;
  try { canonical = JSON.stringify(structured, null, 2); } catch { return undefined; }
  if (canonical !== contentBlock.text || !structured || typeof structured !== "object" || Array.isArray(structured)) return undefined;
  const topKeys = Object.keys(structured).sort();
  const expectedTopKeys = ["computeSubmitted", "modelCount", "models", "notice", "readOnly", "readyCount"];
  if (topKeys.length !== expectedTopKeys.length
    || topKeys.some((key, index) => key !== expectedTopKeys[index])
    || structured.readOnly !== true || structured.computeSubmitted !== false
    || !Number.isInteger(structured.modelCount) || structured.modelCount < 1 || structured.modelCount > 64
    || !Array.isArray(structured.models) || structured.models.length !== structured.modelCount
    || !Number.isInteger(structured.readyCount) || structured.readyCount < 0 || structured.readyCount > structured.modelCount
    || structured.notice !== "Sanitized model inventory only; no scientific compute or job was submitted.") return undefined;

  const identifiers = new Set();
  let readyCount = 0;
  for (const entry of structured.models) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return undefined;
    const entryKeys = Object.keys(entry).sort();
    if (entryKeys.length !== 4
      || entryKeys[0] !== "displayName" || entryKeys[1] !== "family"
      || entryKeys[2] !== "id" || entryKeys[3] !== "readiness"
      || typeof entry.id !== "string" || !/^[a-z0-9][a-z0-9_]{0,79}$/u.test(entry.id)
      || typeof entry.family !== "string" || !/^[a-z0-9][a-z0-9_]{0,79}$/u.test(entry.family)
      || typeof entry.displayName !== "string"
      || entry.displayName.replace(/[\u0000-\u001f\u007f]/gu, " ").replace(/\s+/gu, " ").trim() !== entry.displayName
      || entry.displayName.includes("://")
      || !/^[A-Za-z0-9][A-Za-z0-9 ._+()/-]{0,127}$/u.test(entry.displayName)
      || !["ready", "not_ready", "unknown"].includes(entry.readiness)
      || identifiers.has(entry.id)) return undefined;
    identifiers.add(entry.id);
    if (entry.readiness === "ready") readyCount += 1;
  }
  return readyCount === structured.readyCount ? structured : undefined;
}

export function bionemoSuperCompletedToolTarget(model, context) {
  const superModel = "nvidia/nemotron-3-super-120b-a12b";
  const glmModel = "zai-org/glm-5.2";
  const deepSeekModel = "deepseek-ai/deepseek-v4-pro";
  const tavilySearch = "tavily_web__tavily_search";
  const wrappers = new Set([
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
    "bionemo_molmim",
    "bionemo_openfold2",
    "bionemo_openfold3",
  ]);
  const modelId = String(model?.id || "").toLowerCase();
  if (String(model?.provider || "").toLowerCase() !== "tokenfactory"
    || (modelId !== superModel && modelId !== glmModel && modelId !== deepSeekModel)) return undefined;
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
      : args.id;
  }
  const failed = result.isError === true
    || (result.error !== undefined && result.error !== null && result.error !== false && result.error !== "");
  if (failed) return undefined;
  if (wrappers.has(target)) return target;
  if (target === "bionemo_models_list") {
    return bionemoSuperValidatedModelInventory(model, context) ? target : undefined;
  }
  if (!bionemoIsSourceOwnedTokenFactoryModel(model) || target !== tavilySearch || call.name !== tavilySearch
    || result.toolName !== tavilySearch || result.isError !== false || result.structuredContent !== undefined) return undefined;

  const expected = BIONEMO_SUPER_INITIAL_TURNS.find((entry) => entry.name === tavilySearch);
  if (!expected) return undefined;
  let userIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "user") { userIndex = index; break; }
  }
  if (userIndex < 0) return undefined;
  const userContent = messages[userIndex]?.content;
  const prompt = typeof userContent === "string" ? userContent : Array.isArray(userContent)
    ? userContent.filter((block) => block?.type === "text" && typeof block.text === "string").map((block) => block.text).join("")
    : "";
  if (bionemoNormalizeStrictOpenClawPrompt(prompt) !== expected.prompt) return undefined;

  const currentTurn = messages.slice(userIndex + 1);
  const turnCalls = currentTurn.flatMap((message) => message?.role === "assistant" && Array.isArray(message.content)
    ? message.content.filter((block) => ["toolCall", "toolUse", "functionCall"].includes(block?.type))
    : []);
  const turnResults = currentTurn.filter((message) => ["toolResult", "tool", "function"].includes(message?.role));
  if (turnCalls.length !== 1 || turnCalls[0] !== call || turnResults.length !== 1 || turnResults[0] !== result) return undefined;

  let args = call.arguments;
  if (typeof args === "string") {
    try { args = JSON.parse(args); } catch { return undefined; }
  }
  if (!args || typeof args !== "object" || Array.isArray(args)) return undefined;
  const expectedKeys = Object.keys(expected.params).sort();
  const actualKeys = Object.keys(args).sort();
  if (actualKeys.length !== expectedKeys.length || actualKeys.some((key, index) => key !== expectedKeys[index])) return undefined;
  if (args.query !== expected.params.query
    || args.search_depth !== expected.params.search_depth
    || args.max_results !== expected.params.max_results
    || args.include_raw_content !== expected.params.include_raw_content
    || args.include_images !== expected.params.include_images
    || !Array.isArray(args.include_domains)
    || args.include_domains.length !== expected.params.include_domains.length
    || args.include_domains.some((domain, index) => domain !== expected.params.include_domains[index])) return undefined;

  const hasDetails = Object.hasOwn(result, "details");
  const details = result.details;
  let structured;
  if (hasDetails) {
    if (!details || typeof details !== "object" || Array.isArray(details)
      || details.mcpServer !== "tavily_web" || details.mcpTool !== "tavily_search") return undefined;
    structured = details.structuredContent;
  } else {
    const projectedCallId = /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u;
    if (typeof userContent !== "string"
      || bionemoNormalizeStrictOpenClawPrompt(userContent) !== expected.prompt
      || !Array.isArray(assistant.content) || assistant.content.length !== 1 || assistant.content[0] !== call
      || assistant.stopReason !== "toolUse"
      || call.type !== "toolCall" || call.partialArgs !== JSON.stringify(expected.params)
      || typeof call.id !== "string" || !projectedCallId.test(call.id)
      || typeof result.toolCallId !== "string" || !projectedCallId.test(result.toolCallId)
      || !Object.hasOwn(result, "isError") || result.isError !== false
      || Object.hasOwn(result, "error") || result.error !== undefined
      || Object.hasOwn(result, "structuredContent") || result.structuredContent !== undefined
      || details !== undefined
      || !Array.isArray(result.content) || result.content.length !== 1) return undefined;
    const contentBlock = result.content[0];
    const contentKeys = contentBlock && typeof contentBlock === "object" && !Array.isArray(contentBlock)
      ? Object.keys(contentBlock).sort()
      : [];
    if (contentKeys.length !== 2 || contentKeys[0] !== "text" || contentKeys[1] !== "type"
      || contentBlock.type !== "text" || typeof contentBlock.text !== "string" || contentBlock.text.length > 65_536) return undefined;
    const marker = "structuredContent:\n";
    if (!contentBlock.text.startsWith(marker)) return undefined;
    const suffix = contentBlock.text.slice(marker.length);
    try { structured = JSON.parse(suffix); } catch { return undefined; }
    let canonical;
    try { canonical = JSON.stringify(structured, null, 2); } catch { return undefined; }
    if (canonical !== suffix) return undefined;
  }
  if (!structured || typeof structured !== "object" || Array.isArray(structured)
    || structured.query !== expected.params.query
    || !Array.isArray(structured.results) || structured.results.length < 1 || structured.results.length > 5) return undefined;
  for (const source of structured.results) {
    if (!source || typeof source !== "object" || Array.isArray(source)
      || typeof source.title !== "string" || !source.title.trim() || source.title.length > 300
      || /[\u0000-\u001f\u007f]/u.test(source.title)
      || typeof source.url !== "string" || !source.url.trim() || source.url.length > 2_048) return undefined;
    let url;
    try { url = new URL(source.url); } catch { return undefined; }
    const hostname = url.hostname.toLowerCase();
    const allowedHost = ["rcsb.org", "uniprot.org"].some((domain) => hostname === domain || hostname.endsWith(`.${domain}`));
    if (url.protocol !== "https:" || url.username || url.password || url.port || !allowedHost) return undefined;
  }
  return tavilySearch;
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
  let bounded = summary;
  const runId = structured?.runId;
  const artifacts = structured?.artifacts;
  if (typeof runId === "string"
    && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u.test(runId)
    && Array.isArray(artifacts) && artifacts.length > 0 && artifacts.length <= 64) {
    const projected = [];
    for (const artifact of artifacts) {
      if (!artifact || typeof artifact !== "object" || Array.isArray(artifact)
        || typeof artifact.name !== "string"
        || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u.test(artifact.name)
        || artifact.downloadPath !== `/workspace/agent/artifacts/${runId}/${artifact.name}`) {
        projected.length = 0;
        break;
      }
      projected.push({ name: artifact.name, downloadPath: artifact.downloadPath });
    }
    if (projected.length === artifacts.length) bounded = { ...summary, artifacts: projected };
  }
  let serialized;
  try { serialized = JSON.stringify(bounded, null, 2); } catch { return ""; }
  if (serialized.length > 6_000) serialized = `${serialized.slice(0, 6_000)}\n… (summary bounded)`;
  return serialized.replace(/([?&]access=)[A-Za-z0-9_-]+/gu, "$1[redacted]");
}

export function bionemoSuperDeterministicFinalText(model, context) {
  const target = bionemoSuperCompletedToolTarget(model, context);
  const text = {
    bionemo_research_drug_demo: "The Tavily, OpenFold2, MolMIM, and OpenFold3 research workflow returned a terminal result. Review the cited evidence, model confidence, selected candidate, and attached structures. This is research-only, non-clinical output that requires independent computational and wet-lab validation.",
    bionemo_compare_protein_structures: "The OpenFold2 and OpenFold3 structure-comparison workflow returned a terminal result. Review the returned scalar confidence summaries and attached structures. Neither prediction is experimental ground truth; this research-only output requires independent computational and wet-lab validation.",
    bionemo_optimize_ligand_complex: "The MolMIM and OpenFold3 ligand-complex workflow returned a terminal result after generating two gefitinib-like candidates with the requested QED optimization and seed-similarity objective, then modeling the deterministically selected highest-scoring embeddable candidate. Review both candidate SMILES and MolMIM scores, the selection basis, OpenFold3 confidence, and the attached structure. These proxy and predicted values make no binding, safety, efficacy, or clinical claim and require independent validation.",
    bionemo_batch_fold_demo: "The bounded five-protein OpenFold2 workflow returned a terminal result. Review each record status, confidence summary, and attached structure. These research-only predictions require independent computational and experimental validation.",
    bionemo_molmim: "The bounded MolMIM optimization returned a terminal result. Review the returned candidates and scores as research-only hypotheses. No binding, safety, efficacy, therapeutic, or clinical claim is made; independent computational and wet-lab validation is required.",
    bionemo_openfold2: "The bounded OpenFold2 prediction returned a terminal result. Review the scalar confidence summary and attached structure. This is not experimental ground truth and requires independent computational and experimental validation.",
    bionemo_openfold3: "The bounded OpenFold3 prediction returned a terminal result. Review the scalar confidence summary and attached structure. This is not experimental ground truth and requires independent computational and experimental validation.",
    tavily_web__tavily_search: "The bounded Tavily search completed for the requested RCSB PDB and UniProt documentation comparison. Source claims: none are restated from untrusted search content. Source-owned comparison (not derived from the returned snippets): RCSB PDB is structure-centered, while UniProt is sequence- and annotation-centered; their cross-references connect structures with protein identity and biological context. Validated Tavily response metadata records only that the bounded search returned the source titles and canonical URLs appended below. No BioNeMo, ClawBio, or scientific compute was run.",
  };
  if (!target) return undefined;
  if (target === "tavily_web__tavily_search") {
    const result = Array.isArray(context?.messages) ? context.messages.at(-1) : undefined;
    let structured = result?.details?.structuredContent;
    if (!structured || typeof structured !== "object" || Array.isArray(structured)) {
      const textBlock = Array.isArray(result?.content)
        ? result.content.find((block) => block?.type === "text" && typeof block.text === "string")
        : undefined;
      const marker = "structuredContent:\n";
      if (textBlock?.text?.startsWith(marker)) {
        try { structured = JSON.parse(textBlock.text.slice(marker.length)); } catch { structured = undefined; }
      }
    }
    const sources = Array.isArray(structured?.results) ? structured.results.map(({ title, url }) => ({
      title: title.replace(/[\u0000-\u001f\u007f]/gu, " ").replace(/\s+/gu, " ").trim(),
      url: new URL(url).toString(),
    })) : [];
    const sourceLines = sources.map(({ title, url }) => (
      `- ${title.replace(/([\\`*_[\]{}()<>#+\-.!|])/gu, "\\$1")} — ${url}`
    )).join("\n");
    const hosts = new Set(sources.map(({ url }) => new URL(url).hostname.toLowerCase()));
    const hasDomain = (domain) => [...hosts].some((host) => host === domain || host.endsWith(`.${domain}`));
    const coverage = [
      ...(!hasDomain("uniprot.org") ? ["No direct UniProt source was returned by this bounded search."] : []),
      ...(!hasDomain("rcsb.org") ? ["No direct RCSB source was returned by this bounded search."] : []),
    ];
    return `${text[target]}\n\nSources\n\n${sourceLines}${coverage.length ? `\n\n${coverage.join("\n")}` : ""}`;
  }
  if (target === "bionemo_models_list") {
    const inventory = bionemoSuperValidatedModelInventory(model, context);
    if (!inventory) return undefined;
    const models = inventory.models.map(({ id, displayName, family, readiness }) => (
      `- id: ${id}; displayName: ${displayName}; family: ${family}; readiness: ${readiness}`
    )).join("\n");
    return `Configured BioNeMo model inventory: ${inventory.modelCount} models; ${inventory.readyCount} ready.\n\n${models}\n\nThe inventory was read-only and submitted no scientific compute or model job. Every listed service is callable through its corresponding adapted bionemo_models__* compute operation in this browser; scvi_scanvi has separate scvi_fit_transform and scanvi_fit_transform operations. Readiness does not establish scientific validity.`;
  }
  const summary = bionemoSuperBoundedResultSummary(model, context);
  return summary ? `${text[target]}\n\nReturned workflow summary:\n${summary}` : text[target];
}

export function bionemoSuperLocalCompletionText(model, context) {
  if (!bionemoIsSourceOwnedTokenFactoryModel(model)) return undefined;
  const guided = bionemoGuidedStarterAction(model, context);
  if (guided?.type === "final") return guided.text;
  if (guided) return undefined;
  const target = bionemoSuperCompletedToolTarget(model, context);
  if (!target) return undefined;
  const result = Array.isArray(context?.messages) ? context.messages.at(-1) : undefined;
  if (result?.isError !== false) return undefined;
  if (target === "tavily_web__tavily_search" || target === "bionemo_models_list") {
    return bionemoSuperDeterministicFinalText(model, context);
  }
  let structured = result?.structuredContent;
  if (!structured || typeof structured !== "object" || Array.isArray(structured)) {
    const text = Array.isArray(result?.content)
      ? result.content.find((block) => block?.type === "text" && typeof block.text === "string")?.text
      : undefined;
    if (text) {
      try { structured = JSON.parse(text); } catch { structured = undefined; }
    }
  }
  if (String(structured?.status || "").toLowerCase() !== "completed") return undefined;
  return bionemoSuperDeterministicFinalText(model, context);
}

const HELPER_ANCHOR = "function buildOpenAICompletionsParams(model, context, options) {";
const CLIENT_ANCHOR = `\t\t\t\tconst client = createOpenAICompletionsClient(model, context, options?.apiKey || getEnvApiKey(model.provider) || "", options?.headers);`;
const CLIENT_REPLACEMENT = `\t\t\t\tconst bionemoSuperLocalFinalText = bionemoSuperLocalCompletionText(model, context);\n\t\t\t\tconst client = bionemoSuperLocalFinalText ? undefined : createOpenAICompletionsClient(model, context, options?.apiKey || getEnvApiKey(model.provider) || "", options?.headers);`;
const PAYLOAD_ANCHOR = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {\n\t\t\t\t\tenforceCodeModeResponsesToolSurface(params);\n\t\t\t\t\tassertCodeModeResponsesToolSurface(params);\n\t\t\t\t}`;
const PAYLOAD_REPLACEMENT = `\t\t\t\tconst nextParams = await options?.onPayload?.(params, model);\n\t\t\t\tif (nextParams !== void 0) params = nextParams;\n\t\t\t\tif (options?.openclawCodeModeToolSurface === true) {\n\t\t\t\t\tenforceCodeModeResponsesToolSurface(params);\n\t\t\t\t\tassertCodeModeResponsesToolSurface(params);\n\t\t\t\t}\n\t\t\t\tlet bionemoSuperInitialTool = bionemoSuperInitialNotebookTool(model, context);\n\t\t\t\tlet bionemoSuperFinalText = bionemoSuperLocalFinalText ?? bionemoSuperDeterministicFinalText(model, context);\n\t\t\t\tif (bionemoSuperInitialTool && Array.isArray(params.tools)\n\t\t\t\t\t&& params.tools.some((tool) => tool?.function?.name === bionemoSuperInitialTool.name)) {\n\t\t\t\t\tparams.tool_choice = { type: "function", function: { name: bionemoSuperInitialTool.name } };\n\t\t\t\t} else if (bionemoSuperInitialTool) {\n\t\t\t\t\tbionemoSuperInitialTool = undefined;\n\t\t\t\t\tbionemoSuperFinalText = GUIDED_FAILURE_TEXT;\n\t\t\t\t}\n\t\t\t\tif (bionemoSuperFinalText) {\n\t\t\t\t\tdelete params.tools;\n\t\t\t\t\tparams.tool_choice = "none";\n\t\t\t\t}`;
const REQUEST_ANCHOR = `\t\t\t\tfirstEventAbort = createFirstStreamEventAbortController(options?.signal);\n\t\t\t\tconst responseStream = await client.chat.completions.create(params, buildOpenAISdkRequestOptions(model, firstEventAbort.signal));`;
const REQUEST_REPLACEMENT = `\t\t\t\tfirstEventAbort = createFirstStreamEventAbortController(options?.signal);\n\t\t\t\tconst bionemoSuperLocalResponse = bionemoSuperFinalText || Boolean(bionemoSuperInitialTool);\n\t\t\t\tconst responseStream = bionemoSuperLocalResponse\n\t\t\t\t\t? (async function* bionemoSuperCompletedStream() {\n\t\t\t\t\t\tyield { id: "bionemo-local-completion", choices: [{ index: 0, delta: {}, finish_reason: "stop" }] };\n\t\t\t\t\t})()\n\t\t\t\t\t: await client.chat.completions.create(params, buildOpenAISdkRequestOptions(model, firstEventAbort.signal));`;
const STREAM_OPTIONS_ANCHOR = `\t\t\t\tawait processOpenAICompletionsStream(responseStream, output, model, stream, {\n\t\t\t\t\tsignal: options?.signal,\n\t\t\t\t\temitReasoning,`;
const STREAM_OPTIONS_REPLACEMENT = `\t\t\t\tawait processOpenAICompletionsStream(responseStream, output, model, stream, {\n\t\t\t\t\tsignal: options?.signal,\n\t\t\t\t\tbionemoSuperInitialTool,\n\t\t\t\t\tbionemoSuperFinalText,\n\t\t\t\t\temitReasoning,`;
const STREAM_INIT_ANCHOR = `\tconst emitReasoning = options?.emitReasoning ?? true;\n\tconst compat = getCompat(model);`;
const STREAM_INIT_REPLACEMENT = `\tconst emitReasoning = options?.emitReasoning ?? true;\n\tconst bionemoSuperInitialTool = options?.bionemoSuperInitialTool && typeof options.bionemoSuperInitialTool === "object" ? options.bionemoSuperInitialTool : undefined;\n\tconst bionemoSuperFinalText = typeof options?.bionemoSuperFinalText === "string" ? options.bionemoSuperFinalText : "";\n\tconst compat = getCompat(model);`;
const CONTENT_ANCHOR = `\t\tif (choiceDelta.content) {`;
const CONTENT_REPLACEMENT = `\t\tif (choiceDelta.content && !bionemoSuperFinalText && !bionemoSuperInitialTool) {`;
const REFUSAL_ANCHOR = `\t\tif (refusalText) {`;
const REFUSAL_REPLACEMENT = `\t\tif (refusalText && !bionemoSuperFinalText && !bionemoSuperInitialTool) {`;
const REASONING_ANCHOR = `\t\tfor (const reasoningDelta of reasoningDeltas) {`;
const REASONING_REPLACEMENT = `\t\tfor (const reasoningDelta of bionemoSuperFinalText || bionemoSuperInitialTool ? [] : reasoningDeltas) {`;
const TOOL_CALL_ANCHOR = `\t\tif (choiceDelta.tool_calls && choiceDelta.tool_calls.length > 0) {`;
const TOOL_CALL_REPLACEMENT = `\t\tif (!bionemoSuperFinalText && !bionemoSuperInitialTool && choiceDelta.tool_calls && choiceDelta.tool_calls.length > 0) {`;
const FALLBACK_ANCHOR = `\tconst hasToolCalls = output.content.some((block) => block.type === "toolCall");\n\tconst hasVisibleText = output.content.some((block) => block.type === "text" && typeof block.text === "string" && block.text.trim().length > 0);`;
const FALLBACK_REPLACEMENT = `\tconst hasToolCalls = output.content.some((block) => block.type === "toolCall");\n\tlet hasVisibleText = output.content.some((block) => block.type === "text" && typeof block.text === "string" && block.text.trim().length > 0);\n\tif (bionemoSuperFinalText) {\n\t\toutput.content = output.content.filter((block) => block.type !== "text" && block.type !== "thinking");\n\t\tcurrentBlock = null;\n\t\tappendTextDelta(bionemoSuperFinalText);\n\t\thasVisibleText = true;\n\t}`;
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
    `/* ${PATCH_MARKER} */\nconst SOURCE_OWNED_TOKEN_FACTORY_MODELS = ${JSON.stringify(SOURCE_OWNED_TOKEN_FACTORY_MODELS)};\nconst BIONEMO_SUPER_INITIAL_TURNS = ${JSON.stringify(BIONEMO_SUPER_INITIAL_TURNS)};\nconst GWAS_LIST_NAMES = ${JSON.stringify(GWAS_LIST_NAMES)};\nconst GWAS_CONTRACT_SHA256 = ${JSON.stringify(GWAS_CONTRACT_SHA256)};\nconst GUIDED_FAILURE_TEXT = ${JSON.stringify(GUIDED_FAILURE_TEXT)};\nconst BIONEMO_GUIDED_STARTER_TURNS = ${JSON.stringify(BIONEMO_GUIDED_STARTER_TURNS)};\n${bionemoNormalizeStrictOpenClawPrompt.toString()}\n${bionemoIsSourceOwnedTokenFactoryModel.toString()}\n${bionemoStrictCurrentUserTurn.toString()}\n${bionemoStrictArgsEqual.toString()}\n${bionemoStrictProjectedCallId.toString()}\n${bionemoStrictSha256.toString()}\n${bionemoValidatedClawBioStep.toString()}\n${bionemoValidatedGwasList.toString()}\n${bionemoValidatedGwasContract.toString()}\n${bionemoValidatedGwasDemo.toString()}\n${bionemoGwasDemoFinalText.toString()}\n${bionemoGuidedStarterAction.toString()}\n${bionemoSuperInitialNotebookTool.toString()}\n${bionemoSuperValidatedModelInventory.toString()}\n${bionemoSuperCompletedToolTarget.toString()}\n${bionemoSuperShouldFinalizeWithoutTools.toString()}\n${bionemoSuperBoundedResultSummary.toString()}\n${bionemoSuperDeterministicFinalText.toString()}\n${bionemoSuperLocalCompletionText.toString()}\n${HELPER_ANCHOR}`,
    "helper insertion",
  );
  source = replaceExactlyOnce(source, CLIENT_ANCHOR, CLIENT_REPLACEMENT, "local completion client bypass");
  source = replaceExactlyOnce(source, PAYLOAD_ANCHOR, PAYLOAD_REPLACEMENT, "post-payload tool guard");
  source = replaceExactlyOnce(source, REQUEST_ANCHOR, REQUEST_REPLACEMENT, "local completion request bypass");
  source = replaceExactlyOnce(source, STREAM_OPTIONS_ANCHOR, STREAM_OPTIONS_REPLACEMENT, "final-only stream option");
  source = replaceExactlyOnce(source, STREAM_INIT_ANCHOR, STREAM_INIT_REPLACEMENT, "final-only stream state");
  source = replaceExactlyOnce(source, CONTENT_ANCHOR, CONTENT_REPLACEMENT, "final-only content suppression");
  source = replaceExactlyOnce(source, REFUSAL_ANCHOR, REFUSAL_REPLACEMENT, "final-only refusal suppression");
  source = replaceExactlyOnce(source, REASONING_ANCHOR, REASONING_REPLACEMENT, "final-only reasoning suppression");
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
