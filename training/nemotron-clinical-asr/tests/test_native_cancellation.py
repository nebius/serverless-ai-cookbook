"""Native NeMo CPU tensor regression; real GPU/transport qualification is separate."""
from queue import Queue
from types import SimpleNamespace

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("nemo")
from nemo.collections.asr.inference.streaming.buffering.audio_bufferer import AudioBufferer
from nemo.collections.asr.inference.streaming.buffering.cache_feature_bufferer import BatchedCacheFeatureBufferer
from nemo.collections.asr.inference.streaming.framing.request import Frame
from nemo.collections.asr.inference.utils.context_manager import CacheAwareContextManager

from clinical_asr.contracts import SpeechOptions
from clinical_asr.runtime import NeMoRuntime


def test_cancel_frees_native_inference_tensor_buffers_and_context():
    audio = AudioBufferer(16000, 0.56)
    frame = Frame(samples=torch.zeros(8960), stream_id=1, is_first=True, is_last=False, length=8960)
    with torch.inference_mode():
        audio.update(frame)
    assert audio.sample_buffer.is_inference()
    # This is the exact native failure that previously prevented slot release.
    with pytest.raises(RuntimeError, match="outside InferenceMode"):
        audio.reset()

    bufferer = BatchedCacheFeatureBufferer.__new__(BatchedCacheFeatureBufferer)
    bufferer.device = torch.device("cpu")
    bufferer.ZERO_LEVEL_SPEC_DB_VAL = 0.0
    bufferer.feature_buffer = torch.zeros(1, 1, 1)
    bufferer.audio_bufferers = [audio]
    bufferer.streamidx2slotidx, bufferer.slotidx2streamidx = {1: 0}, {0: 1}
    bufferer.available_slots = Queue(1)
    context = CacheAwareContextManager.__new__(CacheAwareContextManager)
    context.cache_disabled = False
    context.device = torch.device("cpu")
    context.cache_last_channel = torch.zeros(1, 1, 1, 1)
    context.cache_last_time = torch.zeros(1, 1, 1, 1)
    context.cache_last_channel_len = torch.zeros(1, dtype=torch.int64)
    context.streamidx2slotidx, context.slotidx2streamidx = {1: 0}, {0: 1}
    context.free_slots = Queue(1)
    runtime = NeMoRuntime()
    closed = []
    runtime.pipeline = SimpleNamespace(bufferer=bufferer, context_manager=context, close_session=lambda: closed.append(True))
    runtime._active = runtime._next_stream = 1
    runtime.close(1)
    assert closed == [True] and runtime._active is None
    assert not bufferer.streamidx2slotidx and not context.streamidx2slotidx
    assert bufferer.available_slots.qsize() == context.free_slots.qsize() == 1
    assert runtime.begin(SpeechOptions(model=runtime.model_id)) == 2
