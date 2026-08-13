import { randomBytes } from "node:crypto";
import { lstat, readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";

export const NOTEBOOK_ROUTE_PREFIX = "/plugins/bionemo/notebooks";
export const NOTEBOOK_MAX_BYTES = 256 * 1024;
export const NOTEBOOK_CHAT_PATH = "/chat?session=agent%3Abionemo%3Amain";

function notebook(entry) {
  return Object.freeze({ ...entry, steps: Object.freeze([...entry.steps]) });
}

export const NOTEBOOK_CATALOG = Object.freeze([
  notebook({
    slug: "egfr-research-drug-demo",
    file: "01-egfr-research-drug-demo.ipynb",
    title: "Research-first EGFR drug discovery demo",
    description: "Optional Tavily evidence gathering followed by a bounded, cross-backend structure and molecule workflow.",
    steps: ["Optionally research current public EGFR/gefitinib evidence with Tavily", "Characterize the fixed public EGFR kinase sequence with OpenFold2", "Optimize two gefitinib-derived candidates with MolMIM", "Model the selected candidate with the same EGFR sequence using OpenFold3", "Review citations, confidence summaries, artifacts, and limitations"],
    prompt: "Run the backend-neutral research-first EGFR demo. Call bionemo_research_drug_demo exactly once with use_tavily=true, ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call its Tavily, OpenFold2, MolMIM, or OpenFold3 steps separately. Report whether optional Tavily research ran, cite its sources if present, summarize every model step and confidence value, include every artifact viewerMarkdown link verbatim, and state the scientific limitations.",
    optionalTavily: true,
  }),
  notebook({
    slug: "compare-protein-structures",
    file: "02-compare-protein-structures.ipynb",
    title: "Compare protein structure predictions",
    description: "Compare two provider-neutral structure predictions for the same public protein target.",
    steps: ["Load the fixed public crambin sequence", "Predict one structure with OpenFold2", "Independently predict the same sequence with OpenFold3", "Compare scalar confidence summaries and structure artifacts", "Review limitations and experimental-validation requirements"],
    prompt: "Run the backend-neutral public crambin structure-comparison demo. Call bionemo_compare_protein_structures exactly once with ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call OpenFold2 or OpenFold3 separately. Compare the two independent predictions using only returned scalar confidence summaries and artifact links; do not treat either prediction as experimental ground truth. Include every artifact viewerMarkdown link verbatim and state the scientific limitations.",
    optionalTavily: false,
  }),
  notebook({
    slug: "optimize-ligand-complex",
    file: "03-optimize-ligand-complex.ipynb",
    title: "Optimize a ligand and model its complex",
    description: "Generate a bounded molecule set and model the selected molecule with its public protein target.",
    steps: ["Load the fixed public EGFR target and gefitinib seed", "Generate two bounded candidates with MolMIM", "Select one candidate deterministically from returned scores", "Model the selected ligand with the same EGFR sequence using OpenFold3", "Review artifacts, confidence, chemistry, and limitations"],
    prompt: "Run the backend-neutral fixed EGFR/gefitinib ligand-optimization demo. Call bionemo_optimize_ligand_complex exactly once with ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call MolMIM or OpenFold3 separately. Summarize both generated candidates, identify the deterministically selected candidate and returned optimization score, explain the handoff into OpenFold3, include every artifact viewerMarkdown link verbatim, and make no binding, safety, efficacy, or clinical claim.",
    optionalTavily: false,
  }),
  notebook({
    slug: "bulk-openfold2-five-proteins",
    file: "04-bulk-openfold2-five-proteins.ipynb",
    title: "Batch-fold five public proteins",
    description: "A bounded five-protein workbook with sequential execution and explicit per-item results.",
    steps: ["Read and validate the fixed five-record public FASTA fixture", "Fold each protein sequentially with OpenFold2", "Retain per-record success or durable failure status", "Collect confidence summaries, artifacts, and viewer links", "Review batch counts, limitations, and validation requirements"],
    prompt: "Run the backend-neutral fixed five-protein batch-folding demo. Call bionemo_batch_fold_demo exactly once with input_file=notebooks/data/five-proteins.fasta, ack_research_only=true, ack_non_clinical=true, ack_non_commercial=true, ack_aup_accepted=true, and ack_no_safety_or_therapeutic_claims=true. I explicitly accept those five research-only acknowledgements. Do not call OpenFold2 separately or submit duplicate concurrent jobs. Report exactly the five fixture record IDs in source order with per-record status, elapsed time or remote job ID when available, scalar confidence summaries, and every successful artifact viewerMarkdown link verbatim. Preserve and report successful records if another record fails, then state the scientific limitations.",
    optionalTavily: false,
  }),
]);

const NOTEBOOKS_BY_SLUG = new Map(NOTEBOOK_CATALOG.map((entry) => [entry.slug, entry]));

export function notebookViewPath(slug) {
  return `${NOTEBOOK_ROUTE_PREFIX}/${slug}`;
}

export function notebookDownloadPath(slug) {
  return `${notebookViewPath(slug)}.ipynb`;
}

export function notebookChatPath(prompt) {
  return `${NOTEBOOK_CHAT_PATH}&draft=${encodeURIComponent(prompt)}`;
}

export function publicNotebookCatalog() {
  return Object.freeze(NOTEBOOK_CATALOG.map((definition) => Object.freeze({
    ...definition,
    viewPath: notebookViewPath(definition.slug),
    downloadPath: notebookDownloadPath(definition.slug),
    chatPath: notebookChatPath(definition.prompt),
  })));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/gu, (character) => `&#${character.codePointAt(0)};`);
}

