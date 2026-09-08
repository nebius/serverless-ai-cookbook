from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).with_name("runtime_loader.py")
SPEC = importlib.util.spec_from_file_location("gromacs_runtime_loader", MODULE_PATH)
assert SPEC and SPEC.loader
runtime_loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime_loader)


@pytest.mark.parametrize(
    "value", ["latest", "v2026.2", "v2025.3", "2023.2", "sha256-deadbeef"]
)
def test_accepts_safe_version_tags(value: str) -> None:
    assert runtime_loader.validate_requested_version(value) == value


@pytest.mark.parametrize(
    "value", ["", "../latest", "nvidia/gromacs", "tag:other", "tag@sha256:bad", "white space"]
)
def test_rejects_unsafe_version_tags(value: str) -> None:
    with pytest.raises(ValueError):
        runtime_loader.validate_requested_version(value)


def test_latest_ignores_signature_and_metadata_tags() -> None:
    tags = [
        "sha256-deadbeef.sig",
        "v2023.3",
        "v2025.1",
        "v2025.3",
        "v2026.2",
        "sha256-deadbeef.sbom",
    ]
    assert runtime_loader.resolve_latest_tag(tags) == "v2026.2"


def test_latest_uses_numeric_not_lexical_ordering() -> None:
    assert runtime_loader.resolve_latest_tag(["v2026.9", "v2026.10", "v2025.99"]) == "v2026.10"


def test_stable_tags_are_newest_first() -> None:
    assert runtime_loader.stable_version_tags(
        ["v2025.1", "sha256-deadbeef.sig", "v2026.2", "v2025.3"]
    ) == ["v2026.2", "v2025.3", "v2025.1"]


def test_stable_tags_reject_metadata_only_repository() -> None:
    with pytest.raises(RuntimeError, match="no stable version tags"):
        runtime_loader.stable_version_tags(["sha256-deadbeef.sig", "latest.sbom"])


def test_find_gromacs_prefers_requested_build(tmp_path: Path) -> None:
    preferred = tmp_path / "usr/local/gromacs/avx2_256/bin/gmx"
    preferred.parent.mkdir(parents=True)
    preferred.write_text("binary")
    other = tmp_path / "usr/local/gromacs/avx_512/bin/gmx"
    other.parent.mkdir(parents=True)
    other.write_text("binary")
    selected, build = runtime_loader.find_gromacs_binary(tmp_path, "avx2_256")
    assert selected == preferred
    assert build == "avx2_256"


def test_wrapper_uses_pulled_loader_and_driver_paths(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs"
    loader = rootfs / "lib64/ld-linux-x86-64.so.2"
    loader.parent.mkdir(parents=True)
    loader.write_text("loader")
    binary = rootfs / "usr/local/gromacs/avx2_256/bin/gmx"
    binary.parent.mkdir(parents=True)
    binary.write_text("binary")
    (rootfs / "usr/local/cuda-13.0/targets/x86_64-linux/lib").mkdir(parents=True)
    wrapper = runtime_loader.runtime_wrapper(rootfs, binary, "avx2_256")
    assert 'DRIVER_LIBS="/usr/local/nvidia/lib:/usr/local/nvidia/lib64"' in wrapper
    assert "usr/local/cuda/targets/x86_64-linux/lib" in wrapper
    assert "usr/local/cuda-13.0/targets/x86_64-linux/lib" in wrapper
    assert 'LD_LIBRARY_PATH="$TARGET_LIBS:$DRIVER_LIBS' in wrapper
    assert 'exec "$ROOTFS/lib64/ld-linux-x86-64.so.2"' in wrapper


def test_wrapper_can_use_host_elf_loader(tmp_path: Path) -> None:
    rootfs = tmp_path / "rootfs"
    loader = rootfs / "lib64/ld-linux-x86-64.so.2"
    loader.parent.mkdir(parents=True)
    loader.write_text("loader")
    binary = rootfs / "usr/local/gromacs/avx2_256/bin/gmx"
    binary.parent.mkdir(parents=True)
    binary.write_text("binary")
    wrapper = runtime_loader.runtime_wrapper(rootfs, binary, "avx2_256", "host_loader")
    assert 'exec "$ROOTFS/usr/local/gromacs/avx2_256/bin/gmx" "$@"' in wrapper
    assert "--library-path" not in wrapper
    assert "usr/lib/x86_64-linux-gnu" not in wrapper


def test_parse_engine_version() -> None:
    assert runtime_loader.parse_engine_version("GROMACS version:    2026.2\n") == "2026.2"


def test_gpu_startup_smoke_runs_grompp_and_mdrun(tmp_path: Path) -> None:
    commands: list[str] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command[1])
        return subprocess.CompletedProcess(command, 0, "", "")

    runtime_loader.gpu_startup_smoke(tmp_path / "gmx", runner)
    assert commands == ["grompp", "mdrun"]


