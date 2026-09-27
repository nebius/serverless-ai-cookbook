"""Bounded chunk scheduling, not a second admission service or GPU executor pool.

All mutable scheduling state belongs to one asyncio loop. Exactly one blocking
model call executes at a time. The callback may batch distinct sessions using a
native model API; this module never assumes arbitrary model calls can overlap.
"""

import asyncio
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

# Set by a trusted private gateway adapter, not by a public request payload.
# Absent gateway metadata retains session round-robin, not a tenant-fairness claim.
scheduling_group: ContextVar[str] = ContextVar("speech_scheduling_group", default="unattributed")


@dataclass
class Action:
    session: int
    kind: str
    payload: Any
    future: asyncio.Future
    enqueued: float
    audio_bytes: int = 0
    running: bool = False


class ChunkScheduler:
    def __init__(self, execute: Callable[[list[Action]], list[Any]], *, max_sessions: int = 1,
                 max_batch_size: int = 1, batch_wait_seconds: float = 0.005,
                 observe: Callable[[str, float], None] | None = None):
        if (type(max_sessions) is not int or not 1 <= max_sessions <= 128
                or type(max_batch_size) is not int or not 1 <= max_batch_size <= max_sessions
                or not 0 <= batch_wait_seconds <= 0.1):
            raise ValueError("invalid_scheduler_limits")
        self.execute = execute
        self.max_sessions, self.max_batch_size = max_sessions, max_batch_size
        self.batch_wait_seconds = batch_wait_seconds
        self.observe = observe or (lambda *_: None)
        self.sessions: dict[int, str] = {}
        self.pending: dict[int, Action] = {}
        self.groups: OrderedDict[str, deque[Action]] = OrderedDict()
        self.runner: asyncio.Task | None = None
        self.poisoned = False
        self.draining = False
        self._next = 0
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speech-gpu-lane")

    def reserve(self, group: str) -> int:
        if self.poisoned or self.draining:
            self.observe("rejected", 1)
            raise RuntimeError("runtime_not_ready")
        if len(self.sessions) >= self.max_sessions:
            self.observe("rejected", 1)
            raise RuntimeError("runtime_busy")
        if not isinstance(group, str) or not 1 <= len(group) <= 120:
            raise ValueError("invalid_scheduling_group")
        self._next += 1
        self.sessions[self._next] = group
        self.observe("admitted", 1)
        return self._next

    def release(self, session: int) -> None:
        if session in self.pending:
            raise RuntimeError("session_has_inflight_action")
        self.sessions.pop(session, None)

    def snapshot(self) -> dict[str, Any]:
        queued = [job for job in self.pending.values() if not job.running]
        now = time.monotonic()
        return {"active_sessions": len(self.sessions), "queued_actions": len(queued),
                "inflight_actions": len(self.pending) - len(queued),
                "queued_audio_bytes": sum(job.audio_bytes for job in queued),
                "oldest_wait_seconds": max((now - job.enqueued for job in queued), default=0.0),
                "max_sessions": self.max_sessions, "max_batch_size": self.max_batch_size,
                "poisoned": self.poisoned, "draining": self.draining}

    async def shutdown(self):
        self.draining = True
        if self.runner is not None:
            await asyncio.shield(self.runner)
        self.executor.shutdown(wait=True, cancel_futures=False)

    async def submit(self, session: int, kind: str, payload: Any, *, audio_bytes: int = 0) -> Any:
        if session not in self.sessions:
            raise RuntimeError("unknown_stream")
        if self.poisoned and kind != "close":
            raise RuntimeError("runtime_poisoned")
        if session in self.pending:
            raise RuntimeError("session_action_already_pending")
        if type(audio_bytes) is not int or not 0 <= audio_bytes <= 65536:
            raise ValueError("invalid_action_audio_size")
        job = Action(session, kind, payload, asyncio.get_running_loop().create_future(),
                     time.monotonic(), audio_bytes)
        self.pending[session] = job
        self.groups.setdefault(self.sessions[session], deque()).append(job)
        if self.runner is None or self.runner.done():
            self.runner = asyncio.create_task(self._run())
        try:
            return await asyncio.shield(job.future)
        except asyncio.CancelledError:
            self.observe("cancelled", 1)
            if not job.running and not job.future.done():
                group = self.sessions[session]
                self.groups[group].remove(job)
                if not self.groups[group]:
                    del self.groups[group]
                self.pending.pop(session)
                job.future.cancel()
            elif job.running:
                # A second cancellation also cannot free a live CUDA buffer.
                while not job.future.done():
                    try:
                        await asyncio.shield(job.future)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                if not job.future.cancelled():
                    job.future.exception()  # Consume failures without claiming success.
            raise

    def _pop(self) -> Action:
        group, queue = self.groups.popitem(last=False)
        job = queue.popleft()
        if queue:
            self.groups[group] = queue
        return job

    async def _run(self) -> None:
        while self.groups:
            # A bounded coalescing delay trades latency for throughput. Never
            # wait for absent customers to fill a batch.
            first = next(iter(self.groups.values()))[0]
            if first.kind == "step" and self.max_batch_size > 1 and self.batch_wait_seconds:
                await asyncio.sleep(self.batch_wait_seconds)
            if not self.groups:
                break
            batch = [self._pop()]
            while (batch[0].kind == "step" and len(batch) < self.max_batch_size and self.groups
                   and next(iter(self.groups.values()))[0].kind == "step"):
                batch.append(self._pop())
            started = time.monotonic()
            for job in batch:
                job.running = True
                self.observe("queue_seconds", started - job.enqueued)
            try:
                outputs = await asyncio.get_running_loop().run_in_executor(self.executor, self.execute, batch)
                if not isinstance(outputs, list) or len(outputs) != len(batch):
                    raise RuntimeError("native_batch_cardinality_mismatch")
            except Exception:
                # A model exception may leave shared device state inconsistent.
                # Stop admission and fail queued work, retaining close operations.
                self.poisoned = True
                self.observe("failed_batches", 1)
                for job in batch:
                    self.pending.pop(job.session)
                    job.future.set_exception(RuntimeError("runtime_batch_failed"))
                for group, queue in list(self.groups.items()):
                    retained = deque()
                    for job in queue:
                        if job.kind == "close":
                            retained.append(job)
                        else:
                            self.pending.pop(job.session)
                            job.future.set_exception(RuntimeError("runtime_poisoned"))
                    if retained:
                        self.groups[group] = retained
                    else:
                        del self.groups[group]
            else:
                for job, output in zip(batch, outputs, strict=True):
                    self.pending.pop(job.session)
                    job.future.set_result(output)
            finally:
                self.observe("execution_seconds", time.monotonic() - started)
                self.observe("batch_size", len(batch))


