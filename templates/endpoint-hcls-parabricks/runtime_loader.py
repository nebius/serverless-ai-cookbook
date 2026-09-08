from __future__ import annotations

import json
import os
import re
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


REPOSITORY = "nvcr.io/nvidia/clara/clara-parabricks"
STABLE_TAG = re.compile(r"^\d+\.\d+\.\d+-\d+$")


def required_path(rootfs: Path, relative: str, label: str) -> Path:
    preferred = rootfs / relative
    if preferred.is_file():
        return preferred
    candidates = sorted(rootfs.rglob(Path(relative).name))
    if not candidates:
        raise RuntimeError(f"official NVIDIA Parabricks image does not contain {label}")
    return candidates[0]


def probe_runtime(rootfs: Path, image_environment: dict[str, str]) -> dict[str, Any]:
    prepare_chroot_runtime(rootfs)
    pbrun = required_path(rootfs, "usr/local/parabricks/pbrun", "pbrun")
    samtools = required_path(rootfs, "usr/bin/samtools", "samtools")
    nvidia_smi = required_path(rootfs, "usr/bin/nvidia-smi", "nvidia-smi")
    gpu_probe = run_in_runtime(
        rootfs=rootfs,
        guest_command=host_to_guest(rootfs, nvidia_smi),
        args=["-L"],
        cwd=rootfs / "tmp",
        image_environment=image_environment,
        timeout=30,
    )
    if gpu_probe.returncode != 0 or "GPU " not in gpu_probe.stdout:
        detail = (gpu_probe.stderr or gpu_probe.stdout or "no output")[-1200:]
        raise IncompatibleRuntimeError(
            f"Parabricks NVIDIA runtime cannot enumerate the assigned GPU: {detail}"
        )
    completed = run_in_runtime(
        rootfs=rootfs,
        guest_command=host_to_guest(rootfs, pbrun),
        args=["--version"],
        cwd=rootfs / "tmp",
        image_environment=image_environment,
        timeout=120,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "no output")[-1200:]
        raise IncompatibleRuntimeError(
            f"Parabricks startup probe failed with exit={completed.returncode}: {detail}"
        )
    version_match = re.search(r"pbrun:\s*([0-9][0-9.]*-[0-9]+)", completed.stdout + completed.stderr)
    if not version_match:
        raise IncompatibleRuntimeError("Parabricks startup probe did not report an engine version")
    return {
        "actual_engine_version": version_match.group(1),
        "guest_command": host_to_guest(rootfs, pbrun),
        "guest_samtools": host_to_guest(rootfs, samtools),
        "cuda_probe": "nvidia-smi enumerated the GPU and pbrun loaded",
    }


def main() -> None:
    cache_root = Path(os.environ.get("PARABRICKS_RUNTIME_CACHE", "/var/cache/hcls-parabricks"))
    loader = OciRuntimeLoader(
        service_name="Parabricks",
        cache_root=cache_root,
        requested_version=os.environ.get("PARABRICKS_VERSION", "latest"),
        version_variable="PARABRICKS_VERSION",
        repository=os.environ.get("PARABRICKS_IMAGE_REPOSITORY", REPOSITORY),
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
                "guest_samtools": metadata["guest_samtools"],
                "image_environment": image_environment,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_environment(
        Path("/run/hcls-parabricks/runtime.env"),
        {
            "PARABRICKS_RUNTIME_SPEC": str(execution_path),
            "PARABRICKS_RUNTIME_METADATA": str(metadata_path),
            "HCLS_SCRATCH_ROOT": str(rootfs / "tmp/hcls-scratch"),
        },
    )


if __name__ == "__main__":
    main()
