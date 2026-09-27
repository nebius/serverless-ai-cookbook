"""Small adapter over NVIDIA's pinned cache-aware RNNT streaming pipeline.

No encoder, decoder, feature extraction, or language-prompt implementation is
forked here. One loaded profile owns its streams; model-wide settings are fixed.
GPU calls must go through the single-lane bounded scheduler. Native batching
combines distinct stream IDs, never simultaneous calls into the model.
"""

import hashlib
import re
import time
from pathlib import Path
from typing import Any

from .completion import NativeCompletionFence
from .contracts import MODELS, RuntimeProfile, SpeechOptions
from .events import NativeSeparatorObserver
from .framing import PCMFrame


class NeMoRuntime:
    def __init__(self, profile: RuntimeProfile, *, config_path: Path, cache_dir: str | None = None,
                 max_sessions: int = 1, max_batch_size: int = 1) -> None:
        if (type(max_sessions) is not int or not 1 <= max_sessions <= 128
                or type(max_batch_size) is not int or not 1 <= max_batch_size <= max_sessions):
            raise ValueError("invalid_runtime_slot_limits")
        self.profile = profile
        self.config_path = config_path
        self.cache_dir = cache_dir
        self.pipeline: Any = None
        self.timings: dict[str, float] = {}
        self.max_sessions, self.max_batch_size = max_sessions, max_batch_size
        self._active: set[int] = set()
        self._next_stream = 0
        self.checkpoint_sha256: str | None = None
        self.checkpoint_override: tuple[Path, str] | None = None
        self.completion = NativeCompletionFence()
        self.separator_observer = None

    def bind_checkpoint(self, path: Path, sha256: str) -> None:
        """Operator-pinned local artifact only; no customer-selected path/URL.

        Selecting this artifact does not claim that a fine-tuned model passed its
        quality gates. Publication binds that separate evidence to an App ID.
        """
        if self.pipeline is not None or self.checkpoint_override is not None:
            raise RuntimeError("checkpoint_binding_already_fixed")
        if not path.is_absolute() or re.fullmatch(r"[a-f0-9]{64}", sha256) is None:
            raise ValueError("invalid_checkpoint_binding")
        self.checkpoint_override = (path, sha256)

    def verify_checkpoint(self, path: Path, expected: str | None = None) -> str:
        if not path.is_file() or (expected is not None and path.is_symlink()):
            raise RuntimeError("checkpoint_unavailable")
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if expected is not None and actual != expected:
            raise RuntimeError("checkpoint_checksum_mismatch")
        self.checkpoint_sha256 = actual
        return str(path)

    def identity(self) -> dict:
        spec = MODELS[self.profile.model]
        return {"parent_repository": spec.repository, "parent_revision": spec.revision,
                "checkpoint_sha256": self.checkpoint_sha256,
                "checkpoint_kind": "operator_pinned" if self.checkpoint_override else "upstream_pinned",
                "configured_max_sessions": self.max_sessions, "configured_max_batch_size": self.max_batch_size,
                "capacity_status": "configured_not_measured"}

    def load(self) -> None:
        if self.pipeline is not None:
            raise RuntimeError("runtime_already_loaded")
        start = time.monotonic()
        import torch
        from huggingface_hub import hf_hub_download
        from nemo.collections.asr.inference.factory.pipeline_builder import PipelineBuilder
        from omegaconf import OmegaConf

        if not torch.cuda.is_available():
            raise RuntimeError("GPU qualification requires a CUDA device; no silent CPU fallback")
        self.timings["runtime_import_seconds"] = time.monotonic() - start
        spec = MODELS[self.profile.model]
        start = time.monotonic()
        if self.checkpoint_override is not None:
            checkpoint = self.verify_checkpoint(*self.checkpoint_override)
        else:
            checkpoint = self.verify_checkpoint(Path(hf_hub_download(
                spec.repository, filename=spec.filename, revision=spec.revision, cache_dir=self.cache_dir,
            )))
        self.timings["checkpoint_acquisition_seconds"] = time.monotonic() - start
        cfg = OmegaConf.load(self.config_path)
        cfg.asr.model_name = checkpoint
        cfg.asr.device = "cuda"
        cfg.asr.device_id = 0
        cfg.asr.compute_dtype = self.profile.precision
        cfg.asr.use_amp = False
        cfg.asr.use_cuda_graphs = self.profile.cuda_graphs
        cfg.asr.strip_lang_tags = self.profile.strip_language_tags
        cfg.asr.decoding.strategy = self.profile.decoding
        cfg.asr.decoding.beam.beam_size = self.profile.beam_size
        cfg.asr.decoding.greedy.preserve_frame_confidence = self.profile.confidence
        cfg.asr.decoding.beam.preserve_frame_confidence = self.profile.confidence
        cfg.streaming.att_context_size = [spec.left_context, self.profile.chunk_size_ms // 80 - 1]
        cfg.streaming.batch_size = self.max_batch_size
        cfg.streaming.num_slots = self.max_sessions
        cfg.enable_itn = False
        cfg.enable_nmt = False
        cfg.return_tail_result = True
        cfg.lang = spec.default_language
        start = time.monotonic()
        self.pipeline = PipelineBuilder.build_pipeline(cfg)
        self.separator_observer = NativeSeparatorObserver(self.pipeline)
        torch.cuda.synchronize()
        self.timings["model_load_seconds"] = time.monotonic() - start

    @property
    def frame_samples(self) -> int:
        if self.pipeline is None:
            raise RuntimeError("model_not_loaded")
        return round(self.pipeline.chunk_size_in_secs * self.pipeline.sample_rate)

    def begin(self, options: SpeechOptions) -> int:
        self.completion.require_safe()
        if self.pipeline is None:
            raise RuntimeError("model_not_loaded")
        self.profile.require_match(options)
        if len(self._active) >= self.max_sessions:
            raise RuntimeError("runtime_busy")
        self._next_stream += 1
        self._active.add(self._next_stream)
        return self._next_stream

    def step(self, stream_id: int, frame: PCMFrame, options: SpeechOptions) -> Any:
        return self.step_batch([(stream_id, frame, options)])[0]

    def step_batch(self, entries: list[tuple[int, PCMFrame, SpeechOptions]]) -> list[Any]:
        import numpy as np
        import torch
        from nemo.collections.asr.inference.streaming.framing.request import Frame
        from nemo.collections.asr.inference.streaming.framing.request_options import ASRRequestOptions

        if not entries or len(entries) > self.max_batch_size or len({x[0] for x in entries}) != len(entries):
            raise ValueError("invalid_native_batch")
        requests = []
        for stream_id, frame, options in entries:
            if stream_id not in self._active:
                raise RuntimeError("unknown_stream")
            self.profile.require_match(options)
            samples = torch.from_numpy(np.frombuffer(frame.pcm, dtype="<i2").astype(np.float32) / 32768.0)
            requests.append(Frame(
                samples=samples, stream_id=stream_id, is_first=frame.first, is_last=frame.last,
                length=frame.valid_samples, options=ASRRequestOptions(
                    language_code=options.resolved_language, stop_history_eou=options.stop_history_eou_ms,
                    asr_output_granularity=options.output_granularity,
                ),
            ))
        observer = self.separator_observer
        if observer is not None:
            observer.begin_batch(entries)
        try:
            with torch.inference_mode():
                # The scheduler must not report a free lane while CUDA still uses
                # buffers, including a native call that enqueued work then raised.
                results = self.completion.call(self.pipeline.transcribe_step, torch.cuda.synchronize, requests)
            if len(results) != len(entries) or any(result.stream_id != entry[0]
                                                   for result, entry in zip(results, entries, strict=True)):
                raise RuntimeError("native_batch_stream_identity_mismatch")
            if observer is not None:
                observer.annotate(results)
            return results
        finally:
            if observer is not None:
                observer.end_batch()

    def close(self, stream_id: int) -> None:
        """Free encoder/audio/decoder state on EOS, cancellation and failure.

        Called only between GPU steps, never while a kernel/step is in flight.
        Never call pipeline.close_session(): it clears every customer's state.
        """
        if stream_id not in self._active:
            return
        self.completion.require_safe()
        import torch

        def release():
            with torch.inference_mode():
                bufferer = self.pipeline.bufferer
                slot = bufferer.streamidx2slotidx.get(stream_id)
                if slot is not None:
                    bufferer.free_slots([slot])
                # NeMo removes EOS mappings before returning the final result,
                # but leaves freed slot audio/features until their next reuse.
                # This serialized cleanup may clear idle slots only; other
                # admitted streams' mapped slots must remain intact.
                occupied = set(bufferer.streamidx2slotidx.values())
                idle = [slot_id for slot_id in range(bufferer.num_slots) if slot_id not in occupied]
                if idle:
                    bufferer.reset_slots(idle)
                context = self.pipeline.context_manager
                if stream_id in context.streamidx2slotidx:
                    context.reset_slots([stream_id], [True])
                state = self.pipeline.get_state(stream_id)
                decoder = self.pipeline.decoding_computer
                if (state is not None and decoder is not None and decoder.per_stream_biasing_enabled
                        and state.has_biasing_request()):
                    from nemo.collections.asr.inference.utils.per_stream_biasing import (
                        release_auto_managed_stream_biasing,
                    )

                    release_auto_managed_stream_biasing(state, decoder.biasing_multi_model)
                self.pipeline.delete_state(stream_id)
        self.completion.call(release, torch.cuda.synchronize)
        self._active.discard(stream_id)
