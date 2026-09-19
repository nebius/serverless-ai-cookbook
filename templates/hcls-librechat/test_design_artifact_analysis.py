"""Manifest-aware measurements, including the actual .artifact suffix failure."""

import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import gemmi
import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "design_artifacts", ROOT / "design-artifact-analysis.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def pdb(offset=0):
    return (
        "".join(
            f"ATOM  {i:5d}  CA  ALA B{i:4d}    {offset + (i - 1) * 3.8:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 80.00           C  \n"
            for i in range(1, 5)
        )
        + "TER\nEND\n"
    )


def manifest(tmp_path, artifacts):
    entries = []
    for index, (name, media, raw, compression, semantic) in enumerate(artifacts):
        (tmp_path / f"output-{index:02d}.artifact").write_bytes(raw)
        entries.append(
            {
                "name": name,
                "semantic_type": semantic,
                "artifact": {
                    "artifact_id": f"fixture-{index}",
                    "media_type": media,
                    "compression": compression,
                    "size_bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                },
            }
        )
    path = tmp_path / "output-manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
                "entries": entries,
            }
        )
    )
    return path


def test_media_not_dot_artifact_filename_drives_pdb_csv_json_parsing(tmp_path):
    path = manifest(
        tmp_path,
        [
            (
                "structure.1",
                "chemical/x-pdb",
                pdb().encode(),
                "none",
                "protein-structure/v1",
            ),
            ("results.1", "text/csv", b"id,confidence\n0,0.9\n", "none", "results/v1"),
            ("metadata", "application/json", b'{"rejected":3}', "none", "metadata/v1"),
        ],
    )
    result = module.analyze(
        path, binder_chain="B", binder_length_min=4, binder_length_max=4
    )
    assert result["verified_artifacts"] == 3 and result["coordinate_outputs"] == 1
    chain = result["structures"][0]["geometry"]["chains"][0]
    assert chain["residues"] == 4 and chain[
        "adjacent_ca_median_angstrom"
    ] == pytest.approx(3.8)
    assert result["structures"][0]["role"] == "unassigned_without_explicit_provenance"
    assert result["metadata_unmodified_values"][1]["content"]["csv_rows"] == [
        {"id": "0", "confidence": "0.9"}
    ]
    assert result["metadata_unmodified_values"][2]["content"]["rejected"] == 3
    module.publish(result, tmp_path / "analysis")
    assert {p.name for p in (tmp_path / "analysis").iterdir()} == {
        "measurements.json",
        "inventory.csv",
        "report.md",
    }
    assert "biological efficacy" in (tmp_path / "analysis/report.md").read_text()


def test_valid_cif_is_actually_parsed_not_read_as_pdb_columns(tmp_path):
    cif = gemmi.read_pdb_string(pdb()).make_mmcif_document().as_string()
    path = manifest(
        tmp_path,
        [
            (
                "candidate",
                "chemical/x-mmcif",
                cif.encode(),
                "none",
                "protein-structure/v1",
            )
        ],
    )
    result = module.analyze(path)
    chain = result["structures"][0]["geometry"]["chains"][0]
    assert chain["chain"] == "B" and chain["residues"] == 4
    assert chain["ca_step_outside_2_5_to_4_5_fraction"] == 0
    assert result["explicit_binder_unique_sequences"] is None


@pytest.mark.parametrize("change", ["bytes", "size", "order"])
def test_exact_hash_size_and_manifest_order_required(tmp_path, change):
    path = manifest(
        tmp_path,
        [
            ("one", "chemical/x-pdb", pdb().encode(), "none", "structure/v1"),
            ("two", "chemical/x-pdb", pdb(1).encode(), "none", "structure/v1"),
        ],
    )
    if change == "bytes":
        (tmp_path / "output-00.artifact").write_bytes(b"wrong")
    elif change == "order":
        (tmp_path / "output-00.artifact").write_bytes(
            (tmp_path / "output-01.artifact").read_bytes()
        )
    else:
        value = json.loads(path.read_bytes())
        value["entries"][0]["artifact"]["size_bytes"] += 1
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="hash/size"):
        module.analyze(path)