function cellSource(cell, index) {
  if (!cell || typeof cell !== "object" || Array.isArray(cell)) throw new Error(`Notebook cell ${index + 1} is invalid`);
  if (!["markdown", "code", "raw"].includes(cell.cell_type)) throw new Error(`Notebook cell ${index + 1} has an unsupported type`);
  if (typeof cell.source === "string") return cell.source;
  if (!Array.isArray(cell.source) || !cell.source.every((line) => typeof line === "string")) throw new Error(`Notebook cell ${index + 1} has invalid source`);
  return cell.source.join("");
}

function validatedNotebook(value, definition) {
  if (!value || typeof value !== "object" || Array.isArray(value) || value.nbformat !== 4 || !Array.isArray(value.cells)) {
    throw new Error("Notebook must use nbformat 4 and contain a cells array");
  }
  const metadata = value.metadata?.bionemo;
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) throw new Error("Notebook BioNeMo metadata is missing");
  if (metadata.id !== definition.slug) throw new Error("Notebook id does not match its fixed catalog entry");
  if (typeof metadata.title !== "string" || !metadata.title.trim()) throw new Error("Notebook title is missing");
  if (typeof metadata.prompt !== "string" || !metadata.prompt.trim()) throw new Error("Notebook chat prompt is missing");
  if (metadata.title.trim() !== definition.title || metadata.prompt.trim() !== definition.prompt) {
    throw new Error("Notebook title or prompt has drifted from its fixed public catalog entry");
  }
  if (!Array.isArray(metadata.steps) || metadata.steps.length === 0 || !metadata.steps.every((step) => typeof step === "string" && step.trim())) {
    throw new Error("Notebook steps are missing or invalid");
  }
  if (metadata.steps.length !== definition.steps.length || metadata.steps.some((step, index) => step.trim() !== definition.steps[index])) {
    throw new Error("Notebook steps have drifted from its fixed public catalog entry");
  }
  value.cells.forEach((cell, index) => {
    cellSource(cell, index);
    if (cell.cell_type === "code" && (!Array.isArray(cell.outputs) || cell.outputs.length !== 0)) {
      throw new Error(`Notebook code cell ${index + 1} must have an empty outputs array`);
    }
  });
  return {
    notebook: value,
    metadata: {
      id: metadata.id,
      title: metadata.title.trim(),
      prompt: metadata.prompt.trim(),
      steps: metadata.steps.map((step) => step.trim()),
      tool: typeof metadata.tool === "string" ? metadata.tool.trim() : "",
      optionalTavily: metadata.optionalTavily === true,
      backendNeutral: metadata.backendNeutral === true,
      executionStatus: typeof metadata.executionStatus === "string" ? metadata.executionStatus.trim() : "",
    },
  };
}

