"""Bounded local RDKit preflight for OpenFold3 ligand SMILES handoffs."""

from __future__ import annotations

import base64
import json
import re
import sys
from typing import Any

MAX_CANDIDATES = 10
MAX_SMILES_BYTES = 2_048
MAX_TOTAL_SMILES_BYTES = 8_192
MAX_ENCODED_PAYLOAD_BYTES = 16_384
RANDOM_SEED = 0xF00D
KNOWN_NON_EMBEDDABLE = (
    "COc1cc2ncnc(N3C[C@H]4C[C@H]3[C@H]4CCl)c2cc1OC",
    "COc1cc2ncn(CCN3CC4(C3)NC[C@H]3C[C@@]34C)c(=O)c2cc1OC",
)
KNOWN_EMBEDDABLE_CONTROL = "CN1CCc2nnc(NCc3ccc(F)c(Cl)c3)cc2C1"


def fail(message: str) -> "NoReturn":
    print(message, file=sys.stderr)
    raise SystemExit(2)


def load_request() -> list[str]:
    if len(sys.argv) != 2:
        fail("expected one encoded request")
    encoded = sys.argv[1]
    if len(encoded) > MAX_ENCODED_PAYLOAD_BYTES or not re.fullmatch(r"[A-Za-z0-9_-]+", encoded):
        fail("invalid encoded request")
    try:
        padding = "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(encoded + padding)
        request: Any = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        fail("invalid encoded request")
    if not isinstance(request, dict) or request.get("version") != 1:
        fail("invalid request version")
    smiles = request.get("smiles")
    if not isinstance(smiles, list) or not 1 <= len(smiles) <= MAX_CANDIDATES:
        fail("invalid candidate count")
    total_bytes = 0
    for candidate in smiles:
        if not isinstance(candidate, str):
            fail("invalid candidate")
        candidate_bytes = len(candidate.encode("utf-8"))
        if not 1 <= candidate_bytes <= MAX_SMILES_BYTES:
            fail("invalid candidate")
        total_bytes += candidate_bytes
    if total_bytes > MAX_TOTAL_SMILES_BYTES:
        fail("candidate input too large")
    return smiles


def assess(smiles: str) -> dict[str, bool | str]:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem

    RDLogger.DisableLog("rdApp.*")
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {"embeddable": False, "code": "invalid_smiles"}
    try:
        molecule = Chem.AddHs(molecule)
        parameters = AllChem.ETKDGv3()
        parameters.randomSeed = RANDOM_SEED
        parameters.useRandomCoords = False
        parameters.clearConfs = True
        parameters.numThreads = 1
        conformer_id = AllChem.EmbedMolecule(molecule, parameters)
        if conformer_id >= 0:
            return {"embeddable": True, "code": "embedded_etkdg"}
    except Exception:
        pass
    return {"embeddable": False, "code": "conformer_generation_failed"}


def main() -> None:
    if sys.argv[1:] == ["--self-test"]:
        failed = [assess(candidate) for candidate in KNOWN_NON_EMBEDDABLE]
        control = assess(KNOWN_EMBEDDABLE_CONTROL)
        if any(item["embeddable"] for item in failed) or not control["embeddable"]:
            fail("pinned RDKit ligand preflight regression")
        print(json.dumps({"status": "ok", "failedFixtures": len(failed)}, separators=(",", ":")))
        return
    smiles = load_request()
    results = [assess(candidate) for candidate in smiles]
    print(json.dumps({"version": 1, "results": results}, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
