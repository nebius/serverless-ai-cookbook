"""One-GPU full-parameter adaptation retaining the pretrained tokenizer/prompts."""
import argparse
import json
import time
from pathlib import Path

from . import NEMO_REVISION
from .common import base_checkpoint, read_jsonl, sha256_file, write_json
from .families import FAMILIES, assert_training_model, family_spec, training_batch_evidence


def validate_manifests(train_path, dev_path):
    train, dev = read_jsonl(train_path), read_jsonl(dev_path)
    if not train or not dev:
        raise ValueError("train_and_dev_must_be_nonempty")
    train_ids = {r["conversation_id"] for r in train}
    dev_ids = {r["conversation_id"] for r in dev}
    if train_ids & dev_ids:
        raise ValueError("conversation_leakage")
    if any(row.get("split") != "train" for row in train) or any(row.get("split") != "dev" for row in dev):
        raise ValueError("explicit_train_dev_split_required")
    for row in train + dev:
        if not 0.5 <= row["duration"] <= 30.0 or not row["text"].strip():
            raise ValueError("invalid_segment")
        if row.get("target_lang") != "en-US" or not Path(row["audio_filepath"]).is_file():
            raise ValueError("missing_audio_or_language")
    return train, dev


def dataset_configs(model_config, args):
    """Resolve only dataset templates against the actual restored architecture."""
    from omegaconf import OmegaConf
    family = family_spec(args.model_family)
    template = OmegaConf.load("/opt/nemo/examples/asr/conf/fastconformer/cache_aware_streaming/" + family.training_template)
    merged = OmegaConf.create({"model": OmegaConf.to_container(model_config, resolve=True)})
    merged.model.train_ds = template.model.train_ds
    merged.model.validation_ds = template.model.validation_ds
    for config, path, training in [(merged.model.train_ds, args.train_manifest, True),
                                   (merged.model.validation_ds, args.dev_manifest, False)]:
        OmegaConf.set_struct(config, False)
        config.manifest_filepath = str(Path(path).resolve())
        config.is_tarred = False
        config.tarred_audio_filepaths = None
        config.num_workers = 0
        config.pin_memory = True
        config.max_duration = 30.0
        config.min_duration = 0.5
        config.lang_field = "target_lang"
        if args.model_family == "nemotron35":
            config.default_prompt_mode = "langID"
        else:
            # The upstream English config uses `answer`; our paired manifests
            # use `text`. Do not inject multilingual prompt tokens.
            config.text_field = "text"
        config.shuffle = training
        # Lhotse otherwise resets the process seed to 0 and uses entropy-based
        # shard shuffling, independently of Lightning's seed_everything call.
        config.seed = args.seed
        config.shard_seed = args.seed
        config.use_lhotse = True
        config.use_bucketing = training
        if training:
            config.batch_duration = args.batch_duration
            config.num_buckets = 10
        else:
            config.batch_size = 1
    return tuple(OmegaConf.create(OmegaConf.to_container(config, resolve=True))
                 for config in (merged.model.train_ds, merged.model.validation_ds))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-manifest", required=True)
    parser.add_argument("--dev-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-family", choices=sorted(FAMILIES), default="nemotron35")
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--val-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--batch-duration", type=float, default=60)
    parser.add_argument("--accumulate-grad-batches", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--checkpoint-every", type=int, default=0, help="Verified S3 optimizer snapshot interval in steps; 0 disables for short smoke")
    parser.add_argument("--resume-pointer", help="Explicit S3 latest.json pointer; never automatically resume unrelated jobs")
    parser.add_argument("--expected-data-mix", choices=["unspecified", "clinical-only", "mixed"], default="unspecified")
    parser.add_argument("--require-replay-by-step", type=int, default=50,
                        help="Mixed runs fail if no real replay batch consumption by this step")
    parser.add_argument("--require-training-corpus", action="append", default=[],
                        choices=["simulated_clinical", "primock57", "librispeech_replay"],
                        help="Optional component exposure guard at require-replay-by-step; manifest membership is not enough")
    args = parser.parse_args()
    family = family_spec(args.model_family)
    train_rows, dev_rows = validate_manifests(args.train_manifest, args.dev_manifest)
    if not set(args.require_training_corpus) <= {row.get("training_corpus") for row in train_rows}:
        raise ValueError("required_training_corpus_absent_from_manifest")
    if args.max_steps < 1 or args.val_every < 1 or args.require_replay_by_step < 1:
        raise ValueError("positive_steps_required")
    import torch
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import ModelCheckpoint, LearningRateMonitor
    from lightning.pytorch.loggers import CSVLogger
    from nemo.collections.asr.models import ASRModel
    from omegaconf import OmegaConf

    def record_timing(phase, started, **details):
        record = {"phase": phase, "elapsed_seconds": time.monotonic() - started,
                  "finished_at_unix": time.time(), **details}
        with (output / "wall-times.jsonl").open("a") as target:
            target.write(json.dumps(record) + "\n")
        print(json.dumps({"timing": record}), flush=True)

    class TimedCheckpoint(ModelCheckpoint):
        def _save_checkpoint(self, trainer, filepath):
            started = time.monotonic()
            try:
                super()._save_checkpoint(trainer, filepath)
            finally:
                record_timing("local_lightning_checkpoint", started, global_step=trainer.global_step,
                              filename=Path(filepath).name)

    class WallTimes(pl.Callback):
        def on_train_batch_start(self, trainer, module, batch, batch_idx):
            torch.cuda.synchronize()
            self.batch_started = time.monotonic()

        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            torch.cuda.synchronize()
            record_timing("training_batch", self.batch_started, global_step=trainer.global_step,
                          batch_index=batch_idx, cuda_synchronized=True)

        def on_validation_start(self, trainer, module):
            torch.cuda.synchronize()
            self.validation_started = time.monotonic()

        def on_validation_end(self, trainer, module):
            torch.cuda.synchronize()
            record_timing("validation_total", self.validation_started, global_step=trainer.global_step,
                          sanity_check=trainer.sanity_checking, includes_callbacks=True, cuda_synchronized=True)

    class FiniteLoss(pl.Callback):
        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            loss = outputs.get("loss") if isinstance(outputs, dict) else outputs
            if loss is not None and not torch.isfinite(loss).all():
                raise RuntimeError("nonfinite_training_loss")

    manifest_hashes = {"train": sha256_file(args.train_manifest), "dev": sha256_file(args.dev_manifest)}

    class PeriodicSnapshot(pl.Callback):
        last_step = -1
        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            step = trainer.global_step
            if args.checkpoint_every and step > 0 and step != self.last_step and step % args.checkpoint_every == 0:
                from .checkpoints import publish_resume_checkpoint
                started = time.monotonic()
                try:
                    publish_resume_checkpoint(trainer, output / "resume", manifest_hashes=manifest_hashes, base_revision=family.revision)
                finally:
                    record_timing("durable_resume_checkpoint_with_S3_readback", started, global_step=step)
                self.last_step = step

    class ConsumedReferences(pl.Callback):
        audit = None
        step_before = 0

        def on_train_start(self, trainer, module):
            from nemo.collections.common.tokenizers.aggregate_tokenizer import TokenizerWrapper
            from .consumption import ConsumptionAudit
            self.audit = ConsumptionAudit(train_rows, TokenizerWrapper(module.tokenizer),
                                          output / "consumed-training-segments.jsonl")
            from .exposure import ExposureCounter
            self.exposure = ExposureCounter()

        def on_train_batch_start(self, trainer, module, batch, batch_idx):
            self.step_before = trainer.global_step

        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            audio_lens, tokens, token_lens = training_batch_evidence(batch, args.model_family)
            token_rows = [row[:int(length)].detach().cpu().tolist() for row, length in zip(tokens, token_lens)]
            records = self.audit.record(token_rows, audio_lens.detach().cpu().tolist(), batch_index=batch_idx,
                                        step_before=self.step_before, step_after=trainer.global_step)
            self.exposure.update(records)
            if trainer.global_step == 1 or trainer.global_step % 25 == 0 or trainer.global_step == args.max_steps:
                summary = self.exposure.summary(trainer.global_step)
                write_json(output / "consumption-progress.json", summary)
                print(json.dumps({"actual_training_exposure": summary}), flush=True)
            self.exposure.validate(args.expected_data_mix, trainer.global_step,
                                   min(args.require_replay_by_step, args.max_steps))
            self.exposure.validate_corpora(args.require_training_corpus, trainer.global_step,
                                           min(args.require_replay_by_step, args.max_steps))

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pl.seed_everything(args.seed, workers=True)
    checkpoint = TimedCheckpoint(dirpath=output / "checkpoints", monitor="val_wer", mode="min",
                                 save_top_k=1, save_last=True, filename="step{step}-wer{val_wer:.4f}")
    trainer = pl.Trainer(
        accelerator="gpu", devices=1, precision="bf16-mixed", max_steps=args.max_steps,
        max_epochs=-1, accumulate_grad_batches=args.accumulate_grad_batches,
        gradient_clip_val=1.0, check_val_every_n_epoch=None,
        val_check_interval=min(args.val_every, args.max_steps) * args.accumulate_grad_batches,
        num_sanity_val_steps=2, log_every_n_steps=1, enable_progress_bar=False,
        callbacks=[checkpoint, FiniteLoss(), WallTimes(), ConsumedReferences(), PeriodicSnapshot(), LearningRateMonitor(logging_interval="step")],
        logger=CSVLogger(str(output), name="metrics"),
    )
    base = base_checkpoint(args.model_family)
    model = ASRModel.restore_from(base, map_location="cpu")
    assert_training_model(model, args.model_family)
    model.set_trainer(trainer)
    model.cfg.log_prediction = False
    # The WER metric was already constructed during restore; changing cfg alone
    # does not change its live logging flag.
    model.wer.log_prediction = False
    train_cfg, dev_cfg = dataset_configs(model.cfg, args)
    model.setup_training_data(train_cfg)
    model.setup_multiple_validation_data(dev_cfg)
    model.setup_optimization(OmegaConf.create({
        "name": "adamw", "lr": args.learning_rate, "betas": [0.9, 0.98], "weight_decay": 0.01,
        "sched": {"name": "CosineAnnealing", "warmup_steps": min(100, max(1, args.max_steps // 10)),
                  "max_steps": args.max_steps, "min_lr": args.learning_rate / 10},
    }))
    # Preserve cache-aware architecture, vocabulary, language IDs and context configuration.
    OmegaConf.save(model.cfg, output / "resolved-model-config.yaml")
    provenance = {
        "base_model": family.repository, "base_revision": family.revision,
        "model_family": args.model_family, "restored_model_class": type(model).__name__,
        "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "total_parameters": sum(p.numel() for p in model.parameters()),
        "base_sha256": sha256_file(base), "nemo_revision": NEMO_REVISION,
        "train_manifest_sha256": sha256_file(args.train_manifest),
        "dev_manifest_sha256": sha256_file(args.dev_manifest),
        "train_segments": len(train_rows), "dev_segments": len(dev_rows),
        "parameters": vars(args), "status": "training", "clinical_validation": "NOT_PERFORMED",
        "consumption_seen_claim_eligible": not bool(args.resume_pointer),
        "consumption_lineage": "fresh_uninterrupted_attempt" if not args.resume_pointer else "resumed_history_not_restored; seen_claims_disabled",
    }
    write_json(output / "training-provenance.json", provenance)
    resume = None
    if args.resume_pointer:
        from .checkpoints import stage_resume_checkpoint
        resume = stage_resume_checkpoint(args.resume_pointer, output, manifest_hashes=manifest_hashes, base_revision=family.revision)
    torch.cuda.reset_peak_memory_stats()
    try:
        trainer.fit(model, ckpt_path=resume)
    finally:
        write_json(output / "training-memory.json", {
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "allocated_bytes": torch.cuda.memory_allocated(),
            "reserved_bytes": torch.cuda.memory_reserved(),
            "scope": "training_process_since_fit_start_not_total_GPU_or_external_allocators",
            "gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
            "cuda_build": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
        })
    # Require a real finite validation metric; no promotion of unvalidated final step.
    if not checkpoint.best_model_path or checkpoint.best_model_score is None or not torch.isfinite(checkpoint.best_model_score):
        raise RuntimeError("no_finite_validation_checkpoint")
    selected_state = torch.load(checkpoint.best_model_path, map_location="cpu", weights_only=False)
    model.load_state_dict(selected_state["state_dict"])
    selected_step = int(selected_state["global_step"])
    del selected_state
    artifact = output / "nemotron-clinical-en.nemo"
    started = time.monotonic()
    model.save_to(str(artifact))
    record_timing("nemo_export", started, global_step=selected_step)
    provenance.update(status="completed", checkpoint_sha256=sha256_file(artifact),
                      checkpoint_filename=artifact.name, best_validation_wer=float(checkpoint.best_model_score),
                      selected_checkpoint_global_step=selected_step,
                      global_step=trainer.global_step, best_lightning_checkpoint=Path(checkpoint.best_model_path).name)
    write_json(output / "training-provenance.json", provenance)
    print("TRAINING_ARTIFACT", artifact.name, provenance["checkpoint_sha256"], flush=True)
