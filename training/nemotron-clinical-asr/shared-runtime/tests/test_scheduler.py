import asyncio
import threading
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from fs2_speech.contracts import ENGLISH_ID, RuntimeProfile, SpeechOptions
from fs2_speech.nemo_runtime import NeMoRuntime
from fs2_speech.scheduler import ChunkScheduler, ScheduledRuntime


def test_processed_pcm_counts_completed_native_work_not_queued_or_padding():
    class Runtime:
        def __init__(self):
            self.next_id = 0

        def begin(self, options):
            self.next_id += 1
            return self.next_id

        def step_batch(self, entries):
            assert not any(name == "processed_audio_seconds" for name, _ in observed)
            return [None] * len(entries)

        def close(self, session):
            pass

    observed = []

    async def run():
        runtime = ScheduledRuntime(Runtime(), max_sessions=2, max_batch_size=2,
                                   observe=lambda name, value: observed.append((name, value)))
        a, b = await asyncio.gather(runtime.begin(None), runtime.begin(None))
        frame = SimpleNamespace(pcm=b"\0" * 3200, valid_samples=800)
        await asyncio.gather(runtime.step(a, frame, None), runtime.step(b, frame, None))
        assert [value for name, value in observed if name == "processed_audio_seconds"] == [0.1]
        await runtime.close(a)
        await runtime.close(b)
        await runtime.scheduler.shutdown()

    asyncio.run(run())


def test_limits_and_no_unbounded_admission():
    for kwargs in ({"max_sessions": 0}, {"max_sessions": True}, {"max_sessions": 129},
                   {"max_batch_size": 2}, {"batch_wait_seconds": float("nan")}, {"batch_wait_seconds": 1}):
        with pytest.raises(ValueError):
            ChunkScheduler(lambda jobs: [], **kwargs)
    scheduler = ChunkScheduler(lambda jobs: [])
    session = scheduler.reserve("customer")
    with pytest.raises(RuntimeError, match="runtime_busy"):
        scheduler.reserve("other")
    scheduler.release(session)
    scheduler.reserve("other")


def test_distinct_sessions_are_batched_and_group_round_robin_is_bounded():
    batches = []

    def execute(jobs):
        batches.append([(j.session, j.payload) for j in jobs])
        return [j.payload for j in jobs]

    async def run():
        scheduler = ChunkScheduler(execute, max_sessions=4, max_batch_size=4)
        a1, a2 = scheduler.reserve("a"), scheduler.reserve("a")
        b1, b2 = scheduler.reserve("b"), scheduler.reserve("b")
        results = await asyncio.gather(*(scheduler.submit(s, "step", str(s)) for s in (a1, a2, b1, b2)))
        assert results == [str(s) for s in (a1, a2, b1, b2)]
        assert batches == [[(s, str(s)) for s in (a1, b1, a2, b2)]]
        assert scheduler.snapshot()["queued_actions"] == 0
        for session in (a1, a2, b1, b2):
            scheduler.release(session)

    asyncio.run(run())


def test_duplicate_pending_and_cancelled_queue_never_execute():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def execute(jobs):
        calls.extend(j.payload for j in jobs)
        if jobs[0].payload == "blocking":
            entered.set()
            assert release.wait(2)
        return [j.payload for j in jobs]

    async def run():
        scheduler = ChunkScheduler(execute, max_sessions=2)
        a, b = scheduler.reserve("a"), scheduler.reserve("b")
        first = asyncio.create_task(scheduler.submit(a, "step", "blocking"))
        assert await asyncio.to_thread(entered.wait, 1)
        queued = asyncio.create_task(scheduler.submit(b, "step", "cancelled", audio_bytes=32))
        await asyncio.sleep(0)
        assert scheduler.snapshot()["queued_audio_bytes"] == 32
        with pytest.raises(RuntimeError, match="already_pending"):
            await scheduler.submit(b, "step", "duplicate")
        with pytest.raises(RuntimeError, match="inflight"):
            scheduler.release(a)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert scheduler.snapshot()["queued_actions"] == 0
        release.set()
        assert await first == "blocking"
        assert calls == ["blocking"]

    asyncio.run(run())


def test_cancellation_waits_for_inflight_even_when_cancelled_twice():
    entered, release = threading.Event(), threading.Event()

    def execute(jobs):
        entered.set()
        assert release.wait(2)
        return [None]

    async def run():
        scheduler = ChunkScheduler(execute)
        session = scheduler.reserve("a")
        task = asyncio.create_task(scheduler.submit(session, "step", None))
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert scheduler.snapshot()["inflight_actions"] == 1
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        scheduler.release(session)

    asyncio.run(run())


