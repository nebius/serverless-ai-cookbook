import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import { WORKBENCH_EXAMPLE_SESSIONS } from "../runtime/example-session-catalog.mjs";
import {
  BIONEMO_GUIDED_STARTER_TURNS,
  BIONEMO_SUPER_INITIAL_TURNS,
  BIONEMO_SUPER_NOTEBOOK_TURNS,
  bionemoGuidedStarterAction,
  bionemoIsSourceOwnedTokenFactoryModel,
  bionemoNormalizeStrictOpenClawPrompt,
  bionemoSuperBoundedResultSummary,
  bionemoSuperCompletedToolTarget,
  bionemoSuperDeterministicFinalText,
  bionemoSuperInitialNotebookTool,
  bionemoSuperLocalCompletionText,
  bionemoSuperShouldFinalizeWithoutTools,
  bionemoSuperValidatedModelInventory,
  bionemoValidatedClawBioStep,
  bionemoValidatedGwasContract,
  bionemoValidatedGwasDemo,
  bionemoValidatedGwasList,
  patchOpenClawSuperFollowup,
} from "../runtime/patch-openclaw-super-followup.mjs";

const execFileAsync = promisify(execFile);
const PINNED_IMAGE = "ghcr.io/openclaw/openclaw:2026.7.1-2@sha256:8789721d2e9b24b780a1504b56deb4c6bd5c7dbf96a1dd117e7c45c2ed72c8ac";
const superModel = { provider: "tokenfactory", id: "nvidia/nemotron-3-super-120b-a12b" };
const glmModel = { provider: "tokenfactory", id: "zai-org/GLM-5.2" };
const deepSeekModel = { provider: "tokenfactory", id: "deepseek-ai/DeepSeek-V4-Pro" };
const defaultModels = [superModel, glmModel];

function turn(name, { id = name, isError = false, arguments: args = {}, status = "completed" } = {}) {
  return { messages: [
    { role: "user", content: [{ type: "text", text: "run" }] },
    { role: "assistant", content: [{ type: "toolCall", id: "call-1", name, arguments: name === "tool_call" ? { id, ...args } : args }] },
    { role: "toolResult", toolCallId: "call-1", toolName: name, isError, content: [{ type: "text", text: JSON.stringify({ status, summary: { skill: name } }) }] },
  ] };
}

const tavilyInitial = BIONEMO_SUPER_INITIAL_TURNS.find(({ name }) => name === "tavily_web__tavily_search");
const inventoryInitial = BIONEMO_SUPER_INITIAL_TURNS.find(({ name }) => name === "bionemo_models_list");
const INVENTORY_NOTICE = "Sanitized model inventory only; no scientific compute or job was submitted.";

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
const EPHEMERAL_INVENTORY_CALL_ID = "callbionemosuperabcdefabcdef4abc8abcdef0";

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

function inventoryValue() {
  return {
    readOnly: true,
    computeSubmitted: false,
    modelCount: 3,
    readyCount: 1,
    models: [
      { id: "openfold3", displayName: "OpenFold3", family: "bionemo_nim", readiness: "ready" },
      { id: "scvi_scanvi", displayName: "scVI/scANVI", family: "clawbio_custom", readiness: "not_ready" },
      { id: "unknown_model", displayName: "Unknown Model", family: "clawbio_custom", readiness: "unknown" },
    ],
    notice: INVENTORY_NOTICE,
  };
}

function inventoryTurn() {
  const structured = inventoryValue();
  return { messages: [
    {
      role: "user",
      content: `[Fri 2026-08-14 18:06 UTC] ${inventoryInitial.prompt}`,
    },
    {
      role: "assistant",
      stopReason: "toolUse",
      content: [{
        type: "toolCall",
        id: EPHEMERAL_INVENTORY_CALL_ID,
        name: inventoryInitial.name,
        arguments: {},
        partialArgs: "{}",
      }],
    },
    {
      role: "toolResult",
      toolCallId: EPHEMERAL_INVENTORY_CALL_ID,
      toolName: inventoryInitial.name,
      isError: false,
      content: [{ type: "text", text: JSON.stringify(structured, null, 2) }],
    },
  ] };
}

function rewriteInventory(context, mutate) {
  const changed = structuredClone(context);
  const value = JSON.parse(changed.messages[2].content[0].text);
  mutate(value);
  changed.messages[2].content[0].text = JSON.stringify(value, null, 2);
  return changed;
}