function publicNotebook(definition, metadata) {
  return Object.freeze({
    ...definition,
    title: metadata.title,
    prompt: metadata.prompt,
    steps: Object.freeze([...metadata.steps]),
    optionalTavily: metadata.optionalTavily,
    backendNeutral: metadata.backendNeutral,
    executionStatus: metadata.executionStatus,
    tool: metadata.tool,
  });
}

export async function loadNotebookCatalog(root = process.env.BIONEMO_NOTEBOOK_ROOT || "/workspace/agent/notebooks") {
  return Object.freeze(await Promise.all(NOTEBOOK_CATALOG.map(async (definition) => {
    const parsed = await loadNotebook(definition, root);
    return publicNotebook(definition, parsed.metadata);
  })));
}

async function loadNotebook(definition, root) {
  const rootStat = await lstat(root);
  if (!rootStat.isDirectory() || rootStat.isSymbolicLink()) throw new Error("Notebook root must be a real directory");
  const rootReal = await realpath(root);
  const rootRealStat = await stat(rootReal);
  if (!rootRealStat.isDirectory() || rootRealStat.dev !== rootStat.dev || rootRealStat.ino !== rootStat.ino) throw new Error("Notebook root is unsafe");
  const filePath = path.join(rootReal, definition.file);
  const originalStat = await lstat(filePath);
  if (!originalStat.isFile() || originalStat.isSymbolicLink() || originalStat.size > NOTEBOOK_MAX_BYTES) {
    throw new Error("Notebook is unavailable, linked, or exceeds the preview limit");
  }
  const fileReal = await realpath(filePath);
  if (path.dirname(fileReal) !== rootReal) throw new Error("Notebook path escapes the fixed notebook directory");
  const fileStat = await lstat(fileReal);
  if (!fileStat.isFile() || fileStat.isSymbolicLink() || fileStat.size > NOTEBOOK_MAX_BYTES) throw new Error("Notebook is unavailable or exceeds the preview limit");
  const body = await readFile(fileReal);
  if (body.length > NOTEBOOK_MAX_BYTES) throw new Error("Notebook exceeds the preview limit");
  let parsed;
  try { parsed = JSON.parse(body.toString("utf8")); } catch { throw new Error("Notebook JSON is invalid"); }
  return { ...validatedNotebook(parsed, definition), body };
}

function notebookHtml(nonce, definition, parsed) {
  const { notebook: value, metadata } = parsed;
  const chatHref = notebookChatPath(metadata.prompt);
  const downloadHref = notebookDownloadPath(definition.slug);
  const cells = value.cells.map((cell, index) => {
    const kind = cell.cell_type;
    const source = cellSource(cell, index);
    return `<section class="cell ${kind}"><div class="cell-label">${escapeHtml(kind)} cell ${index + 1}</div><pre><code>${escapeHtml(source)}</code></pre></section>`;
  }).join("");
  const steps = metadata.steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(metadata.title)} · BioNeMo</title><style nonce="${nonce}">:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#07110d;color:#e9fff3}*{box-sizing:border-box}body{margin:0;padding:24px;background:radial-gradient(circle at top right,#153b28,#07110d 55%);min-height:100vh}main{max-width:1000px;margin:auto}.hero,.cell{border:1px solid #2c5f43;background:#0d1c15f2;border-radius:14px;padding:18px;box-shadow:0 14px 45px #0005}.hero{display:grid;gap:12px;margin-bottom:16px}h1,p{margin:0}.muted{color:#9fc8af}.warning{border-left:4px solid #ffd35c;padding-left:12px;color:#ffe5a0}.pill{display:inline-block;width:max-content;padding:3px 8px;border-radius:999px;background:#183d2a;color:#88f2b3;font-size:12px}.actions{display:flex;gap:9px;flex-wrap:wrap}.action{display:inline-block;border-radius:9px;padding:10px 12px;background:#71f2a8;color:#052010;font-weight:700;text-decoration:none}.action.secondary{background:#1b3b2b;color:#d9fbe7}.steps{display:flex;gap:8px;flex-wrap:wrap;padding:0;margin:0;list-style:none}.steps li{font-size:12px;border:1px solid #315b42;border-radius:999px;padding:5px 9px;color:#b5f7cf}.cell{margin-top:12px}.cell-label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#88f2b3;margin-bottom:9px}.cell.code{border-left:4px solid #71f2a8}.cell.markdown{border-left:4px solid #6aa7ff}.cell.raw{border-left:4px solid #d2a8ff}pre{margin:0;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;color:#e9fff3}</style></head><body><main><section class="hero"><span class="pill">Read-only guided notebook</span><h1>${escapeHtml(metadata.title)}</h1><p class="muted">This is a safe preview of the image-baked notebook. Cells are not executed in this page; launch its reviewed prompt in the bounded BioNeMo chat.</p><ol class="steps">${steps}</ol><p class="warning">Research use only. Outputs are computational hypotheses and require expert review and experimental validation.</p><div class="actions"><a class="action" target="_top" rel="noopener" href="${escapeHtml(chatHref)}">Run in BioNeMo chat</a><a class="action secondary" href="${escapeHtml(downloadHref)}" download="${escapeHtml(definition.file)}">Download .ipynb</a><a class="action secondary" href="/plugins/bionemo">All starting points</a></div></section>${cells}</main></body></html>`;
}

