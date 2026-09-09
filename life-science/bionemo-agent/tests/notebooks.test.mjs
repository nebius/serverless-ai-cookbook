import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { WORKFLOWS } from "../openclaw-plugin/src/catalog.mjs";
import { NOTEBOOK_CATALOG } from "../openclaw-plugin/src/notebooks.mjs";

const recipe = new URL("../", import.meta.url);
const notebookDirectory = fileURLToPath(new URL("workspace/notebooks/", recipe));
const NOTEBOOKS = Object.freeze([
  {
    file: "01-egfr-research-drug-demo.ipynb",
    id: "egfr-research-drug-demo",
    tool: "bionemo_research_drug_demo",
    optionalTavily: true,
  },
  {
    file: "02-compare-protein-structures.ipynb",
    id: "compare-protein-structures",
    tool: "bionemo_compare_protein_structures",
    optionalTavily: false,
  },
  {
    file: "03-optimize-ligand-complex.ipynb",
    id: "optimize-ligand-complex",
    tool: "bionemo_optimize_ligand_complex",
    optionalTavily: false,
  },
  {
    file: "04-bulk-openfold2-five-proteins.ipynb",
    id: "bulk-openfold2-five-proteins",
    tool: "bionemo_batch_fold_demo",
    optionalTavily: false,
    sourceFixture: "notebooks/data/five-proteins.fasta",
  },
]);

const FIXTURE_RECORDS = Object.freeze([
  ["1CRN", "TTCCPSIVARSNFNVCRLPGTPEAICATYTGCIIIPGATCPGDYAN"],
  ["1UBQ", "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"],
  ["1PGA", "MTYKLILNGKTLKGETTTEAVDAATAEKVFKQYANDNGVDGEWTYDDATKTFTVTE"],
  ["2CI2", "SSVEKKPEGVNTGAGDRHNLKTEWPELVGKSVEEAKKVILQDKPEAQIIVLPVGTIVTMEYRIDRVRLFVDKLDNIAEVPRVG"],
  ["1VII", "MLSDEDFKAVFGMTRSAFANLPLWKQQNLKKEKGLF"],
]);

function cellText(notebook) {
  return notebook.cells.flatMap(({ source }) => source).join("");
}

function parseFasta(value) {
  const records = [];
  let active = null;
  for (const rawLine of value.trim().split(/\r?\n/u)) {
    const line = rawLine.trim();
    if (line.startsWith(">")) {
      if (active) records.push(active);
      active = { id: line.slice(1).split(/\s+/u)[0], sequence: "" };
      continue;
    }
    assert.ok(active, "FASTA sequence must follow a header");
    active.sequence += line;
  }
  if (active) records.push(active);
  return records;
}

