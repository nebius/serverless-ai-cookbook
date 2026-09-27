import asyncio
import sys
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from fs2_speech.contracts import ENGLISH_ID, RuntimeProfile, SpeechOptions
from fs2_speech.framing import PCMFrame
from fs2_speech.nemo_runtime import NeMoRuntime
from fs2_speech.scheduler import ScheduledRuntime


@pytest.mark.parametrize("sync_fails", [False, True])
def test_native_error_is_synchronized_before_close_or_quarantined(monkeypatch, sync_fails):
    calls = []

    def sync():
        calls.append("sync")
        if sync_fails:
            raise RuntimeError("private CUDA detail")

    def native(requests):
        calls.append("native-enqueue-then-raise")
        raise ValueError("private native detail")

    class Array:
        def astype(self, unused):
            return self

        def __truediv__(self, unused):
            return self

    # Host contract tests intentionally do not install NumPy/NeMo/CUDA.
    monkeypatch.setitem(sys.modules, "numpy", SimpleNamespace(frombuffer=lambda *args, **kw: Array(), float32="f32"))

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext, from_numpy=lambda x: x,
        cuda=SimpleNamespace(synchronize=sync)))
    monkeypatch.setitem(sys.modules, "nemo.collections.asr.inference.streaming.framing.request",
                        SimpleNamespace(Frame=lambda **kw: SimpleNamespace(**kw)))
    monkeypatch.setitem(sys.modules, "nemo.collections.asr.inference.streaming.framing.request_options",
                        SimpleNamespace(ASRRequestOptions=lambda **kw: SimpleNamespace(**kw)))
    runtime = NeMoRuntime(RuntimeProfile(model=ENGLISH_ID), config_path=None)
    runtime.pipeline = SimpleNamespace(transcribe_step=native,
        bufferer=SimpleNamespace(num_slots=1, streamidx2slotidx={},
            reset_slots=lambda slots: calls.append("close-reset")),
        context_manager=SimpleNamespace(streamidx2slotidx={}), get_state=lambda _: None,
        delete_state=lambda _: calls.append("close-delete"), decoding_computer=None)
    class Observer:
        hints = {}

        def begin_batch(self, entries):
            self.hints = {entries[0][0]: " "}

        def end_batch(self):
            self.hints.clear()

    runtime.separator_observer = Observer()
    options = SpeechOptions(model=ENGLISH_ID)
    session = runtime.begin(options)
    with pytest.raises(RuntimeError, match="native_action") as caught:
        runtime.step(session, PCMFrame(b"\0\0", 1, True, True), options)
    assert "private" not in str(caught.value)
    assert calls == ["native-enqueue-then-raise", "sync"]
    assert not runtime.separator_observer.hints
    if sync_fails:
        with pytest.raises(RuntimeError, match="quarantined"):
            runtime.close(session)
        with pytest.raises(RuntimeError, match="quarantined"):
            runtime.begin(options)
        assert calls == ["native-enqueue-then-raise", "sync"]
        assert session in runtime._active  # Keep uncertain state referenced.
    else:
        runtime.close(session)
        assert calls == ["native-enqueue-then-raise", "sync", "close-reset", "close-delete", "sync"]
        assert not runtime._active


@pytest.mark.parametrize("native_fails", [False, True])
def test_completion_counter_excludes_queued_cancel_and_failed_native_call(native_fails):
    entered, release = threading.Event(), threading.Event()
    observed, calls = [], []

    class Raw:
        index = 0

        def begin(self, options):
            self.index += 1
            return self.index

        def close(self, session):
            pass

        def step_batch(self, entries):
            calls.extend(row[0] for row in entries)
            entered.set()
            assert release.wait(2)
            if native_fails:
                raise ValueError("private failure")
            return [None] * len(entries)

    async def run():
        runtime = ScheduledRuntime(Raw(), max_sessions=2,
            observe=lambda name, value: observed.append((name, value)))
        a, b = await asyncio.gather(runtime.begin(None), runtime.begin(None))
        frame = PCMFrame(b"\0" * 3200, 800, True, True)
        first = asyncio.create_task(runtime.step(a, frame, None))
        assert await asyncio.to_thread(entered.wait, 1)
        queued = asyncio.create_task(runtime.step(b, frame, None))
        await asyncio.sleep(0)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        release.set()
        if native_fails:
            with pytest.raises(RuntimeError, match="runtime_batch_failed"):
                await first
            assert runtime.scheduler.poisoned
        else:
            await first
        assert calls == [a]
        assert [v for k, v in observed if k == "processed_audio_seconds"] == ([] if native_fails else [.05])
        await runtime.close(a)
        await runtime.close(b)
        await runtime.scheduler.shutdown()

    asyncio.run(run())
