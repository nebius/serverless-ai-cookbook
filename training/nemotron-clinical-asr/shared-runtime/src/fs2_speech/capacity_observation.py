"""Authenticated raw worker observations, not capacity or cloud attestation.

One bounded hardware query can be outstanding. Telemetry never joins the native
execution lane, synchronizes CUDA, runs inference, or exposes scheduling groups.
"""

import asyncio
import csv
import io
import json
import math
import os
import re
import select
import shutil
import socket
import subprocess
import threading
import time
from concurrent.futures import Future
from datetime import UTC, datetime
from uuid import uuid4


def utc_now():
    return datetime.now(UTC).isoformat()


def unknown_hardware(reason):
    return {"status": "unknown", "reason": reason, "sampled_at": None, "devices": None,
            "cuda_version": None, "driver_version": None, "llm_kv_cache": "not_applicable"}


def _nvml_uuid(value):
    if not isinstance(value, str):
        return None
    # Torch exposes a bare CUDA UUID; NVML/nvidia-smi expect GPU-UUID. Never
    # translate physical indices or MIG identities into an unrelated device.
    bare = value.removeprefix("GPU-")
    if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", bare) is None:
        return None
    return "GPU-" + bare.lower()


def _bounded_smi(command):
    """Fixed read-only query caller; output capped before buffering, no logs."""
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, shell=False)
    deadline = time.monotonic() + 0.15
    body = bytearray()
    try:
        descriptor = process.stdout.fileno()
        os.set_blocking(descriptor, False)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
                raise TimeoutError("hardware_query_deadline")
            chunk = os.read(descriptor, 16385 - len(body))
            if not chunk:
                break
            body.extend(chunk)
            if len(body) > 16384:
                raise ValueError("hardware_query_size")
        if process.wait(timeout=max(0.001, deadline - time.monotonic())) != 0:
            raise ValueError("hardware_query_failed")
        return bytes(body)
    finally:
        if process.poll() is None:
            process.kill()
            # Runs only in the existing single daemon hardware query. If the
            # driver cannot finish termination, its future remains outstanding;
            # the sampler times out and cannot spawn additional child queries.
            process.wait()
        process.stdout.close()


def _smi_observation(devices):
    """Optional runtime-injected utility; all absence/errors remain unknown."""
    try:
        uuids = [_nvml_uuid(device.get("uuid")) for device in devices]
        selected = sorted({value for value in uuids if value is not None})
        if not selected or len(selected) > 64:
            return None, {}
        executable = shutil.which("nvidia-smi")
        if executable is None:
            return None, {}
        raw = _bounded_smi([executable, "--id=" + ",".join(selected),
                            "--query-gpu=uuid,driver_version,utilization.gpu,utilization.memory",
                            "--format=csv,noheader,nounits"])
        if not 0 < len(raw) <= 16384:
            return None, {}
        rates, drivers = {}, set()
        for row in csv.reader(io.StringIO(raw.decode("ascii"))):
            if len(row) != 4:
                return None, {}
            uuid, driver, gpu, memory = (value.strip() for value in row)
            normalized = _nvml_uuid(uuid)
            if (not uuid.startswith("GPU-") or normalized not in selected or normalized in rates
                    or re.fullmatch(r"[0-9]{1,5}(?:\.[0-9]{1,5}){1,3}", driver) is None
                    or re.fullmatch(r"[0-9]{1,3}", gpu) is None
                    or re.fullmatch(r"[0-9]{1,3}", memory) is None
                    or not 0 <= int(gpu) <= 100 or not 0 <= int(memory) <= 100):
                return None, {}
            drivers.add(driver)
            rates[normalized] = (int(gpu), int(memory))
        if set(rates) != set(selected) or len(drivers) != 1:
            return None, {}
        return drivers.pop(), rates
    except (OSError, ValueError, UnicodeError, TimeoutError, subprocess.SubprocessError):
        return None, {}


