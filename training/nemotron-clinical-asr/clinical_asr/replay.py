"""Mix replay before a bounded-buffer sampler, without changing row membership."""
import hashlib
import json
import os
import random
from pathlib import Path

from .common import read_jsonl, sha256_file


def _row_hashes(rows):
    return [hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode()).hexdigest() for row in rows]


def _hash_order(hashes):
    return hashlib.sha256("\n".join(hashes).encode()).hexdigest()


def mix_replay_manifest(train_manifest, replay_rows, *, seed):
    """Seeded full-manifest shuffle; expose every cohort to the initial buffer.

    This makes replay eligible for sampling. Only the actual consumed-batch
    ledger establishes whether/how much replay a finite training run consumed.
    The generated training manifest changes; source manifests/audio do not.
    """
    if not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        raise ValueError("training_seed_requires_uint32")
    path = Path(train_manifest)
    clinical_rows = read_jsonl(path)
    if not clinical_rows or not replay_rows:
        raise ValueError("replay_mix_requires_both_cohorts")
    original = clinical_rows + list(replay_rows)
    if any(row.get("split") != "train" for row in original):
        raise ValueError("replay_mix_accepts_training_rows_only")
    input_hashes = _row_hashes(original)
    mixed = list(original)
    random.Random(seed).shuffle(mixed)
    output_hashes = _row_hashes(mixed)
    membership_sha = _hash_order(sorted(input_hashes))
    if membership_sha != _hash_order(sorted(output_hashes)):
        raise RuntimeError("replay_mix_changed_membership")
    provenance = {
        "strategy": "seeded_full_manifest_shuffle_v1", "seed": seed,
        "clinical_rows": len(clinical_rows), "replay_rows": len(replay_rows),
        "total_rows": len(mixed),
        "clinical_manifest_before_mix_sha256": sha256_file(path),
        "input_membership_sha256": membership_sha,
        "output_membership_sha256": _hash_order(sorted(output_hashes)),
        "input_order_sha256": _hash_order(input_hashes),
        "output_order_sha256": _hash_order(output_hashes),
        "row_hash_format": "SHA256(canonical_JSON_full_row); membership=SHA256(sorted_row_hashes_joined_by_newline)",
        "qualification": "manifest_membership_and_order_only; actual_replay_consumption_requires_batch_ledger",
    }
    temp = path.with_suffix(path.suffix + ".mixing.tmp")
    with temp.open("w", encoding="utf-8") as output:
        for row in mixed:
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)
    provenance["mixed_manifest_sha256"] = sha256_file(path)
    return provenance
