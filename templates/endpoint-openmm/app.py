from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from hcls_api import create_app


MAX_PARTICLES = 4096
MAX_STEPS = 1_000_000


class OpenMMAdapter:
    service_id = "openmm-md"

    def __init__(self) -> None:
        self.python = ""
        self.worker = str(Path(__file__).with_name("openmm_worker.py"))
        self.runtime: dict[str, Any] = {}
        self.timeout_seconds = max(
            30, min(int(os.environ.get("HCLS_ENGINE_TIMEOUT_SECONDS", "1800")), 7200)
        )

    def load(self) -> None:
        probe = subprocess.run(
            [sys.executable, self.worker, "probe"],
            capture_output=True, text=True, timeout=180, check=True,
        )
        report = json.loads(probe.stdout.strip().splitlines()[-1])
        if not report.get("cuda_step_passed"):
            raise RuntimeError("OpenMM startup probe did not complete a CUDA integration step")
        self.runtime = {
            "actual_engine_version": report["engine_version"],
            "available_platforms": report["available_platforms"],
            "source": "PyPI openmm[cuda12] (installed at image build time)",
            "cuda_step_passed": True,
        }
        self.python = sys.executable

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
        completed = subprocess.run(
            [self.python, self.worker, str(request_path), str(result_path)],
            cwd=work_dir,
            capture_output=True, text=True, check=False,
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
