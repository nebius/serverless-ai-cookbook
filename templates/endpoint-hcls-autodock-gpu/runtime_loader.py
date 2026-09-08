from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from hcls_api.oci_runtime import (
    IncompatibleRuntimeError,
    OciRuntimeLoader,
    host_to_guest,
    prepare_chroot_runtime,
    run_in_runtime,
    write_environment,
)


REPOSITORY = "nvcr.io/hpc/autodock"
STABLE_TAG = re.compile(r"^\d{4}\.\d{2}$")


def find_binary(rootfs: Path) -> Path:
    preferred = rootfs / "usr/local/bin/autodock_gpu_128wi"
    if preferred.is_file():
        return preferred
    candidates = sorted(rootfs.rglob("autodock_gpu_128wi"))
    if not candidates:
        candidates = sorted(rootfs.rglob("autodock_gpu_*wi"))
    if not candidates:
        raise RuntimeError("official NGC image does not contain an AutoDock-GPU executable")
    return candidates[0]


def prepare_assets(rootfs: Path) -> Path:
    source = Path("/opt/hcls-seed/autodock-gpu")
    destination = rootfs / "opt/hcls/examples/autodock-gpu"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination / "1stp"


def probe_runtime(rootfs: Path, image_environment: dict[str, str]) -> dict[str, Any]:
    prepare_chroot_runtime(rootfs)
    example_root = prepare_assets(rootfs)
    binary = find_binary(rootfs)
    binary.chmod(binary.stat().st_mode | 0o111)
    guest_binary = host_to_guest(rootfs, binary)
    workspace = Path(tempfile.mkdtemp(prefix="autodock-gpu-probe-", dir=rootfs / "tmp"))
    try:
        completed = run_in_runtime(
            rootfs=rootfs,
            guest_command=guest_binary,
            args=[
                "--ffile",
                str(example_root / "1stp_protein.maps.fld"),
                "--lfile",
                str(example_root / "1stp_ligand.pdbqt"),
                "--resnam",
                "startup-probe",
                "--nrun",
                "1",
                "--nev",
                "25000",
                "--heuristics",
                "0",
                "--autostop",
                "1",
                "--seed",
                "17",
                "--xmloutput",
                "0",
                "--dlgoutput",
                "1",
            ],
            cwd=workspace,
            image_environment=image_environment,
            timeout=180,
        )
        if completed.returncode != 0 or not (workspace / "startup-probe.dlg").is_file():
            detail = (completed.stderr or completed.stdout or "no output")[-1200:]
            raise IncompatibleRuntimeError(
                f"AutoDock-GPU CUDA startup probe failed with exit={completed.returncode}: {detail}"
            )
        version_text = f"{completed.stdout}\n{completed.stderr}"
        version_match = re.search(r"AutoDock-GPU(?: version)?\s+v?([0-9][0-9.]+)", version_text, re.I)
        return {
            "actual_engine_version": version_match.group(1) if version_match else "NGC-2020.06",
            "guest_command": guest_binary,
            "cuda_probe": "1STP docking passed",
        }
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def main() -> None:
    cache_root = Path(os.environ.get("AUTODOCK_RUNTIME_CACHE", "/var/cache/hcls-autodock"))
    loader = OciRuntimeLoader(
        service_name="AutoDock-GPU",
        cache_root=cache_root,
        requested_version=os.environ.get("AUTODOCK_VERSION", "latest"),
        version_variable="AUTODOCK_VERSION",
        repository=os.environ.get("AUTODOCK_IMAGE_REPOSITORY", REPOSITORY),
        required_repository=REPOSITORY,
        stable_pattern=STABLE_TAG,
        api_key=os.environ.get("NGC_API_KEY", ""),
    )
    rootfs, metadata_path, metadata, image_environment = loader.load(probe_runtime)
    execution_path = cache_root / "runtime-execution.json"
    execution_path.write_text(
        json.dumps(
            {
                "rootfs": str(rootfs),
                "guest_command": metadata["guest_command"],
                "image_environment": image_environment,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_environment(
        Path("/run/hcls-autodock/runtime.env"),
        {
            "AUTODOCK_RUNTIME_SPEC": str(execution_path),
            "AUTODOCK_RUNTIME_METADATA": str(metadata_path),
            "AUTODOCK_GPU_EXAMPLE_ROOT": str(rootfs / "opt/hcls/examples/autodock-gpu/1stp"),
            "HCLS_SCRATCH_ROOT": str(rootfs / "tmp/hcls-scratch"),
        },
    )


if __name__ == "__main__":
    main()
