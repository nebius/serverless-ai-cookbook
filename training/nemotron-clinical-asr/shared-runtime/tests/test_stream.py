import asyncio
import json
import threading
from types import SimpleNamespace

from fs2_speech.contracts import ENGLISH_ID
from fs2_speech.stream import run_stream


class FakeRuntime:
    frame_samples = 2

    def __init__(self):
        self.closed = []
        self.frames = []

    def begin(self, options):
        return 1

    def step(self, stream_id, frame, options):
        self.frames.append(frame)
        return SimpleNamespace(final_transcript="Complete." if frame.last else "",
                               partial_transcript="Partial" if not frame.last else "")

    def close(self, stream_id):
        self.closed.append(stream_id)


START = json.dumps({"type": "session.start", "options": {"model": ENGLISH_ID}})
FINISH = json.dumps({"type": "input.finish"})


async def messages(*items):
    for item in items:
        yield item


def run(items, runtime=None):
    runtime = runtime or FakeRuntime()
    output = []

    async def send(event):
        output.append(event)

    asyncio.run(run_stream(runtime, messages(*items), send))
    return runtime, output


def test_partial_is_sent_before_client_finishes():
    runtime, output = run([START, b"\0" * 6, FINISH])
    assert [event["type"] for event in output] == [
        "session.ready", "transcript.partial", "transcript.final", "session.completed",
    ]
    assert output[-1]["audio_seconds"] == 3 / 16000
    assert runtime.closed == [1]


def test_disconnect_is_an_error_and_always_releases_state():
    runtime, output = run([START, b"\0" * 6])
    assert output[-1]["code"] == "stream_disconnected"
    assert not any(event["type"] == "session.completed" for event in output)
    assert runtime.closed == [1]


def test_word_alignment_comes_from_runtime_and_confidence_is_not_fabricated():
    class AlignedRuntime(FakeRuntime):
        profile = SimpleNamespace(confidence=False)

        def step(self, stream_id, frame, options):
            output = super().step(stream_id, frame, options)
            output.final_segments = [SimpleNamespace(text="Complete.", start=0.08, end=0.42, conf=1.0)]
            return output

    _, output = run([START, b"\0" * 6, FINISH], AlignedRuntime())
    final = next(event for event in output if event["type"] == "transcript.final")
    assert final["items"] == [{"text": "Complete.", "start_seconds": 0.08,
                               "end_seconds": 0.42, "confidence": None}]
    assert final["granularity"] == "segment"


def test_native_explicit_separator_is_metadata_not_a_text_or_timestamp_rewrite():
    class Runtime(FakeRuntime):
        def step(self, stream_id, frame, options):
            output = super().step(stream_id, frame, options)
            output.separator_before = " "
            output.final_segments = [SimpleNamespace(text="Complete.", start=0.08, end=0.42, conf=1.0)]
            return output

    _, output = run([START, b"\0" * 6, FINISH], Runtime())
    final = next(event for event in output if event["type"] == "transcript.final")
    assert final["text"] == "Complete." and final["separator_before"] == " "
    assert final["items"][0]["text"] == "Complete."
    assert final["items"][0]["start_seconds"] == 0.08
    assert all("separator_before" not in event for event in output if event["type"] == "transcript.partial")


def test_cancel_does_not_flush_or_report_success():
    runtime, output = run([START, b"\0\0", '{"type":"session.cancel"}'])
    assert output[-1]["type"] == "session.cancelled"
    assert not runtime.frames
    assert runtime.closed == [1]


def test_invalid_options_do_not_allocate_a_stream():
    runtime, output = run(['{"options":{"model":"unknown"}}'])
    assert output[-1]["code"] == "invalid_session_options"
    assert runtime.closed == []


def test_odd_audio_and_empty_recording_are_not_success():
    for items in ([START, b"\0"], [START, FINISH]):
        runtime, output = run(items)
        assert output[-1]["code"] == "invalid_audio"
        assert runtime.closed == [1]


def test_idle_timeout_releases_stream():
    runtime = FakeRuntime()
    output = []

    async def stalled():
        yield START
        await asyncio.sleep(1)

    async def send(event):
        output.append(event)

    asyncio.run(run_stream(runtime, stalled(), send, idle_seconds=0.01))
    assert output[-1]["code"] == "session_timeout"
    assert runtime.closed == [1]


def test_task_cancellation_waits_for_inflight_gpu_step_before_cleanup():
    started = threading.Event()
    finish = threading.Event()

    class SlowRuntime(FakeRuntime):
        def step(self, stream_id, frame, options):
            started.set()
            assert finish.wait(2)
            return super().step(stream_id, frame, options)

    runtime = SlowRuntime()

    async def send(event):
        pass

    async def scenario():
        task = asyncio.create_task(run_stream(runtime, messages(START, b"\0" * 6), send))
        await asyncio.to_thread(started.wait, 1)
        task.cancel()
        await asyncio.sleep(0.01)
        assert runtime.closed == []
        finish.set()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError("cancellation was swallowed")
        assert runtime.closed == [1]

    asyncio.run(scenario())
