from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import pytest

from app import ParabricksAdapter, validate_https_url
import app


def test_default_one_gpu_is_ready(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("PARABRICKS_GPU_COUNT", raising=False)
    # Reload in a subprocess so the default is tested independently of this module's import.
    probe = subprocess.run(
        [sys.executable, "-c", "import app; print(app.GPU_COUNT)"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert probe.stdout.strip() == "1"
    monkeypatch.setattr(app, "INPUT_ROOT", tmp_path)
    monkeypatch.setattr(app, "gpu_names", lambda: ["NVIDIA H100 80GB HBM3"])
    adapter = ParabricksAdapter()
    adapter.pbrun = "/usr/local/parabricks/pbrun"
    assert adapter.health()["ready"] is True


def test_load_executes_baked_tools_directly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "pbrun: 4.7.1-1\n", "")

    monkeypatch.setattr(app.shutil, "which", lambda name: f"/usr/local/bin/{name}")
    monkeypatch.setattr(app.subprocess, "run", run)
    monkeypatch.setattr(app, "INPUT_ROOT", tmp_path / "fixtures")
    adapter = ParabricksAdapter()
    adapter.load()
    assert calls == [["/usr/local/bin/pbrun", "--version"]]
    assert adapter.runtime["actual_engine_version"] == "4.7.1-1"
    assert (tmp_path / "fixtures").is_dir()


def test_capabilities_publish_runtime_and_bounded_public_example() -> None:
    adapter = ParabricksAdapter()
    adapter.runtime = {
        "actual_engine_version": "4.7.1-1",
        "resolved_tag": "4.7.1-1",
        "resolved_digest": f"sha256:{'a' * 64}",
    }
    capabilities = adapter.capabilities()
    example = capabilities["examples"][0]
    assert capabilities["engine"]["version"] == "4.7.1-1"
    assert example["id"] == "deepvariant-chr20-smoke"
    assert example["input"]["reads"]["sha256"]


def test_remote_inputs_require_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        validate_https_url("http://example.com/input.bam")
    with pytest.raises(ValueError, match="credentials"):
        validate_https_url("https://user:pass@example.com/input.bam")


def test_remote_inputs_reject_private_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))
        ],
    )
    with pytest.raises(ValueError, match="non-public"):
        validate_https_url("https://example.com/input.bam")