class ScheduledRuntime:
    """Adapt the existing Nemotron stream port without changing audio semantics."""

    def __init__(self, runtime, *, max_sessions=1, max_batch_size=1, batch_wait_seconds=0.005, observe=None):
        self.runtime = runtime
        self.ids: dict[int, int] = {}
        self.buffered: dict[int, int] = {}
        self.scheduler = ChunkScheduler(self._execute, max_sessions=max_sessions, max_batch_size=max_batch_size,
                                        batch_wait_seconds=batch_wait_seconds, observe=observe)

    @property
    def profile(self):
        return getattr(self.runtime, "profile", None)

    @property
    def frame_samples(self):
        return self.runtime.frame_samples

    def _execute(self, jobs):
        if jobs[0].kind == "step":
            entries = [(self.ids[job.session], *job.payload) for job in jobs]
            if hasattr(self.runtime, "step_batch"):
                results = self.runtime.step_batch(entries)
            else:
                # Only compatibility/test adapters may use sequential calls.
                # They still execute in the single lane, never concurrently.
                results = [self.runtime.step(*entry) for entry in entries]
            # Native step_batch has completed CUDA before returning. Count
            # consumed, unpadded PCM, including completed work whose caller
            # cancelled; queued/cancelled-before-execution audio isn't counted.
            consumed = [getattr(frame, "valid_samples", None) for _, frame, _ in entries]
            if len(results) == len(entries) and all(type(value) is int and value >= 0 for value in consumed):
                self.scheduler.observe("processed_audio_seconds", sum(consumed) / 16000)
            return results
        job = jobs[0]
        if job.kind == "begin":
            self.ids[job.session] = self.runtime.begin(job.payload)
            return [None]
        if job.kind == "close":
            native_id = self.ids.get(job.session)
            if native_id is not None:
                self.runtime.close(native_id)
                self.ids.pop(job.session)
            return [None]
        raise RuntimeError("unknown_scheduler_action")

    async def begin(self, options):
        # Validate before entering the GPU lane: client profile errors do not
        # poison a healthy worker or reserve device state.
        if self.profile is not None:
            self.profile.require_match(options)
        session = self.scheduler.reserve(scheduling_group.get())
        try:
            await self.scheduler.submit(session, "begin", options)
        except BaseException:
            await self.close(session)
            raise
        return session

    async def step(self, session, frame, options):
        return await self.scheduler.submit(session, "step", (frame, options), audio_bytes=len(frame.pcm))

    async def close(self, session):
        if session not in self.scheduler.sessions:
            return
        action = asyncio.create_task(self.scheduler.submit(session, "close", None))
        cancelled = False
        try:
            while not action.done():
                try:
                    await asyncio.shield(action)
                except asyncio.CancelledError:
                    # Cleanup is not optional when the caller cancels again.
                    cancelled = True
            await action
        finally:
            self.scheduler.release(session)
            self.buffered.pop(session, None)
        if cancelled:
            raise asyncio.CancelledError

    def note_buffered(self, session, size):
        if session in self.scheduler.sessions:
            self.buffered[session] = size
