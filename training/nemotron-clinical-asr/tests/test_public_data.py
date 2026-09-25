import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import zipfile

import pytest

RECIPE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RECIPE / "data"))
sys.path.insert(0, str(RECIPE / "evaluation"))
import download_public as download
import prepare_corpus as corpus
import prepare_external as external
import prepare_replay as replay
import select_dev
from prepare_references import annotate
from score_pair import paired_scores
from upload_inputs import inputs


def test_pinned_archive_hashes_are_sha256():
    for item in download.ARCHIVES.values():
        assert len(item["sha256"]) == 64
        assert item["url"].startswith("https://")


def test_transcript_preserves_dose_negation_and_case():
    raw = "D: Take 0.5 mg.\nP: I do not take Metformin.\n".encode("utf-16")
    decoded, encoding = corpus.decode_transcript(raw)
    text, turns, warnings = corpus.normalize_transcript(decoded)
    assert encoding == "utf-16"
    assert text == "Take 0.5 mg. I do not take Metformin."
    assert [row["speaker"] for row in turns] == ["doctor", "patient"]
    assert not warnings


def test_frozen_split_is_disjoint_seeded_and_immutable(tmp_path):
    ids = [f"RES{i:04}" for i in range(272)]
    path = tmp_path / "split.json"
    split = corpus.freeze_splits(ids, path, "public-fixture")
    assert split == corpus.freeze_splits(list(reversed(ids)), path, "public-fixture")
    assert {key: len(value) for key, value in split.items()} == {"train": 218, "dev": 27, "test": 27}
    assert len(set(sum(split.values(), []))) == 272
    with pytest.raises(ValueError):
        corpus.freeze_splits(ids, path, "another-experiment")


def test_archive_traversal_and_changed_same_size_member_rejected(tmp_path):
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../escaped.txt", "no")
    with pytest.raises(ValueError):
        corpus.safe_extract(bad, tmp_path / "extract")
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as archive:
        archive.writestr("file.txt", "original")
    corpus.safe_extract(good, tmp_path / "extract")
    (tmp_path / "extract/file.txt").write_text("modified")
    with pytest.raises(ValueError, match="differs"):
        corpus.safe_extract(good, tmp_path / "extract")


def test_download_checks_content_and_never_overwrites(tmp_path, monkeypatch):
    class Response(io.BytesIO):
        status = 200
        headers = {}
    monkeypatch.setattr(download.urllib.request, "urlopen", lambda *a, **k: Response(b"approved"))
    path = tmp_path / "source"
    sha = hashlib.sha256(b"approved").hexdigest()
    assert download.download("https://fixture.invalid/source", path, sha)["state"] == "downloaded_verified"
    assert download.download("https://fixture.invalid/source", path, sha)["state"] == "verified_existing"
    with pytest.raises(ValueError, match="no overwrite"):
        download.download("https://fixture.invalid/source", path, "0" * 64)
    with pytest.raises(ValueError, match="hash mismatch"):
        download.download("https://fixture.invalid/source", tmp_path / "mismatch", "0" * 64)
    assert not (tmp_path / "mismatch").exists()


def test_native_flac_metadata_without_decoder(tmp_path):
    header = bytearray(42)
    header[:8] = b"fLaC\x00\x00\x00\x22"
    header[18:26] = ((16000 << 44) | 20000).to_bytes(8, "big")
    path = tmp_path / "fixture.flac"
    path.write_bytes(header)
    assert replay.flac_info(path) == {"duration": 1.25, "sample_rate": 16000, "channels": 1}


def test_replay_selection_is_seeded_and_keeps_whole_utterances():
    rows = [{"id": f"u{i}", "duration": 20 + i % 10} for i in range(30)]
    selected = replay.choose_hours(rows, .05, "fixture")
    assert selected == replay.choose_hours(list(reversed(rows)), .05, "fixture")
    assert sum(r["duration"] for r in selected[:-1]) < 180 <= sum(r["duration"] for r in selected)


def test_textgrid_preserves_quote_and_negation():
    text = 'intervals [1]:\n xmin = 1.0\n xmax = 2.0\n text = "No ""fever""."'
    assert external.textgrid_intervals(text) == [(1., 2., 'No "fever".')]


def test_reference_annotation_never_claims_train_consumption():
    row = annotate({"id": "x", "text": "No metformin.", "split": "train"}, {"categories": {"drug": ["metformin"]}})
    assert row["example_exposure"] == "training_manifest_membership_only"
    assert row["keywords"] == [{"text": "metformin", "category": "drug"}]


def test_dev_selection_is_reference_only_and_bounded():
    rows = [{"id": str(i), "source_word_start": i, "duration": 10, "text": "metformin" if i == 2 else "hello"} for i in range(6)]
    chosen, audit = select_dev.select(rows, {"categories": {"drug": ["metformin"]}})
    assert [row["id"] for row in chosen] == ["1", "2", "3"]
    assert audit["seconds"] == 30
    assert select_dev.select(list(reversed(rows)), {"categories": {"drug": ["metformin"]}}) == (chosen, audit)


def test_upload_refuses_reference_outside_prepared_root(tmp_path):
    manifest = tmp_path / "source.jsonl"
    manifest.write_text(json.dumps({"audio_filepath": "/etc/passwd"}) + "\n")
    with pytest.raises(ValueError):
        inputs(tmp_path, ["source.jsonl"], [])


