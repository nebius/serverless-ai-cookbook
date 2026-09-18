from __future__ import annotations

import json
import subprocess
import sys

import pytest

from app import OpenMMAdapter
from openmm_worker import bounded_float, bounded_int


def test_adapter_requires_successful_cuda_step(monkeypatch: pytest.MonkeyPatch) -> None:
    report = {"engine_version": "8.6.1", "available_platforms": ["CPU", "CUDA"], "cuda_step_passed": True}
    calls = []

    def probe(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, json.dumps(report), "")

    monkeypatch.setattr(subprocess, "run", probe)
    adapter = OpenMMAdapter()
    adapter.load()
    assert calls == [[sys.executable, adapter.worker, "probe"]]
    assert adapter.capabilities()["engine"]["version"] == "8.6.1"
    report["cuda_step_passed"] = False
    with pytest.raises(RuntimeError, match="CUDA integration step"):
        OpenMMAdapter().load()


def test_worker_bounds_are_enforced() -> None:
    assert bounded_int({"steps": 10}, "steps", 1, 1, 100) == 10
    assert bounded_float({"timestep_fs": 2}, "timestep_fs", 1, 0.1, 10) == 2
    with pytest.raises(ValueError, match="steps"):
        bounded_int({"steps": 101}, "steps", 1, 1, 100)
    with pytest.raises(ValueError, match="timestep_fs"):
        bounded_float({"timestep_fs": float("nan")}, "timestep_fs", 1, 0.1, 10)
