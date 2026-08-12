import { constants as fsConstants } from "node:fs";
import { mkdir, open, readdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";
import { LIMITS } from "./validation.mjs";
import { InputError, redactSecrets } from "./errors.mjs";

const RUN_ID = /^[a-f0-9-]{36}$/u;
const FILE_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/u;
const STRUCTURE_EXTENSIONS = new Set([".cif", ".mmcif", ".pdb"]);
// OpenClaw 2026.7.1 treats root-relative /plugins/* Markdown links as
// documentation paths and rewrites them onto docs.openclaw.ai. Keep the
// capability URL on an application-owned top-level route so the Control UI
// preserves it as a same-origin link on dynamically assigned Nebius URLs.
export const VIEWER_ROUTE_PREFIX = "/bionemo/view";
const CONTENT_TYPES = Object.freeze({
  ".json": "application/json; charset=utf-8",
  ".cif": "chemical/x-mmcif",
  ".mmcif": "chemical/x-mmcif",
  ".pdb": "chemical/x-pdb",
  ".sdf": "chemical/x-mdl-sdfile",
  ".a3m": "text/plain; charset=utf-8",
  ".fa": "text/plain; charset=utf-8",
  ".fasta": "text/plain; charset=utf-8",
  ".smi": "text/plain; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
});

function normalizedPublicOrigin(value) {
  if (!value) return "";
  try {
    const url = new URL(value);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) return "";
    return url.origin;
  } catch {
    return "";
  }
}

function safeName(value, fallback = "artifact") {
  const cleaned = String(value).replace(/[^A-Za-z0-9._-]+/gu, "-").replace(/^[.-]+/u, "").slice(0, 96);
  return cleaned || fallback;
}

function inferStructureExtension(format, structure) {
  const normalized = String(format || "").toLowerCase();
  if (normalized === "pdb" || /^ATOM\s+/mu.test(structure)) return ".pdb";
  return ".cif";
}

function collectStructures(value, output, prefix = "structure", depth = 0) {
  if (depth > 10 || output.length >= 50) return;
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectStructures(item, output, `${prefix}-${index + 1}`, depth + 1));
    return;
  }
  if (!value || typeof value !== "object") return;
  if (typeof value.structure === "string" && value.structure.length > 20) {
    output.push({ name: `${safeName(prefix)}${inferStructureExtension(value.format, value.structure)}`, content: value.structure });
  }
  for (const [key, item] of Object.entries(value)) collectStructures(item, output, `${prefix}-${key}`, depth + 1);
}

function collectAlignments(value, output, prefix = "alignment", depth = 0) {
  if (depth > 10 || output.length >= 50) return;
  if (!value || typeof value !== "object") return;
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectAlignments(item, output, `${prefix}-${index + 1}`, depth + 1));
    return;
  }
  for (const [key, item] of Object.entries(value)) {
    if ((key === "alignment" || key === "a3m" || key === "fasta") && typeof item === "string" && item.includes(">")) {
      const ext = key === "fasta" ? ".fasta" : ".a3m";
      output.push({ name: `${safeName(prefix)}${ext}`, content: item });
    } else collectAlignments(item, output, `${prefix}-${key}`, depth + 1);
  }
}

function moleculeRows(data) {
  let items = data?.molecules ?? data?.generated ?? [];
  if (typeof items === "string") {
    try { items = JSON.parse(items); } catch { return []; }
  }
  if (!Array.isArray(items)) return [];
  return items.map((item) => {
    if (typeof item === "string") return item;
    const smiles = item?.smiles || item?.sample || item?.smi;
    return smiles ? `${smiles}${item?.score === undefined ? "" : `\t${item.score}`}` : null;
  }).filter(Boolean);
}

