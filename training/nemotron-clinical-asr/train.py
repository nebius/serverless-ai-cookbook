"""Finite English Nemotron fine-tuning from labelled, bucket-mounted WAVs."""
import argparse
import hashlib
import json
import math
import tempfile
import uuid
import wave
from pathlib import Path

MODEL = "nvidia/nemotron-speech-streaming-en-0.6b"
REVISION = "ebe59e5a817142986528bbbee5dba8db7b38ed50"
FILENAME = "nemotron-speech-streaming-en-0.6b.nemo"
BASE_SHA256 = "283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd"


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_manifest(path, root):
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("manifest exceeds 8 MiB")
    rows, seen = [], set()
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != {"audio_filepath", "text", "conversation_id"}:
            raise ValueError("expected audio_filepath, text, conversation_id")
        if not all(isinstance(value, str) and value.strip() for value in row.values()):
            raise ValueError("all fields must be nonempty strings")
        relative = Path(row["audio_filepath"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("audio",):
            raise ValueError("audio must be a relative path below audio/")
        audio = (root / relative).resolve(strict=True)
        if not audio.is_relative_to(root.resolve()) or audio in seen:
            raise ValueError("escaped or duplicate audio path")
        with wave.open(str(audio)) as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (16000, 1, 2, "NONE"):
                raise ValueError("expected mono 16 kHz PCM16 WAV")
            duration = wav.getnframes() / 16000
            pcm = wav.readframes(min(wav.getnframes(), 30 * 16000 + 1))
            if wav.getnframes() > 30 * 16000 or len(pcm) != wav.getnframes() * 2:
                raise ValueError("truncated or oversized PCM data")
        if not 0.5 <= duration <= 30:
            raise ValueError("use complete labelled segments of 0.5–30 seconds")
        seen.add(audio)
        rows.append({**row, "audio_filepath": str(audio), "duration": duration,
                     "audio_sha256": digest(audio), "pcm_sha256": hashlib.sha256(pcm).hexdigest()})
    if not rows:
        raise ValueError("manifest must not be empty")
    return rows


def inputs(root):
    root = root.resolve(strict=True)
    train = read_manifest(root / "train.jsonl", root)
    validation = read_manifest(root / "validation.jsonl", root)
    for key in ("conversation_id", "audio_filepath", "pcm_sha256"):
        if {r[key] for r in train} & {r[key] for r in validation}:
            raise ValueError("training and validation must be disjoint by conversation and audio")
    return train, validation


def dataset_config(template, training):
    from omegaconf import OmegaConf
    # Resolve root-relative ${model.sample_rate} before detaching this subtree.
    cfg = OmegaConf.create(OmegaConf.to_container(template.model.train_ds if training else template.model.validation_ds, resolve=True))
    OmegaConf.set_struct(cfg, False)
    cfg.fault_tolerant_audio_loading = False
    return cfg


def run(root, output, steps, learning_rate):
    manifest_hashes = {name: digest(root / (name + ".jsonl")) for name in ("train", "validation")}
    train, validation = inputs(root)  # Before GPU imports/downloads.
    if any(digest(root / (name + ".jsonl")) != value for name, value in manifest_hashes.items()):
        raise ValueError("manifest changed while validating")
    if not 1 <= steps <= 100000 or not math.isfinite(learning_rate) or not 0 < learning_rate <= 0.01:
        raise ValueError("invalid finite training budget")
    output.mkdir(parents=True, exist_ok=False)
    import torch
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import ModelCheckpoint
    from lightning.pytorch.loggers import CSVLogger
    from huggingface_hub import hf_hub_download
    from nemo.collections.asr.models import ASRModel
    from omegaconf import OmegaConf

    base = Path(hf_hub_download(MODEL, FILENAME, revision=REVISION))
    if digest(base) != BASE_SHA256:
        raise ValueError("base checkpoint hash mismatch")
    pl.seed_everything(42, workers=True)
    model = ASRModel.restore_from(str(base), map_location="cpu")
    if type(model).__name__ != "EncDecRNNTBPEModel":
        raise ValueError("wrong model family")
    checkpoint = ModelCheckpoint(dirpath=output / "checkpoints", monitor="val_wer", mode="min", save_top_k=1)
    trainer = pl.Trainer(accelerator="gpu", devices=1, precision="bf16-mixed", max_steps=steps,
        max_epochs=-1, accumulate_grad_batches=4, gradient_clip_val=1.0,
        check_val_every_n_epoch=None, val_check_interval=min(50, steps) * 4,
        num_sanity_val_steps=2, callbacks=[checkpoint], enable_progress_bar=False,
        logger=CSVLogger(str(output), name="metrics"))
    model.set_trainer(trainer)
    model.cfg.log_prediction = False
    model.wer.log_prediction = False
    template = OmegaConf.load("/opt/nemo/examples/asr/conf/fastconformer/cache_aware_streaming/fastconformer_transducer_bpe_streaming.yaml")
    with tempfile.TemporaryDirectory(prefix="nemotron-manifests-") as directory:
        for name, rows, training in (("train", train, True), ("validation", validation, False)):
            path = Path(directory) / (name + ".jsonl")
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            cfg = dataset_config(template, training)
            cfg.manifest_filepath, cfg.text_field = str(path), "text"
            cfg.is_tarred, cfg.tarred_audio_filepaths = False, None
            cfg.num_workers, cfg.pin_memory, cfg.use_lhotse = 0, True, True
            cfg.min_duration, cfg.max_duration, cfg.shuffle = 0.5, 30.0, training
            cfg.seed, cfg.shard_seed, cfg.use_bucketing = 42, 42, training
            if training:
                cfg.batch_duration, cfg.num_buckets = 60, 10
                model.setup_training_data(cfg)
            else:
                cfg.batch_size = 1
                model.setup_multiple_validation_data(cfg)
        model.setup_optimization(OmegaConf.create({"name": "adamw", "lr": learning_rate,
            "betas": [0.9, 0.98], "weight_decay": 0.01,
            "sched": {"name": "CosineAnnealing", "warmup_steps": min(100, max(1, steps // 10)),
                      "max_steps": steps, "min_lr": learning_rate / 10}}))
        trainer.fit(model)
    if not checkpoint.best_model_path or checkpoint.best_model_score is None or not torch.isfinite(checkpoint.best_model_score):
        raise RuntimeError("no finite validation checkpoint; no model exported")
    selected = torch.load(checkpoint.best_model_path, map_location="cpu", weights_only=False)
    if any(value.is_floating_point() and not torch.isfinite(value).all() for value in selected["state_dict"].values()):
        raise RuntimeError("nonfinite selected weights; no model exported")
    model.load_state_dict(selected["state_dict"])
    artifact = output / "model.nemo"
    model.save_to(str(artifact))
    sha = digest(artifact)
    (output / "model.sha256").write_text(sha + "  model.nemo\n")
    (output / "result.json").write_text(json.dumps({"checkpoint_sha256": sha,
        "parent": MODEL, "revision": REVISION, "steps": trainer.global_step,
        "selected_step": int(selected["global_step"]), "validation_wer": float(checkpoint.best_model_score),
        "train_manifest_sha256": manifest_hashes["train"],
        "validation_manifest_sha256": manifest_hashes["validation"],
        "clinical_validation": "not_performed"}, indent=2) + "\n")
    print("Checkpoint:", artifact, "SHA256:", sha)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("/data"))
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    args = parser.parse_args()
    run(args.data, args.data / "runs" / uuid.uuid4().hex, args.steps, args.learning_rate)
