"""Audit actual completed training batches without modifying the data loader.

The pinned RNNT prompt loader returns tensors, not source cut IDs. Match exact
reference token vectors AND audio sample lengths to the original manifest.
Ambiguous matches are never reported as a uniquely consumed source segment.
"""
import hashlib
import json
import wave


def reference_key(token_ids, samples):
    token_hash = hashlib.sha256(json.dumps(list(token_ids), separators=(",", ":")).encode()).hexdigest()
    return token_hash, int(samples)


class ConsumptionAudit:
    def __init__(self, rows, tokenize, output):
        self.output = output
        if output.exists():
            raise ValueError("consumption_audit_path_exists_new_attempt_required")
        self.matches = {}
        for row in rows:
            with wave.open(row["audio_filepath"], "rb") as audio:
                samples = audio.getnframes()
                if audio.getframerate() != 16000:
                    raise ValueError("consumption_audit_requires_16khz")
            key = reference_key(tokenize(row["text"], row["target_lang"]), samples)
            self.matches.setdefault(key, []).append({
                "id": row.get("id", row.get("conversation_id")),
                "audio_filepath": row["audio_filepath"],
                "conversation_id": row["conversation_id"],
                "training_corpus": row.get("training_corpus"),
                "source_word_start": row.get("source_word_start"),
                "source_word_end_exclusive": row.get("source_word_end_exclusive"),
            })

    def record(self, token_rows, sample_lengths, *, batch_index, step_before, step_after):
        records = []
        for token_ids, samples in zip(token_rows, sample_lengths):
            key = reference_key(token_ids, samples)
            candidates = self.matches.get(key, [])
            records.append({
                "batch_index": batch_index,
                "global_step_before": step_before, "global_step_after": step_after,
                "reference_token_sha256": key[0], "audio_samples": key[1],
                "match": "unique" if len(candidates) == 1 else "ambiguous" if candidates else "unmatched",
                "candidate_segments": candidates,
                "scope": "completed_training_batch; filter global_step_before below selected_checkpoint_step",
            })
        with self.output.open("a") as target:
            for record in records:
                target.write(json.dumps(record) + "\n")
            target.flush()
        return records