export function extractArtifacts(skillId, data) {
  const artifacts = [];
  if (skillId === "boltz2" || skillId === "openfold2" || skillId === "openfold3") collectStructures(data, artifacts);
  if (skillId === "diffdock" && Array.isArray(data?.ligand_positions)) {
    data.ligand_positions.slice(0, 20).forEach((content, index) => {
      if (typeof content === "string") artifacts.push({ name: `docked-pose-${index + 1}.sdf`, content });
    });
  }
  if (skillId === "evo2" && typeof data?.sequence === "string") {
    artifacts.push({ name: "generated-sequence.fasta", content: `>evo2_generated_research_sequence\n${data.sequence}\n` });
  }
  if (skillId === "genmol" || skillId === "molmim") {
    const rows = moleculeRows(data);
    if (rows.length) artifacts.push({ name: "generated-molecules.smi", content: `${rows.join("\n")}\n` });
  }
  if (skillId === "msa_search") collectAlignments(data, artifacts);
  if (skillId === "proteinmpnn" && typeof data?.mfasta === "string") artifacts.push({ name: "designed-sequences.fasta", content: data.mfasta });
  if (skillId === "rfdiffusion" && typeof data?.output_pdb === "string") artifacts.push({ name: "designed-backbone.pdb", content: data.output_pdb });
  return artifacts.slice(0, LIMITS.maxArtifactsPerRun);
}

export class ArtifactStore {
  constructor(root = process.env.BIONEMO_ARTIFACT_ROOT || "/workspace/agent/artifacts", { publicBaseUrl = process.env.BIONEMO_PUBLIC_URL || process.env.BIONEMO_PUBLIC_ORIGIN } = {}) {
    this.root = path.resolve(root);
    this.publicBaseUrl = normalizedPublicOrigin(publicBaseUrl);
  }

  async initialize() {
    await mkdir(this.root, { recursive: true, mode: 0o700 });
    return this;
  }

  async createRun({ kind, id, inputSummary = {} }) {
    await this.initialize();
    const runId = randomUUID();
    const directory = path.join(this.root, runId);
    await mkdir(directory, { recursive: false, mode: 0o700 });
    const viewerCapability = randomBytes(24).toString("base64url");
    const manifest = {
      schemaVersion: 1,
      runId,
      kind,
      id,
      status: "running",
      createdAt: new Date().toISOString(),
      inputSummary: redactSecrets(inputSummary),
      steps: [],
      artifacts: [],
      structureCapabilityDigest: createHash("sha256").update(viewerCapability).digest("hex"),
    };
    await this.writeManifest(directory, manifest);
    return { runId, directory, manifest, viewerCapability };
  }