def test_invalid_declared_coordinates_do_not_become_successful_empty_inventory(
    tmp_path,
):
    path = manifest(
        tmp_path,
        [("structure", "chemical/x-pdb", b"not coordinates", "none", "structure/v1")],
    )
    with pytest.raises((ValueError, StopIteration)):
        module.analyze(path)


def test_gzip_and_archive_members_parsed_without_extracting_paths(tmp_path):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        raw = pdb().encode()
        member = tarfile.TarInfo("../../outside.pdb")
        member.size = len(raw)
        archive.addfile(member, io.BytesIO(raw))
    path = manifest(
        tmp_path,
        [
            (
                "bundle",
                "application/x-tar",
                gzip.compress(buffer.getvalue()),
                "gzip",
                "design-bundle/v1",
            )
        ],
    )
    result = module.analyze(path)
    assert result["coordinate_outputs"] == 1
    assert result["structures"][0]["member"] == "../../outside.pdb"
    assert not (tmp_path.parent / "outside.pdb").exists()


def test_proteina_roles_and_metrics_use_existing_verified_provenance_join(tmp_path):
    structure = pdb()
    sequence = "AAAA"
    row = {
        "id_gen": "0",
        "self_sequence": sequence,
        "generated_structure_artifact": "raw",
        "self_refolded_structure_artifact": "refold",
        "self_binder_scRMSD_ca": "0.0",
    }
    table = io.StringIO()
    writer = csv.DictWriter(table, fieldnames=list(row))
    writer.writeheader()
    writer.writerow(row)
    provenance = {
        "schema_version": "fs2-serve.nebius.ai/proteina-complexa-design-provenance/v1",
        "designs": [
            {
                "id_gen": "0",
                "results_artifact": "results",
                "results_row_sha256": module.digest(
                    json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
                ),
                "sequence_sha256": module.digest(sequence.encode()),
                "refolding_model": "fixture",
                "relaxation": "not-claimed",
                **{
                    role: {
                        "artifact_name": name,
                        "sha256": module.digest(structure.encode()),
                        "binder_chain": "B",
                    }
                    for role, name in [
                        ("generated", "raw"),
                        ("self_refolded", "refold"),
                    ]
                },
            }
        ],
    }
    path = manifest(
        tmp_path,
        [
            (
                "raw",
                "chemical/x-pdb",
                structure.encode(),
                "none",
                "protein-complex-structure/v1",
            ),
            (
                "refold",
                "chemical/x-pdb",
                structure.encode(),
                "none",
                "proteina-complexa-self-refolded-structure/v1",
            ),
            (
                "results",
                "text/csv",
                table.getvalue().encode(),
                "none",
                "proteina-complexa-results-csv/v1",
            ),
            (
                "provenance",
                "application/json",
                json.dumps(provenance).encode(),
                "none",
                "design-provenance/v1",
            ),
        ],
    )
    result = module.analyze(path)
    assert [row["role"] for row in result["structures"]] == [
        "generated",
        "self_refolded",
    ]
    assert result["linked_designs"]["design_count"] == 1
    assert result["linked_designs"]["predictions"][0]["csv_rmsd_agrees"]


def test_missing_target_chain_is_not_guessed(tmp_path):
    path = manifest(
        tmp_path,
        [("structure", "chemical/x-pdb", pdb().encode(), "none", "structure/v1")],
    )
    reference = tmp_path / "reference.pdb"
    reference.write_text(pdb())
    with pytest.raises(ValueError, match="supplied together"):
        module.analyze(path, target_reference=reference)
    result = module.analyze(path, target_reference=reference, target_chain="B")
    assert result["structures"][0]["target_sequence_matching_chains"] == ["B"]
    assert result["structures"][0]["target_sequence_exact_unique"]


def test_unknown_content_remains_explicit_not_a_science_pass(tmp_path):
    path = manifest(
        tmp_path,
        [("opaque", "application/octet-stream", b"opaque", "none", "unknown/v1")],
    )
    result = module.analyze(path)
    assert result["coordinate_outputs"] == 0 and result["linked_designs"] is None
    assert result["metadata_unmodified_values"][0]["content"]["uninterpreted"]