const GWAS_SKILL_SPEC_BASE64 = `
LS0tCm5hbWU6IGd3YXMtbG9va3VwCmRlc2NyaXB0aW9uOiBGZWRlcmF0ZWQgdmFyaWFudCBsb29rdXAgYWNyb3NzIDkgZ2Vu
b21pYyBkYXRhYmFzZXMg4oCUIEdXQVMgQ2F0YWxvZywgT3BlbiBUYXJnZXRzLCBQaGVXZWIgKFVLQiwgRmlubkdlbiwgQkJK
KSwKICBHVEV4LCBlUVRMIENhdGFsb2d1ZSwgYW5kIG1vcmUuCmxpY2Vuc2U6IE1JVAptZXRhZGF0YToKICB2ZXJzaW9uOiAw
LjEuMAogIG9wZW5jbGF3OgogICAgcmVxdWlyZXM6CiAgICAgIGJpbnM6CiAgICAgIC0gcHl0aG9uMwogICAgYWx3YXlzOiBm
YWxzZQogICAgZW1vamk6IPCflI0KICAgIGhvbWVwYWdlOiBodHRwczovL2dpdGh1Yi5jb20vQ2xhd0Jpby9DbGF3QmlvCiAg
ICBvczoKICAgIC0gZGFyd2luCiAgICAtIGxpbnV4CiAgICBpbnN0YWxsOgogICAgLSBraW5kOiBwaXAKICAgICAgcGFja2Fn
ZTogcmVxdWVzdHMKICAgIC0ga2luZDogcGlwCiAgICAgIHBhY2thZ2U6IG1hdHBsb3RsaWIKLS0tCgojIPCflI0gR1dBUyBM
b29rdXAKCllvdSBhcmUgKipHV0FTIExvb2t1cCoqLCBhIHNwZWNpYWxpc2VkIENsYXdCaW8gYWdlbnQgZm9yIGZlZGVyYXRl
ZCB2YXJpYW50IHF1ZXJpZXMuIFlvdXIgcm9sZSBpcyB0byB0YWtlIGEgc2luZ2xlIHJzSUQgYW5kIHF1ZXJ5IDkgZ2Vub21p
YyBkYXRhYmFzZXMgaW4gcGFyYWxsZWwsIHJldHVybmluZyBhIHVuaWZpZWQgcmVwb3J0IG9mIEdXQVMgYXNzb2NpYXRpb25z
LCBQaGVXQVMgcmVzdWx0cywgZVFUTCBkYXRhLCBhbmQgZmluZS1tYXBwaW5nIGNyZWRpYmxlIHNldHMuCgpJbnNwaXJlZCBi
eSBbU2FzaGEgR3VzZXYncyBHV0FTIExvb2t1cF0oaHR0cHM6Ly9zYXNoYWd1c2V2LmdpdGh1Yi5pby9nd2FzX2xvb2t1cC8p
LgoKIyMgQ29yZSBDYXBhYmlsaXRpZXMKCjEuICoqVmFyaWFudCByZXNvbHV0aW9uKio6IFJlc29sdmUgcnNJRCDihpIgY2hy
OnBvcyAoR1JDaDM4ICsgR1JDaDM3KSwgYWxsZWxlcywgY29uc2VxdWVuY2UsIE1BRgoyLiAqKkdXQVMgYXNzb2NpYXRpb24g
bG9va3VwKio6IFF1ZXJ5IEdXQVMgQ2F0YWxvZyArIE9wZW4gVGFyZ2V0cyBmb3IgdHJhaXQgYXNzb2NpYXRpb25zCjMuICoq
UGhlV0FTIHNjYW5uaW5nKio6IFF1ZXJ5IFVLQi1UT1BNZWQsIEZpbm5HZW4sIGFuZCBCaW9iYW5rIEphcGFuIGZvciBwaGVu
b3R5cGUtd2lkZSBhc3NvY2lhdGlvbnMKNC4gKiplUVRMIGxvb2t1cCoqOiBRdWVyeSBHVEV4IGFuZCBFQkkgZVFUTCBDYXRh
bG9ndWUgZm9yIGV4cHJlc3Npb24gYXNzb2NpYXRpb25zCjUuICoqRmluZS1tYXBwaW5nKio6IFJldHJpZXZlIE9wZW4gVGFy
Z2V0cyBjcmVkaWJsZSBzZXQgbWVtYmVyc2hpcAo2LiAqKlVuaWZpZWQgcmVwb3J0aW5nKio6IE1lcmdlLCBkZWR1cGxpY2F0
ZSwgYW5kIHJhbmsgcmVzdWx0cyBhY3Jvc3MgYWxsIHNvdXJjZXMKCiMjIElucHV0IEZvcm1hdHMKCi0gKipyc0lEKio6IEFu
eSB2YWxpZCBkYlNOUCByc0lEIChlLmcuLCByczM3OTgyMjAsIHJzNDI5MzU4LCByczc5MDMxNDYpCgojIyBEYXRhYmFzZXMg
UXVlcmllZAoKfCBEYXRhYmFzZSB8IEVuZHBvaW50IHwgQ29vcmRpbmF0ZXMgfAp8LS0tLS0tLS0tLXwtLS0tLS0tLS0tfC0t
LS0tLS0tLS0tLS18CnwgRW5zZW1ibCB8IFJFU1QgL3ZhcmlhdGlvbiArIC92ZXAgfCBHUkNoMzggfAp8IEdXQVMgQ2F0YWxv
ZyB8IEVCSSBSRVNUIEFQSSB8IEdSQ2gzOCB8CnwgT3BlbiBUYXJnZXRzIHwgR3JhcGhRTCB2NCB8IEdSQ2gzOCB8CnwgVUtC
LVRPUE1lZCBQaGVXZWIgfCBQaGVXZWIgQVBJIHwgR1JDaDM4IHwKfCBGaW5uR2VuIHIxMiB8IFBoZVdlYiBBUEkgfCBHUkNo
MzggfAp8IEJpb2JhbmsgSmFwYW4gUGhlV2ViIHwgUGhlV2ViIEFQSSB8ICoqR1JDaDM3KiogfAp8IEdURXggdjggfCBQb3J0
YWwgQVBJIHYyIHwgR1JDaDM4IHwKfCBFQkkgZVFUTCBDYXRhbG9ndWUgfCBSRVNUIEFQSSB2MyB8IEdSQ2gzOCB8CnwgTG9j
dXNab29tIFBvcnRhbERldiB8IE9tbmlzZWFyY2ggQVBJIHwgQm90aCB8CgojIyBXb3JrZmxvdwoKV2hlbiB0aGUgdXNlciBh
c2tzIHRvIGxvb2sgdXAgYSB2YXJpYW50OgoKMS4gKipSZXNvbHZlKio6IFF1ZXJ5IEVuc2VtYmwgZm9yIHZhcmlhbnQgY29v
cmRpbmF0ZXMsIGFsbGVsZXMsIGNvbnNlcXVlbmNlCjIuICoqRGlzcGF0Y2gqKjogUXVlcnkgYWxsIDggcmVtYWluaW5nIEFQ
SXMgaW4gcGFyYWxsZWwgKFRocmVhZFBvb2xFeGVjdXRvcikKMy4gKipOb3JtYWxpc2UqKjogTWVyZ2UgcmVzdWx0cywgZGVk
dXBsaWNhdGUsIHNvcnQgYnkgcC12YWx1ZSwgZmxhZyBHV1MgaGl0cwo0LiAqKlJlcG9ydCoqOiBHZW5lcmF0ZSBtYXJrZG93
biByZXBvcnQgKyBDU1YgdGFibGVzICsgZmlndXJlcwoKIyMgRXhhbXBsZSBRdWVyaWVzCgotICJMb29rIHVwIHJzMzc5ODIy
MCIKLSAiV2hhdCBhcmUgdGhlIEdXQVMgYXNzb2NpYXRpb25zIGZvciByczQyOTM1OD8iCi0gIlNlYXJjaCBhbGwgZGF0YWJh
c2VzIGZvciB2YXJpYW50IHJzNzkwMzE0NiIKLSAiR1dBUyBsb29rdXAgZm9yIHRoZSBMUEEgbWlzc2Vuc2UgdmFyaWFudCIK
CiMjIE91dHB1dCBTdHJ1Y3R1cmUKCmBgYApvdXRwdXRfZGlyZWN0b3J5LwrilJzilIDilIAgcmVwb3J0Lm1kICAgICAgICAg
ICAgICAgICAgICAjIEZ1bGwgbWFya2Rvd24gcmVwb3J0CuKUnOKUgOKUgCByYXdfcmVzdWx0cy5qc29uICAgICAgICAgICAg
ICMgUmF3IEFQSSByZXNwb25zZXMgKGRlYnVnKQrilJzilIDilIAgdGFibGVzLwrilIIgICDilJzilIDilIAgZ3dhc19hc3Nv
Y2lhdGlvbnMuY3N2CuKUgiAgIOKUnOKUgOKUgCBwaGV3YXNfdWtiLmNzdgrilIIgICDilJzilIDilIAgcGhld2FzX2Zpbm5n
ZW4uY3N2CuKUgiAgIOKUnOKUgOKUgCBwaGV3YXNfYmJqLmNzdgrilIIgICDilJzilIDilIAgZXF0bF9hc3NvY2lhdGlvbnMu
Y3N2CuKUgiAgIOKUlOKUgOKUgCBjcmVkaWJsZV9zZXRzLmNzdgrilJzilIDilIAgZmlndXJlcy8K4pSCICAg4pSc4pSA4pSA
IGd3YXNfdHJhaXRzX2RvdHBsb3QucG5nCuKUgiAgIOKUlOKUgOKUgCBhbGxlbGVfZnJlcV9wb3B1bGF0aW9ucy5wbmcK4pSU
4pSA4pSAIHJlcHJvZHVjaWJpbGl0eS8KICAgIOKUnOKUgOKUgCBjb21tYW5kcy5zaAogICAg4pSU4pSA4pSAIGFwaV92ZXJz
aW9ucy5qc29uCmBgYAoKIyMgRGVwZW5kZW5jaWVzCgoqKlJlcXVpcmVkKio6Ci0gYHJlcXVlc3RzYCA+PSAyLjI4IChIVFRQ
IGNsaWVudCkKLSBQeXRob24gMy4xMCsKCioqT3B0aW9uYWwqKjoKLSBgbWF0cGxvdGxpYmAgPj0gMy41IChmaWd1cmVzOyBz
a2lwcGVkIGdyYWNlZnVsbHkgaWYgYWJzZW50KQoKIyMgU2FmZXR5CgotIEFsbCBwcm9jZXNzaW5nIGlzIGxvY2FsIOKAlCBn
ZW5ldGljIGRhdGEgbmV2ZXIgbGVhdmVzIHRoaXMgbWFjaGluZQotIEFQSSBxdWVyaWVzIHVzZSBvbmx5IHB1YmxpYyByc0lE
cyAobm8gcGF0aWVudCBkYXRhIHRyYW5zbWl0dGVkKQotIDI0LWhvdXIgbG9jYWwgZmlsZSBjYWNoZSB0byByZWR1Y2UgQVBJ
IGxvYWQKLSBHcmFjZWZ1bCBkZWdyYWRhdGlvbjogZmFpbGVkIEFQSXMgcHJvZHVjZSB3YXJuaW5ncywgbm90IGNyYXNoZXMK
LSBSYXRlIGxpbWl0aW5nIHBlciBBUEkgdG8gcmVzcGVjdCBzZXJ2ZXIgcG9saWNpZXMKCiMjIEludGVncmF0aW9uIHdpdGgg
QmlvIE9yY2hlc3RyYXRvcgoKVGhpcyBza2lsbCBpcyBpbnZva2VkIGJ5IHRoZSBCaW8gT3JjaGVzdHJhdG9yIHdoZW46Ci0g
VXNlciBtZW50aW9ucyAiR1dBUyBsb29rdXAiLCAidmFyaWFudCBsb29rdXAiLCAicnNJRCBzZWFyY2giCi0gVXNlciBwcm92
aWRlcyBhbiByc0lEIGFuZCBhc2tzIGFib3V0IGFzc29jaWF0aW9ucywgUGhlV0FTLCBvciBlUVRMcwotIFF1ZXJ5IGNvbnRh
aW5zIGtleXdvcmRzOiAiZ3dhcyBsb29rdXAiLCAidmFyaWFudCBzZWFyY2giLCAicnMgbG9va3VwIgoKSXQgY2FuIGJlIGNo
YWluZWQgd2l0aDoKLSBgY2xpbnBneGA6IExvb2sgdXAgcGhhcm1hY29nZW5vbWljIGRhdGEgZm9yIGdlbmVzIG5lYXIgdGhl
IHZhcmlhbnQKLSBgZ3dhcy1wcnNgOiBJZiB0aGUgdmFyaWFudCBpcyBwYXJ0IG9mIGEgcG9seWdlbmljIHNjb3JlLCBjYWxj
dWxhdGUgUFJTCi0gYGxpdC1zeW50aGVzaXplcmA6IEZpbmQgcHVibGljYXRpb25zIGFib3V0IHRoZSB2YXJpYW50J3MgYXNz
b2NpYXRlZCB0cmFpdHMK
`.replace(/\s/gu, "");
const GWAS_SKILL_SPEC = Buffer.from(GWAS_SKILL_SPEC_BASE64, "base64").toString("utf8");
const GWAS_NAMES = [
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
];

