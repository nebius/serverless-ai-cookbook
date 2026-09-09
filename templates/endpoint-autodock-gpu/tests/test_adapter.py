from __future__ import annotations

import subprocess

import pytest

from app import AutoDockGpuAdapter


def test_capabilities_publish_architecture_boundary() -> None:
    capabilities = AutoDockGpuAdapter().capabilities()
    accelerator = capabilities["accelerator"]
    assert accelerator["compiled_compute_capabilities"] == ["8.0", "8.6", "8.9", "9.0"]
    assert accelerator["blackwell_supported"] is False
    assert "Blackwell GPUs are not supported" in capabilities["disclaimer"]


def test_cuda_probe_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AutoDockGpuAdapter()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, "", "no kernel image"),
    )
    with pytest.raises(RuntimeError, match="no kernel image"):
        adapter.probe_cuda()
    assert adapter.cuda_probe_passed is False


def test_cuda_probe_records_success(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AutoDockGpuAdapter()
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "ok", ""),
    )
    adapter.probe_cuda()
    assert adapter.cuda_probe_passed is True