def test_gpu_startup_smoke_rejects_failed_mdrun(tmp_path: Path) -> None:
    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            0 if command[1] == "grompp" else 1,
            "",
            "CUDA driver mismatch",
        )

    with pytest.raises(runtime_loader.IncompatibleRuntimeError, match="CUDA driver mismatch"):
        runtime_loader.gpu_startup_smoke(tmp_path / "gmx", runner)


def test_latest_falls_back_to_first_gpu_compatible_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth_dir = tmp_path / "auth"

    def fake_mkdtemp(**_: object) -> str:
        auth_dir.mkdir()
        return str(auth_dir)

    monkeypatch.setattr(runtime_loader.tempfile, "mkdtemp", fake_mkdtemp)
    loader = runtime_loader.RuntimeLoader(
        cache_root=tmp_path / "cache",
        requested_version="latest",
        requested_build="avx2_256",
        api_key="test-key",
    )
    monkeypatch.setattr(loader, "_auth_environment", lambda _: {})
    monkeypatch.setattr(
        loader,
        "_run",
        lambda *_, **__: "v2025.1\nv2026.2\nv2025.3\nsha256-deadbeef.sig",
    )
    attempted: list[str] = []

    def fake_candidate(tag: str, _: dict[str, str]) -> tuple[Path, Path, dict[str, str]]:
        attempted.append(tag)
        if tag != "v2025.1":
            raise runtime_loader.IncompatibleRuntimeError("CUDA driver mismatch")
        return tmp_path / "gmx", tmp_path / "runtime.json", {
            "resolved_tag": tag,
            "resolved_digest": f"sha256:{'0' * 64}",
        }

    monkeypatch.setattr(loader, "_load_candidate", fake_candidate)
    _, metadata_path, metadata = loader.load()
    assert attempted == ["v2026.2", "v2025.3", "v2025.1"]
    assert metadata["requested_version"] == "latest"
    assert metadata["resolved_tag"] == "v2025.1"
    assert [item["tag"] for item in metadata["rejected_newer_tags"]] == [
        "v2026.2",
        "v2025.3",
    ]
    assert metadata_path.name == "runtime-selection.json"


def test_registry_error_redacts_api_key(tmp_path: Path) -> None:
    key = "test-ngc-key-that-must-not-leak"

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", f"registry rejected {key}")

    loader = runtime_loader.RuntimeLoader(
        cache_root=tmp_path,
        requested_version="v2025.1",
        requested_build="avx2_256",
        api_key=key,
        runner=runner,
    )
    with pytest.raises(RuntimeError) as raised:
        loader._run(["crane", "digest"], {})
    assert key not in str(raised.value)
    assert "[REDACTED]" in str(raised.value)


def test_digest_cache_requires_matching_metadata_and_wrapper(tmp_path: Path) -> None:
    digest = f"sha256:{'a' * 64}"
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "gmx-runtime").write_text("wrapper", encoding="utf-8")
    (cache / "runtime.json").write_text(
        '{"resolved_digest": "' + digest + '"}', encoding="utf-8"
    )
    loader = runtime_loader.RuntimeLoader(
        cache_root=tmp_path,
        requested_version="v2025.1",
        requested_build="avx2_256",
        api_key="test-key",
    )
    assert loader._cached(cache, digest) == {"resolved_digest": digest}
    assert loader._cached(cache, f"sha256:{'b' * 64}") is None