function gwasListValue() {
  return { result: GWAS_NAMES.map((name) => ({
    cli_alias: name === "gwas-lookup" ? "gwas" : null,
    demo_command: name === "gwas-lookup" ? "clawbio run gwas --demo" : "",
    demo_runnable_in_image: name === "gwas-lookup",
    description: `${name} packaged research workflow`,
    has_demo: name === "gwas-lookup",
    maturity_tier: name === "gwas-lookup" ? "ci-validated" : "documented",
    name,
    runnable: name === "gwas-lookup",
    status: name === "gwas-lookup" ? "mvp" : "documented",
    tags: ["genomics"],
  })) };
}

function gwasContractValue() {
  return {
    chaining_partners: ["gwas-prs"],
    cli_alias: "gwas",
    data_license: "public sources",
    demo_command: "clawbio run gwas --demo",
    demo_runnable_in_image: true,
    dependencies: ["requests"],
    description: "Federated public-variant lookup",
    has_demo: true,
    has_script: true,
    has_tests: true,
    license: "MIT",
    maturity_evidence: "CI validated",
    maturity_tier: "ci-validated",
    model_license: null,
    name: "gwas-lookup",
    spec: GWAS_SKILL_SPEC,
    status: "mvp",
    tags: ["genomics", "gwas"],
    trigger_keywords: ["GWAS lookup", "rsID"],
    version: "0.1.0",
  };
}

function gwasDemoValue(root = "/workspace/agent/artifacts/clawbio/output/gwas_20260818_123456") {
  return {
    demo: true,
    exit_code: 0,
    skill: "gwas-lookup",
    stderr: "",
    stdout: `GWAS Lookup: rs3798220
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

  Report: ${root}/report.md
  Full output: ${root}/

  ClawBio is a research and educational tool. It is not a medical device and does not provide clinical diagnoses. Consult a healthcare professional before making any medical decisions.
`,
    success: true,
  };
}

const GUIDED_CALL_IDS = [
  "call_bionemo_super_01234567-89ab-4cde-8f01-23456789abcd",
  "call_bionemo_super_abcdef01-2345-4678-9abc-def012345678",
];

function clawBioPair(step, structuredContent, index) {
  const id = GUIDED_CALL_IDS[index];
  return [
    {
      role: "assistant",
      stopReason: "toolUse",
      content: [{
        type: "toolCall",
        id,
        name: step.name,
        arguments: { ...step.params },
        partialArgs: JSON.stringify(step.params),
      }],
    },
    {
      role: "toolResult",
      toolCallId: id,
      toolName: step.name,
      isError: false,
      content: [{ type: "text", text: `structuredContent:\n${JSON.stringify(structuredContent, null, 2)}` }],
      details: {
        mcpServer: "clawbio",
        mcpTool: step.name.slice("clawbio__".length),
        structuredContent,
      },
    },
  ];
}

function guidedContext(entry, values = []) {
  return {
    messages: [
      { role: "user", content: `[Tue 2026-08-18 12:34 UTC] ${entry.prompt}` },
      ...values.flatMap((value, index) => clawBioPair(entry.steps[index], value, index)),
    ],
  };
}

test("the two default Token Factory models finalize after successful atomic wrappers", () => {
  for (const name of [
    "bionemo_research_drug_demo",
    "bionemo_compare_protein_structures",
    "bionemo_optimize_ligand_complex",
    "bionemo_batch_fold_demo",
    "bionemo_molmim",
    "bionemo_openfold2",
    "bionemo_openfold3",
  ]) {
    for (const model of [...defaultModels, deepSeekModel]) {
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
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(glmModel, errored), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, errored), false);
});

test("host-local completion is limited to exact completed default-model tool boundaries", () => {
  const completed = turn("bionemo_molmim");
  for (const model of defaultModels) {
    assert.match(bionemoSuperLocalCompletionText(model, completed), /MolMIM optimization returned a terminal result/u);
  }
  const structured = structuredClone(completed);
  structured.messages.at(-1).content = [{ type: "text", text: "not-json" }];
  structured.messages.at(-1).structuredContent = { status: "completed", summary: { skill: "MolMIM" } };
  for (const model of defaultModels) {
    assert.match(bionemoSuperLocalCompletionText(model, structured), /MolMIM optimization returned a terminal result/u);
  }
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
  for (const model of defaultModels) {
    assert.equal(bionemoSuperCompletedToolTarget(model, completed), tavilyInitial.name);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(model, completed), true);
  }
  const final = bionemoSuperLocalCompletionText(superModel, completed);
  assert.equal(bionemoSuperLocalCompletionText(glmModel, completed), final);
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
  assert.equal(bionemoSuperCompletedToolTarget(glmModel, completed), tavilyInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, completed), true);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(glmModel, completed), true);
  assert.match(bionemoSuperLocalCompletionText(superModel, completed), /RCSB PDB/u);
  assert.equal(bionemoSuperLocalCompletionText(glmModel, completed), bionemoSuperLocalCompletionText(superModel, completed));

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

