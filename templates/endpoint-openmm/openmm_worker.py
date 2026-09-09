from __future__ import annotations

import importlib.metadata
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


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


def platforms(openmm: Any) -> list[str]:
    return [
        openmm.Platform.getPlatform(index).getName()
        for index in range(openmm.Platform.getNumPlatforms())
    ]


def create_system(openmm: Any, unit: Any, particle_count: int) -> tuple[Any, float, list[Any]]:
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
    positions = [
        openmm.Vec3(
            (index % side) * 0.42,
            ((index // side) % side) * 0.42,
            (index // side**2) * 0.42,
        )
        * unit.nanometer
        for index in range(particle_count)
    ]
    return system, box_length_nm, positions


def execute(payload: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    import openmm
    from openmm import unit

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
    available = platforms(openmm)
    if platform_name != "CUDA" or platform_name not in available:
        raise ValueError("this Serverless template requires the OpenMM CUDA platform")

    system, box_length_nm, positions = create_system(openmm, unit, particle_count)
    if integrator_name == "Verlet":
        integrator = openmm.VerletIntegrator(timestep_fs * unit.femtosecond)
    else:
        integrator = openmm.LangevinMiddleIntegrator(
            temperature_k * unit.kelvin,
            friction_per_ps / unit.picosecond,
            timestep_fs * unit.femtosecond,
        )
        integrator.setRandomNumberSeed(seed)
    platform = openmm.Platform.getPlatformByName("CUDA")
    context = openmm.Context(system, integrator, platform, {"Precision": precision})
    context.setPositions(positions)
    context.setVelocitiesToTemperature(temperature_k * unit.kelvin, seed)
    started = time.perf_counter()
    integrator.step(steps)
    integration_seconds = time.perf_counter() - started
    state = context.getState(getEnergy=True, getPositions=True)
    final_positions = state.getPositions(asNumpy=False).value_in_unit(unit.nanometer)
    preview = [
        [round(float(position.x), 6), round(float(position.y), 6), round(float(position.z), 6)]
        for position in final_positions[:32]
    ]
    (output_dir / "final-positions-preview.json").write_text(
        json.dumps({"units": "nm", "positions": preview}, indent=2), encoding="utf-8"
    )
    simulated_ns = steps * timestep_fs / 1_000_000
    result = {
        "engine": "OpenMM",
        "engine_version": importlib.metadata.version("openmm"),
        "system": "argon_lennard_jones",
        "ensemble": "NVE" if integrator_name == "Verlet" else "NVT",
        "platform": "CUDA",
        "precision": precision,
        "particle_count": particle_count,
        "periodic_box_length_nm": round(box_length_nm, 6),
        "steps": steps,
        "timestep_fs": timestep_fs,
        "simulated_ns": round(simulated_ns, 9),
        "integration_seconds": round(integration_seconds, 6),
        "integration_ns_per_day": round(simulated_ns * 86400 / integration_seconds, 3),
        "potential_energy_kj_per_mol": round(
            float(state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)), 6
        ),
        "kinetic_energy_kj_per_mol": round(
            float(state.getKineticEnergy().value_in_unit(unit.kilojoule_per_mole)), 6
        ),
        "research_only": True,
    }
    del context, integrator, system
    return result


def probe() -> None:
    import openmm
    from openmm import unit

    available = platforms(openmm)
    if "CUDA" not in available:
        failures = list(openmm.Platform.getPluginLoadFailures())
        raise RuntimeError(
            "OpenMM CUDA platform is unavailable; plugin load failures: "
            + json.dumps(failures)
        )
    system, _, positions = create_system(openmm, unit, 8)
    integrator = openmm.VerletIntegrator(1.0 * unit.femtosecond)
    context = openmm.Context(
        system,
        integrator,
        openmm.Platform.getPlatformByName("CUDA"),
        {"Precision": "single"},
    )
    context.setPositions(positions)
    integrator.step(1)
    del context, integrator, system
    print(
        json.dumps(
            {
                "engine_version": importlib.metadata.version("openmm"),
                "available_platforms": available,
                "cuda_step_passed": True,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "probe":
        probe()
        return
    if len(sys.argv) != 3:
        raise SystemExit("usage: openmm_worker.py INPUT_JSON OUTPUT_JSON")
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    result = execute(json.loads(input_path.read_text(encoding="utf-8")), output_path.parent)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
