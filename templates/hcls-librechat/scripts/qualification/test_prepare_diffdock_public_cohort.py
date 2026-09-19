import hashlib

import pytest

from prepare_diffdock_public_cohort import prepare


def fixture(tmp_path):
    path = tmp_path / "reference.sdf"
    path.write_bytes(b"reference")
    return [{"case_id": "diffdock-fixed", "model_id": "diffdock", "mode": "native",
             "arguments": {"seed": 19, "num_poses": 4},
             "expected": {"reference_path": "reference.sdf", "thresholds": {"rmsd": 2}},
             "provenance": {"sources": [{"path": "reference.sdf", "size_bytes": 9,
                                        "sha256": hashlib.sha256(b"reference").hexdigest()}]}}]


def test_preserves_inputs_and_freezes_reference(tmp_path):
    cases = fixture(tmp_path)
    prepared = prepare(cases, tmp_path)
    assert prepared["cases"][0]["arguments"] == cases[0]["arguments"]
    assert prepared["cases"][0]["expected"]["thresholds"] == {"rmsd": 2}
    assert prepared["cases"][0]["expected"]["reference_path"] == str(tmp_path / "reference.sdf")
    assert cases[0]["expected"]["reference_path"] == "reference.sdf"


def test_rejects_corrupt_reference(tmp_path):
    cases = fixture(tmp_path)
    (tmp_path / "reference.sdf").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash/size"):
        prepare(cases, tmp_path)


def test_rejects_unqualified_reference_and_duplicate_case(tmp_path):
    cases = fixture(tmp_path)
    cases[0]["expected"]["reference_path"] = "unfrozen.sdf"
    with pytest.raises(ValueError, match="checksum"):
        prepare(cases, tmp_path)
    cases = fixture(tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        prepare(cases * 2, tmp_path)
