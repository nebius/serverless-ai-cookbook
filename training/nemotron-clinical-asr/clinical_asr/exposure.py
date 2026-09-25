"""Aggregate real completed-batch exposure, never manifest membership claims."""


class ExposureCounter:
    def __init__(self):
        self.samples = {"clinical": 0, "general_replay": 0, "unresolved": 0}
        self.events = {key: 0 for key in self.samples}
        self.corpus_samples = {}
        self.corpus_events = {}

    def update(self, records):
        for record in records:
            domains = {"general_replay" if str(c["conversation_id"]).startswith("librispeech-train-clean100:")
                       else "clinical" for c in record["candidate_segments"]}
            domain = next(iter(domains)) if len(domains) == 1 else "unresolved"
            self.samples[domain] += record["audio_samples"]
            self.events[domain] += 1
            corpora = {candidate.get("training_corpus") for candidate in record["candidate_segments"]}
            corpus = next(iter(corpora)) if len(corpora) == 1 and None not in corpora else "unresolved"
            self.corpus_samples[corpus] = self.corpus_samples.get(corpus, 0) + record["audio_samples"]
            self.corpus_events[corpus] = self.corpus_events.get(corpus, 0) + 1

    def summary(self, step):
        total = sum(self.samples.values())
        return {"global_step": step, "events": dict(self.events),
                "audio_seconds": {k: v / 16000 for k, v in self.samples.items()},
                "replay_audio_fraction": self.samples["general_replay"] / total if total else None,
                "corpus_audio_seconds": {k: v / 16000 for k, v in self.corpus_samples.items()},
                "corpus_events": dict(self.corpus_events),
                "scope": "actual completed batches; ambiguous same-domain matches counted only at domain level"}

    def validate(self, expected, step, require_by):
        if expected == "clinical-only" and self.events["general_replay"]:
            raise RuntimeError("unexpected_replay_in_clinical_only_run")
        if expected == "mixed" and step >= require_by and not self.events["general_replay"]:
            raise RuntimeError("actual_replay_not_consumed_by_required_step")

    def validate_corpora(self, required, step, require_by):
        if step >= require_by and any(self.corpus_samples.get(corpus, 0) <= 0 for corpus in required):
            raise RuntimeError("required_training_corpus_not_actually_consumed")