test("host-local model inventory completion accepts only the exact sanitized synthetic boundary", () => {
  const completed = inventoryTurn();
  assert.equal(EPHEMERAL_INVENTORY_CALL_ID.length, 40);
  assert.match(EPHEMERAL_INVENTORY_CALL_ID, /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u);
  assert.deepEqual(bionemoSuperValidatedModelInventory(superModel, completed), inventoryValue());
  assert.deepEqual(bionemoSuperValidatedModelInventory(glmModel, completed), inventoryValue());
  assert.equal(bionemoSuperCompletedToolTarget(superModel, completed), inventoryInitial.name);
  assert.equal(bionemoSuperCompletedToolTarget(glmModel, completed), inventoryInitial.name);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, completed), true);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(glmModel, completed), true);
  const final = bionemoSuperLocalCompletionText(superModel, completed);
  assert.equal(bionemoSuperLocalCompletionText(glmModel, completed), final);
  assert.match(final, /3 models; 1 ready/u);
  for (const { id, displayName, family, readiness } of inventoryValue().models) {
    assert.equal(final.includes(`id: ${id}; displayName: ${displayName}; family: ${family}; readiness: ${readiness}`), true);
  }
  assert.match(final, /submitted no scientific compute or model job/u);
  assert.match(final, /Every listed service is callable through its corresponding adapted bionemo_models__\* compute operation/u);
  assert.match(final, /scvi_scanvi has separate scvi_fit_transform and scanvi_fit_transform operations/u);
  assert.match(final, /Readiness does not establish scientific validity/u);

  const rejected = [];
  const malformed = structuredClone(completed);
  malformed.messages[2].content[0].text = "{";
  rejected.push(["malformed JSON", malformed]);
  const compact = structuredClone(completed);
  compact.messages[2].content[0].text = JSON.stringify(inventoryValue());
  rejected.push(["non-pretty JSON", compact]);
  const trailing = structuredClone(completed);
  trailing.messages[2].content[0].text += "\n";
  rejected.push(["trailing JSON data", trailing]);
  const duplicateJsonKey = structuredClone(completed);
  duplicateJsonKey.messages[2].content[0].text = duplicateJsonKey.messages[2].content[0].text.replace(
    "{\n",
    "{\n  \"readOnly\": true,\n",
  );
  rejected.push(["duplicate JSON key", duplicateJsonKey]);
  rejected.push(["extra top key", rewriteInventory(completed, (value) => { value.status = "completed"; })]);
  rejected.push(["missing top key", rewriteInventory(completed, (value) => { delete value.notice; })]);
  rejected.push(["wrong read-only flag", rewriteInventory(completed, (value) => { value.readOnly = false; })]);
  rejected.push(["wrong compute flag", rewriteInventory(completed, (value) => { value.computeSubmitted = true; })]);
  rejected.push(["wrong notice", rewriteInventory(completed, (value) => { value.notice += " "; })]);
  rejected.push(["extra model key", rewriteInventory(completed, (value) => { value.models[0].endpoint = "private"; })]);
  rejected.push(["missing model key", rewriteInventory(completed, (value) => { delete value.models[0].displayName; })]);
  rejected.push(["duplicate model id", rewriteInventory(completed, (value) => { value.models[1].id = value.models[0].id; })]);
  rejected.push(["model count mismatch", rewriteInventory(completed, (value) => { value.modelCount = 2; })]);
  rejected.push(["model count lower bound", rewriteInventory(completed, (value) => { value.modelCount = 0; value.models = []; value.readyCount = 0; })]);
  rejected.push(["model count upper bound", rewriteInventory(completed, (value) => {
    value.models = Array.from({ length: 65 }, (_, index) => ({
      id: `model_${index}`,
      displayName: `Model ${index}`,
      family: "bionemo_nim",
      readiness: "unknown",
    }));
    value.modelCount = 65;
    value.readyCount = 0;
  })]);
  rejected.push(["ready count mismatch", rewriteInventory(completed, (value) => { value.readyCount = 2; })]);
  rejected.push(["non-integer ready count", rewriteInventory(completed, (value) => { value.readyCount = 1.5; })]);
  rejected.push(["invalid readiness status", rewriteInventory(completed, (value) => { value.models[0].readiness = "starting"; value.readyCount = 0; })]);
  rejected.push(["unsafe model id", rewriteInventory(completed, (value) => { value.models[0].id = "OpenFold3"; })]);
  rejected.push(["unsafe family", rewriteInventory(completed, (value) => { value.models[0].family = "bionemo-nim"; })]);
  rejected.push(["unsafe display name control", rewriteInventory(completed, (value) => { value.models[0].displayName = "OpenFold3\nInjected"; })]);
  rejected.push(["unsafe display name URL", rewriteInventory(completed, (value) => { value.models[0].displayName = "https://private.example"; })]);
  rejected.push(["unnormalized display name", rewriteInventory(completed, (value) => { value.models[0].displayName = "OpenFold3  Model"; })]);
  const oversized = rewriteInventory(completed, (value) => { value.models[0].displayName = "A".repeat(65_536); });
  assert.ok(oversized.messages[2].content[0].text.length > 65_536);
  rejected.push(["oversized text", oversized]);
  const extraResultBlock = structuredClone(completed);
  extraResultBlock.messages[2].content.push({ type: "text", text: "extra" });
  rejected.push(["extra result block", extraResultBlock]);
  const extraContentField = structuredClone(completed);
  extraContentField.messages[2].content[0].metadata = {};
  rejected.push(["extra content field", extraContentField]);
  const wrongPrompt = structuredClone(completed);
  wrongPrompt.messages[0].content += " ";
  rejected.push(["wrong prompt", wrongPrompt]);
  const userBlocks = structuredClone(completed);
  userBlocks.messages[0].content = [{ type: "text", text: userBlocks.messages[0].content }];
  rejected.push(["non-string source prompt", userBlocks]);
  const badArgs = structuredClone(completed);
  badArgs.messages[1].content[0].arguments = { retry: true };
  rejected.push(["nonempty arguments", badArgs]);
  const stringArgs = structuredClone(completed);
  stringArgs.messages[1].content[0].arguments = "{}";
  rejected.push(["string arguments", stringArgs]);
  const alteredPartialArgs = structuredClone(completed);
  alteredPartialArgs.messages[1].content[0].partialArgs = "{ }";
  rejected.push(["altered partial args", alteredPartialArgs]);
  const mismatchedId = structuredClone(completed);
  mismatchedId.messages[2].toolCallId = "callbionemosuper0123456789ab4cde8f012345";
  rejected.push(["mismatched IDs", mismatchedId]);
  for (const [label, invalidId] of [
    ["empty ID", ""],
    ["provider-shaped ID", "call_provider_generated_inventory_boundary_123456"],
    ["arbitrary projected ID", "0123456789abcdef0123456789abcdef01234567"],
    ["raw synthetic ID", "call_bionemo_super_abcdefab-cdef-4abc-8abc-def0"],
    ["wrong projected version", EPHEMERAL_INVENTORY_CALL_ID.replace("4abc8", "5abc8")],
    ["wrong projected variant", EPHEMERAL_INVENTORY_CALL_ID.replace("4abc8", "4abc7")],
  ]) {
    const invalid = structuredClone(completed);
    invalid.messages[1].content[0].id = invalidId;
    invalid.messages[2].toolCallId = invalidId;
    rejected.push([label, invalid]);
  }
  const missingSuccess = structuredClone(completed);
  delete missingSuccess.messages[2].isError;
  rejected.push(["missing explicit success", missingSuccess]);
  const errored = structuredClone(completed);
  errored.messages[2].isError = true;
  rejected.push(["errored result", errored]);
  for (const [label, field, value] of [
    ["own error", "error", null],
    ["own details", "details", undefined],
    ["own top structured content", "structuredContent", undefined],
  ]) {
    const ambiguous = structuredClone(completed);
    ambiguous.messages[2][field] = value;
    rejected.push([label, ambiguous]);
  }
  const extraAssistantBlock = structuredClone(completed);
  extraAssistantBlock.messages[1].content.push({ type: "text", text: "extra" });
  rejected.push(["extra assistant block", extraAssistantBlock]);
  const wrongStopReason = structuredClone(completed);
  wrongStopReason.messages[1].stopReason = "stop";
  rejected.push(["wrong stop reason", wrongStopReason]);
  const wrongCallType = structuredClone(completed);
  wrongCallType.messages[1].content[0].type = "toolUse";
  rejected.push(["wrong call type", wrongCallType]);
  const wrongTool = structuredClone(completed);
  wrongTool.messages[1].content[0].name = "tool_call";
  wrongTool.messages[2].toolName = "tool_call";
  rejected.push(["non-direct tool", wrongTool]);
  const earlierBoundary = structuredClone(completed);
  earlierBoundary.messages.splice(1, 0, { role: "assistant", content: [{ type: "text", text: "earlier" }] });
  rejected.push(["non-sole current turn", earlierBoundary]);

  for (const [label, boundary] of rejected) {
    assert.equal(bionemoSuperValidatedModelInventory(superModel, boundary), undefined, label);
    assert.equal(bionemoSuperCompletedToolTarget(superModel, boundary), undefined, label);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, boundary), false, label);
    assert.equal(bionemoSuperLocalCompletionText(superModel, boundary), undefined, label);
  }
  assert.equal(bionemoSuperValidatedModelInventory(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperCompletedToolTarget(deepSeekModel, completed), undefined);
  assert.equal(bionemoSuperValidatedModelInventory({ ...superModel, provider: "nvidia" }, completed), undefined);
});

test("source-owned routing is restricted to the two configured Token Factory defaults", () => {
  for (const model of defaultModels) assert.equal(bionemoIsSourceOwnedTokenFactoryModel(model), true);
  assert.equal(bionemoIsSourceOwnedTokenFactoryModel({ provider: "TOKENFACTORY", id: "ZAI-ORG/GLM-5.2" }), true);
  assert.equal(bionemoIsSourceOwnedTokenFactoryModel(deepSeekModel), false);
  assert.equal(bionemoIsSourceOwnedTokenFactoryModel({ ...superModel, provider: "nvidia" }), false);
  assert.equal(bionemoIsSourceOwnedTokenFactoryModel({ ...glmModel, id: "zai-org/glm-5.1" }), false);
});

