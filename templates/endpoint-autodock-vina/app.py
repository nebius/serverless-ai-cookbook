from __future__ import annotations

import csv
import importlib.metadata
import json
import math
import os
from pathlib import Path
from typing import Any

from hcls_api import create_app


MAX_STRUCTURE_CHARS = 2_000_000


def finite_vector(payload: dict[str, Any], name: str, default: list[float], low: float, high: float) -> list[float]:
    raw = payload.get(name, default)
    if not isinstance(raw, list) or len(raw) != 3:
        raise ValueError(f"{name} must be a three-number list")
    values = [float(item) for item in raw]
    if any(not math.isfinite(item) or item < low or item > high for item in values):
        raise ValueError(f"{name} values must be between {low} and {high}")
    return values


class VinaAdapter:
    service_id = "autodock-vina"

    def __init__(self) -> None:
        self.vina_class = None
        self.example_root = Path(os.environ.get("VINA_EXAMPLE_ROOT", "/opt/hcls/examples/vina"))

    def load(self) -> None:
        from vina import Vina

        self.vina_class = Vina
        for name in ("1iep_receptor.pdbqt", "1iep_ligand.pdbqt"):
            if not (self.example_root / name).is_file():
                raise RuntimeError(f"missing bundled example asset: {name}")

    def health(self) -> dict[str, Any]:
        return {"ready": self.vina_class is not None, "engine": "AutoDock Vina", "engine_version": importlib.metadata.version("vina"), "accelerator": "CPU"}

    def capabilities(self) -> dict[str, Any]:
        return {
            "workload": "molecular_docking",
            "engine": {"name": "AutoDock Vina", "version": importlib.metadata.version("vina"), "scoring_semantics": "vina"},
            "accelerator": {"required": False, "kind": "CPU"},
            "examples": [{"id": "1iep-sti-redocking", "label": "1IEP/STI public redocking", "input": {"center": [15.19, 53.903, 16.917], "size": [20.0, 20.0, 20.0], "exhaustiveness": 8, "n_poses": 9, "seed": 17}}],
            "accepted_inputs": ["bundled_1iep_sti", "receptor_pdbqt+ligand_pdbqt"],
            "limits": {"structure_chars": MAX_STRUCTURE_CHARS, "exhaustiveness": 64, "n_poses": 20, "cpu": 32},
            "metrics": ["best_affinity_kcal_per_mol", "wall_clock_seconds"],
            "disclaimer": "Vina scores are research heuristics and are not interchangeable with AutoDock-GPU/AutoDock4 scores.",
        }

    def structure(self, payload: dict[str, Any], key: str, default_name: str, destination: Path) -> Path:
        value = payload.get(key)
        if value is None:
            source = self.example_root / default_name
            destination.write_bytes(source.read_bytes())
            return destination
        if not isinstance(value, str) or len(value) > MAX_STRUCTURE_CHARS:
            raise ValueError(f"{key} must be PDBQT text no larger than {MAX_STRUCTURE_CHARS} characters")
        if "ROOT" not in value and key == "ligand_pdbqt":
            raise ValueError("ligand_pdbqt does not look like a PDBQT ligand")
        if "ATOM" not in value and "HETATM" not in value:
            raise ValueError(f"{key} does not contain PDBQT atom records")
        destination.write_text(value, encoding="utf-8")
        return destination

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        if self.vina_class is None:
            raise RuntimeError("Vina runtime is not loaded")
        custom_structure = payload.get("receptor_pdbqt") is not None or payload.get("ligand_pdbqt") is not None
        if custom_structure and ("center" not in payload or "size" not in payload):
            raise ValueError("custom receptor or ligand inputs require explicit center and size")
        center = finite_vector(payload, "center", [15.19, 53.903, 16.917], -1000, 1000)
        size = finite_vector(payload, "size", [20.0, 20.0, 20.0], 1, 60)
        exhaustiveness = int(payload.get("exhaustiveness", 8))
        n_poses = int(payload.get("n_poses", 9))
        cpu = int(payload.get("cpu", 0))
        seed = int(payload.get("seed", 17))
        if exhaustiveness < 1 or exhaustiveness > 64:
            raise ValueError("exhaustiveness must be between 1 and 64")
        if n_poses < 1 or n_poses > 20:
            raise ValueError("n_poses must be between 1 and 20")
        if cpu < 0 or cpu > 32:
            raise ValueError("cpu must be between 0 and 32")
        if seed < 0 or seed > 2_147_483_647:
            raise ValueError("seed is out of range")
        receptor = self.structure(payload, "receptor_pdbqt", "1iep_receptor.pdbqt", work_dir / "receptor.pdbqt")
        ligand = self.structure(payload, "ligand_pdbqt", "1iep_ligand.pdbqt", work_dir / "ligand.pdbqt")
        output = work_dir / "poses.pdbqt"
        vina = self.vina_class(sf_name="vina", cpu=cpu, seed=seed, verbosity=1)
        vina.set_receptor(str(receptor))
        vina.set_ligand_from_file(str(ligand))
        vina.compute_vina_maps(center=center, box_size=size)
        vina.dock(exhaustiveness=exhaustiveness, n_poses=n_poses)
        vina.write_poses(str(output), n_poses=n_poses, overwrite=True)
        energies = vina.energies(n_poses=n_poses).tolist()
        with (work_dir / "scores.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "pose_rank",
                    "total_kcal_per_mol",
                    "inter_kcal_per_mol",
                    "intra_kcal_per_mol",
                    "torsions_kcal_per_mol",
                    "intra_best_pose_kcal_per_mol",
                ]
            )
            for index, row in enumerate(energies, 1):
                writer.writerow([index, *row])
        summary = {
            "engine": "AutoDock Vina",
            "engine_version": importlib.metadata.version("vina"),
            "scoring_semantics": "vina",
            "center": center,
            "size": size,
            "exhaustiveness": exhaustiveness,
            "n_poses": n_poses,
            "seed": seed,
            "scores": [
                {
                    "rank": index,
                    "total_kcal_per_mol": row[0],
                    "inter_kcal_per_mol": row[1],
                    "intra_kcal_per_mol": row[2],
                    "torsions_kcal_per_mol": row[3],
                    "intra_best_pose_kcal_per_mol": row[4],
                }
                for index, row in enumerate(energies, 1)
            ],
            "best_affinity_kcal_per_mol": energies[0][0] if energies else None,
            "research_only": True,
        }
        (work_dir / "docking-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary


app = create_app(VinaAdapter())
