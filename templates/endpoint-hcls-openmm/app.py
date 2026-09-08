from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hcls_api import create_app
from hcls_api.oci_runtime import run_in_runtime


MAX_PARTICLES = 4096
MAX_STEPS = 1_000_000


class OpenMMAdapter:
    service_id = "openmm-md"

    def __init__(self) -> None:
        self.rootfs = Path("/")
        self.python = ""
        self.worker = ""
        self.image_environment: dict[str, str] = {}
        self.runtime: dict[str, Any] = {}
        self.timeout_seconds = max(
            30, min(int(os.environ.get("HCLS_ENGINE_TIMEOUT_SECONDS", "1800")), 7200)
        )

    def load(self) -> None:
        spec_path = os.environ.get("OPENMM_RUNTIME_SPEC")
        metadata_path = os.environ.get("OPENMM_RUNTIME_METADATA")
        if not spec_path or not metadata_path:
            raise RuntimeError("OpenMM runtime selection is unavailable")
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        self.runtime = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        self.rootfs = Path(spec["rootfs"])
        self.python = str(spec["guest_command"])
        self.worker = str(spec["guest_worker"])
        self.image_environment = dict(spec["image_environment"])
        if not self.python.startswith("/") or not self.worker.startswith("/"):
            raise RuntimeError("OpenMM runtime command is invalid")

    @staticmethod
    def gpu_visible() -> bool:
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return False
        probe = subprocess.run([nvidia_smi, "-L"], capture_output=True, timeout=10, check=False)
        return probe.returncode == 0

    def health(self) -> dict[str, Any]:
        gpu_visible = self.gpu_visible()
        return {
            "ready": bool(self.python) and gpu_visible,
            "engine": "OpenMM",
            "engine_version": self.runtime.get("actual_engine_version", "unknown"),
            "available_platforms": self.runtime.get("available_platforms", []),
            "cuda_available": "CUDA" in self.runtime.get("available_platforms", []),
            "nvidia_device_detected": gpu_visible,
            "runtime": self.runtime,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_dynamics",
            "engine": {
                "name": "OpenMM",
                "version": self.runtime.get("actual_engine_version", "unknown"),
            },
            "runtime": self.runtime,
            "accelerator": {"required": True, "kind": "NVIDIA CUDA"},
            "examples": [
                {
                    "id": "argon-4096-nvt",
                    "label": "Argon 4096-particle NVT smoke",
                    "input": {
                        "particle_count": 4096,
                        "steps": 10000,
                        "integrator": "LangevinMiddle",
                        "precision": "mixed",
                    },
                },
                {
                    "id": "argon-4096-nve-throughput",
                    "label": "Argon 4096-particle NVE throughput",
                    "input": {
                        "particle_count": 4096,
                        "steps": 100000,
                        "integrator": "Verlet",
                        "precision": "single",
                    },
                },
            ],
            "limits": {"particle_count": MAX_PARTICLES, "steps": MAX_STEPS},
            "metrics": ["integration_ns_per_day", "wall_clock_seconds"],
            "disclaimer": (
                "Research-only synthetic MD example; hardware throughput is not biological validation."
            ),
        }

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        if not self.gpu_visible():
            raise RuntimeError("OpenMM CUDA endpoint requires a visible NVIDIA GPU")
        request_path = work_dir / "openmm-request.json"
        result_path = work_dir / "openmm-result.json"
        request_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        completed = run_in_runtime(
            rootfs=self.rootfs,
            guest_command=self.python,
            args=[self.worker, str(request_path), str(result_path)],
            cwd=work_dir,
            image_environment=self.image_environment,
            timeout=self.timeout_seconds,
        )
        (work_dir / "openmm.stdout.log").write_text(completed.stdout[-16000:], encoding="utf-8")
        (work_dir / "openmm.stderr.log").write_text(completed.stderr[-16000:], encoding="utf-8")
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no output")[-1200:]
            raise RuntimeError(f"OpenMM failed with exit code {completed.returncode}: {detail}")
        if not result_path.is_file():
            raise RuntimeError("OpenMM completed without a result document")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["runtime"] = self.runtime
        return result


app = create_app(OpenMMAdapter())
