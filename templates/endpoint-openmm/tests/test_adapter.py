from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import OpenMMAdapter
from openmm_worker import bounded_float, bounded_int


def test_adapter_loads_selected_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = tmp_path / "spec.json"
    metadata = tmp_path / "metadata.json"
    spec.write_text(
        json.dumps(
            {
                "rootfs": str(tmp_path / "rootfs"),
                "guest_command": "/usr/bin/python3",
                "guest_worker": "/opt/hcls-wrapper/openmm_worker.py",
                "image_environment": {"PATH": "/usr/bin"},
            }
        ),
        encoding="utf-8",
    )
    metadata.write_text(
        json.dumps(
            {
                "actual_engine_version": "8.1.1",
                "available_platforms": ["Reference", "CPU", "CUDA"],
                "resolved_tag": "8.1.1",
                "resolved_digest": f"sha256:{'a' * 64}",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENMM_RUNTIME_SPEC", str(spec))
    monkeypatch.setenv("OPENMM_RUNTIME_METADATA", str(metadata))
    adapter = OpenMMAdapter()
    adapter.load()
    capabilities = adapter.capabilities()
    assert capabilities["engine"]["version"] == "8.1.1"
    assert capabilities["runtime"]["resolved_tag"] == "8.1.1"


def test_worker_bounds_are_enforced() -> None:
    assert bounded_int({"steps": 10}, "steps", 1, 1, 100) == 10
    assert bounded_float({"timestep_fs": 2}, "timestep_fs", 1, 0.1, 10) == 2
    with pytest.raises(ValueError, match="steps"):
        bounded_int({"steps": 101}, "steps", 1, 1, 100)
    with pytest.raises(ValueError, match="timestep_fs"):
        bounded_float({"timestep_fs": float("nan")}, "timestep_fs", 1, 0.1, 10)
