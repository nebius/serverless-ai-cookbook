"""Explicit English parent-weights initialization, never optimizer resumption.

Defaults remain upstream initialization. A SHA pin proves bytes, not licensing,
data admission or model quality; the caller must separately qualify those.
"""
import hashlib
import json
import math
from pathlib import Path
import re

from .common import sha256_file
from .families import assert_training_model


def validate_options(location, checksum, *, model_family, resume_pointer=None):
    if location is None and checksum is None:
        return False
    if not isinstance(location, str) or not location or not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-f]{64}", checksum):
        raise ValueError("parent_weights_location_and_sha256_required_together")
    if model_family != "english_specialist" or resume_pointer:
        raise ValueError("parent_weights_require_english_and_fresh_optimizer_not_resume")
    return True


def checked_path(location, checksum):
    path = Path(location).resolve(strict=True)
    if not path.is_file() or sha256_file(path) != checksum:
        raise ValueError("parent_weights_sha256_mismatch")
    return path


def model_signature(model):
    """Compare live restored identity, including the actual SentencePiece bytes."""
    from omegaconf import OmegaConf
    processor = getattr(model.tokenizer, "tokenizer", None)
    proto = processor.serialized_model_proto() if processor is not None else None
    if not isinstance(proto, bytes) or not proto:
        raise ValueError("native_sentencepiece_bytes_required")
    cfg = OmegaConf.to_container(model.cfg, resolve=True)
    keys = ("preprocessor", "encoder", "decoder", "joint", "decoding")
    if any(key not in cfg or cfg[key] is None for key in keys):
        raise ValueError("complete_native_architecture_config_required")
    # Tokenizer artifact file paths intentionally vary after .nemo restoration;
    # actual serialized tokenizer content above is the stronger identity check.
    architecture = {key: cfg[key] for key in keys}
    state = {key: {"shape": list(value.shape), "dtype": str(value.dtype)}
             for key, value in model.state_dict().items()}
    return {"model_class": type(model).__name__, "tokenizer_sha256": hashlib.sha256(proto).hexdigest(),
            "architecture_sha256": hashlib.sha256(json.dumps(architecture, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
            "state_schema": state}


def validate_signatures(base, parent):
    for key in ("model_class", "tokenizer_sha256", "architecture_sha256", "state_schema"):
        if key not in base or key not in parent or not base[key] or base[key] != parent[key]:
            raise ValueError("parent_weights_identity_mismatch:" + key)


def restore_parent(base_model, location, checksum, *, model_family, restore):
    """`restore` is the actual ASRModel.restore_from; no Trainer/optimizer load."""
    import torch
    validate_options(location, checksum, model_family=model_family)
    path = checked_path(location, checksum)
    assert_training_model(base_model, model_family)
    parent = restore(str(path), map_location="cpu")
    assert_training_model(parent, model_family)
    base_signature, parent_signature = model_signature(base_model), model_signature(parent)
    validate_signatures(base_signature, parent_signature)
    if any(not torch.isfinite(value).all().item() for value in parent.state_dict().values()
           if value.is_floating_point() or value.is_complex()):
        raise ValueError("parent_weights_nonfinite")
    return parent, {"mode": "parent_weights_fresh_optimizer", "parent_checkpoint_sha256": checksum,
                    "parent_checkpoint_filename": path.name,
                    "model_class": parent_signature["model_class"],
                    "tokenizer_sha256": parent_signature["tokenizer_sha256"],
                    "architecture_sha256": parent_signature["architecture_sha256"],
                    "state_schema_matches_upstream": True, "all_parent_floating_weights_finite": True,
                    "optimizer_restored": False, "scheduler_restored": False,
                    "step_counter_restored": False, "parent_exposure_in_current_ledger": False,
                    "parent_quality_or_training_data_approval": "NOT_ESTABLISHED_BY_INITIALIZATION"}


def check_baseline_result(results, *, examples, batches, expected_examples, global_step):
    if not isinstance(results, list) or len(results) != 1 or not isinstance(results[0], dict):
        raise ValueError("single_full_dev_validation_result_required")
    metric = results[0].get("val_wer")
    if isinstance(metric, bool) or not isinstance(metric, (int, float)) or not math.isfinite(metric) or metric < 0:
        raise ValueError("finite_parent_validation_wer_required")
    if type(expected_examples) is not int or expected_examples <= 0 or examples != expected_examples or batches != expected_examples:
        raise ValueError("full_parent_dev_batch1_coverage_required")
    if global_step != 0:
        raise ValueError("parent_baseline_must_not_optimize")
    return float(metric)


def validate_parent_development(model, *, main_trainer, expected_examples, model_family):
    """Separate validation-only Trainer: cannot seed candidate checkpoint selection."""
    import lightning.pytorch as pl
    from .families import training_batch_evidence
    class Coverage(pl.Callback):
        examples = 0
        batches = 0
        def on_validation_batch_end(self, trainer, module, outputs, batch, batch_idx, dataloader_idx=0):
            if dataloader_idx != 0:
                raise ValueError("one_parent_dev_loader_required")
            audio_lens, _, _ = training_batch_evidence(batch, model_family)
            self.examples += len(audio_lens)
            self.batches += 1
    coverage = Coverage()
    # No ModelCheckpoint, logger, optimizer fit or sanity subset. The exact
    # full validation dataset is already configured on the restored model.
    baseline = pl.Trainer(accelerator="gpu", devices=1, precision="bf16-mixed",
                          logger=False, enable_checkpointing=False, enable_progress_bar=False,
                          num_sanity_val_steps=0, limit_val_batches=1.0, callbacks=[coverage])
    try:
        model.set_trainer(baseline)
        results = baseline.validate(model, verbose=False)
        wer = check_baseline_result(results, examples=coverage.examples, batches=coverage.batches,
                                    expected_examples=expected_examples, global_step=baseline.global_step)
    finally:
        model.set_trainer(main_trainer)
    return {"status": "PASS_FULL_PARENT_DEV_VALIDATION_ONLY", "val_wer": wer,
            "examples": coverage.examples, "batches": coverage.batches, "global_step": 0,
            "raw_metrics": results[0], "precision": "bf16-mixed",
            "candidate_checkpoint_selection_affected": False, "optimizer_updates": 0}
