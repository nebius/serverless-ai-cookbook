from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from hcls_api import create_app


MAX_LIGANDS = 32
MAX_LIGAND_CHARS = 2_000_000
SAFE_LIGAND_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ENERGY_PATTERN = re.compile(
    r"Estimated Free Energy of Binding\s*=\s*([+-]?[0-9]+(?:\.[0-9]+)?)\s+kcal/mol"
)


class AutoDockGpuAdapter:
    service_id = "autodock-gpu"

    def __init__(self) -> None:
        self.binary = Path(os.environ.get("AUTODOCK_GPU_BINARY", "/usr/local/bin/autodock_gpu_128wi"))
        self.example_root = Path(os.environ.get("AUTODOCK_GPU_EXAMPLE_ROOT", "/opt/hcls/examples/autodock-gpu/1stp"))
        self.timeout_seconds = max(30, min(int(os.environ.get("HCLS_ENGINE_TIMEOUT_SECONDS", "900")), 3600))
        self.cuda_probe_passed = False

    def load(self) -> None:
        required = [
            self.binary,
            self.example_root / "1stp_protein.maps.fld",
            self.example_root / "1stp_ligand.pdbqt",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(f"missing AutoDock-GPU runtime assets: {', '.join(missing)}")
        if not os.access(self.binary, os.X_OK):
            raise RuntimeError(f"AutoDock-GPU binary is not executable: {self.binary}")
        self.probe_cuda()

    def probe_cuda(self) -> None:
        workspace = Path(tempfile.mkdtemp(prefix="autodock-gpu-probe-"))
        try:
            completed = subprocess.run(
                [
                    str(self.binary),
                    "--ffile",
                    str(self.example_root / "1stp_protein.maps.fld"),
                    "--lfile",
                    str(self.example_root / "1stp_ligand.pdbqt"),
                    "--resnam",
                    "startup-probe",
                    "--nrun",
                    "1",
                    "--nev",
                    "1000",
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
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "no output")[-1200:]
                raise RuntimeError(f"AutoDock-GPU CUDA startup probe failed: {detail}")
            self.cuda_probe_passed = True
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

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
            "ready": self.binary.is_file() and bool(gpu.get("available")) and self.cuda_probe_passed,
            "engine": "AutoDock-GPU",
            "engine_version": "v1.6",
            "accelerator": "CUDA",
            "gpu": gpu,
            "cuda_probe": "1STP docking passed" if self.cuda_probe_passed else "not passed",
        }

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_docking",
            "engine": {
                "name": "AutoDock-GPU",
                "version": "v1.6",
                "source_revision": "e63e6f6280ebfad18caa3e8f48afdc269e79e063",
                "scoring_semantics": "autodock4",
            },
            "accelerator": {
                "required": True,
                "kind": "NVIDIA CUDA",
                "thread_block_size": 128,
                "compiled_compute_capabilities": ["8.0", "8.6", "8.9", "9.0"],
                "blackwell_supported": False,
            },
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
                "This build contains native SM80, SM86, SM89, and SM90 cubins only; Blackwell GPUs are not supported. "
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
            completed = subprocess.run(
                [
                    str(self.binary),
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
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
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
            "engine_version": "v1.6",
            "scoring_semantics": "autodock4",
            "nrun": nrun,
            "max_evaluations": max_evaluations,
            "seed": seed,
            "gpu": gpu,
            "compiled_compute_capabilities": ["8.0", "8.6", "8.9", "9.0"],
            "ligand_count": len(results),
            "results": results,
            "research_only": True,
        }
        (work_dir / "docking-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


app = create_app(AutoDockGpuAdapter())
