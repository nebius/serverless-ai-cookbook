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


REPOSITORY = "nvcr.io/nvidia/openmm"
STABLE_TAG = re.compile(r"^\d+\.\d+\.\d+$")


def find_python(rootfs: Path) -> Path:
    for relative in ("usr/bin/python3", "usr/local/bin/python3", "usr/bin/python3.10"):
        candidate = rootfs / relative
        if candidate.is_file():
            return candidate
    candidates = sorted(rootfs.rglob("python3"))
    if not candidates:
        raise RuntimeError("official NGC image does not contain Python 3")
    return candidates[0]


def prepare_worker(rootfs: Path) -> Path:
    destination = rootfs / "opt/hcls-wrapper/openmm_worker.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("/app/openmm_worker.py", destination)
    return destination


def probe_runtime(rootfs: Path, image_environment: dict[str, str]) -> dict[str, Any]:
    prepare_chroot_runtime(rootfs)
    python = find_python(rootfs)
    worker = prepare_worker(rootfs)
    workspace = Path(tempfile.mkdtemp(prefix="openmm-probe-", dir=rootfs / "tmp"))
    completed = run_in_runtime(
        rootfs=rootfs,
        guest_command=host_to_guest(rootfs, python),
        args=[host_to_guest(rootfs, worker), "probe"],
        cwd=workspace,
        image_environment=image_environment,
        timeout=180,
    )
    shutil.rmtree(workspace, ignore_errors=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "no output")[-1200:]
        raise IncompatibleRuntimeError(
            f"OpenMM CUDA startup probe failed with exit={completed.returncode}: {detail}"
        )
    try:
        report = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise IncompatibleRuntimeError("OpenMM startup probe returned invalid metadata") from exc
    if not report.get("cuda_step_passed"):
        raise IncompatibleRuntimeError("OpenMM startup probe did not complete a CUDA integration step")
    return {
        "actual_engine_version": report.get("engine_version", "unknown"),
        "available_platforms": report.get("available_platforms", []),
        "guest_python": host_to_guest(rootfs, python),
        "guest_worker": host_to_guest(rootfs, worker),
        "cuda_probe": "one integration step passed",
    }


def main() -> None:
    cache_root = Path(os.environ.get("OPENMM_RUNTIME_CACHE", "/var/cache/hcls-openmm"))
    loader = OciRuntimeLoader(
        service_name="OpenMM",
        cache_root=cache_root,
        requested_version=os.environ.get("OPENMM_VERSION", "latest"),
        version_variable="OPENMM_VERSION",
        repository=os.environ.get("OPENMM_IMAGE_REPOSITORY", REPOSITORY),
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
                "guest_command": metadata["guest_python"],
                "guest_worker": metadata["guest_worker"],
                "image_environment": image_environment,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_environment(
        Path("/run/hcls-openmm/runtime.env"),
        {
            "OPENMM_RUNTIME_SPEC": str(execution_path),
            "OPENMM_RUNTIME_METADATA": str(metadata_path),
            "HCLS_SCRATCH_ROOT": str(rootfs / "tmp/hcls-scratch"),
        },
    )


if __name__ == "__main__":
    main()
