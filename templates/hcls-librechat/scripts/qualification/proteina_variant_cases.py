"""Freeze public FAD-binding and enzyme-motif inputs for advertised variants.

Preparation only; no inference. These are service/structural checks, not a claim
of cofactor affinity, catalytic activity, or reproduction of a paper benchmark.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

from datasets import fetch
from manage_campaign import save

TARGETS = [("ligand-target", "41_7BKC_LIGAND"), ("ame", "M0584_1ldm")]


def target_bundle(path, data):
    if path.startswith("/") or ".." in Path(path).parts:
        raise ValueError("Target path must be source-relative")
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        member = tarfile.TarInfo(path)
        member.size, member.mode, member.mtime = len(data), 0o644, 0
        archive.addfile(member, io.BytesIO(data))
    return gzip.compress(stream.getvalue(), mtime=0)


def prepare(schema_path, output):
    schema = json.loads(schema_path.read_text())
    catalog = schema["target_catalog"]
    revision = catalog["source_revision"]
    cases = []
    for variant, target_id in TARGETS:
        target = catalog["variants"][variant]["targets"][target_id]
        source_path = target["bundle_path"]
        source, provenance = fetch("https://raw.githubusercontent.com/" + catalog["source_repository"] +
                                   "/" + revision + "/" + source_path,
                                   output / "sources" / target_id / Path(source_path).name)
        if not source.startswith((b"CRYST1", b"HEADER", b"ATOM", b"HETATM", b"REMARK")):
            raise ValueError("Upstream target is not the expected PDB text")
        provenance["path"] = str(Path(provenance["path"]).relative_to(output))
        payload = target_bundle(source_path, source)
        bundle = output / "inputs" / (target_id + ".tar.gz")
        bundle.parent.mkdir(parents=True, exist_ok=True)
        bundle.write_bytes(payload)
        for seed in (7, 42):
            case_id = f"proteina-{variant}-{target_id.lower()}-s{seed}"
            cases.append({"case_id": case_id, "model_id": "proteina-complexa",
                "persona": "cofactor-and-enzyme-methods-researcher", "tool": "submit_proteina_complexa",
                "mode": "scientific-batch", "arguments": {
                    "schema": "fs2-serve.nebius.ai/scientific-run-request/v1", "operation": "design-binders",
                    "service_class": "customer-batch", "parameters": {"variant": variant, "target_id": target_id,
                        "run_name": case_id.replace("_", "-"), "seed": seed, "num_samples": 1, "diffusion_steps": 100}},
                "preparation": {"inputs": [{"name": "target-bundle", "semantic_type": "proteina-complexa-target-bundle/v1",
                    "local_path": str(bundle.relative_to(output)), "media_type": "application/x-tar", "compression": "gzip",
                    "sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}]},
                "expected": {"evaluator": "design_constraints", "minimum_structures": 1},
                "provenance": {"source_repository": catalog["source_repository"], "source_revision": revision,
                    "sources": [provenance], "exact_target_configuration": target,
                    "protocol_deviation": "Pinned upstream FAD target / lactate-dehydrogenase motif; bounded two-seed method coverage. No binding, catalysis, or experimental-success claim."},
                "workload": {"unique_input_id": target_id, "seed": seed, "repetition": 1, "priority": "batch"}})
    save(output / "cases.json", {"schema_version": 1, "study_id": "public-proteina-variant-coverage",
         "source_schema_sha256": hashlib.sha256(schema_path.read_bytes()).hexdigest(), "cases": cases})
    print(json.dumps({"cases": len(cases), "variants": [v for v, _ in TARGETS], "manifest": str(output / "cases.json")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.schema, args.output)
