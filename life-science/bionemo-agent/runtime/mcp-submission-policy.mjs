export const MCP_TURN_ID_FIELD = "__bionemo_agent_run_id";

// These are the asynchronous, compute-submitting tools exposed by the
// BioNeMo MCP server. Administrative tools such as job status/list
// and model discovery are intentionally absent.
export const MCP_SUBMISSION_TOOL_NAMES = Object.freeze([
  "clawbio_alphagenome_predict",
  "clawbio_boltz2_predict",
  "clawbio_cellpose_segment",
  "clawbio_deepvariant_call",
  "clawbio_diffdock_dock",
  "clawbio_esm2_embed",
  "clawbio_esmc_analyze",
  "clawbio_evo2_generate",
  "clawbio_genmol_generate",
  "clawbio_molmim_optimize",
  "clawbio_msa_search",
  "clawbio_openfold2_predict",
  "clawbio_openfold3_predict",
  "clawbio_proteinmpnn_design",
  "clawbio_rfdiffusion_generate",
  "clawbio_scanvi_fit_transform",
  "clawbio_scvi_fit_transform",
]);

const SUBMISSION_TOOL_SET = new Set(MCP_SUBMISSION_TOOL_NAMES);
const PRODUCT_SUBMISSION_TOOL_SET = new Set(
  MCP_SUBMISSION_TOOL_NAMES.map((name) => name.replace(/^clawbio_/u, "")),
);
const SAFE_TURN_ID = /^[A-Za-z0-9._:-]{8,256}$/u;

export function submissionToolBaseName(value) {
  if (typeof value !== "string") return null;
  const name = value.trim();
  if (SUBMISSION_TOOL_SET.has(name)) return name;
  const separator = name.lastIndexOf("__");
  if (separator < 1) return null;
  const baseName = name.slice(separator + 2);
  if (SUBMISSION_TOOL_SET.has(baseName)) return baseName;
  return PRODUCT_SUBMISSION_TOOL_SET.has(baseName) ? `clawbio_${baseName}` : null;
}

export function validMcpTurnId(value) {
  return typeof value === "string" && SAFE_TURN_ID.test(value);
}
