from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from hcls_api import create_app
from hcls_api.oci_runtime import run_in_runtime


MAX_LIGANDS = 32
MAX_LIGAND_CHARS = 2_000_000
SAFE_LIGAND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ENERGY_PATTERN = re.compile(
    r"Estimated Free Energy of Binding\s*=\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s+kcal/mol"
)


class AutoDockGpuAdapter:
    service_id = "autodock-gpu"

    def __init__(self) -> None:
        self.rootfs = Path("/")
        self.binary = ""
        self.image_environment: dict[str, str] = {}
        self.runtime: dict[str, Any] = {}
        self.example_root = Path(os.environ.get("AUTODOCK_GPU_EXAMPLE_ROOT", "/opt/hcls/examples/autodock-gpu/1stp"))
        self.timeout_seconds = max(30, min(int(os.environ.get("HCLS_ENGINE_TIMEOUT_SECONDS", "900")), 3600))

    def load(self) -> None:
        spec_path = os.environ.get("AUTODOCK_RUNTIME_SPEC")
        metadata_path = os.environ.get("AUTODOCK_RUNTIME_METADATA")
        if not spec_path or not metadata_path:
            raise RuntimeError("AutoDock-GPU runtime selection is unavailable")
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        self.runtime = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        self.rootfs = Path(spec["rootfs"])
        self.binary = str(spec["guest_command"])
        self.image_environment = dict(spec["image_environment"])
        required = [
            self.example_root / "1stp_protein.maps.fld",
            self.example_root / "1stp_ligand.pdbqt",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"missing AutoDock-GPU runtime assets: {', '.join(missing)}")
        if not self.binary.startswith("/"):
            raise RuntimeError("AutoDock-GPU runtime command is invalid")

    def gpu_details(self) -> dict[str, Any]:
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi is None:
            return {"available": False, "reason": "nvidia-smi is not available"}
        probe = subprocess.run(
            [nvidia_smi, "--query-gpu=name,driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if probe.returncode != 0 or not probe.stdout.strip():
            return {"available": False, "reason": probe.stderr.strip()[:300] or "GPU probe failed"}
        first = probe.stdout.strip().splitlines()[0]
        name, _, driver = first.partition(",")
        return {"available": True, "name": name.strip(), "driver_version": driver.strip()}

    def health(self) -> dict[str, Any]:
        gpu = self.gpu_details()
        return {
            "ready": bool(self.binary) and bool(gpu.get("available")),
            "engine": "AutoDock-GPU",
            "engine_version": self.runtime.get("actual_engine_version", "unknown"),
            "accelerator": "CUDA",
            "gpu": gpu,
            "runtime": self.runtime,
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_docking",
            "engine": {
                "name": "AutoDock-GPU",
                "version": self.runtime.get("actual_engine_version", "unknown"),
                "scoring_semantics": "autodock4",
            },
            "runtime": self.runtime,
            "accelerator": {"required": True, "kind": "NVIDIA CUDA", "thread_block_size": 128},
            "examples": [
                {
                    "id": "1stp-biotin-redocking",
                    "label": "1STP/biotin public redocking",
                    "input": {"nrun": 5, "max_evaluations": 250000, "seed": 17},
                }
            ],
            "accepted_inputs": ["bundled_1stp_biotin", "ligands[].pdbqt_against_bundled_1stp_maps"],
            "limits": {
                "ligands_per_run": MAX_LIGANDS,
                "ligand_chars": MAX_LIGAND_CHARS,
                "nrun": 100,
                "max_evaluations": 2_500_000,
            },
            "metrics": ["best_estimated_binding_energy_kcal_per_mol", "wall_clock_seconds"],
            "disclaimer": (
                "AutoDock4 scores are research heuristics and are not interchangeable with AutoDock Vina scores. "
                "This initial template docks against the bundled 1STP affinity maps."
            ),
        }

    def ligands(self, payload: dict[str, Any], work_dir: Path) -> list[tuple[str, Path]]:
        raw_ligands = payload.get("ligands")
        if raw_ligands is None:
            return [("1stp-biotin", self.example_root / "1stp_ligand.pdbqt")]
        if not isinstance(raw_ligands, list) or not 1 <= len(raw_ligands) <= MAX_LIGANDS:
            raise ValueError(f"ligands must contain between 1 and {MAX_LIGANDS} entries")
        parsed: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for index, item in enumerate(raw_ligands, 1):
            if not isinstance(item, dict):
                raise ValueError("each ligand must be an object with id and pdbqt")
            ligand_id = str(item.get("id", f"ligand-{index:03d}"))
            pdbqt = item.get("pdbqt")
            if not SAFE_LIGAND_ID.fullmatch(ligand_id) or ligand_id in seen:
                raise ValueError(f"invalid or duplicate ligand id: {ligand_id}")
            if not isinstance(pdbqt, str) or not 1 <= len(pdbqt) <= MAX_LIGAND_CHARS:
                raise ValueError(f"ligand {ligand_id} must contain bounded PDBQT text")
            if "ROOT" not in pdbqt or ("ATOM" not in pdbqt and "HETATM" not in pdbqt):
                raise ValueError(f"ligand {ligand_id} does not look like a PDBQT ligand")
            path = work_dir / f"{ligand_id}.pdbqt"
            path.write_text(pdbqt, encoding="utf-8")
            parsed.append((ligand_id, path))
            seen.add(ligand_id)
        return parsed

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        gpu = self.gpu_details()
        if not gpu.get("available"):
            raise RuntimeError(f"CUDA GPU is required: {gpu.get('reason', 'GPU unavailable')}")
        nrun = int(payload.get("nrun", 5))
        max_evaluations = int(payload.get("max_evaluations", 250_000))
        seed = int(payload.get("seed", 17))
        if not 1 <= nrun <= 100:
            raise ValueError("nrun must be between 1 and 100")
        if not 1_000 <= max_evaluations <= 2_500_000:
            raise ValueError("max_evaluations must be between 1000 and 2500000")
        if not 0 <= seed <= 2_147_483_647:
            raise ValueError("seed is out of range")

        fld_file = self.example_root / "1stp_protein.maps.fld"
        results: list[dict[str, Any]] = []
        for index, (ligand_id, ligand_path) in enumerate(self.ligands(payload, work_dir), 1):
            result_name = f"result-{index:03d}-{ligand_id}"
            completed = run_in_runtime(
                rootfs=self.rootfs,
                guest_command=self.binary,
                args=[
                    "--ffile",
                    str(fld_file),
                    "--lfile",
                    str(ligand_path),
                    "--resnam",
                    result_name,
                    "--nrun",
                    str(nrun),
                    "--nev",
                    str(max_evaluations),
                    "--heuristics",
                    "0",
                    "--autostop",
                    "1",
                    "--seed",
                    str(seed + index - 1),
                    "--xmloutput",
                    "1",
                    "--dlgoutput",
                    "1",
                ],
                cwd=work_dir,
                image_environment=self.image_environment,
                timeout=self.timeout_seconds,
            )
            (work_dir / f"{result_name}.stdout.log").write_text(completed.stdout[-1_000_000:], encoding="utf-8")
            (work_dir / f"{result_name}.stderr.log").write_text(completed.stderr[-1_000_000:], encoding="utf-8")
            if completed.returncode != 0:
                raise RuntimeError(
                    f"AutoDock-GPU failed for {ligand_id} with exit code {completed.returncode}: "
                    f"{completed.stderr.strip()[-800:]}"
                )
            dlg_path = work_dir / f"{result_name}.dlg"
            if not dlg_path.is_file():
                raise RuntimeError(f"AutoDock-GPU did not create {dlg_path.name}")
            values = [float(match) for match in ENERGY_PATTERN.findall(dlg_path.read_text(encoding="utf-8", errors="replace"))]
            if not values:
                raise RuntimeError(f"AutoDock-GPU output for {ligand_id} did not contain binding energies")
            results.append(
                {
                    "ligand_id": ligand_id,
                    "best_estimated_binding_energy_kcal_per_mol": min(values),
                    "run_energies_kcal_per_mol": values,
                    "dlg_artifact": dlg_path.name,
                    "xml_artifact": f"{result_name}.xml",
                }
            )

        with (work_dir / "scores.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ligand_id", "best_estimated_binding_energy_kcal_per_mol"])
            for result in results:
                writer.writerow([result["ligand_id"], result["best_estimated_binding_energy_kcal_per_mol"]])
        summary = {
            "engine": "AutoDock-GPU",
            "engine_version": self.runtime.get("actual_engine_version", "unknown"),
            "runtime": self.runtime,
            "scoring_semantics": "autodock4",
            "nrun": nrun,
            "max_evaluations": max_evaluations,
            "seed": seed,
            "gpu": gpu,
            "ligand_count": len(results),
            "results": results,
            "research_only": True,
        }
        (work_dir / "docking-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


app = create_app(AutoDockGpuAdapter())
