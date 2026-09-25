"""Offline publication-validated cloud audio path mapping tests."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

RECIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RECIPE / "evaluation"))
spec = importlib.util.spec_from_file_location("public_prepare_references", RECIPE / "evaluation/prepare_references.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    row = {"id": "clinical_00001", "conversation_id": "clinical", "split": "dev", "duration": 1.5,
           "text": "No fever. Metformin?", "audio_filepath": "/output/training-v1/segments/audio/clinical_00001.wav"}
    publication = {"status": "completed", "run_id": "training-v1", "objects": [
        {"key": "runs/training-v1/segments/audio/clinical_00001.wav", "sha256": "a" * 64, "bytes": 48044}]}
    return row, publication


def test_mapping_adds_exact_clip_hash_and_preserves_reference():
    row, publication = fixture()
    original = copy.deepcopy(row)
    mapped, audit = module.map_published_audio([row], publication, "training-v1")
    assert row == original
    assert mapped[0]["audio_filepath"] == "/data/clinical-speech/runs/training-v1/segments/audio/clinical_00001.wav"
    assert mapped[0]["audio_sha256"] == "a" * 64
    assert {k: v for k, v in mapped[0].items() if k not in {"audio_filepath", "audio_sha256"}} == {
        k: v for k, v in original.items() if k != "audio_filepath"}
    assert audit[0]["audio_hash_added"] is True


@pytest.mark.parametrize("fault", ["wrong_run", "not_completed", "missing_clip", "duplicate_key", "hash_conflict", "source_hash_only", "traversal"])
def test_mapping_fails_closed(fault):
    row, publication = fixture()
    if fault == "wrong_run":
        publication["run_id"] = "another-run"
    elif fault == "not_completed":
        publication["status"] = "running"
    elif fault == "missing_clip":
        publication["objects"] = []
    elif fault == "duplicate_key":
        publication["objects"] *= 2
    elif fault == "hash_conflict":
        row["audio_sha256"] = "b" * 64
    elif fault == "source_hash_only":
        row["source_audio_sha256"] = "c" * 64
        publication["objects"][0].pop("sha256")
    elif fault == "traversal":
        row["audio_filepath"] = "/output/training-v1/segments/audio/../clinical_00001.wav"
    with pytest.raises(ValueError):
        module.map_published_audio([row], publication, "training-v1")


def test_cli_mapping_receipt_and_no_overwrite(tmp_path):
    row, publication = fixture()
    row["audio_sha256"] = "a" * 64
    manifest = tmp_path / "source.jsonl"
    manifest.write_text(json.dumps(row) + "\n")
    completed = tmp_path / "completed.json"
    completed.write_text(json.dumps(publication))
    output = tmp_path / "references.jsonl"
    command = [sys.executable, str(RECIPE / "evaluation/prepare_references.py"), "--manifest", str(manifest),
               "--output", str(output), "--cloud-run-id", "training-v1", "--cloud-publication", str(completed)]
    subprocess.run(command, check=True, capture_output=True)
    result = json.loads(output.read_text())
    assert result["text"] == row["text"]
    receipt = json.loads(output.with_suffix(".references.json").read_text())
    assert receipt["cloud_audio_mapping"]["rows"][0]["audio_hash_added"] is False
    assert receipt["cloud_audio_mapping"]["publication_sha256"]
    assert receipt["clinical_keyword_occurrences"] > 0
    before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == before