def hardware_snapshot():
    """Torch plus existing NVML/utility; missing measurements stay unknown."""
    import torch

    if not torch.cuda.is_available():
        return unknown_hardware("cuda_unavailable")
    devices = []
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        free, total = torch.cuda.mem_get_info(index)
        device_uuid = getattr(props, "uuid", None)
        devices.append({"logical_index": index, "name": str(props.name),
                        "uuid": str(device_uuid) if device_uuid is not None else None,
                        "total_memory_bytes": int(total), "free_memory_bytes": int(free),
                        "process_allocated_bytes": int(torch.cuda.memory_allocated(index)),
                        "process_reserved_bytes": int(torch.cuda.memory_reserved(index)),
                        "utilization_percent": None, "memory_utilization_percent": None})
    driver = None
    try:
        import pynvml

        pynvml.nvmlInit()
        try:
            driver = pynvml.nvmlSystemGetDriverVersion()
            driver = driver.decode("ascii") if isinstance(driver, bytes) else str(driver)
            for device in devices:
                # Do not confuse CUDA_VISIBLE_DEVICES indices with physical GPU
                # indices. MIG or UUID-less devices stay unknown when unsupported.
                device_uuid = _nvml_uuid(device["uuid"])
                if device_uuid is None:
                    continue
                try:
                    handle = pynvml.nvmlDeviceGetHandleByUUID(device_uuid)
                    rates = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    device["utilization_percent"] = int(rates.gpu)
                    device["memory_utilization_percent"] = int(rates.memory)
                except Exception:
                    pass
        finally:
            pynvml.nvmlShutdown()
    except Exception:
        pass
    if driver is None or any(device["utilization_percent"] is None for device in devices):
        fallback_driver, rates = _smi_observation(devices)
        if driver is None:
            driver = fallback_driver
        for device in devices:
            measured = rates.get(_nvml_uuid(device["uuid"]))
            if measured is not None and device["utilization_percent"] is None:
                device["utilization_percent"], device["memory_utilization_percent"] = measured
    return {"status": "observed", "reason": None, "sampled_at": utc_now(), "devices": devices,
            "cuda_version": torch.version.cuda, "driver_version": driver,
            "llm_kv_cache": "not_applicable"}


class BoundedHardwareSampler:
    """A stalled driver call cannot create an unbounded thread/queue backlog.

    Caller deadline is bounded; Python cannot interrupt a native driver query.
    The sole daemon query may finish later. Its original sample time is retained,
    and no second query starts while it is outstanding.
    """

    def __init__(self, query=hardware_snapshot, *, timeout_seconds=0.2):
        if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= 1:
            raise ValueError("invalid_hardware_deadline")
        self.query = query
        self.timeout_seconds = timeout_seconds
        self.pending = None
        self.last = None
        self.last_completed = 0.0
        self.closed = False

    async def sample(self):
        if self.closed:
            return unknown_hardware("sampler_closed")
        if self.last is not None and time.monotonic() - self.last_completed < 1:
            return self.last
        if self.pending is None:
            future = Future()
            self.pending = future

            def run():
                try:
                    result = self.query()
                    if len(json.dumps(result, allow_nan=False).encode()) > 16384:
                        raise ValueError("hardware_observation_too_large")
                    future.set_result((result, time.monotonic()))
                except Exception:
                    future.set_result((unknown_hardware("hardware_query_failed"), time.monotonic()))

            threading.Thread(target=run, name="stt-read-only-hardware", daemon=True).start()
        current = self.pending
        try:
            result, completed = await asyncio.wait_for(
                asyncio.shield(asyncio.wrap_future(current)), self.timeout_seconds,
            )
        except TimeoutError:
            return unknown_hardware("hardware_query_deadline")
        if self.pending is current:
            self.pending = None
            self.last, self.last_completed = result, completed
        if time.monotonic() - completed > 2:
            return unknown_hardware("hardware_query_stale")
        return result

    def close(self):
        self.closed = True


class WorkerObservation:
    def __init__(self, *, identity, profile, state, hardware=None):
        self.boot_id = str(uuid4())
        self.started = time.monotonic()
        self.identity, self.profile, self.state = identity, profile, state
        self.hardware = hardware or BoundedHardwareSampler()
        self.lock = threading.Lock()
        self.processed_seconds = 0.0

    def processed(self, value):
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("invalid_completed_pcm_counter")
        with self.lock:
            self.processed_seconds += value

    async def sample(self):
        # Capture logical occupancy on the event loop before awaiting hardware.
        observed_at, monotonic = utc_now(), time.monotonic()
        state = self.state()
        identity = self.identity()
        with self.lock:
            processed = self.processed_seconds
        hardware = (await self.hardware.sample() if state["ready"]
                    else unknown_hardware("worker_not_ready"))
        result = {"schema_version": 1, "scope": "raw_worker_not_capacity",
                  "boot_id": self.boot_id, "backend_id": socket.gethostname(),
                  "observed_at": observed_at, "uptime_seconds": monotonic - self.started,
                  "runtime_identity": identity, "profile": self.profile(), **state,
                  "processed_audio_seconds_total": processed,
                  "processed_audio_semantics": "native_completed_unpadded_pcm_including_cancelled_work",
                  "hardware": hardware, "measured_capacity": None,
                  "gateway_pending_sessions": None, "cloud_identity": None}
        if len(json.dumps(result, allow_nan=False).encode()) > 65536:
            raise RuntimeError("worker_observation_too_large")
        return result