function responseHeaders(contentType, length, extra = {}) {
  return {
    "Cache-Control": "no-store",
    "Content-Type": contentType,
    "Content-Length": length,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    ...extra,
  };
}

function finish(res, method, status, headers, body) {
  res.writeHead(status, headers);
  res.end(method === "HEAD" ? undefined : body);
}

function errorResponse(req, res, status, code, message, extraHeaders = {}) {
  const body = Buffer.from(`${JSON.stringify({ code, message })}\n`, "utf8");
  finish(res, req.method || "GET", status, responseHeaders("application/json; charset=utf-8", body.length, extraHeaders), body);
}

export function createNotebookHandler({ root = process.env.BIONEMO_NOTEBOOK_ROOT || "/workspace/agent/notebooks", nonceFactory = () => randomBytes(18).toString("base64") } = {}) {
  return async function notebookHandler(req, res) {
    const method = req.method || "GET";
    const url = new URL(req.url || "/", "http://localhost");
    const escapedPrefix = NOTEBOOK_ROUTE_PREFIX.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    const match = url.pathname.match(new RegExp(`^${escapedPrefix}/([a-z0-9][a-z0-9-]*)(\\.ipynb)?$`, "u"));
    const definition = match ? NOTEBOOKS_BY_SLUG.get(match[1]) : undefined;
    if (!definition) {
      errorResponse(req, res, 404, "not_found", "Unknown BioNeMo notebook");
      return true;
    }
    if (method !== "GET" && method !== "HEAD") {
      errorResponse(req, res, 405, "method_not_allowed", "Notebook routes support GET and HEAD only", { Allow: "GET, HEAD" });
      return true;
    }
    try {
      const parsed = await loadNotebook(definition, root);
      if (match[2]) {
        finish(res, method, 200, responseHeaders("application/x-ipynb+json; charset=utf-8", parsed.body.length, {
          "Content-Disposition": `attachment; filename="${definition.file}"`,
        }), parsed.body);
        return true;
      }
      const nonce = nonceFactory();
      const body = Buffer.from(notebookHtml(nonce, definition, parsed), "utf8");
      finish(res, method, 200, responseHeaders("text/html; charset=utf-8", body.length, {
        "Content-Security-Policy": `default-src 'none'; style-src 'nonce-${nonce}'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'`,
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        "X-Frame-Options": "SAMEORIGIN",
      }), body);
      return true;
    } catch {
      errorResponse(req, res, 503, "notebook_unavailable", "The image-baked notebook is unavailable or invalid");
      return true;
    }
  };
}

export const __test = { cellSource, escapeHtml, loadNotebook, notebookHtml, validatedNotebook };