test("Examples 5 and 6 return reviewed orientation text for both default models without tools", () => {
  for (const entry of [BIONEMO_GUIDED_STARTER_TURNS.tour, BIONEMO_GUIDED_STARTER_TURNS.skills]) {
    const context = guidedContext(entry);
    for (const model of defaultModels) {
      const action = bionemoGuidedStarterAction(model, context);
      assert.deepEqual(action, { type: "final", text: entry.finalText });
      assert.equal(bionemoSuperInitialNotebookTool(model, context), undefined);
      assert.equal(bionemoSuperLocalCompletionText(model, context), entry.finalText);
      assert.match(entry.finalText, /research|nonclinical/iu);
    }
    assert.equal(bionemoGuidedStarterAction(deepSeekModel, context), undefined);
    const continued = structuredClone(context);
    continued.messages.push({ role: "assistant", content: [{ type: "text", text: "untrusted continuation" }] });
    for (const model of defaultModels) {
      const action = bionemoGuidedStarterAction(model, continued);
      assert.equal(action.type, "final");
      assert.match(action.text, /could not validate the packaged example result/iu);
      assert.equal(bionemoSuperInitialNotebookTool(model, continued), undefined);
      assert.equal(bionemoSuperLocalCompletionText(model, continued), action.text);
    }
  }
});

test("Examples 7 and 8 follow exact finite-state ClawBio tool paths on both default models", () => {
  const catalog = BIONEMO_GUIDED_STARTER_TURNS.catalog;
  const demo = BIONEMO_GUIDED_STARTER_TURNS.demo;
  const listValue = gwasListValue();
  const contractValue = gwasContractValue();
  const demoValue = gwasDemoValue();
  assert.equal(bionemoValidatedGwasList(listValue), true);
  assert.equal(bionemoValidatedGwasContract(contractValue), true);
  assert.deepEqual(bionemoValidatedGwasDemo(demoValue), {
    root: "/workspace/agent/artifacts/clawbio/output/gwas_20260818_123456",
    reportPath: "/workspace/agent/artifacts/clawbio/output/gwas_20260818_123456/report.md",
  });

  const catalogInitial = guidedContext(catalog);
  const catalogListed = guidedContext(catalog, [listValue]);
  const catalogComplete = guidedContext(catalog, [listValue, contractValue]);
  const demoInitial = guidedContext(demo);
  const demoDescribed = guidedContext(demo, [contractValue]);
  const demoComplete = guidedContext(demo, [contractValue, demoValue]);
  assert.deepEqual(
    bionemoValidatedClawBioStep(catalogListed.messages.slice(1), catalog.steps[0]),
    listValue,
  );

  for (const model of defaultModels) {
    for (const [context, expected] of [
      [catalogInitial, catalog.steps[0]],
      [catalogListed, catalog.steps[1]],
      [demoInitial, demo.steps[0]],
      [demoDescribed, demo.steps[1]],
    ]) {
      assert.deepEqual(bionemoGuidedStarterAction(model, context), { type: "tool", ...expected });
      assert.deepEqual(bionemoSuperInitialNotebookTool(model, context), { name: expected.name, params: { ...expected.params } });
      assert.equal(bionemoSuperLocalCompletionText(model, context), undefined);
    }

    const catalogFinal = bionemoGuidedStarterAction(model, catalogComplete);
    assert.deepEqual(catalogFinal, { type: "final", text: catalog.finalText });
    assert.equal(bionemoSuperLocalCompletionText(model, catalogComplete), catalog.finalText);
    assert.match(catalogFinal.text, /GWAS Lookup.*gwas-lookup/isu);
    assert.match(catalogFinal.text, /report\.md/iu);
    assert.match(catalogFinal.text, /lookup was not run/iu);

    const demoFinal = bionemoGuidedStarterAction(model, demoComplete);
    assert.equal(demoFinal.type, "final");
    assert.equal(bionemoSuperLocalCompletionText(model, demoComplete), demoFinal.text);
    assert.match(demoFinal.text, /rs3798220/iu);
    assert.match(demoFinal.text, /11 merged GWAS associations/iu);
    assert.match(demoFinal.text, /gwas_20260818_123456\/report\.md/iu);
    assert.match(demoFinal.text, /research-only/iu);
    assert.match(demoFinal.text, /not a diagnosis/iu);
  }
});

test("Examples 7 and 8 fail closed on malformed or untrusted ClawBio results", () => {
  const catalog = BIONEMO_GUIDED_STARTER_TURNS.catalog;
  const demo = BIONEMO_GUIDED_STARTER_TURNS.demo;
  const malformed = [];

  const mismatchedId = guidedContext(catalog, [gwasListValue()]);
  mismatchedId.messages[2].toolCallId = GUIDED_CALL_IDS[1];
  malformed.push(["mismatched call ID", mismatchedId]);

  const wrongArguments = guidedContext(catalog, [gwasListValue()]);
  wrongArguments.messages[1].content[0].arguments = { query: "GWAS" };
  malformed.push(["wrong arguments", wrongArguments]);

  const errored = guidedContext(catalog, [gwasListValue()]);
  errored.messages[2].isError = true;
  malformed.push(["errored result", errored]);

  const wrongServer = guidedContext(catalog, [gwasListValue()]);
  wrongServer.messages[2].details.mcpServer = "other";
  malformed.push(["wrong MCP provenance", wrongServer]);

  const noncanonical = guidedContext(catalog, [gwasListValue()]);
  noncanonical.messages[2].content[0].text += "\n";
  malformed.push(["noncanonical projection", noncanonical]);

  const alteredListValue = gwasListValue();
  alteredListValue.result[4].runnable = false;
  malformed.push(["non-runnable GWAS entry", guidedContext(catalog, [alteredListValue])]);

  const alteredContractValue = gwasContractValue();
  alteredContractValue.spec += "\nUnreviewed mutation";
  malformed.push(["contract hash mismatch", guidedContext(demo, [alteredContractValue])]);

  malformed.push(["unsafe demo output root", guidedContext(demo, [gwasContractValue(), gwasDemoValue("/tmp/gwas_20260818_123456")])]);
  const failedDemoValue = gwasDemoValue();
  failedDemoValue.success = false;
  malformed.push(["reported demo failure", guidedContext(demo, [gwasContractValue(), failedDemoValue])]);

  for (const [label, context] of malformed) {
    for (const model of defaultModels) {
      const action = bionemoGuidedStarterAction(model, context);
      assert.equal(action?.type, "final", label);
      assert.match(action.text, /could not validate the packaged example result/iu, label);
      assert.equal(bionemoSuperInitialNotebookTool(model, context), undefined, label);
      assert.equal(bionemoSuperLocalCompletionText(model, context), action.text, label);
    }
  }
});

