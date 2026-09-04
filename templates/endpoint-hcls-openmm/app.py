from __future__ import annotations

import importlib.metadata
import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from hcls_api import create_app


MAX_PARTICLES = 4096
MAX_STEPS = 1_000_000


def bounded_int(payload: dict[str, Any], name: str, default: int, low: int, high: int) -> int:
    value = int(payload.get(name, default))
    if value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def bounded_float(payload: dict[str, Any], name: str, default: float, low: float, high: float) -> float:
    value = float(payload.get(name, default))
    if not math.isfinite(value) or value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


class OpenMMAdapter:
    service_id = "openmm-md"

    def __init__(self) -> None:
        self.openmm = None
        self.unit = None
        self.platforms: list[str] = []

    def load(self) -> None:
        import openmm
        from openmm import unit

        self.openmm = openmm
        self.unit = unit
        self.platforms = [
            openmm.Platform.getPlatform(index).getName()
            for index in range(openmm.Platform.getNumPlatforms())
        ]

    def health(self) -> dict[str, Any]:
        cuda_available = "CUDA" in self.platforms
        gpu_visible = self.gpu_visible()
        return {
            "ready": self.openmm is not None and cuda_available and gpu_visible,
            "engine": "OpenMM",
            "engine_version": importlib.metadata.version("openmm"),
            "available_platforms": self.platforms,
            "cuda_available": cuda_available,
            "nvidia_device_detected": gpu_visible,
        }

    @staticmethod
    def gpu_visible() -> bool:
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return False
        probe = subprocess.run([nvidia_smi, "-L"], capture_output=True, timeout=10, check=False)
        return probe.returncode == 0

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_dynamics",
            "engine": {"name": "OpenMM", "version": importlib.metadata.version("openmm")},
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
            "disclaimer": "Research-only synthetic MD example; hardware throughput is not biological validation.",
        }

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        if self.openmm is None or self.unit is None:
            raise RuntimeError("OpenMM runtime is not loaded")
        if not self.gpu_visible():
            raise RuntimeError("OpenMM CUDA endpoint requires a visible NVIDIA GPU")
        openmm = self.openmm
        unit = self.unit
        particle_count = bounded_int(payload, "particle_count", 512, 2, MAX_PARTICLES)
        steps = bounded_int(payload, "steps", 10000, 1, MAX_STEPS)
        timestep_fs = bounded_float(payload, "timestep_fs", 2.0, 0.1, 10.0)
        temperature_k = bounded_float(payload, "temperature_k", 120.0, 1.0, 1000.0)
        friction_per_ps = bounded_float(payload, "friction_per_ps", 1.0, 0.001, 100.0)
        seed = bounded_int(payload, "seed", 17, 0, 2_147_483_647)
        integrator_name = str(payload.get("integrator", "LangevinMiddle"))
        if integrator_name not in {"LangevinMiddle", "Verlet"}:
            raise ValueError("integrator must be LangevinMiddle or Verlet")
        precision = str(payload.get("precision", "mixed")).lower()
        if precision not in {"single", "mixed", "double"}:
            raise ValueError("precision must be single, mixed, or double")
        platform_name = str(payload.get("platform", "CUDA"))
        if platform_name not in self.platforms:
            raise ValueError(f"platform {platform_name!r} is unavailable")
        if platform_name != "CUDA":
            raise ValueError("this Serverless template requires platform=CUDA")

        system = openmm.System()
        force = openmm.NonbondedForce()
        force.setNonbondedMethod(openmm.NonbondedForce.CutoffPeriodic)
        force.setCutoffDistance(1.0 * unit.nanometer)
        force.setUseDispersionCorrection(True)
        for _ in range(particle_count):
            system.addParticle(39.948 * unit.dalton)
            force.addParticle(
                0.0 * unit.elementary_charge,
                0.3405 * unit.nanometer,
                0.996 * unit.kilojoule_per_mole,
            )
        system.addForce(force)
        side = math.ceil(particle_count ** (1 / 3))
        box_length_nm = max(side * 0.42, 2.5)
        system.setDefaultPeriodicBoxVectors(
            openmm.Vec3(box_length_nm, 0, 0) * unit.nanometer,
            openmm.Vec3(0, box_length_nm, 0) * unit.nanometer,
            openmm.Vec3(0, 0, box_length_nm) * unit.nanometer,
        )
        if integrator_name == "Verlet":
            integrator = openmm.VerletIntegrator(timestep_fs * unit.femtosecond)
        else:
            integrator = openmm.LangevinMiddleIntegrator(
                temperature_k * unit.kelvin,
                friction_per_ps / unit.picosecond,
                timestep_fs * unit.femtosecond,
            )
            integrator.setRandomNumberSeed(seed)
        platform = openmm.Platform.getPlatformByName(platform_name)
        properties = {"Precision": precision} if platform_name == "CUDA" else {}
        context = openmm.Context(system, integrator, platform, properties)
        positions = [
            openmm.Vec3((i % side) * 0.42, ((i // side) % side) * 0.42, (i // side**2) * 0.42)
            * unit.nanometer
            for i in range(particle_count)
        ]
        context.setPositions(positions)
        context.setVelocitiesToTemperature(temperature_k * unit.kelvin, seed)
        started = time.perf_counter()
        integrator.step(steps)
        integration_seconds = time.perf_counter() - started
        state = context.getState(getEnergy=True, getPositions=True)
        final_positions = state.getPositions(asNumpy=False).value_in_unit(unit.nanometer)
        preview = [[round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6)] for p in final_positions[:32]]
        simulated_ns = steps * timestep_fs / 1_000_000
        ns_per_day = simulated_ns * 86400 / integration_seconds
        positions_artifact = work_dir / "final-positions-preview.json"
        positions_artifact.write_text(
            __import__("json").dumps({"units": "nm", "positions": preview}, indent=2),
            encoding="utf-8",
        )
        del context, integrator, system
        return {
            "engine": "OpenMM",
            "engine_version": importlib.metadata.version("openmm"),
            "system": "argon_lennard_jones",
            "ensemble": "NVE" if integrator_name == "Verlet" else "NVT",
            "platform": platform_name,
            "precision": precision,
            "particle_count": particle_count,
            "periodic_box_length_nm": round(box_length_nm, 6),
            "steps": steps,
            "timestep_fs": timestep_fs,
            "simulated_ns": round(simulated_ns, 9),
            "integration_seconds": round(integration_seconds, 6),
            "integration_ns_per_day": round(ns_per_day, 3),
            "potential_energy_kj_per_mol": round(float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)), 6),
            "kinetic_energy_kj_per_mol": round(float(state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)), 6),
            "research_only": True,
        }


app = create_app(OpenMMAdapter())
