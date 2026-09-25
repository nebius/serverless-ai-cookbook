import hashlib
import json
from collections import Counter

import pytest

from clinical_asr.common import read_jsonl, sha256_file
from clinical_asr.replay import mix_replay_manifest


def manifest(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return path


def fixture_rows(cohort, count):
    return [{"id": f"{cohort}:{index}", "conversation_id": f"{cohort}:{index // 50}",
             "split": "train", "text": f"Keep Cased naïve target {index}, please!",
             "audio_filepath": f"/data/clinical-speech/{cohort}/{index}.wav",
             "duration": 3.25, "target_lang": "en-US", "source_word_start": index}
            for index in range(count)]


def canonical(rows):
    return Counter(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")) for row in rows)


def test_large_clinical_prefix_no_longer_hides_replay_from_initial_buffer(tmp_path):
    clinical = fixture_rows("clinical", 28809)
    replay = fixture_rows("librispeech-train-clean100", 2832)
    original = clinical + replay
    # Reproduce the source-order failure: even after refilling 3,735 records,
    # a 20,000-cut buffer cannot reach the old replay tail.
    assert all(row["id"].startswith("clinical:") for row in original[:20000 + 3735])
    path = manifest(tmp_path / "train.jsonl", clinical)
    before = sha256_file(path)
    provenance = mix_replay_manifest(path, replay, seed=20260925)
    mixed = read_jsonl(path)
    prefix_replay = [row for row in mixed[:20000] if row["id"].startswith("librispeech-")]
    assert len(prefix_replay) > 1000  # eligibility, NOT a GPU consumption claim
    assert canonical(mixed) == canonical(original)
    assert provenance["clinical_manifest_before_mix_sha256"] == before
    assert provenance["mixed_manifest_sha256"] == sha256_file(path)
    assert provenance["input_membership_sha256"] == provenance["output_membership_sha256"]
    assert provenance["input_order_sha256"] != provenance["output_order_sha256"]
    assert provenance["total_rows"] == 31641


def test_seed_and_full_row_membership_are_reproducible(tmp_path):
    clinical, replay = fixture_rows("clinical", 30), fixture_rows("replay", 5)
    a, b, c = (manifest(tmp_path / name, clinical) for name in ("a.jsonl", "b.jsonl", "c.jsonl"))
    first = mix_replay_manifest(a, replay, seed=42)
    same = mix_replay_manifest(b, replay, seed=42)
    other = mix_replay_manifest(c, replay, seed=43)
    assert a.read_bytes() == b.read_bytes()
    assert first == same
    assert first["mixed_manifest_sha256"] != other["mixed_manifest_sha256"]
    assert canonical(read_jsonl(a)) == canonical(read_jsonl(c)) == canonical(clinical + replay)
    assert first["seed"] == 42 and other["seed"] == 43


def test_membership_hash_is_independent_of_input_order_but_counts_duplicates(tmp_path):
    clinical, replay = fixture_rows("clinical", 3), fixture_rows("replay", 2)
    a = manifest(tmp_path / "a.jsonl", clinical)
    b = manifest(tmp_path / "b.jsonl", list(reversed(clinical)))
    c = manifest(tmp_path / "c.jsonl", clinical + [clinical[0]])
    first = mix_replay_manifest(a, replay, seed=0)
    reverse = mix_replay_manifest(b, replay, seed=0)
    duplicate = mix_replay_manifest(c, replay, seed=0)
    assert first["input_membership_sha256"] == reverse["input_membership_sha256"]
    assert first["input_membership_sha256"] != duplicate["input_membership_sha256"]
    assert first["input_order_sha256"] != reverse["input_order_sha256"]


@pytest.mark.parametrize("bad_split", ["dev", "test", None])
def test_replay_mix_rejects_nontraining_membership_without_overwriting(tmp_path, bad_split):
    clinical, replay = fixture_rows("clinical", 2), fixture_rows("replay", 1)
    replay[0]["split"] = bad_split
    path = manifest(tmp_path / "train.jsonl", clinical)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="training_rows_only"):
        mix_replay_manifest(path, replay, seed=20260925)
    assert path.read_bytes() == before


@pytest.mark.parametrize("seed", [-1, 2**32, "42"])
def test_invalid_seed_does_not_modify_manifest(tmp_path, seed):
    path = manifest(tmp_path / "train.jsonl", fixture_rows("clinical", 1))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="seed_requires_uint32"):
        mix_replay_manifest(path, fixture_rows("replay", 1), seed=seed)
    assert sha256_file(path) == before
