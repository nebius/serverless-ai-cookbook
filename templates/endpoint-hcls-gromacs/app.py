from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from hcls_api import create_app


MAX_STEPS = 100_000
MAX_TPR_BYTES = 64 * 1024 * 1024
MAX_TEXT_CHARS = 250_000
PERFORMANCE = re.compile(r"Performance:\s+([0-9.]+)")


def bounded_int(payload: dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    value = int(payload.get(name, default))
    if value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def default_inputs(steps: int, timestep_ps: float, temperature_k: float, seed: int) -> dict[str, str]:
    return {
        "mdp": f"""integrator = md
nsteps = {steps}
dt = {timestep_ps:.6f}
cutoff-scheme = Verlet
nstlist = 10
rcoulomb = 0.8
rvdw = 0.8
coulombtype = Cut-off
vdwtype = Cut-off
pbc = xyz
constraints = none
tcoupl = no
pcoupl = no
gen_vel = yes
gen_temp = {temperature_k:.3f}
gen_seed = {seed}
nstxout = 0
nstvout = 0
nstenergy = 10
nstlog = 10
""",
        "gro": """Argon four-particle smoke system
    4
    1ARG     AR    1   0.000   0.000   0.000
    1ARG     AR    2   0.500   0.000   0.000
    1ARG     AR    3   0.000   0.500   0.000
    1ARG     AR    4   0.000   0.000   0.500
   2.00000   2.00000   2.00000
""",
        "top": """[ defaults ]
1 1 no 1.0 1.0
[ atomtypes ]
Ar 18 39.948 0.0 A 0.3405 0.996
[ moleculetype ]
ARG 1
[ atoms ]
1 Ar 1 ARG AR 1 0.0 39.948
[ system ]
Argon smoke system
[ molecules ]
ARG 4
""",
    }


class GromacsAdapter:
    service_id = "gromacs-md"

    def __init__(self) -> None:
        self.binary = os.environ.get("GROMACS_BINARY", "/usr/local/gromacs/avx2_256/bin/gmx")
        self.version = "unknown"

    def load(self) -> None:
        if not shutil.which(self.binary):
            raise RuntimeError(f"GROMACS binary not found: {self.binary}")
        completed = subprocess.run([self.binary, "--version"], capture_output=True, text=True, check=True, timeout=60)
        self.version = next((line.split(":", 1)[1].strip() for line in completed.stdout.splitlines() if "GROMACS version" in line), "unknown")

    def health(self) -> dict[str, Any]:
        gpu = self.gpu_available()
        return {"ready": self.version != "unknown" and gpu, "engine": "GROMACS", "engine_version": self.version, "nvidia_device_detected": gpu}

    @staticmethod
    def gpu_available() -> bool:
        if Path("/dev/nvidiactl").exists():
            return True
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return False
        probe = subprocess.run([nvidia_smi, "-L"], capture_output=True, timeout=10, check=False)
        return probe.returncode == 0

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_dynamics",
            "engine": {"name": "GROMACS", "version": self.version},
            "accelerator": {"required": True, "kind": "NVIDIA CUDA", "offload": "nonbonded"},
            "examples": [{"id": "argon-gpu-smoke", "label": "Argon GPU-offload smoke", "input": {"steps": 10000, "gpu_mode": "gpu", "threads": 1}}],
            "accepted_inputs": ["prepared_tpr_base64", "coordinate_gro+topology_top+mdp", "guided_argon"],
            "limits": {"steps": MAX_STEPS, "tpr_bytes": MAX_TPR_BYTES, "text_chars": MAX_TEXT_CHARS},
            "metrics": ["ns_per_day", "wall_clock_seconds"],
            "disclaimer": "Research-only MD execution; validate topology, force field, ensemble, equilibration, and sampling independently.",
        }

    def run_command(self, command: list[str], work_dir: Path, stage: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(command, cwd=work_dir, capture_output=True, text=True, timeout=900, check=False)
        (work_dir / f"{stage}.stdout.log").write_text(completed.stdout[-16000:], encoding="utf-8")
        (work_dir / f"{stage}.stderr.log").write_text(completed.stderr[-16000:], encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(f"{stage} failed with exit code {completed.returncode}: {completed.stderr[-1000:]}")
        return completed

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        steps = bounded_int(payload, "steps", 10000, 1, MAX_STEPS)
        threads = bounded_int(payload, "threads", 1, 1, 32)
        timestep_ps = float(payload.get("timestep_ps", 0.001))
        if timestep_ps < 0.0001 or timestep_ps > 0.02:
            raise ValueError("timestep_ps must be between 0.0001 and 0.02")
        temperature_k = float(payload.get("temperature_k", 120.0))
        if temperature_k < 1 or temperature_k > 1000:
            raise ValueError("temperature_k must be between 1 and 1000")
        seed = bounded_int(payload, "seed", 17, 0, 2_147_483_647)
        gpu_mode = str(payload.get("gpu_mode", "gpu")).lower()
        if gpu_mode not in {"gpu", "cpu", "auto"}:
            raise ValueError("gpu_mode must be gpu, cpu, or auto")
        gpu_available = self.gpu_available()
        if gpu_mode == "gpu" and not gpu_available:
            raise RuntimeError("gpu_mode=gpu but no NVIDIA device is visible")

        tpr = payload.get("tpr_base64")
        if tpr:
            raw = base64.b64decode(str(tpr), validate=True)
            if len(raw) > MAX_TPR_BYTES:
                raise ValueError("decoded tpr exceeds 64 MiB")
            (work_dir / "input.tpr").write_bytes(raw)
            input_mode = "tpr"
        else:
            provided = {key: payload.get(key) for key in ("coordinate_gro", "topology_top", "mdp")}
            if any(provided.values()) and not all(provided.values()):
                raise ValueError("coordinate_gro, topology_top, and mdp must be supplied together")
            if all(provided.values()):
                if any(len(str(value)) > MAX_TEXT_CHARS for value in provided.values()):
                    raise ValueError("text input exceeds 250000 characters")
                inputs = {"gro": str(provided["coordinate_gro"]), "top": str(provided["topology_top"]), "mdp": str(provided["mdp"])}
                input_mode = "custom_text"
            else:
                inputs = default_inputs(steps, timestep_ps, temperature_k, seed)
                input_mode = "guided_argon"
            (work_dir / "input.gro").write_text(inputs["gro"], encoding="utf-8")
            (work_dir / "topol.top").write_text(inputs["top"], encoding="utf-8")
            (work_dir / "input.mdp").write_text(inputs["mdp"], encoding="utf-8")
            self.run_command([self.binary, "grompp", "-f", "input.mdp", "-c", "input.gro", "-p", "topol.top", "-o", "input.tpr", "-maxwarn", "1"], work_dir, "grompp")

        command = [self.binary, "mdrun", "-s", "input.tpr", "-deffnm", "run", "-nsteps", str(steps), "-ntmpi", "1", "-ntomp", str(threads)]
        use_gpu = gpu_mode == "gpu" or (gpu_mode == "auto" and gpu_available)
        if use_gpu:
            command.extend(["-nb", "gpu"])
        started = time.perf_counter()
        completed = self.run_command(command, work_dir, "mdrun")
        elapsed = time.perf_counter() - started
        log = (work_dir / "run.log").read_text(encoding="utf-8", errors="replace") if (work_dir / "run.log").exists() else ""
        match = PERFORMANCE.search(log)
        ns_per_day = float(match.group(1)) if match else None
        return {
            "engine": "GROMACS",
            "engine_version": self.version,
            "input_mode": input_mode,
            "gpu_selected": use_gpu,
            "steps": steps,
            "timestep_ps": timestep_ps,
            "simulated_ns": round(steps * timestep_ps / 1000, 9),
            "mdrun_seconds": round(elapsed, 6),
            "ns_per_day": ns_per_day,
            "mdrun_summary": (completed.stdout + completed.stderr)[-2000:],
            "research_only": True,
        }


app = create_app(GromacsAdapter())