@pytest.mark.parametrize("code", ["412", "PreconditionFailed", "KeyAlreadyExists"])
@pytest.mark.parametrize("corrupt", [False, True])
def test_upload_collision_requires_full_content_match(tmp_path, monkeypatch, code, corrupt):
    import io
    from types import SimpleNamespace
    import boto3
    from botocore.exceptions import ClientError
    from botocore.response import StreamingBody
    import upload_inputs

    audio = tmp_path / "approved.wav"
    audio.write_bytes(b"synthetic fixture bytes")
    manifest = tmp_path / "source.jsonl"
    manifest.write_text(json.dumps({"audio_filepath": "/data/clinical-speech/approved.wav"}) + "\n")
    receipt = tmp_path / "receipt.json"
    registered = []

    class ExistingOnly:
        exceptions = SimpleNamespace(ClientError=ClientError)
        meta = SimpleNamespace(events=SimpleNamespace(register=lambda event, handler: registered.append((event, handler))))

        def put_object(self, **kwargs):
            raise ClientError({"Error": {"Code": code}}, "PutObject")

        def get_object(self, **kwargs):
            body = (tmp_path / kwargs["Key"]).read_bytes()
            if corrupt:
                body += b"changed"
            return {"Body": StreamingBody(io.BytesIO(body), len(body)), "ContentLength": len(body)}

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: ExistingOnly())
    monkeypatch.setenv("AWS_ENDPOINT_URL", "https://invalid.example")
    monkeypatch.setattr(sys, "argv", ["upload_inputs.py", "--data-root", str(tmp_path),
        "--bucket", "synthetic", "--manifest", "source.jsonl", "--receipt", str(receipt)])
    if corrupt:
        with pytest.raises(ValueError, match="mismatch; no overwrite"):
            upload_inputs.main()
        assert not receipt.exists()
    else:
        upload_inputs.main()
        assert all(row["state"] == "verified_existing" for row in json.loads(receipt.read_text())["objects"])
    assert registered[0][0] == "before-sign.s3.PutObject"
    request = SimpleNamespace(headers={})
    registered[0][1](request)
    assert request.headers["If-None-Match"] == "*"


def test_paired_scoring_fails_on_missing_ids_or_audio_mismatch():
    refs = {"x": {"id": "x", "text": "No metformin"}}
    with pytest.raises(ValueError, match="ID sets"):
        paired_scores(refs, {}, {})
    with pytest.raises(ValueError, match="input hashes"):
        paired_scores(refs, {"x": {"input_sha256": "a"}}, {"x": {"input_sha256": "b"}})


def test_paired_score_preserves_worse_result_and_checkpoint_identity():
    ref = {"x": {"id": "x", "text": "No metformin", "audio_sha256": "audio", "keywords": [{"text": "metformin"}]}}
    runtime = {"base_model": "fixture", "base_revision": "revision", "nemo_revision": "nemo", "precision": "float32", "chunk_size_ms": 560, "language": "en-US"}
    base = {"x": {"input_sha256": "audio", "text": "No metformin", "runtime": {**runtime, "checkpoint_sha256": "base", "fine_tuned": False}}}
    tuned = {"x": {"input_sha256": "audio", "text": "", "runtime": {**runtime, "checkpoint_sha256": "tuned", "fine_tuned": True}}}
    result = paired_scores(ref, base, tuned)
    assert result["base"]["aggregate"]["wer"] == 0
    assert result["tuned"]["aggregate"]["wer"] == 1
    assert result["tuned"]["aggregate"]["clinical_keywords"]["keyword_error_rate"] == 1
    tuned["x"]["runtime"]["chunk_size_ms"] = 320
    with pytest.raises(ValueError, match="setting"):
        paired_scores(ref, base, tuned)


def test_public_evaluation_cli_roundtrip(tmp_path):
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"conversation_id": "fixture", "split": "dev", "text": "source reference"}) + "\n")
    rows = [{"id": f"fixture_{i}", "conversation_id": "fixture", "split": "dev", "source_word_start": i * 4,
             "text": "No metformin" if i == 2 else "hello there", "duration": 10., "audio_filepath": f"/approved/{i}.wav",
             "audio_sha256": f"audio{i}"} for i in range(6)]
    aligned = tmp_path / "aligned.jsonl"
    aligned.write_text("".join(json.dumps(row) + "\n" for row in rows))
    selected = tmp_path / "selected.jsonl"
    subprocess.run([sys.executable, str(RECIPE / "evaluation/select_dev.py"), "--source-dev", str(source), "--aligned-dev", str(aligned), "--output", str(selected)], check=True, capture_output=True)
    refs = [json.loads(line) for line in selected.read_text().splitlines()]
    runtime = {"base_model": "fixture", "base_revision": "revision", "nemo_revision": "nemo", "precision": "float32", "chunk_size_ms": 560, "language": "en-US"}
    for label in ("base", "tuned"):
        predictions = [{"id": row["id"], "text": row["text"] if label == "base" else "", "input_sha256": row["audio_sha256"],
                        "runtime": {**runtime, "checkpoint_sha256": label, "fine_tuned": label == "tuned"}} for row in refs]
        (tmp_path / (label + ".jsonl")).write_text("".join(json.dumps(row) + "\n" for row in predictions))
    output = tmp_path / "scores.json"
    command = [sys.executable, str(RECIPE / "evaluation/score_pair.py"), "--reference", str(selected), "--base", str(tmp_path / "base.jsonl"), "--tuned", str(tmp_path / "tuned.jsonl"), "--output", str(output)]
    subprocess.run(command, check=True, capture_output=True)
    result = json.loads(output.read_text())
    assert result["scores"]["base"]["aggregate"]["wer"] == 0
    assert result["scores"]["tuned"]["aggregate"]["wer"] == 1
    assert subprocess.run(command, capture_output=True).returncode != 0