  async writeManifest(directory, manifest) {
    const target = path.join(directory, "manifest.json");
    await writeFile(target, `${JSON.stringify(redactSecrets(manifest), null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  }

  async save(run, name, content) {
    if (run.manifest.artifacts.length >= LIMITS.maxArtifactsPerRun) throw new InputError("artifact count limit exceeded");
    const fileName = safeName(name);
    if (!FILE_NAME.test(fileName) || fileName === "manifest.json") throw new InputError("invalid generated artifact name");
    const buffer = Buffer.isBuffer(content) ? content : Buffer.from(String(content), "utf8");
    if (buffer.length > LIMITS.responseBytes) throw new InputError("artifact exceeds output size limit");
    const target = path.join(run.directory, fileName);
    const handle = await open(target, fsConstants.O_CREAT | fsConstants.O_EXCL | fsConstants.O_WRONLY | fsConstants.O_NOFOLLOW, 0o600);
    try { await handle.writeFile(buffer); } finally { await handle.close(); }
    const entry = { name: fileName, bytes: buffer.length, downloadPath: target };
    run.manifest.artifacts.push(entry);
    await this.writeManifest(run.directory, run.manifest);
    return entry;
  }

  async saveNimResult(run, result, prefix = "") {
    const safePrefix = prefix ? `${safeName(prefix)}-` : "";
    const sanitized = redactSecrets(result.data);
    await this.save(run, `${safePrefix}response.json`, `${JSON.stringify(sanitized, null, 2)}\n`);
    for (const artifact of extractArtifacts(result.skillId, result.data)) await this.save(run, `${safePrefix}${artifact.name}`, artifact.content);
    return run.manifest.artifacts;
  }

  async complete(run, { status = "completed", error, steps } = {}) {
    run.manifest.status = status;
    run.manifest.completedAt = new Date().toISOString();
    if (error) run.manifest.error = redactSecrets(error);
    if (steps) run.manifest.steps = redactSecrets(steps);
    await this.writeManifest(run.directory, run.manifest);
    return run.manifest;
  }

  presentArtifacts(run) {
    return run.manifest.artifacts.map((artifact) => {
      if (!STRUCTURE_EXTENSIONS.has(path.extname(artifact.name).toLowerCase())) return artifact;
      const viewerPath = `${VIEWER_ROUTE_PREFIX}/${run.runId}/${encodeURIComponent(artifact.name)}?access=${encodeURIComponent(run.viewerCapability)}`;
      const viewerUrl = this.publicBaseUrl ? new URL(viewerPath, `${this.publicBaseUrl}/`).toString() : viewerPath;
      return {
        ...artifact,
        viewerUrl,
        viewerMarkdown: `[View structure in 3D](<${viewerUrl}>)`,
      };
    });
  }

  async listRuns(limit = 25) {
    await this.initialize();
    const names = await readdir(this.root);
    const manifests = [];
    for (const name of names.filter((item) => RUN_ID.test(item)).slice(0, 200)) {
      try {
        const value = JSON.parse(await readFile(path.join(this.root, name, "manifest.json"), "utf8"));
        delete value.structureCapabilityDigest;
        manifests.push(redactSecrets(value));
      } catch { /* ignore incomplete/corrupt run dirs */ }
    }
    return manifests.sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt))).slice(0, Math.max(1, Math.min(limit, 100)));
  }

  async openArtifact(runId, fileName) {
    if (!RUN_ID.test(runId) || !FILE_NAME.test(fileName) || fileName === "manifest.json") throw new InputError("invalid artifact identifier");
    await this.initialize();
    const rootReal = await realpath(this.root);
    const target = path.join(this.root, runId, fileName);
    const targetReal = await realpath(target);
    if (!targetReal.startsWith(`${rootReal}${path.sep}`)) throw new InputError("artifact path escapes the workspace");
    const metadata = await stat(targetReal);
    if (!metadata.isFile() || metadata.size > LIMITS.responseBytes) throw new InputError("artifact is not a bounded regular file");
    const handle = await open(targetReal, fsConstants.O_RDONLY | fsConstants.O_NOFOLLOW);
    return { handle, size: metadata.size, type: CONTENT_TYPES[path.extname(fileName).toLowerCase()] || "application/octet-stream" };
  }

  async openViewerArtifact(runId, fileName, capability) {
    if (typeof capability !== "string" || capability.length < 24 || capability.length > 128) throw new InputError("invalid structure viewer capability");
    if (!STRUCTURE_EXTENSIONS.has(path.extname(fileName).toLowerCase())) throw new InputError("artifact format is not viewable in 3D");
    if (!RUN_ID.test(runId) || !FILE_NAME.test(fileName) || fileName === "manifest.json") throw new InputError("invalid artifact identifier");
    const manifest = JSON.parse(await readFile(path.join(this.root, runId, "manifest.json"), "utf8"));
    const actual = createHash("sha256").update(capability).digest();
    const expected = Buffer.from(String(manifest.structureCapabilityDigest || ""), "hex");
    if (expected.length !== actual.length || !timingSafeEqual(expected, actual)) throw new InputError("invalid structure viewer capability");
    return this.openArtifact(runId, fileName);
  }
}

export const __test = { safeName, RUN_ID, FILE_NAME, STRUCTURE_EXTENSIONS, moleculeRows, normalizedPublicOrigin };
