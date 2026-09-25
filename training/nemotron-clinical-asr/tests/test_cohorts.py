import hashlib
import json
from pathlib import Path

import pytest

from clinical_asr.cloud_evaluate import evaluate_cohorts, pinned_cohorts, stage_cohorts


class S3:
    def __init__(self, data):
        self.data, self.downloaded = data, []

    def download_file(self, bucket, key, path):
        self.downloaded.append(key)
        Path(path).write_bytes(self.data[key])


def fixture(tmp_path, *, duplicate=False, unsafe=False, wrong_audio_hash=False):
    root = tmp_path / "source"
    audio = b"fixture-audio-not-sent-to-inference"
    row = {"id": "sample-1", "text": "human reference", "duration": 2,
           "split": "external_test", "example_exposure": "external_heldout",
           "audio_filepath": str(root / ("../escape.wav" if unsafe else "audio/1.wav")),
           "audio_sha256": "0" * 64 if wrong_audio_hash else hashlib.sha256(audio).hexdigest()}
    manifest = (json.dumps(row) + "\n") * (2 if duplicate else 1)
    manifest = manifest.encode()
    client = S3({"manifests/frozen-v1.jsonl": manifest, "audio/1.wav": audio})
    specs = pinned_cohorts(["manifests/frozen-v1.jsonl"], [hashlib.sha256(manifest).hexdigest()])
    return client, root, specs


def test_all_frozen_cohort_rows_and_reference_provenance_are_retained(tmp_path):
    client, root, specs = fixture(tmp_path)
    cohorts = stage_cohorts(client, "bucket", root, tmp_path / "out", specs)
    assert cohorts[0]["rows"] == 1
    assert cohorts[0]["split_labels"] == ["external_test"]
    assert cohorts[0]["example_exposure_labels"] == ["external_heldout"]
    assert cohorts[0]["manifest"].read_bytes() == client.data[specs[0]["key"]]
    assert client.downloaded == ["manifests/frozen-v1.jsonl", "audio/1.wav"]
    calls = []
    evaluate_cohorts(cohorts, "/checkpoint.nemo", "a" * 64, lambda *args: calls.append(args))
    assert len(calls) == 2
    assert all("--limit" not in args for _, args in calls)
    assert "--checkpoint-sha" not in calls[0][1]
    assert calls[1][1][-1] == "a" * 64
    assert calls[0][1][4].endswith("frozen-v1/base-predictions.jsonl")
    assert calls[1][1][4].endswith("frozen-v1/tuned-predictions.jsonl")


def test_wrong_frozen_manifest_hash_fails_before_any_audio_download(tmp_path):
    client, root, specs = fixture(tmp_path)
    specs[0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="download_sha256_mismatch"):
        stage_cohorts(client, "bucket", root, tmp_path / "out", specs)
    assert client.downloaded == ["manifests/frozen-v1.jsonl"]


@pytest.mark.parametrize("invalid_hash", [None, "", "not-a-sha256", 123])
def test_exact_clip_hash_is_required_even_if_original_source_hash_exists(tmp_path, invalid_hash):
    client, root, specs = fixture(tmp_path)
    row = json.loads(client.data[specs[0]["key"]])
    row["source_audio_sha256"] = row["audio_sha256"]
    row["audio_sha256"] = invalid_hash
    manifest = (json.dumps(row) + "\n").encode()
    client.data[specs[0]["key"]] = manifest
    specs[0]["sha256"] = hashlib.sha256(manifest).hexdigest()
    with pytest.raises(ValueError, match="requires_frozen_audio_sha256"):
        stage_cohorts(client, "bucket", root, tmp_path / "out", specs)
    assert client.downloaded == ["manifests/frozen-v1.jsonl"]


@pytest.mark.parametrize("options,match", [({"duplicate": True}, "unique_string_ids"),
                                         ({"unsafe": True}, "unsafe_object_key"),
                                         ({"wrong_audio_hash": True}, "audio_sha256_mismatch")])
def test_invalid_evaluation_inputs_fail_closed(tmp_path, options, match):
    client, root, specs = fixture(tmp_path, **options)
    with pytest.raises(ValueError, match=match):
        stage_cohorts(client, "bucket", root, tmp_path / "out", specs)


def test_paired_key_hash_counts_and_output_names_are_unambiguous():
    with pytest.raises(ValueError, match="one_frozen_sha256"):
        pinned_cohorts(["a.jsonl"], [])
    with pytest.raises(ValueError, match="duplicate_cohort_output_name"):
        pinned_cohorts(["a/cohort.jsonl", "b/cohort.jsonl"], ["a" * 64, "b" * 64])
    with pytest.raises(ValueError, match="invalid_manifest_sha256"):
        pinned_cohorts(["a.jsonl"], ["not-a-digest"])
