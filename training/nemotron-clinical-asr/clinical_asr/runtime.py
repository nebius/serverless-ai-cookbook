"""One resident .nemo model; NVIDIA native cache-aware encoder/decoder state.

Transport/framing derived from the Scientific AI speech runtime. No replaying
the complete accumulated waveform to simulate streaming, and no text animation.
"""
import time
import platform
from pathlib import Path
from types import SimpleNamespace

from . import NEMO_REVISION
from .common import checked_checkpoint, sha256_file
from .families import family_spec


class NeMoRuntime:
    def __init__(self, *, checkpoint=None, checkpoint_sha=None, model_id="nemotron35-base-en", chunk_ms=560,
                 model_family="nemotron35", fine_tuned=None):
        if model_id == "nemotron-clinical-en" and not checkpoint:
            raise ValueError("clinical_model_requires_actual_finetuned_checkpoint")
        self.checkpoint = checkpoint
        self.checkpoint_sha = checkpoint_sha
        self.model_id = model_id
        family_spec(model_family)
        if model_family == "english_specialist" and not checkpoint:
            raise ValueError("english_specialist_requires_pinned_checkpoint")
        self.model_family = model_family
        self.fine_tuned = bool(checkpoint) if fine_tuned is None else bool(fine_tuned)
        self.chunk_ms = chunk_ms
        self.pipeline = None
        self._active = None
        self._next_stream = 0
        self.profile = SimpleNamespace(confidence=False)
        self.identity = {}

    def load(self):
        import torch
        from nemo.collections.asr.inference.factory.pipeline_builder import PipelineBuilder
        from omegaconf import OmegaConf
        if not torch.cuda.is_available():
            raise RuntimeError("cuda_required")
        start = time.monotonic()
        checkpoint = checked_checkpoint(self.checkpoint, self.checkpoint_sha)
        config = OmegaConf.load("/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml")
        config.asr.model_name = checkpoint
        config.asr.device = "cuda"
        config.asr.device_id = 0
        config.asr.compute_dtype = "float32"
        config.asr.use_amp = False
        config.asr.use_cuda_graphs = False
        config.asr.strip_lang_tags = True
        config.asr.decoding.strategy = "greedy_batch"
        config.asr.decoding.beam.beam_size = 4
        config.asr.decoding.greedy.preserve_frame_confidence = False
        config.asr.decoding.beam.preserve_frame_confidence = False
        family = family_spec(self.model_family)
        left_context = family.left_context
        config.streaming.att_context_size = [left_context, self.chunk_ms // 80 - 1]
        config.streaming.batch_size = 1
        config.streaming.num_slots = 1
        config.enable_itn = False
        config.enable_nmt = False
        config.return_tail_result = True
        config.lang = "en-US"
        self.pipeline = PipelineBuilder.build_pipeline(config)
        torch.cuda.synchronize()
        self.identity = {
            "id": self.model_id,
            "base_model": family.repository,
            "base_revision": family.revision,
            "checkpoint_sha256": sha256_file(checkpoint), "fine_tuned": self.fine_tuned,
            "attention_context": [left_context, self.chunk_ms // 80 - 1],
            "nemo_revision": NEMO_REVISION, "precision": "float32", "chunk_size_ms": self.chunk_ms,
            "language": "en-US", "load_seconds": time.monotonic() - start,
            "gpu": torch.cuda.get_device_name(), "clinical_validation": "NOT_PERFORMED",
            "python": platform.python_version(), "torch": torch.__version__,
            "cuda_build": torch.version.cuda, "cudnn": torch.backends.cudnn.version(),
            "compute_capability": list(torch.cuda.get_device_capability()),
            "gpu_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
            "post_load_memory": self.memory_snapshot(),
            "diarization": False,
        }

    def memory_snapshot(self):
        import torch
        return {"allocated_bytes": torch.cuda.memory_allocated(),
                "reserved_bytes": torch.cuda.memory_reserved(),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "scope": "this_PyTorch_process_not_total_GPU_or_external_allocators"}

    @property
    def frame_samples(self):
        return round(self.pipeline.chunk_size_in_secs * self.pipeline.sample_rate)

    def begin(self, options):
        if options.model != self.model_id or options.chunk_size_ms != self.chunk_ms:
            raise ValueError("runtime_profile_mismatch")
        if self._active is not None:
            raise RuntimeError("runtime_busy")
        import torch
        torch.cuda.reset_peak_memory_stats()
        self._next_stream += 1
        self._active = self._next_stream
        return self._active

    def step(self, stream_id, frame, options):
        import numpy as np
        import torch
        from nemo.collections.asr.inference.streaming.framing.request import Frame
        from nemo.collections.asr.inference.streaming.framing.request_options import ASRRequestOptions
        if stream_id != self._active:
            raise RuntimeError("unknown_stream")
        samples = torch.from_numpy(np.frombuffer(frame.pcm, dtype="<i2").astype(np.float32) / 32768.0)
        request = Frame(samples=samples, stream_id=stream_id, is_first=frame.first, is_last=frame.last,
                        length=frame.valid_samples, options=ASRRequestOptions(
                            language_code="en-US", stop_history_eou=options.stop_history_eou_ms,
                            asr_output_granularity=options.output_granularity))
        with torch.inference_mode():
            return self.pipeline.transcribe_step([request])[0]

    def close(self, stream_id):
        import torch
        if stream_id != self._active:
            return
        try:
            # AudioBufferer.update replaces sample_buffer using torch.roll in
            # step's inference_mode. On cancellation its zero_ reset must run in
            # that mode too; otherwise reset raises before the sole slot is freed.
            with torch.inference_mode():
                bufferer = self.pipeline.bufferer
                slot = bufferer.streamidx2slotidx.get(stream_id)
                if slot is not None:
                    bufferer.reset_slots([slot])
                    bufferer.free_slots([slot])
                context = self.pipeline.context_manager
                if stream_id in context.streamidx2slotidx:
                    context.reset_slots([stream_id], [True])
                self.pipeline.close_session()
        finally:
            self._active = None
