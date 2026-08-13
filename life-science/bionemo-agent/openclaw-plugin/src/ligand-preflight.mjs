import { execFile } from "node:child_process";
import { promisify } from "node:util";

export const LIGAND_PREFLIGHT_PYTHON = "/opt/clawbio/bin/python";
export const LIGAND_PREFLIGHT_CHECKER = "/opt/bionemo/openclaw-plugin/src/ligand-embeddability.py";
export const LIGAND_PREFLIGHT_TIMEOUT_MS = 30_000;
export const LIGAND_PREFLIGHT_MAX_OUTPUT_BYTES = 16_384;

const MAX_CANDIDATES = 10;
const MAX_SMILES_BYTES = 2_048;
const MAX_TOTAL_SMILES_BYTES = 8_192;
const MAX_ENCODED_PAYLOAD_BYTES = 16_384;
const RESULT_CODES = new Set([
  "embedded_etkdg",
  "invalid_smiles",
  "conformer_generation_failed",
]);
const CHECKER_ENV = Object.freeze({
  LC_ALL: "C",
  PYTHONDONTWRITEBYTECODE: "1",
  PYTHONNOUSERSITE: "1",
});
const execFileAsync = promisify(execFile);

function preflightError(code, message, status = 500) {
  return Object.assign(new Error(message), {
    name: "LigandPreflightError",
    code,
    status,
    retryable: false,
  });
}

function encodedRequest(smiles) {
  if (!Array.isArray(smiles) || smiles.length === 0 || smiles.length > MAX_CANDIDATES) {
    throw preflightError("ligand_preflight_invalid_input", `Ligand preflight requires between 1 and ${MAX_CANDIDATES} candidates.`, 400);
  }
  let totalBytes = 0;
  for (const candidate of smiles) {
    const bytes = typeof candidate === "string" ? Buffer.byteLength(candidate, "utf8") : 0;
    if (bytes === 0 || bytes > MAX_SMILES_BYTES) {
      throw preflightError("ligand_preflight_invalid_input", `Each ligand candidate must contain between 1 and ${MAX_SMILES_BYTES} UTF-8 bytes.`, 400);
    }
    totalBytes += bytes;
  }
  if (totalBytes > MAX_TOTAL_SMILES_BYTES) {
    throw preflightError("ligand_preflight_invalid_input", `Ligand candidates exceed the ${MAX_TOTAL_SMILES_BYTES}-byte preflight limit.`, 400);
  }
  const encoded = Buffer.from(JSON.stringify({ version: 1, smiles }), "utf8").toString("base64url");
  if (Buffer.byteLength(encoded, "ascii") > MAX_ENCODED_PAYLOAD_BYTES) {
    throw preflightError("ligand_preflight_invalid_input", "The encoded ligand preflight request is too large.", 400);
  }
  return encoded;
}

function parsedResults(stdout, expectedCount) {
  let response;
  try {
    response = JSON.parse(stdout);
  } catch {
    throw preflightError("ligand_preflight_invalid_response", "The local ligand preflight checker returned invalid JSON.");
  }
  if (response?.version !== 1 || !Array.isArray(response.results) || response.results.length !== expectedCount) {
    throw preflightError("ligand_preflight_invalid_response", "The local ligand preflight checker returned an invalid result set.");
  }
  return response.results.map((result) => {
    if (typeof result?.embeddable !== "boolean" || !RESULT_CODES.has(result?.code)) {
      throw preflightError("ligand_preflight_invalid_response", "The local ligand preflight checker returned an invalid candidate result.");
    }
    if (result.embeddable !== result.code.startsWith("embedded_")) {
      throw preflightError("ligand_preflight_invalid_response", "The local ligand preflight checker returned an inconsistent candidate result.");
    }
    return Object.freeze({ embeddable: result.embeddable, code: result.code });
  });
}

export class LocalLigandEmbeddabilityPreflight {
  constructor({ execFileImpl = execFileAsync } = {}) {
    if (typeof execFileImpl !== "function") throw new TypeError("execFileImpl must be a function");
    this.execFileImpl = execFileImpl;
  }

  async assess(smiles) {
    const payload = encodedRequest(smiles);
    let stdout;
    try {
      ({ stdout } = await this.execFileImpl(
        LIGAND_PREFLIGHT_PYTHON,
        [LIGAND_PREFLIGHT_CHECKER, payload],
        {
          encoding: "utf8",
          timeout: LIGAND_PREFLIGHT_TIMEOUT_MS,
          killSignal: "SIGKILL",
          maxBuffer: LIGAND_PREFLIGHT_MAX_OUTPUT_BYTES,
          windowsHide: true,
          shell: false,
          env: CHECKER_ENV,
        },
      ));
    } catch {
      throw preflightError(
        "ligand_preflight_unavailable",
        "The bounded local ligand embeddability preflight could not complete; OpenFold3 was not called.",
      );
    }
    return parsedResults(stdout, smiles.length);
  }
}

export const __test = {
  MAX_CANDIDATES,
  MAX_SMILES_BYTES,
  MAX_TOTAL_SMILES_BYTES,
  MAX_ENCODED_PAYLOAD_BYTES,
  CHECKER_ENV,
  encodedRequest,
  parsedResults,
};
