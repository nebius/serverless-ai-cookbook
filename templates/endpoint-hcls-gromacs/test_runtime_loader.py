from __future__ import annotations

import importlib.util
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
