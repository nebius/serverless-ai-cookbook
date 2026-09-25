"""Aggregate real completed-batch exposure, never manifest membership claims."""


class ExposureCounter:
    def __init__(self):
        self.samples = {"clinical": 0, "general_replay": 0, "unresolved": 0}
        self.events = {key: 0 for key in self.samples}

    def update(self, records):
        for record in records:
            domains = {"general_replay" if str(c["conversation_id"]).startswith("librispeech-train-clean100:")
                       else "clinical" for c in record["candidate_segments"]}
            domain = next(iter(domains)) if len(domains) == 1 else "unresolved"
            self.samples[domain] += record["audio_samples"]
            self.events[domain] += 1

    def summary(self, step):
        total = sum(self.samples.values())
        return {"global_step": step, "events": dict(self.events),
                "audio_seconds": {k: v / 16000 for k, v in self.samples.items()},
                "replay_audio_fraction": self.samples["general_replay"] / total if total else None,
                "scope": "actual completed batches; ambiguous same-domain matches counted only at domain level"}

    def validate(self, expected, step, require_by):
        if expected == "clinical-only" and self.events["general_replay"]:
            raise RuntimeError("unexpected_replay_in_clinical_only_run")
        if expected == "mixed" and step >= require_by and not self.events["general_replay"]:
            raise RuntimeError("actual_replay_not_consumed_by_required_step")