def test_native_failure_fails_all_queued_stops_admission_but_allows_cleanup():
    entered, release = threading.Event(), threading.Event()

    def execute(jobs):
        if jobs[0].kind == "close":
            return [None]
        entered.set()
        assert release.wait(2)
        raise ValueError("private backend detail")

    async def run():
        scheduler = ChunkScheduler(execute, max_sessions=2)
        a, b = scheduler.reserve("a"), scheduler.reserve("b")
        first = asyncio.create_task(scheduler.submit(a, "step", None))
        assert await asyncio.to_thread(entered.wait, 1)
        second = asyncio.create_task(scheduler.submit(b, "step", None))
        await asyncio.sleep(0)
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert [str(x) for x in results] == ["runtime_batch_failed", "runtime_poisoned"]
        with pytest.raises(RuntimeError, match="not_ready"):
            scheduler.reserve("c")
        await scheduler.submit(a, "close", None)
        await scheduler.submit(b, "close", None)
        scheduler.release(a)
        scheduler.release(b)

    asyncio.run(run())


def test_bad_batch_cardinality_is_fatal_not_cross_customer_misrouting():
    async def run():
        scheduler = ChunkScheduler(lambda jobs: [], max_sessions=2, max_batch_size=2)
        a, b = scheduler.reserve("a"), scheduler.reserve("b")
        results = await asyncio.gather(scheduler.submit(a, "step", "a"), scheduler.submit(b, "step", "b"),
                                       return_exceptions=True)
        assert all(str(x) == "runtime_batch_failed" for x in results)
        assert scheduler.poisoned
    asyncio.run(run())


def test_scheduled_runtime_preserves_per_session_ids_outputs_and_cleanup():
    class Runtime:
        def __init__(self):
            self.states = {}
            self.next_id = 10
            self.inflight = 0

        def begin(self, options):
            self.next_id += 1
            self.states[self.next_id] = options
            return self.next_id

        def step_batch(self, entries):
            assert self.inflight == 0
            self.inflight += 1
            result = [(self.states[s], frame.pcm) for s, frame, _ in entries]
            self.inflight -= 1
            return result

        def close(self, session):
            del self.states[session]

    async def run():
        raw = Runtime()
        runtime = ScheduledRuntime(raw, max_sessions=2, max_batch_size=2)
        a, b = await asyncio.gather(runtime.begin("A"), runtime.begin("B"))
        assert await asyncio.gather(runtime.step(a, SimpleNamespace(pcm=b"AA"), None),
                                    runtime.step(b, SimpleNamespace(pcm=b"BB"), None)) == [("A", b"AA"), ("B", b"BB")]
        await runtime.close(a)
        assert list(raw.states.values()) == ["B"]
        await runtime.close(b)
        assert raw.states == {}
        assert runtime.scheduler.snapshot()["active_sessions"] == 0
    asyncio.run(run())


@pytest.mark.parametrize("eos_mapping_already_freed", [False, True])
def test_native_close_does_not_reset_another_session(monkeypatch, eos_mapping_already_freed):
    import sys

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext,
                                                             cuda=SimpleNamespace(synchronize=lambda: None)))
    runtime = NeMoRuntime(RuntimeProfile(model=ENGLISH_ID), config_path=None, max_sessions=2, max_batch_size=2)
    states = {1: "A", 2: "B"}
    buffer_map, context_map = ({2: 1} if eos_mapping_already_freed else {1: 0, 2: 1}), {1: 0, 2: 1}
    reset_slots = []

    def free_slots(slots):
        for key, value in list(buffer_map.items()):
            if value in slots:
                del buffer_map[key]

    def reset_context(ids, eos):
        for key in ids:
            del context_map[key]

    runtime.pipeline = SimpleNamespace(
        bufferer=SimpleNamespace(num_slots=2, streamidx2slotidx=buffer_map,
                                 reset_slots=reset_slots.extend, free_slots=free_slots),
        context_manager=SimpleNamespace(streamidx2slotidx=context_map, reset_slots=reset_context),
        get_state=states.get, delete_state=lambda key: states.pop(key, None), decoding_computer=None,
        close_session=lambda: pytest.fail("global reset is forbidden"),
    )
    options = SpeechOptions(model=ENGLISH_ID)
    assert runtime.begin(options) == 1
    assert runtime.begin(options) == 2
    with pytest.raises(RuntimeError, match="busy"):
        runtime.begin(options)
    runtime.close(1)
    assert states == {2: "B"} and buffer_map == {2: 1} and context_map == {2: 1}
    assert reset_slots == [0] and runtime._active == {2}
    runtime.close(1)  # Idempotent; no new reset of another stream.


def test_operator_checkpoint_is_immutable_exact_and_not_a_customer_url(tmp_path):
    import hashlib

    runtime = NeMoRuntime(RuntimeProfile(model=ENGLISH_ID), config_path=None)
    path = tmp_path / "candidate.nemo"
    path.write_bytes(b"unit-test-artifact-not-a-model")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    runtime.bind_checkpoint(path, digest)
    assert runtime.verify_checkpoint(*runtime.checkpoint_override) == str(path)
    assert runtime.identity()["checkpoint_sha256"] == digest
    assert runtime.identity()["capacity_status"] == "configured_not_measured"
    with pytest.raises(RuntimeError, match="already_fixed"):
        runtime.bind_checkpoint(path, digest)
    with pytest.raises(RuntimeError, match="checksum"):
        runtime.verify_checkpoint(path, "a" * 64)
    link = tmp_path / "alias.nemo"
    link.symlink_to(path)
    with pytest.raises(RuntimeError, match="unavailable"):
        runtime.verify_checkpoint(link, digest)
