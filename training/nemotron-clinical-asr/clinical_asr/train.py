"""One-GPU full-parameter adaptation retaining the pretrained tokenizer/prompts."""
import argparse
from pathlib import Path

from . import BASE_REPOSITORY, BASE_REVISION, NEMO_REVISION
from .common import base_checkpoint, read_jsonl, sha256_file, write_json


def validate_manifests(train_path, dev_path):
    train, dev = read_jsonl(train_path), read_jsonl(dev_path)
    if not train or not dev:
        raise ValueError("train_and_dev_must_be_nonempty")
    train_ids = {r["conversation_id"] for r in train}
    dev_ids = {r["conversation_id"] for r in dev}
    if train_ids & dev_ids:
        raise ValueError("conversation_leakage")
    for row in train + dev:
        if not 0.5 <= row["duration"] <= 30.0 or not row["text"].strip():
            raise ValueError("invalid_segment")
        if row.get("target_lang") != "en-US" or not Path(row["audio_filepath"]).is_file():
            raise ValueError("missing_audio_or_language")
    return train, dev


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-manifest", required=True)
    parser.add_argument("--dev-manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--val-every", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--batch-duration", type=float, default=60)
    parser.add_argument("--accumulate-grad-batches", type=int, default=4)
    parser.add_argument("--seed", type=int, default=20260925)
    parser.add_argument("--checkpoint-every", type=int, default=0, help="Verified S3 optimizer snapshot interval in steps; 0 disables for short smoke")
    parser.add_argument("--resume-pointer", help="Explicit S3 latest.json pointer; never automatically resume unrelated jobs")
    args = parser.parse_args()
    train_rows, dev_rows = validate_manifests(args.train_manifest, args.dev_manifest)
    if args.max_steps < 1 or args.val_every < 1:
        raise ValueError("positive_steps_required")
    import torch
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import ModelCheckpoint, LearningRateMonitor
    from lightning.pytorch.loggers import CSVLogger
    from nemo.collections.asr.models import ASRModel
    from omegaconf import OmegaConf

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
                publish_resume_checkpoint(trainer, output / "resume", manifest_hashes=manifest_hashes, base_revision=BASE_REVISION)
                self.last_step = step

    class ConsumedReferences(pl.Callback):
        audit = None
        step_before = 0

        def on_train_start(self, trainer, module):
            from nemo.collections.common.tokenizers.aggregate_tokenizer import TokenizerWrapper
            from .consumption import ConsumptionAudit
            self.audit = ConsumptionAudit(train_rows, TokenizerWrapper(module.tokenizer),
                                          output / "consumed-training-segments.jsonl")

        def on_train_batch_start(self, trainer, module, batch, batch_idx):
            self.step_before = trainer.global_step

        def on_train_batch_end(self, trainer, module, outputs, batch, batch_idx):
            _, audio_lens, tokens, token_lens, _ = batch
            token_rows = [row[:int(length)].detach().cpu().tolist() for row, length in zip(tokens, token_lens)]
            self.audit.record(token_rows, audio_lens.detach().cpu().tolist(), batch_index=batch_idx,
                              step_before=self.step_before, step_after=trainer.global_step)

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pl.seed_everything(args.seed, workers=True)
    checkpoint = ModelCheckpoint(dirpath=output / "checkpoints", monitor="val_wer", mode="min",
                                 save_top_k=1, save_last=True, filename="step{step}-wer{val_wer:.4f}")
    trainer = pl.Trainer(
        accelerator="gpu", devices=1, precision="bf16-mixed", max_steps=args.max_steps,
        max_epochs=-1, accumulate_grad_batches=args.accumulate_grad_batches,
        gradient_clip_val=1.0, check_val_every_n_epoch=None,
        val_check_interval=min(args.val_every, args.max_steps) * args.accumulate_grad_batches,
        num_sanity_val_steps=2, log_every_n_steps=1, enable_progress_bar=False,
        callbacks=[checkpoint, FiniteLoss(), ConsumedReferences(), PeriodicSnapshot(), LearningRateMonitor(logging_interval="step")],
        logger=CSVLogger(str(output), name="metrics"),
    )
    base = base_checkpoint()
    model = ASRModel.restore_from(base, map_location="cpu")
    model.set_trainer(trainer)
    model.cfg.log_prediction = False
    # The WER metric was already constructed during restore; changing cfg alone
    # does not change its live logging flag.
    model.wer.log_prediction = False
    # Resolve dataset interpolations against ACTUAL checkpoint architecture/prompts.
    template = OmegaConf.load("/opt/nemo/examples/asr/conf/fastconformer/cache_aware_streaming/fastconformer_transducer_bpe_streaming_prompt.yaml")
    merged = OmegaConf.create({"model": OmegaConf.to_container(model.cfg, resolve=True)})
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
        config.default_prompt_mode = "langID"
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
    train_cfg = OmegaConf.create(OmegaConf.to_container(merged.model.train_ds, resolve=True))
    dev_cfg = OmegaConf.create(OmegaConf.to_container(merged.model.validation_ds, resolve=True))
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
        "base_model": BASE_REPOSITORY, "base_revision": BASE_REVISION,
        "base_sha256": sha256_file(base), "nemo_revision": NEMO_REVISION,
        "train_manifest_sha256": sha256_file(args.train_manifest),
        "dev_manifest_sha256": sha256_file(args.dev_manifest),
        "train_segments": len(train_rows), "dev_segments": len(dev_rows),
        "parameters": vars(args), "status": "training", "clinical_validation": "NOT_PERFORMED",
    }
    write_json(output / "training-provenance.json", provenance)
    resume = None
    if args.resume_pointer:
        from .checkpoints import stage_resume_checkpoint
        resume = stage_resume_checkpoint(args.resume_pointer, output, manifest_hashes=manifest_hashes, base_revision=BASE_REVISION)
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
    model.save_to(str(artifact))
    provenance.update(status="completed", checkpoint_sha256=sha256_file(artifact),
                      checkpoint_filename=artifact.name, best_validation_wer=float(checkpoint.best_model_score),
                      selected_checkpoint_global_step=selected_step,
                      global_step=trainer.global_step, best_lightning_checkpoint=Path(checkpoint.best_model_path).name)
    write_json(output / "training-provenance.json", provenance)
    print("TRAINING_ARTIFACT", artifact.name, provenance["checkpoint_sha256"], flush=True)