test("four bundled notebooks are clean user-oriented launch templates", async () => {
  assert.equal(NOTEBOOKS.length, 4);
  const catalogByTool = new Map(Object.values(WORKFLOWS).map((workflow) => [workflow.tool, workflow]));
  const notebookBySlug = new Map(NOTEBOOK_CATALOG.map((definition) => [definition.slug, definition]));

  for (const expected of NOTEBOOKS) {
    const definition = notebookBySlug.get(expected.id);
    assert.ok(definition, `${expected.id} must exist in the public notebook catalog`);
    const serialized = await readFile(path.join(notebookDirectory, expected.file), "utf8");
    const notebook = JSON.parse(serialized);
    const metadata = notebook.metadata?.bionemo;
    const source = cellText(notebook);

    assert.equal(notebook.nbformat, 4, `${expected.file} must use nbformat v4`);
    assert.equal(notebook.nbformat_minor, 5);
    assert.ok(Array.isArray(notebook.cells) && notebook.cells.length >= 4);
    assert.equal(new Set(notebook.cells.map(({ id }) => id)).size, notebook.cells.length, "cell IDs must be unique");
    for (const cell of notebook.cells) {
      assert.ok(["markdown", "code"].includes(cell.cell_type));
      assert.ok(Array.isArray(cell.source) && cell.source.every((line) => typeof line === "string"));
      if (cell.cell_type === "code") {
        assert.equal(cell.execution_count, null, `${expected.file} must not imply execution`);
        assert.deepEqual(cell.outputs, [], `${expected.file} must not bake model output`);
      } else {
        assert.equal(Object.hasOwn(cell, "execution_count"), false);
        assert.equal(Object.hasOwn(cell, "outputs"), false);
      }
    }

    assert.equal(metadata.schemaVersion, 1);
    assert.equal(metadata.id, expected.id);
    assert.equal(metadata.title, definition.title);
    assert.equal(metadata.tool, expected.tool);
    assert.deepEqual(metadata.steps, definition.steps);
    assert.equal(metadata.prompt, definition.prompt);
    assert.equal(metadata.optionalTavily, expected.optionalTavily);
    assert.equal(metadata.backendNeutral, true);
    assert.equal(metadata.executionStatus, "template-unexecuted");
    assert.equal(metadata.sourceFixture, expected.sourceFixture);
    assert.ok(source.includes(metadata.prompt), "visible launch prompt must exactly match launch metadata");
    assert.match(source, /unexecuted launch template/iu);
    assert.doesNotMatch(source, /\b(?:bionemo_|bionemo_models__|clawbio__|tavily_web__)/u);
    assert.doesNotMatch(source, /\b(?:ack_[a-z_]+|input_file|viewerMarkdown)\b/u);
    assert.doesNotMatch(source, /\bcall\s+[a-z0-9_*]+\s+exactly\s+once\b/iu);
    assert.match(metadata.prompt, /research/u);
    assert.match(metadata.prompt, /independent validation/u);
    assert.doesNotMatch(serialized, /\b(?:tvly|nvapi|sk-ant|sk-proj)-[A-Za-z0-9_-]{8,}/u);
    assert.doesNotMatch(serialized, /\b(?:NVIDIA|NEBIUS|OPENAI|ANTHROPIC|BIONEMO_MCP|TAVILY)_API_KEY\b/u);
    assert.equal(serialized.includes("output_type"), false, "serialized execution output is forbidden");

    const workflow = catalogByTool.get(expected.tool);
    assert.ok(workflow, `${expected.tool} must be registered in the workbench workflow catalog`);
    assert.equal(workflow.crossBackend, true, `${expected.tool} must stay provider-neutral`);
  }
});

test("batch notebook fixture contains exactly the five pinned public sequences in source order", async () => {
  const [fasta, sourceText] = await Promise.all([
    readFile(path.join(notebookDirectory, "data/five-proteins.fasta"), "utf8"),
    readFile(path.join(notebookDirectory, "data/five-proteins.sources.json"), "utf8"),
  ]);
  const records = parseFasta(fasta);
  assert.deepEqual(records.map(({ id, sequence }) => [id, sequence]), FIXTURE_RECORDS);
  assert.equal(new Set(records.map(({ id }) => id)).size, 5);
  assert.ok(records.every(({ sequence }) => /^[ACDEFGHIKLMNPQRSTVWY]+$/u.test(sequence)));

  const sources = JSON.parse(sourceText);
  assert.equal(sources.schemaVersion, 1);
  assert.deepEqual(sources.records.map(({ id }) => id), FIXTURE_RECORDS.map(([id]) => id));
  assert.ok(sources.records.every(({ pdbId, source }) => source === `https://www.rcsb.org/fasta/entry/${pdbId}/display`));

  const batch = JSON.parse(await readFile(path.join(notebookDirectory, "04-bulk-openfold2-five-proteins.ipynb"), "utf8"));
  assert.equal(batch.metadata.bionemo.sourceFixture, "notebooks/data/five-proteins.fasta");
  assert.match(cellText(batch), /exactly five unique IDs/u);
  for (const [id, sequence] of FIXTURE_RECORDS) {
    assert.match(cellText(batch), new RegExp(`\\b${id}\\b`, "u"));
    assert.equal(sequence.length >= 36 && sequence.length <= 83, true);
  }
});
