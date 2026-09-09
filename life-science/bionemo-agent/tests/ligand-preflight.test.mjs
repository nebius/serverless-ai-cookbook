import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  LIGAND_PREFLIGHT_CHECKER,
  LIGAND_PREFLIGHT_MAX_OUTPUT_BYTES,
  LIGAND_PREFLIGHT_PYTHON,
  LIGAND_PREFLIGHT_TIMEOUT_MS,
  LocalLigandEmbeddabilityPreflight,
  __test as preflightInternals,
} from "../openclaw-plugin/src/ligand-preflight.mjs";

test("local ligand preflight uses fixed absolute paths, one bounded base64url argument, no shell, and a secret-free environment", async () => {
  let invocation;
  const preflight = new LocalLigandEmbeddabilityPreflight({
    execFileImpl: async (file, args, options) => {
      invocation = { file, args, options };
      return { stdout: JSON.stringify({
        version: 1,
        results: [
          { embeddable: false, code: "conformer_generation_failed" },
          { embeddable: true, code: "embedded_etkdg" },
        ],
      }), stderr: "" };
    },
  });

  const results = await preflight.assess(["C1=CC=CC=C1", "CCO"]);
  assert.deepEqual(results, [
    { embeddable: false, code: "conformer_generation_failed" },
    { embeddable: true, code: "embedded_etkdg" },
  ]);
  assert.equal(invocation.file, LIGAND_PREFLIGHT_PYTHON);
  assert.equal(invocation.args[0], LIGAND_PREFLIGHT_CHECKER);
  assert.equal(invocation.args.length, 2);
  assert.match(invocation.args[1], /^[A-Za-z0-9_-]+$/u);
  assert.deepEqual(JSON.parse(Buffer.from(invocation.args[1], "base64url").toString("utf8")), {
    version: 1,
    smiles: ["C1=CC=CC=C1", "CCO"],
  });
  assert.equal(invocation.options.shell, false);
  assert.equal(invocation.options.timeout, LIGAND_PREFLIGHT_TIMEOUT_MS);
  assert.equal(invocation.options.maxBuffer, LIGAND_PREFLIGHT_MAX_OUTPUT_BYTES);
  assert.equal(invocation.options.killSignal, "SIGKILL");
  assert.deepEqual(invocation.options.env, {
    LC_ALL: "C",
    PYTHONDONTWRITEBYTECODE: "1",
    PYTHONNOUSERSITE: "1",
  });
  assert.equal(Object.keys(invocation.options.env).some((key) => /(?:key|secret|token|credential)/iu.test(key)), false);
});

test("local ligand preflight rejects oversized input before spawning a process", async () => {
  let calls = 0;
  const preflight = new LocalLigandEmbeddabilityPreflight({
    execFileImpl: async () => { calls += 1; },
  });
  await assert.rejects(
    () => preflight.assess(["C".repeat(preflightInternals.MAX_SMILES_BYTES + 1)]),
    (error) => error.code === "ligand_preflight_invalid_input" && error.status === 400,
  );
  assert.equal(calls, 0);
});

test("local ligand preflight fails closed on process or response errors without leaking child output", async () => {
  const failedProcess = new LocalLigandEmbeddabilityPreflight({
    execFileImpl: async () => { throw new Error("NVIDIA_API_KEY=must-not-leak"); },
  });
  await assert.rejects(
    () => failedProcess.assess(["CCO"]),
    (error) => error.code === "ligand_preflight_unavailable" && !error.message.includes("must-not-leak"),
  );

  const invalidResponse = new LocalLigandEmbeddabilityPreflight({
    execFileImpl: async () => ({ stdout: JSON.stringify({ version: 1, results: [{ embeddable: true, code: "embedded_random_coordinates" }] }) }),
  });
  await assert.rejects(
    () => invalidResponse.assess(["CCO"]),
    (error) => error.code === "ligand_preflight_invalid_response",
  );
});

test("RDKit checker has exactly one deterministic ETKDG attempt and no random-coordinate fallback", async () => {
  const source = await readFile(new URL("../openclaw-plugin/src/ligand-embeddability.py", import.meta.url), "utf8");
  assert.equal((source.match(/AllChem\.EmbedMolecule\(/gu) || []).length, 1);
  assert.match(source, /AllChem\.ETKDGv3\(\)/u);
  assert.match(source, /parameters\.randomSeed = RANDOM_SEED/u);
  assert.match(source, /parameters\.useRandomCoords = False/u);
  assert.doesNotMatch(source, /useRandomCoords\s*=\s*True/u);
  assert.match(source, /KNOWN_NON_EMBEDDABLE/u);
  assert.match(source, /KNOWN_EMBEDDABLE_CONTROL/u);
  assert.match(source, /pinned RDKit ligand preflight regression/u);
});
