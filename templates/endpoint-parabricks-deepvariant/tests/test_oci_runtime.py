from __future__ import annotations

import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

import pytest

from hcls_api import oci_runtime


def test_stable_version_tags_support_workload_tag_shapes() -> None:
    assert oci_runtime.stable_version_tags(
        ["4.7.0-1", "4.6.0-2", "4.7.1-1", "sha256-deadbeef.sig"],
        re.compile(r"^\d+\.\d+\.\d+-\d+$"),
    ) == ["4.7.1-1", "4.7.0-1", "4.6.0-2"]
    assert oci_runtime.stable_version_tags(
        ["8.1.1", "8.1.9", "8.1.10"], re.compile(r"^\d+\.\d+\.\d+$")
    )[0] == "8.1.10"


@pytest.mark.parametrize("value", ["../latest", "repo:tag", "tag@digest", "white space", ""])
def test_version_validation_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        oci_runtime.validate_requested_version(value, "ENGINE_VERSION")


def test_public_config_reports_names_but_execution_drops_sensitive_values() -> None:
    raw = {
        "config": {
            "Entrypoint": ["/entry"],
            "Env": ["PATH=/bin", "LD_LIBRARY_PATH=/lib", "API_TOKEN=must-not-propagate"],
        }
    }
    public = oci_runtime.public_image_config(raw)
    assert public["image_environment_names"] == ["API_TOKEN", "LD_LIBRARY_PATH", "PATH"]
    assert "must-not-propagate" not in json.dumps(public)
    assert oci_runtime.execution_environment(raw) == {
        "PATH": "/bin",
        "LD_LIBRARY_PATH": "/lib",
    }


def test_safe_tar_rejects_traversal_and_hardlink(tmp_path: Path) -> None:
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as handle:
        member = tarfile.TarInfo("../escape")
        member.size = 1
        handle.addfile(member, io.BytesIO(b"x"))
    with pytest.raises(RuntimeError, match="unsafe path"):
        oci_runtime.safe_tar_members(archive)

    with tarfile.open(archive, "w") as handle:
        member = tarfile.TarInfo("safe-link")
        member.type = tarfile.LNKTYPE
        member.linkname = "../escape"
        handle.addfile(member)
    with pytest.raises(RuntimeError, match="unsafe hard link"):
        oci_runtime.safe_tar_members(archive)

def test_bind_mount_uses_recursive_mode_for_dev(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[str] = []

    monkeypatch.setattr(oci_runtime, "_mounted_at", lambda _: False)

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(oci_runtime.subprocess, "run", fake_run)
    oci_runtime._bind_mount(Path("/dev"), tmp_path / "rootfs/dev", recursive=True)
    assert captured[:3] == ["/usr/bin/mount", "--rbind", "/dev"]


def test_copy_device_copies_regular_runtime_tool(tmp_path: Path) -> None:
    source = tmp_path / "source-tool"
    source.write_text("runtime-tool", encoding="utf-8")
    source.chmod(0o755)
    destination = tmp_path / "rootfs/usr/bin/runtime-tool"
    oci_runtime._copy_device(source, destination)
    assert destination.read_text(encoding="utf-8") == "runtime-tool"
    assert destination.stat().st_mode & 0o777 == 0o755


def test_host_to_guest_requires_runtime_root(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs"
    work = rootfs / "tmp/run"
    work.mkdir(parents=True)
    assert oci_runtime.host_to_guest(rootfs, work) == "/tmp/run"
    with pytest.raises(ValueError, match="outside"):
        oci_runtime.host_to_guest(rootfs, tmp_path / "other")


def test_run_in_runtime_maps_rootfs_paths_and_filters_sensitive_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rootfs = tmp_path / "rootfs"
    work = rootfs / "tmp/run"
    work.mkdir(parents=True)
    captured: list[str] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(oci_runtime.subprocess, "run", fake_run)
    result = oci_runtime.run_in_runtime(
        rootfs=rootfs,
        guest_command="/usr/local/bin/engine",
        args=[str(work / "input.dat")],
        cwd=work,
        image_environment={"PATH": "/bin", "API_KEY": "never-pass"},
        timeout=30,
    )
    assert result.returncode == 0
    assert "/tmp/run/input.dat" in captured
    assert not any("never-pass" in item for item in captured)