test("default-model initial calls are source-owned only for exact reviewed prompts", () => {
  assert.equal(BIONEMO_SUPER_NOTEBOOK_TURNS.length, 4);
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS.length, 7);
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
  assert.equal(BIONEMO_SUPER_INITIAL_TURNS[6], inventoryInitial);
  assert.equal(inventoryInitial.prompt, WORKBENCH_EXAMPLE_SESSIONS.find(({ slug }) => slug === "bionemo-model-inventory")?.prompt);
  assert.deepEqual(inventoryInitial.params, {});
  for (const expected of BIONEMO_SUPER_INITIAL_TURNS) {
    for (const model of defaultModels) {
      const actual = bionemoSuperInitialNotebookTool(model, {
        messages: [{ role: "user", content: [{ type: "text", text: expected.prompt }] }],
      });
      assert.deepEqual(actual, { name: expected.name, params: { ...expected.params } });
      assert.deepEqual(
        bionemoSuperInitialNotebookTool(model, { prompt: expected.prompt, messages: [] }),
        { name: expected.name, params: { ...expected.params } },
      );
      assert.deepEqual(
        bionemoSuperInitialNotebookTool(model, {
          messages: [{ role: "user", content: `[Fri 2026-08-14 18:06 UTC] ${expected.prompt}` }],
        }),
        { name: expected.name, params: { ...expected.params } },
      );
    }
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
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    messages: [
      { role: "user", content: first.prompt },
      { role: "assistant", content: [{ type: "text", text: "untrusted continuation" }] },
    ],
  }), undefined);
  assert.equal(bionemoSuperInitialNotebookTool(superModel, {
    messages: [{
      role: "user",
      content: [
        { type: "text", text: first.prompt },
        { type: "image", image_url: "data:image/png;base64,AA==" },
      ],
    }],
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

test("default-model fallback includes only bounded summaries and exact safe artifact paths", () => {
  const context = turn("bionemo_compare_protein_structures");
  context.messages.at(-1).content = [{ type: "text", text: JSON.stringify({
    summary: { predictions: { openfold2: { confidence: { ptm_score: 0.81 } }, openfold3: { confidence: { ptm_score: 0.87 } } }, note: "safe" },
    artifacts: [{ viewerMarkdown: "access=must-not-appear" }],
  }) }];
  for (const model of defaultModels) {
    const summary = bionemoSuperBoundedResultSummary(model, context);
    assert.match(summary, /ptm_score/u);
    assert.doesNotMatch(summary, /must-not-appear/u);
    assert.match(bionemoSuperDeterministicFinalText(model, context), /Returned workflow summary/u);
  }

  const runId = "01234567-89ab-4cde-8f01-23456789abcd";
  const safe = turn("bionemo_molmim");
  safe.messages.at(-1).content = [{ type: "text", text: JSON.stringify({
    status: "completed",
    runId,
    summary: { startingMolecule: "gefitinib", optimizationObjective: "QED", minimumSimilarity: 0.7 },
    artifacts: [
      {
        name: "molmim_candidates.json",
        downloadPath: `/workspace/agent/artifacts/${runId}/molmim_candidates.json`,
        viewerMarkdown: "[secret](?access=must-not-appear)",
        bytes: 1234,
      },
      {
        name: "molmim_candidates.csv",
        downloadPath: `/workspace/agent/artifacts/${runId}/molmim_candidates.csv`,
        viewerUrl: "https://private.invalid/?access=must-not-appear",
      },
    ],
  }) }];
  for (const model of defaultModels) {
    const summary = bionemoSuperBoundedResultSummary(model, safe);
    assert.match(summary, /gefitinib/u);
    assert.match(summary, /QED/u);
    assert.match(summary, /molmim_candidates\.json/u);
    assert.match(summary, new RegExp(`/workspace/agent/artifacts/${runId}/molmim_candidates\\.csv`, "u"));
    assert.doesNotMatch(summary, /viewerMarkdown|viewerUrl|must-not-appear/u);
    assert.match(bionemoSuperLocalCompletionText(model, safe), /minimumSimilarity/iu);
  }

  for (const [label, mutate] of [
    ["unsafe name", (value) => { value.artifacts[0].name = "../secret"; }],
    ["mismatched path", (value) => { value.artifacts[0].downloadPath = "/tmp/molmim_candidates.json"; }],
    ["wrong run ID", (value) => { value.runId = "not-a-run-id"; }],
  ]) {
    const rejected = structuredClone(safe);
    const value = JSON.parse(rejected.messages.at(-1).content[0].text);
    mutate(value);
    rejected.messages.at(-1).content[0].text = JSON.stringify(value);
    const summary = bionemoSuperBoundedResultSummary(superModel, rejected);
    assert.doesNotMatch(summary, /\/workspace\/agent\/artifacts\//u, label);
    assert.doesNotMatch(summary, /molmim_candidates\.(?:json|csv)/u, label);
  }
});

test("post-success guard leaves initial, unrelated tools/models, errors, and mismatched chains untouched", () => {
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, { messages: [{ role: "user", content: [] }] }), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...superModel, id: "meta/llama-3.3-70b-instruct" }, turn("bionemo_batch_fold_demo")), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools({ ...deepSeekModel, provider: "nvidia" }, turn("bionemo_batch_fold_demo")), false);
  for (const name of ["openfold2_predict", "job_status", "clawbio__run_skill", "clawbio_run_skill", "tavily_search", "web_search"]) {
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, turn(name)), false);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(glmModel, turn(name)), false);
    assert.equal(bionemoSuperShouldFinalizeWithoutTools(deepSeekModel, turn(name)), false);
  }
  const mismatch = structuredClone(turn("bionemo_batch_fold_demo"));
  mismatch.messages.at(-1).toolCallId = "other";
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(superModel, mismatch), false);
  assert.equal(bionemoSuperShouldFinalizeWithoutTools(glmModel, mismatch), false);
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
  assert.match(source, /openclaw\.bionemo\.super-followup\.v16/u);
  const callback = source.indexOf("if (nextParams !== void 0) params = nextParams;");
  const codeMode = source.indexOf("if (options?.openclawCodeModeToolSurface === true)", callback);
  const guard = source.indexOf("if (bionemoSuperFinalText)");
  const request = source.indexOf("client.chat.completions.create(params");
  assert.ok(callback >= 0 && callback < codeMode && codeMode < guard && guard < request);
  assert.match(source, /delete params\.tools;\s*params\.tool_choice = "none";/su);
  assert.match(source, /const bionemoSuperLocalFinalText = bionemoSuperLocalCompletionText\(model, context\)/u);
  assert.match(source, /const client = bionemoSuperLocalFinalText \? undefined : createOpenAICompletionsClient/u);
  assert.match(source, /function bionemoNormalizeStrictOpenClawPrompt\(/u);
  assert.match(source, /function bionemoGuidedStarterAction\(/u);
  assert.match(source, /function bionemoValidatedGwasDemo\(/u);
  assert.match(source, /bionemoSuperInitialTool && Array\.isArray\(params\.tools\)\s*&& params\.tools\.some\(\(tool\) => tool\?\.function\?\.name === bionemoSuperInitialTool\.name\)/su);
  assert.doesNotMatch(source, /bionemoSuperContextTavilyTool|mcp:bundle-mcp:tavily_web__tavily_search/u);
  assert.equal(source.includes(["BIONEMO", "TEMP", "TAVILY", "POST", "RESULT", "TRANSPORT", "DIAGNOSTIC"].join("_")), false);
  assert.doesNotMatch(source, /bionemoEmitTempTavily/u);
  assert.equal(source.includes(["bionemo", "super", "initial", "diagnostic"].join("-")), false);
  assert.match(source, /const responseStream = bionemoSuperLocalResponse\s*\? \(async function\* bionemoSuperCompletedStream\(\) \{\s*yield \{ id: "bionemo-local-completion", choices:/su);
  assert.match(source, /const bionemoSuperLocalResponse = bionemoSuperFinalText \|\| Boolean\(bionemoSuperInitialTool\)/u);
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
  const expectedInventoryInitial = inventoryInitial;
  const catalog = BIONEMO_GUIDED_STARTER_TURNS.catalog;
  const demo = BIONEMO_GUIDED_STARTER_TURNS.demo;
  const malformedCatalog = guidedContext(catalog, [gwasListValue()]);
  malformedCatalog.messages[2].toolCallId = GUIDED_CALL_IDS[1];
  const malformedDemo = guidedContext(demo, [gwasContractValue(), gwasDemoValue("/tmp/gwas_20260818_123456")]);
  const guidedIntegrationCases = [
    ["Example 5 final", guidedContext(BIONEMO_GUIDED_STARTER_TURNS.tour)],
    ["Example 6 final", guidedContext(BIONEMO_GUIDED_STARTER_TURNS.skills)],
    ["Example 7 list", guidedContext(catalog)],
    ["Example 7 describe", guidedContext(catalog, [gwasListValue()])],
    ["Example 7 final", guidedContext(catalog, [gwasListValue(), gwasContractValue()])],
    ["Example 8 describe", guidedContext(demo)],
    ["Example 8 run", guidedContext(demo, [gwasContractValue()])],
    ["Example 8 final", guidedContext(demo, [gwasContractValue(), gwasDemoValue()])],
    ["Example 7 malformed fail-closed", malformedCatalog],
    ["Example 8 malformed fail-closed", malformedDemo],
  ].map(([label, context]) => {
    const tool = bionemoSuperInitialNotebookTool(superModel, context);
    const finalText = bionemoSuperLocalCompletionText(superModel, context);
    assert.equal(Boolean(tool) !== Boolean(finalText), true, label);
    return { label, context, tool, finalText };
  });
  const integrationScript = `
    import assert from "node:assert/strict";
    const patched = await import("file:///app/dist/${file}?test=" + Date.now());
    const model = ${JSON.stringify({ ...superModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const glmModel = ${JSON.stringify({ ...glmModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 262_144, maxTokens: 8_192, compat: { maxTokensField: "max_tokens", requiresStringContent: true } })};
    const deepSeekModel = ${JSON.stringify({ ...deepSeekModel, api: "openai-completions", baseUrl: "https://example.invalid/v1", reasoning: true, input: ["text"], contextWindow: 1_048_576, maxTokens: 8_192 })};
    const expectedInitial = ${JSON.stringify({ name: expectedInitial.name, params: { ...expectedInitial.params } })};
    const expectedTavilyInitial = ${JSON.stringify({ name: expectedTavilyInitial.name, params: { ...expectedTavilyInitial.params } })};
    const expectedInventoryInitial = ${JSON.stringify({ name: expectedInventoryInitial.name, params: { ...expectedInventoryInitial.params } })};
    const expectedInitialTurns = ${JSON.stringify(BIONEMO_SUPER_INITIAL_TURNS.map(({ prompt, name, params }) => ({ prompt, name, params: { ...params } })))};
    const guidedIntegrationCases = ${JSON.stringify(guidedIntegrationCases)};
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
    const successfulInventoryBoundary = ${JSON.stringify(inventoryTurn())};
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
    for (const sourceModel of [model, glmModel]) {
      for (const expected of expectedInitialTurns) {
        const exactInitialContext = { messages: [{ role: "user", content: "[Fri 2026-08-14 18:06 UTC] " + expected.prompt }] };
        const initialEvents = await within(collectEvents(transport(sourceModel, exactInitialContext, {
          apiKey: "test-key",
          emitReasoning: false,
          signal: AbortSignal.timeout(500),
          onPayload(params) {
            return { ...params, tools: [{ type: "function", function: { name: expected.name, description: "bounded test", parameters: { type: "object" } } }] };
          },
        })), 750);
        assert.equal(providerFetchCalls, 0, sourceModel.id + ": " + expected.name + " must not start a provider request");
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
    }
    for (const sourceModel of [model, glmModel]) {
      for (const guidedCase of guidedIntegrationCases) {
        const before = providerFetchCalls;
        const guidedEvents = await within(collectEvents(transport(sourceModel, guidedCase.context, {
          apiKey: "test-key",
          emitReasoning: false,
          signal: AbortSignal.timeout(500),
          onPayload(params) {
            return guidedCase.tool
              ? { ...params, tools: [{ type: "function", function: { name: guidedCase.tool.name, description: "bounded test", parameters: { type: "object" } } }] }
              : params;
          },
        })), 750);
        assert.equal(providerFetchCalls, before, sourceModel.id + ": " + guidedCase.label + " must remain source-owned");
        assert.equal(guidedEvents.some(({ type }) => type === "error"), false, guidedCase.label + ": " + JSON.stringify(guidedEvents));
        assert.equal(guidedEvents.at(0).type, "start", guidedCase.label);
        assert.equal(guidedEvents.at(-1).type, "done", guidedCase.label);
        if (guidedCase.tool) {
          assert.equal(guidedEvents.at(-1).message.stopReason, "toolUse", guidedCase.label);
          assert.deepEqual(guidedEvents.at(-1).message.content, [{
            type: "toolCall",
            id: guidedEvents.at(-1).message.content[0].id,
            name: guidedCase.tool.name,
            arguments: guidedCase.tool.params,
            partialArgs: JSON.stringify(guidedCase.tool.params),
          }], guidedCase.label);
        } else {
          assert.equal(guidedEvents.at(-1).message.stopReason, "stop", guidedCase.label);
          assert.deepEqual(guidedEvents.at(-1).message.content, [{ type: "text", text: guidedCase.finalText }], guidedCase.label);
          assert.equal(guidedEvents.some(({ type }) => type.startsWith("toolcall_")), false, guidedCase.label);
        }
      }
    }
    const expectedScienceInitial = expectedInitialTurns[0];
    const exactScienceInitialContext = { messages: [{ role: "user", content: "[Fri 2026-08-14 18:06 UTC] " + expectedScienceInitial.prompt }] };
    for (const sourceModel of [model, glmModel]) {
      const localFinal = patched.__bionemoSuperLocalCompletionText(sourceModel, successfulBoundary);
      assert.equal(localFinal, superLocalFinal);
      const localEvents = await within(collectEvents(transport(sourceModel, successfulBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
      assert.equal(providerFetchCalls, 0, "completed default-model boundary must not start a provider follow-up");
      assert.equal(localEvents.some(({ type }) => type === "error"), false, JSON.stringify(localEvents));
      assert.equal(localEvents.at(0).type, "start");
      assert.equal(localEvents.at(-1).type, "done");
      assert.equal(localEvents.some(({ type }) => type === "text_start"), true);
      assert.equal(localEvents.some(({ type }) => type === "text_delta"), true);
      assert.deepEqual(localEvents.at(-1).message.content, [{ type: "text", text: localFinal }]);
      assert.equal(localEvents.at(-1).message.stopReason, "stop");
    }

    const timestampedSuccessfulTavilyBoundary = structuredClone(successfulTavilyBoundary);
    timestampedSuccessfulTavilyBoundary.messages[0].content[0].text = "[Fri 2026-08-14 18:06 UTC] "
      + timestampedSuccessfulTavilyBoundary.messages[0].content[0].text;
    const tavilyLocalFinal = patched.__bionemoSuperLocalCompletionText(model, timestampedSuccessfulTavilyBoundary);
    assert.match(tavilyLocalFinal, /RCSB PDB/u);
    assert.match(tavilyLocalFinal, /UniProt/u);
    assert.equal(patched.__bionemoSuperLocalCompletionText(glmModel, timestampedSuccessfulTavilyBoundary), tavilyLocalFinal);
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

    assert.equal(successfulInventoryBoundary.messages[1].content[0].id.length, 40);
    assert.match(successfulInventoryBoundary.messages[1].content[0].id, /^callbionemosuper[0-9a-f]{12}4[0-9a-f]{3}[89ab][0-9a-f]{7}$/u);
    const inventoryLocalFinal = patched.__bionemoSuperLocalCompletionText(model, successfulInventoryBoundary);
    assert.equal(patched.__bionemoSuperLocalCompletionText(glmModel, successfulInventoryBoundary), inventoryLocalFinal);
    assert.match(inventoryLocalFinal, /3 models; 1 ready/u);
    for (const entry of ${JSON.stringify(inventoryValue().models)}) {
      assert.equal(inventoryLocalFinal.includes("id: " + entry.id + "; displayName: " + entry.displayName + "; family: " + entry.family + "; readiness: " + entry.readiness), true);
    }
    assert.match(inventoryLocalFinal, /submitted no scientific compute or model job/u);
    assert.match(inventoryLocalFinal, /adapted bionemo_models__\\* compute operation/u);
    assert.match(inventoryLocalFinal, /scientific validity/u);
    const inventoryLocalEvents = await within(collectEvents(transport(model, successfulInventoryBoundary, { apiKey: "test-key", emitReasoning: false, signal: AbortSignal.timeout(500) })), 750);
    assert.equal(providerFetchCalls, 0, "exact stripped inventory boundary must not start a provider request");
    assert.equal(inventoryLocalEvents.some(({ type }) => type === "error"), false, JSON.stringify(inventoryLocalEvents));
    assert.equal(inventoryLocalEvents.at(0).type, "start");
    assert.equal(inventoryLocalEvents.at(-1).type, "done");
    assert.deepEqual(inventoryLocalEvents.at(-1).message.content, [{ type: "text", text: inventoryLocalFinal }]);
    assert.equal(inventoryLocalEvents.at(-1).message.stopReason, "stop");

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

    assert.equal(successfulInventoryBoundary.messages[1].content[0].name, expectedInventoryInitial.name);
    assert.deepEqual(successfulInventoryBoundary.messages[1].content[0].arguments, expectedInventoryInitial.params);
    const rewriteInventoryBoundary = (mutate) => {
      const boundary = structuredClone(successfulInventoryBoundary);
      const value = JSON.parse(boundary.messages[2].content[0].text);
      mutate(value);
      boundary.messages[2].content[0].text = JSON.stringify(value, null, 2);
      return boundary;
    };
    const inventoryRejected = [];
    const malformedInventory = structuredClone(successfulInventoryBoundary);
    malformedInventory.messages[2].content[0].text = "{";
    inventoryRejected.push(["malformed inventory JSON", malformedInventory]);
    const compactInventory = structuredClone(successfulInventoryBoundary);
    compactInventory.messages[2].content[0].text = JSON.stringify(JSON.parse(compactInventory.messages[2].content[0].text));
    inventoryRejected.push(["noncanonical inventory JSON", compactInventory]);
    inventoryRejected.push(["extra inventory status", rewriteInventoryBoundary((value) => { value.status = "completed"; })]);
    inventoryRejected.push(["missing inventory notice", rewriteInventoryBoundary((value) => { delete value.notice; })]);
    inventoryRejected.push(["duplicate inventory id", rewriteInventoryBoundary((value) => { value.models[1].id = value.models[0].id; })]);
    inventoryRejected.push(["inventory model count mismatch", rewriteInventoryBoundary((value) => { value.modelCount -= 1; })]);
    inventoryRejected.push(["inventory ready count mismatch", rewriteInventoryBoundary((value) => { value.readyCount += 1; })]);
    inventoryRejected.push(["invalid inventory readiness", rewriteInventoryBoundary((value) => { value.models[0].readiness = "starting"; value.readyCount = 0; })]);
    inventoryRejected.push(["unsafe inventory display name", rewriteInventoryBoundary((value) => { value.models[0].displayName = "OpenFold3\\nInjected"; })]);
    inventoryRejected.push(["unsafe inventory identifier", rewriteInventoryBoundary((value) => { value.models[0].id = "OpenFold3"; })]);
    const extraInventoryBlock = structuredClone(successfulInventoryBoundary);
    extraInventoryBlock.messages[2].content.push({ type: "text", text: "extra" });
    inventoryRejected.push(["extra inventory result block", extraInventoryBlock]);
    const missingInventorySuccess = structuredClone(successfulInventoryBoundary);
    delete missingInventorySuccess.messages[2].isError;
    inventoryRejected.push(["missing inventory success", missingInventorySuccess]);
    const erroredInventory = structuredClone(successfulInventoryBoundary);
    erroredInventory.messages[2].isError = true;
    inventoryRejected.push(["errored inventory", erroredInventory]);
    const ambiguousInventoryError = structuredClone(successfulInventoryBoundary);
    ambiguousInventoryError.messages[2].error = null;
    inventoryRejected.push(["ambiguous inventory error", ambiguousInventoryError]);
    const ambiguousInventoryDetails = structuredClone(successfulInventoryBoundary);
    ambiguousInventoryDetails.messages[2].details = undefined;
    inventoryRejected.push(["ambiguous inventory details", ambiguousInventoryDetails]);
    const ambiguousInventoryStructured = structuredClone(successfulInventoryBoundary);
    ambiguousInventoryStructured.messages[2].structuredContent = undefined;
    inventoryRejected.push(["ambiguous inventory structured content", ambiguousInventoryStructured]);
    const wrongInventoryPrompt = structuredClone(successfulInventoryBoundary);
    wrongInventoryPrompt.messages[0].content += " ";
    inventoryRejected.push(["wrong inventory prompt", wrongInventoryPrompt]);
    const badInventoryArgs = structuredClone(successfulInventoryBoundary);
    badInventoryArgs.messages[1].content[0].arguments = { retry: true };
    inventoryRejected.push(["bad inventory arguments", badInventoryArgs]);
    const badInventoryPartialArgs = structuredClone(successfulInventoryBoundary);
    badInventoryPartialArgs.messages[1].content[0].partialArgs = "{ }";
    inventoryRejected.push(["bad inventory partial arguments", badInventoryPartialArgs]);
    const mismatchedInventoryId = structuredClone(successfulInventoryBoundary);
    mismatchedInventoryId.messages[2].toolCallId = successfulEphemeralTavilyBoundary.messages[1].content[0].id;
    inventoryRejected.push(["mismatched inventory ID", mismatchedInventoryId]);
    const providerInventoryId = structuredClone(successfulInventoryBoundary);
    providerInventoryId.messages[1].content[0].id = "provider-generated-inventory-call-boundary-123456";
    providerInventoryId.messages[2].toolCallId = providerInventoryId.messages[1].content[0].id;
    inventoryRejected.push(["provider inventory ID", providerInventoryId]);
    const inventoryProviderStart = providerFetchCalls;
    for (const [label, boundary] of inventoryRejected) {
      assert.equal(patched.__bionemoSuperLocalCompletionText(model, boundary), undefined, label);
      const events = await within(collectEvents(transport(model, boundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
      assert.equal(events.at(-1).type, "done", label);
      assert.deepEqual(events.at(-1).message.content, [{ type: "text", text: "Provider normal path." }], label);
    }
    assert.equal(providerFetchCalls, inventoryProviderStart + inventoryRejected.length, "every rejected inventory shape must retain the provider transport");
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
    assert.equal(providerFetchCalls, providerBaseline + 1, "a missing projected source-owned tool must fail closed without a provider request");
    assert.equal(missingSurfaceEvents.at(-1).type, "done");
    assert.match(missingSurfaceEvents.at(-1).message.content[0].text, /could not validate the packaged example result/iu);
    const wrongProviderModel = { ...model, provider: "nvidia" };
    const wrongProviderEvents = await within(collectEvents(transport(wrongProviderModel, exactScienceInitialContext, {
      apiKey: "test-key",
      emitReasoning: false,
      onPayload(params) {
        return { ...params, tools: [{ type: "function", function: { name: expectedScienceInitial.name, description: "bounded test", parameters: { type: "object" } } }] };
      },
    })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 2, "the exact timestamped prompt on another provider must retain the provider transport");
    assert.equal(wrongProviderEvents.at(-1).type, "done");
    assert.deepEqual(wrongProviderEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const malformedTavilyBoundary = structuredClone(successfulTavilyBoundary);
    malformedTavilyBoundary.messages.at(-1).details.mcpServer = "untrusted-server";
    assert.equal(patched.__bionemoSuperLocalCompletionText(model, malformedTavilyBoundary), undefined);
    const malformedTavilyEvents = await within(collectEvents(transport(model, malformedTavilyBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 3, "malformed Tavily provenance retains the provider transport");
    assert.equal(malformedTavilyEvents.at(-1).type, "done");
    assert.deepEqual(malformedTavilyEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const erroredBoundaryForTransport = ${JSON.stringify(turn("bionemo_batch_fold_demo", { isError: true }))};
    const erroredEvents = await within(collectEvents(transport(model, erroredBoundaryForTransport, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 4, "errored Super boundary retains the provider transport");
    assert.equal(erroredEvents.at(-1).type, "done");
    assert.deepEqual(erroredEvents.at(-1).message.content, [{ type: "text", text: "Provider normal path." }]);
    const deepSeekEvents = await within(collectEvents(transport(deepSeekModel, successfulBoundary, { apiKey: "test-key", emitReasoning: false })), 2_000);
    assert.equal(providerFetchCalls, providerBaseline + 4, "legacy completed-wrapper final must not start a discarded provider request");
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
  const integrationPath = path.join(root, "openclaw-super-followup-integration.mjs");
  await writeFile(integrationPath, integrationScript);
  await execFileAsync("docker", [
    "run", "--rm", "--network", "none", "--entrypoint", "node",
    "--mount", `type=bind,src=${path.join(distRoot, file)},dst=/app/dist/${file},readonly`,
    "--mount", `type=bind,src=${integrationPath},dst=/tmp/openclaw-super-followup-integration.mjs,readonly`,
    PINNED_IMAGE, "/tmp/openclaw-super-followup-integration.mjs",
  ]);
});
