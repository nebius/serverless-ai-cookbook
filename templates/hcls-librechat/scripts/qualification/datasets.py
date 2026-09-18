#!/usr/bin/env python3
"""Freeze public experimental references and prepare exact hosted-model cases.

Network downloads go to the requested campaign directory with hashes/provenance.
No model calls, keys, cluster mutations, or external MSA service calls occur here.
"""

from __future__ import annotations

import argparse
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen


PROTEINS = [
    ("1L2Y", "1", "A", "Trp-cage miniprotein"),
    ("1FSD", "1", "A", "Designed zinc-finger fold"),
    ("1CRN", "1", "A", "Crambin"),
    ("1ENH", "1", "A", "Engrailed homeodomain"),
    ("1BPI", "1", "A", "Bovine pancreatic trypsin inhibitor"),
    ("1PGB", "1", "A", "Protein G B1 domain"),
    ("1VII", "1", "A", "Villin headpiece"),
    ("2CI2", "1", "I", "Chymotrypsin inhibitor 2"),
    ("1CSP", "1", "A", "Cold-shock protein"),
    ("2PTL", "1", "A", "Protein L domain"),
    ("1UBQ", "1", "A", "Ubiquitin"),
    ("1BTA", "1", "A", "Barstar"),
    ("1TEN", "1", "A", "Tenascin fibronectin type III domain"),
    ("1QYS", "1", "A", "Top7 designed protein"),
    ("2TRX", "1", "A", "Thioredoxin"),
    ("1LYZ", "1", "A", "Lysozyme"),
    ("1MBN", "1", "A", "Myoglobin"),
    ("1AKE", "1", "A", "Adenylate kinase"),
    ("1GFL", "1", "A", "Green fluorescent protein"),
    ("1TIM", "1", "A", "Triosephosphate isomerase"),
]

DOCKING = [
    ("3PTB", "A", "BEN", "Trypsin-benzamidine"),
    ("1IEP", "A", "STI", "ABL kinase-imatinib"),
    ("1STP", "A", "BTN", "Streptavidin-biotin"),
    ("3O96", "A", "IQO", "AKT1-allosteric inhibitor"),
    ("3ERT", "A", "OHT", "Estrogen receptor-4-hydroxytamoxifen"),
    ("1A52", "A", "EST", "Estrogen receptor-estradiol"),
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def fetch(url: str, path: Path) -> tuple[bytes, dict]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        data = path.read_bytes()
    else:
        for attempt in range(3):
            try:
                with urlopen(Request(url, headers={"User-Agent": "ScientificAI-qualification/1.0"}), timeout=45) as response:
                    data = response.read(10_000_001)
                if len(data) > 10_000_000:
                    raise ValueError("Reference exceeds the 10 MB preparation limit.")
                path.write_bytes(data)
                break
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(1 + attempt)
    return data, {"url": url, "path": str(path), "sha256": digest(data), "size_bytes": len(data)}


def protein_chain(pdb: str, chain: str) -> str:
    selected = []
    for line in pdb.splitlines():
        if line.startswith("ENDMDL"):
            break
        if line.startswith("ATOM  ") and line[21:22] == chain and line[16:17] in {" ", "A"}:
            selected.append(line)
    if not selected:
        raise ValueError(f"No ATOM records for chain {chain}.")
    return "\n".join(selected + ["TER", "END", ""])


def prepare_protein(spec: tuple, output: Path, repetitions: int, include_batch: bool = False) -> tuple[list, dict]:
    pdb_id, entity, chain, label = spec
    folder = output / "references" / pdb_id.lower()
    pdb_bytes, pdb_receipt = fetch(f"https://files.rcsb.org/download/{pdb_id}.pdb", folder / "source.pdb")
    entity_bytes, entity_receipt = fetch(f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity}", folder / "entity.json")
    metadata = json.loads(entity_bytes)
    auth_chains = metadata["rcsb_polymer_entity_container_identifiers"]["auth_asym_ids"]
    if chain not in auth_chains:
        raise ValueError(f"Expected chain {chain} is absent from polymer entity {entity}: {auth_chains}")
    sequence = "".join(metadata["entity_poly"]["pdbx_seq_one_letter_code_can"].split())
    if not sequence or any(letter not in "ACDEFGHIKLMNPQRSTVWY" for letter in sequence):
        raise ValueError("Canonical sequence contains noncanonical residues; retain as preparation blocker.")
    receptor = protein_chain(pdb_bytes.decode(), chain)
    ref_path = folder / "reference-chain.pdb"
    ref_path.write_text(receptor)
    sources = [pdb_receipt, entity_receipt]
    for source in sources:
        source["path"] = str(Path(source["path"]).relative_to(output))
    provenance = {"dataset_id": f"rcsb-{pdb_id.lower()}", "pdb_id": pdb_id,
                  "label": label, "source_url": f"https://www.rcsb.org/structure/{pdb_id}",
                  "license": "CC0", "sources": sources, "reference_sha256": digest(receptor.encode()),
                  "protocol_deviation": "Single-sequence only; no templates, relaxation or online MSA. Historical structures may overlap training data. Not a paper-reproduction or held-out benchmark."}
    cases = []
    for repetition in range(1, repetitions + 1):
        for model in ("openfold2", "boltz2"):
            case_id = f"{model}-{pdb_id.lower()}-{chain}-r{repetition}"
            arguments = {"input_id": case_id, "sequence": sequence, "selected_models": [1], "relax_prediction": False}
            tool = "infer_openfold2_native"
            if model == "boltz2":
                tool = "boltz2_predict_native"
                arguments = {"polymers": [{"id": "A", "molecule_type": "protein", "sequence": sequence,
                    "msa": {"msa_search": {"a3m": {"alignment": f">query\n{sequence}\n"}}}}],
                    "recycling_steps": 3, "sampling_steps": 200, "diffusion_samples": 1, "output_format": "mmcif"}
            cases.append({"case_id": case_id, "persona": "structural-bioinformatician", "model_id": model,
                "tool": tool, "mode": "native", "arguments": arguments,
                "expected": {"evaluator": "protein_structure", "reference_path": str(ref_path.relative_to(output)),
                    "reference_chain": chain, "input_sequence": sequence,
                    "thresholds": {"sequence_identity_min": 1.0, "input_coverage_min": 1.0}},
                "provenance": provenance, "workload": {"unique_input_id": f"rcsb-{pdb_id.lower()}-{chain}",
                    "repetition": repetition, "seed": None, "priority": "interactive" if repetition == 1 else "batch"}})
        if include_batch:
            template = copy.deepcopy(cases[-1])
            case_id = f"openfold3-{pdb_id.lower()}-{chain}-r{repetition}"
            native = copy.deepcopy(template)
            native.update(case_id=case_id, model_id="openfold3", tool="infer_openfold3_native",
                arguments={"request_id": case_id, "inputs": [{"input_id": case_id, "output_format": "cif",
                    "molecules": [{"type": "protein", "id": "A", "sequence": sequence}]}]})
            native["workload"]["seed"] = 42
            native["provenance"]["protocol_deviation"] += " Preview2 has fixed seed 42; repeats are not different seeds."
            cases.append(native)
            for model in ("esmfold2", "esmfold2-fast", "protenix-v2", "openfold3-openbind", "alphafold3"):
                cases.append(batch_folding_case(template, model, sequence, repetition, folder, output))
    return cases, {"pdb_id": pdb_id, "residues": len(sequence), "status": "prepared", "case_count": len(cases)}


def batch_folding_case(template: dict, model: str, sequence: str, repetition: int, folder: Path, output: Path) -> dict:
    seed = (1, 7, 42, 101, 202, 303, 404, 505, 606, 707)[repetition - 1]
    case = copy.deepcopy(template)
    case_id = template["case_id"].replace("boltz2", model, 1)
    operation = "predict-complex-structure"
    input_name, semantic_type = "", ""
    if model.startswith("esmfold2"):
        operation = "predict-structure" if model == "esmfold2" else "predict-protein-structure"
        input_name, semantic_type = f"{model}-input", f"{model}-input-json/v1"
        source = {"sequences": [{"id": "A", "sequence": sequence, "type": "protein"}]}
        parameters = {"sequence": sequence, "mode": "single-sequence", "seed": seed}
    elif model == "protenix-v2":
        input_name, semantic_type = "protenix-input", "protenix-input-json/v1"
        source = [{"name": case_id, "sequences": [{"proteinChain": {"count": 1, "sequence": sequence}}]}]
        parameters = {"checkpoint": "protenix-v2", "msa_mode": "none", "sample_count": 1, "model_seeds": [seed]}
    elif model == "openfold3-openbind":
        input_name, semantic_type = "openfold3-input", "openfold3-input-json/v1"
        source = {"queries": {case_id: {"chains": [{"chain_ids": ["A"], "molecule_type": "protein", "sequence": sequence}]}}}
        parameters = {"msa_mode": "none", "model_seeds": [seed]}
    elif model == "alphafold3":
        input_name, semantic_type = "fold-input", "alphafold3-fold-input/v1"
        source = {"dialect": "alphafold3", "version": 2, "name": case_id, "modelSeeds": [seed],
            "sequences": [{"protein": {"id": "A", "sequence": sequence,
                "unpairedMsa": f">query\n{sequence}\n", "pairedMsa": "", "templates": []}}]}
        parameters = {"input_mode": "raw"}
    else:
        raise ValueError(f"Unsupported batch folding model: {model}")
    source_path = folder / f"{case_id}-input.json"
    write_json(source_path, source)
    case.update(case_id=case_id, model_id=model, tool="submit_" + model.replace("-", "_"), mode="scientific-batch",
        arguments={"schema": "fs2-serve.nebius.ai/scientific-run-request/v1", "operation": operation,
            "service_class": "customer-batch", "parameters": parameters},
        preparation={"inputs": [{"name": input_name, "semantic_type": semantic_type,
            "local_path": str(source_path.relative_to(output)), "media_type": "application/json", "compression": "none",
            "sha256": digest(source_path.read_bytes()), "size_bytes": source_path.stat().st_size}]})
    case["workload"]["seed"] = seed
    return case


def prepare_docking(spec: tuple, output: Path, seeds: list[int]) -> tuple[list, dict]:
    from rdkit import Chem
    pdb_id, chain, ligand, label = spec
    folder = output / "references" / (pdb_id.lower() + "-" + ligand.lower())
    pdb_bytes, pdb_receipt = fetch(f"https://files.rcsb.org/download/{pdb_id}.pdb", folder / "source.pdb")
    sdf_url = f"https://models.rcsb.org/v1/{pdb_id.lower()}/ligand?auth_asym_id={chain}&label_comp_id={ligand}&encoding=sdf"
    ligand_bytes, ligand_receipt = fetch(sdf_url, folder / "reference-ligand.sdf")
    mol = Chem.MolFromMolBlock(ligand_bytes.decode().split("$$$$")[0], removeHs=True)
    if mol is None or mol.GetNumAtoms() < 4:
        raise ValueError("Bound ligand instance cannot be parsed or is absent.")
    smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    receptor = protein_chain(pdb_bytes.decode(), chain)
    receptor_path = folder / "receptor.pdb"
    receptor_path.write_text(receptor)
    sources = [pdb_receipt, ligand_receipt]
    for source in sources:
        source["path"] = str(Path(source["path"]).relative_to(output))
    cases = []
    for seed in seeds:
        for num_poses in (1, 4):
            cases.append({"case_id": f"diffdock-{pdb_id.lower()}-{ligand.lower()}-s{seed}-n{num_poses}",
                "persona": "computational-chemist", "model_id": "diffdock", "tool": "infer_diffdock_native", "mode": "native",
                "arguments": {"protein": receptor, "ligand": smiles, "ligand_file_type": "txt",
                    "num_poses": num_poses, "time_divisions": 20, "steps": 18, "random_seed": seed,
                    "save_trajectory": False, "skip_gen_conformer": False},
                "preparation": {"artifact_fields": [{"argument_path": "protein", "local_path": str(receptor_path.relative_to(output)), "media_type": "chemical/x-pdb"}]},
                "expected": {"evaluator": "docking_pose", "reference_path": str((folder / "reference-ligand.sdf").relative_to(output)),
                    "num_poses": num_poses, "thresholds": {"success_rmsd_angstrom": 2.0}},
                "provenance": {"dataset_id": f"rcsb-{pdb_id.lower()}-{ligand.lower()}", "pdb_id": pdb_id,
                    "label": label, "source_url": f"https://www.rcsb.org/structure/{pdb_id}", "license": "CC0", "sources": sources,
                    "protocol_deviation": "Bound receptor redocking, one protein chain, no waters/cofactors; crystal ligand coordinates used only for evaluation. No PDBbind dataset reproduction claim; training overlap unknown."},
                "workload": {"unique_input_id": f"rcsb-{pdb_id.lower()}-{ligand.lower()}", "repetition": 1, "seed": seed, "priority": "batch"}})
    return cases, {"pdb_id": pdb_id, "ligand": ligand, "heavy_atoms": mol.GetNumHeavyAtoms(), "status": "prepared", "case_count": len(cases)}


def prepare_designs(backend: Path, output: Path, seeds: list[int]) -> list[dict]:
    """Reuse the solution's exact public artifact encoders and vary real studies."""
    module_path = backend / "acceptance/scientific-fleet/run_acceptance.py"
    spec = importlib.util.spec_from_file_location("qualification_public_fixture_encoder", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    cases = []
    for model in ("proteina-complexa", "boltzgen", "mosaic", "bindcraft", "rfdiffusion"):
        root = "models/cancer-immunotherapy/" + ("images/bindcraft-native" if model == "bindcraft" else f"runtime-images/{model}")
        fragment_path = backend / root / "activation/fragment.json"
        fragment = json.loads(fragment_path.read_text())
        fixtures = fragment["public_fixtures"]
        request = json.loads((backend / fixtures["request"]).read_text())
        materialized = [module._read_declared_input(backend, item) for item in fixtures["supporting_inputs"]]
        original_manifest = json.loads(next(item.data for item in materialized if item.role == "request-input-manifest"))
        inputs = []
        for item in materialized:
            if item.role != "manifest-artifact":
                continue
            entry = next(entry for entry in original_manifest["entries"] if
                         (entry["name"] == item.name if item.name else entry["artifact"]["sha256"] == digest(item.data)))
            folder = output / "design-inputs" / model
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (entry["name"] + ".input")
            path.write_bytes(item.data)
            inputs.append({"name": entry["name"], "semantic_type": entry["semantic_type"],
                "local_path": str(path.relative_to(output)), "media_type": entry["artifact"]["media_type"],
                "compression": entry["artifact"].get("compression", "none"),
                "sha256": digest(item.data), "size_bytes": len(item.data)})
        variants = []
        for seed in seeds:
            if model == "proteina-complexa":
                variants.extend((f"pdl1-s{seed}-n{samples}", {"seed": seed, "num_samples": samples,
                    "diffusion_steps": 100, "run_name": f"qualification-pdl1-s{seed}-n{samples}"},
                    {"minimum_structures": samples}) for samples in (1, 4))
            elif model == "boltzgen":
                # The deployed workflow needs enough candidates for its filters;
                # these repetitions expose selection variance, not seeded replay.
                variants.append((f"pdl1-r{seed}", {"batches": [{"shard_id": "pdl1-face",
                    "num_designs": 20, "budget": 1, "reuse_completed": False}]},
                    {"minimum_structures": 1, "binder_length_min": 60, "binder_length_max": 80}))
            elif model == "mosaic":
                variants.extend((f"ubiquitin-s{seed}-l{length}", {"base_seed": seed, "shard_count": 1,
                    "hotspots": [8, 44, 70], "binder_length": length, "optimizer_steps": 100},
                    {"minimum_structures": 1, "binder_length_min": length, "binder_length_max": length}) for length in (40, 64, 80))
            elif model == "bindcraft":
                variants.extend((f"pdl1-s{seed}-{lane}", {"seed": seed, "designs": 1, "mpnn_lane": lane},
                    {"minimum_structures": 1, "binder_length_min": 67, "binder_length_max": 67}) for lane in ("soluble", "vanilla"))
            else:
                variants.extend((f"unconditional-s{seed}-l{length}", {"seed": seed, "num_designs": 2,
                    "contigs": [f"{length}-{length}"], "diffuser_T": 50},
                    {"minimum_structures": 2, "binder_length_min": length, "binder_length_max": length}) for length in (48, 76, 128, 256))
        if model == "mosaic":
            sequence = json.loads((output / "references/1ubq/entity.json").read_text())["entity_poly"]["pdbx_seq_one_letter_code_can"]
            path = output / inputs[0]["local_path"]
            path.write_text(f">1UBQ_A_ubiquitin\n{sequence}\n")
            inputs[0].update(sha256=digest(path.read_bytes()), size_bytes=path.stat().st_size)
        for variant_id, updates, constraints in variants:
            arguments = {key: copy.deepcopy(request[key]) for key in ("schema", "operation", "service_class", "parameters")}
            arguments["parameters"].update(updates)
            cases.append({"case_id": f"{model}-{variant_id}", "persona": "binder-design-researcher",
                "model_id": model, "tool": "submit_" + model.replace("-", "_"), "mode": "scientific-batch",
                "arguments": arguments, "preparation": {"inputs": copy.deepcopy(inputs)},
                "expected": {"evaluator": "design_constraints", **constraints},
                "provenance": {"dataset_id": "rcsb-1ubq" if model == "mosaic" else "public-pdl1-design" if model != "rfdiffusion" else "unconditional-backbone-design",
                    "source_url": "https://www.rcsb.org/structure/1UBQ" if model == "mosaic" else "https://www.rcsb.org/structure/5J89",
                    "fixture_source": str(fragment_path.relative_to(backend)), "fixture_sha256": digest(fragment_path.read_bytes()),
                    "protocol_deviation": "Computational design, constraint checks and downstream fold evaluation; no experimental binding or efficacy claim. Production filters remain enabled; no winners is a scientific outcome requiring honest delivery, not fabricated success."},
                "workload": {"unique_input_id": ("ubiquitin-hotspots-8-44-70" if model == "mosaic" else "pdl1-binding-face") if model != "rfdiffusion" else variant_id.split("-l")[-1] + "-residue-backbone",
                    "repetition": 1, "seed": updates.get("seed", updates.get("base_seed")), "priority": "batch"}})
    return cases


def prepare_auxiliary_cases(existing: list[dict], output: Path) -> list[dict]:
    from evaluators import design_input_sequence, parse_chain
    cases = []
    for source in [case for case in existing if case["model_id"] == "openfold2" and case["workload"]["repetition"] == 1]:
        pdb_id = source["provenance"]["pdb_id"].lower()
        sequence = source["arguments"]["sequence"]
        for depth in (64, 512):
            cases.append({"case_id": f"msa-search-{pdb_id}-depth{depth}", "persona": "structural-bioinformatician",
                "model_id": "msa-search-pdb70", "tool": "msa_search_native", "mode": "native",
                "arguments": {"sequence": sequence, "databases": ["pdb70_220313"], "output_alignment_formats": ["a3m"], "max_msa_sequences": depth},
                "expected": {"evaluator": "msa_alignment", "input_sequence": sequence, "max_sequences": depth},
                "provenance": copy.deepcopy(source["provenance"]),
                "workload": {"unique_input_id": f"rcsb-{pdb_id}", "repetition": 1, "seed": None, "priority": "interactive"},
                "followups": [{"model_id": "boltz2", "mode": "real-pdb70-msa", "compare_to": source["case_id"].replace("openfold2", "boltz2")},
                    {"model_id": "esmfold2", "mode": "precomputed-msa"}, {"model_id": "openfold3", "mode": "supplied-msa"}]})
        reference_path = output / source["expected"]["reference_path"]
        receptor = reference_path.read_text()
        parsed = parse_chain(receptor, source["expected"]["reference_chain"])
        for seed in (1, 7, 42):
            for temp in (0.1, 0.3, 0.7):
                cases.append({"case_id": f"proteinmpnn-{pdb_id}-s{seed}-t{temp}", "persona": "protein-design-researcher",
                    "model_id": "proteinmpnn", "tool": "infer_proteinmpnn_native", "mode": "native",
                    "arguments": {"input_pdb": receptor, "input_pdb_chains": [parsed["chain"]], "random_seed": seed,
                        "num_seq_per_target": 4, "sampling_temp": temp, "omit_AAs": ["X"]},
                    "preparation": {"artifact_fields": [{"argument_path": "input_pdb", "local_path": source["expected"]["reference_path"], "media_type": "chemical/x-pdb"}]},
                    "expected": {"evaluator": "protein_sequence_design", "input_sequence": design_input_sequence(receptor, [parsed["chain"]]), "num_sequences": 4, "omit_AAs": ["X"]},
                    "provenance": copy.deepcopy(source["provenance"]),
                    "workload": {"unique_input_id": f"rcsb-{pdb_id}", "repetition": 1, "seed": seed, "priority": "batch"},
                    "followups": [{"model_id": "esmfold2-fast", "mode": "sequence-refolding", "reference_path": source["expected"]["reference_path"]}]})
    ligand_sources = {}
    for source in [case for case in existing if case["model_id"] == "diffdock"]:
        ligand_sources.setdefault(source["workload"]["unique_input_id"], source)
    for dataset_id, source in ligand_sources.items():
        for similarity in (0.3, 0.7):
            for count in (1, 8):
                for minimize in (False, True):
                    suffix = f"sim{similarity}-n{count}-{'min' if minimize else 'max'}"
                    cases.append({"case_id": f"molmim-{dataset_id}-{suffix}", "persona": "computational-chemist",
                        "model_id": "molmim", "tool": "molmim_run_native", "mode": "native",
                        "arguments": {"smi": source["arguments"]["ligand"], "algorithm": "CMA-ES", "num_molecules": count,
                            "property_name": "QED", "minimize": minimize, "min_similarity": similarity, "particles": 8, "iterations": 4, "radius": 1},
                        "expected": {"evaluator": "molecule_generation", "source_smiles": source["arguments"]["ligand"],
                            "scoring": "QED", "num_molecules": count, "min_similarity": similarity},
                        "provenance": copy.deepcopy(source["provenance"]),
                        "workload": {"unique_input_id": dataset_id, "repetition": 1, "seed": None, "priority": "batch"}})
    for lower, upper in ((10, 20), (20, 30), (30, 50)):
        for scoring in ("QED", "LogP"):
            for count in (1, 16):
                for repetition in (1, 2, 3):
                    cases.append({"case_id": f"genmol-{lower}-{upper}-{scoring.lower()}-n{count}-r{repetition}",
                        "persona": "computational-chemist", "model_id": "genmol", "tool": "genmol_generate_native", "mode": "native",
                        "arguments": {"smiles": f"[*{{{lower}-{upper}}}]", "num_molecules": count, "scoring": scoring,
                            "temperature": 1, "noise": 1, "unique": False},
                        "expected": {"evaluator": "molecule_generation", "scoring": scoring, "num_molecules": count},
                        "provenance": {"dataset_id": "genmol-denovo-size-property-grid", "source_url": "https://github.com/NVIDIA-Digital-Bio/genmol",
                            "protocol_deviation": "De novo size/property study; tests molecular validity, requested yield and independent property calculation. No molecule-specific experimental reference or paper benchmark reproduction."},
                        "workload": {"unique_input_id": f"genmol-{lower}-{upper}-{scoring.lower()}", "repetition": repetition, "seed": None, "priority": "batch"}})
    return cases


def prepare_aging(output: Path) -> list[dict]:
    import io
    import numpy as np
    import pandas as pd
    from evaluators import altumage_reference, phenoage_reference
    cases, sources = [], []
    columns = {"age_years": "RIDAGEYR", "albumin_g_l": "LBDSALSI", "creatinine_umol_l": "LBDSCRSI",
        "glucose_mmol_l": "LBDSGLSI", "c_reactive_protein_mg_dl": "LBXCRP", "lymphocyte_percent": "LBXLYPCT",
        "mean_cell_volume_fl": "LBXMCVSI", "red_cell_distribution_width_percent": "LBXRDW",
        "alkaline_phosphatase_u_l": "LBXSAPSI", "white_blood_cell_count_10e3_per_ul": "LBXWBCSI"}
    joined = None
    for name in ("BIOPRO_F", "CBC_F", "CRP_F", "DEMO_F"):
        url = f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2009/DataFiles/{name}.xpt"
        content, receipt = fetch(url, output / "references/nhanes-2009" / f"{name}.xpt")
        receipt["path"] = str(Path(receipt["path"]).relative_to(output))
        sources.append(receipt)
        table = pd.read_sas(io.BytesIO(content), format="xport")
        table = table[["SEQN"] + [field for field in columns.values() if field in table.columns]]
        joined = table if joined is None else joined.merge(table, on="SEQN", how="inner", validate="one_to_one")
    joined = joined.dropna(subset=list(columns.values()))
    joined = joined[(joined.RIDAGEYR >= 20) & (joined.LBXCRP > 0)].sort_values(["RIDAGEYR", "SEQN"])
    sampled = joined.iloc[np.linspace(0, len(joined) - 1, 512, dtype=int)]
    samples = [{"sample_id": f"NHANES2009-{int(row.SEQN)}", **{field: float(row[column]) for field, column in columns.items()}}
               for _, row in sampled.iterrows()]
    for start, count in [(index * 32, 1) for index in range(16)] + [(0, 32), (128, 128), (0, 512)]:
        batch = samples[start:start + count]
        cases.append({"case_id": f"phenoage-nhanes-{start}-n{count}", "persona": "aging-researcher", "model_id": "phenoage",
            "tool": "infer_phenoage_native", "mode": "native", "arguments": {"samples": batch},
            "expected": {"evaluator": "scalar_predictions", "prediction_field": "phenotypic_age_years", "absolute_tolerance": 1e-7,
                "reference_predictions": {sample["sample_id"]: phenoage_reference(sample) for sample in batch}},
            "provenance": {"dataset_id": "nhanes-2009-2010-complete-case-adults", "sources": sources,
                "source_url": "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/overview.aspx?BeginYear=2009",
                "unit_mapping": columns, "eligible_complete_cases": len(joined),
                "selection": "512 deterministic evenly-spaced rows after sorting adult complete cases by age/SEQN",
                "protocol_deviation": "Formula/numerical/unit/batching qualification. Not survey-weighted mortality or population inference. Age80 is NHANES top-coded. CRP native mg/dL; SI albumin/creatinine/glucose used directly."},
            "workload": {"unique_input_id": f"nhanes2009-{start}-{count}", "unique_sample_ids": [sample["sample_id"] for sample in batch],
                "samples": len(batch), "repetition": 1, "seed": None, "priority": "interactive" if count == 1 else "batch"}})
    revision = "696c477dac9b7641bf283c48af1cc9bb0a0803a3"
    base_url = f"https://raw.githubusercontent.com/rsinghlab/AltumAge/{revision}/example_dependencies/"
    folder = output / "references/altumage-published-example"
    known_hashes = {"multi_platform_cpgs.pkl": "068ed91ba02ec575262c7e9d0857eb9589224e478b8f2a9181c0fbcb0e26359d",
        "scaler.pkl": "68331c0b8974c192460e2ebf31e4a974da3292775f82c52d54a11dea629ff53d",
        "AltumAge.h5": "2db4011115c3f877746d6dd722045da74055d25e8803368a1679d0dbaafe1846"}
    sources, downloaded = [], {}
    for filename in ("example_data.pkl", "multi_platform_cpgs.pkl", "scaler.pkl", "AltumAge.h5"):
        content, receipt = fetch(base_url + filename, folder / filename)
        if filename in known_hashes and digest(content) != known_hashes[filename]:
            raise ValueError(f"Original AltumAge artifact hash mismatch: {filename}")
        downloaded[filename] = content
        receipt["path"] = str(Path(receipt["path"]).relative_to(output))
        sources.append(receipt)
    # These are revision-pinned original publication data/preprocessing objects;
    # only the prepared JSON and independently computed reference leave this step.
    data = pd.read_pickle(io.BytesIO(downloaded["example_data.pkl"]))
    cpgs = [str(value) for value in pd.read_pickle(io.BytesIO(downloaded["multi_platform_cpgs.pkl"]))]
    scaler = pd.read_pickle(io.BytesIO(downloaded["scaler.pkl"]))
    values = data[cpgs].to_numpy(dtype=float)
    if len(cpgs) != 20318 or not np.isfinite(values).all() or values.min() < 0 or values.max() > 1:
        raise ValueError("Original AltumAge example does not satisfy the declared complete beta-value contract.")
    normal_predictions = altumage_reference(folder / "AltumAge.h5", (values - scaler.center_) / scaler.scale_)
    indexes = [[index] for index in range(len(data))] + [list(range(len(data)))] * 4
    for number, selected in enumerate(indexes):
        variant = "complete" if number <= len(data) else ("reversed-columns", "missing-1pct", "missing-5pct")[number - len(data) - 1]
        selected_values = values[selected].copy()
        ordered_cpgs = cpgs
        missing_counts = np.zeros(len(selected), dtype=int)
        predictions = normal_predictions[selected]
        missing_policy = "error"
        if variant == "reversed-columns":
            ordered_cpgs = list(reversed(cpgs))
            selected_values = selected_values[:, ::-1]
        elif variant.startswith("missing"):
            step = 100 if variant == "missing-1pct" else 20
            selected_values[:, ::step] = np.nan
            missing_counts = np.isnan(selected_values).sum(axis=1)
            filled = np.where(np.isnan(selected_values), scaler.center_, selected_values)
            predictions = altumage_reference(folder / "AltumAge.h5", (filled - scaler.center_) / scaler.scale_)
            missing_policy = "reference_median"
        samples = [{"sample_id": str(data.index[index]), "beta_values": [float(value) if np.isfinite(value) else None for value in selected_values[position]]}
                   for position, index in enumerate(selected)]
        case_id = f"altumage-published-{number}-{variant}"
        cases.append({"case_id": case_id, "persona": "aging-researcher", "model_id": "altumage", "tool": "infer_altumage_native", "mode": "native",
            "arguments": {"cpg_sites": ordered_cpgs, "samples": samples, "missing_values": missing_policy},
            "expected": {"evaluator": "scalar_predictions", "prediction_field": "predicted_chronological_age_years",
                "absolute_tolerance": 0.002, "reference_predictions": {sample["sample_id"]: float(predictions[position]) for position, sample in enumerate(samples)},
                "true_ages": {str(data.index[index]): float(data.iloc[index]["age"]) for index in selected},
                "imputed_counts": {sample["sample_id"]: int(missing_counts[position]) for position, sample in enumerate(samples)}},
            "provenance": {"dataset_id": "altumage-original-example-16", "source_url": f"https://github.com/rsinghlab/AltumAge/tree/{revision}",
                "source_revision": revision, "sources": sources, "reference_method": "independent float64 NumPy inference from original Keras H5 (hosted implementation uses converted PyTorch)",
                "protocol_deviation": "Published 16-sample usage example, known age labels. Training/test membership of this example is not established. Missingness is a declared controlled perturbation; no pan-tissue generalization claim."},
            "workload": {"unique_input_id": "altumage-original-example-16", "unique_sample_ids": [sample["sample_id"] for sample in samples],
                "samples": len(samples), "repetition": 1, "seed": None, "priority": "batch"}})
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seeds", default="1,7,42")
    parser.add_argument("--protein-limit", type=int, default=len(PROTEINS))
    parser.add_argument("--skip-docking", action="store_true")
    parser.add_argument("--include-batch", action="store_true", help="Add native OpenFold3 and five matched scientific-batch folding Apps.")
    parser.add_argument("--design-backend", type=Path, help="Solution k8s-inference root supplying exact public design artifact encoders.")
    parser.add_argument("--include-auxiliary", action="store_true", help="Add MSA, inverse folding and molecular property studies.")
    parser.add_argument("--include-aging", action="store_true", help="Add public NHANES and original AltumAge example studies.")
    args = parser.parse_args()
    if not 1 <= args.repetitions <= 10:
        parser.error("repetitions must be between 1 and 10")
    args.output.mkdir(parents=True, exist_ok=True)
    cases, preparations = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(prepare_protein, spec, args.output, args.repetitions, args.include_batch): spec[0] for spec in PROTEINS[:args.protein_limit]}
        if not args.skip_docking:
            futures.update({pool.submit(prepare_docking, spec, args.output, [int(s) for s in args.seeds.split(",")]): spec[0] for spec in DOCKING})
        for future in as_completed(futures):
            try:
                prepared, receipt = future.result()
                cases.extend(prepared)
                preparations.append(receipt)
            except Exception as error:
                preparations.append({"pdb_id": futures[future], "status": "blocked_preparation", "error": str(error)})
    cases.sort(key=lambda case: case["case_id"])
    if args.design_backend:
        try:
            cases.extend(prepare_designs(args.design_backend, args.output, [int(s) for s in args.seeds.split(",")]))
        except Exception as error:
            preparations.append({"pdb_id": "design-apps", "status": "blocked_preparation", "error": str(error)})
    if args.include_auxiliary:
        cases.extend(prepare_auxiliary_cases(cases, args.output))
    if args.include_aging:
        try:
            cases.extend(prepare_aging(args.output))
        except Exception as error:
            preparations.append({"pdb_id": "aging-studies", "status": "blocked_preparation", "error": str(error)})
    manifest = {"schema_version": 1, "study_id": "experimental-structure-docking-v1",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sources": [{"url": "https://www.rcsb.org/pages/policies", "license": "CC0"},
                            {"url": "https://github.com/gcorso/DiffDock", "purpose": "metric/protocol source"},
                            {"url": "https://github.com/aqlaboratory/openfold", "purpose": "model/protocol source"}],
                "preparations": sorted(preparations, key=lambda receipt: receipt["pdb_id"]), "cases": cases}
    write_json(args.output / "cases.json", manifest)
    print(json.dumps({"manifest": str(args.output / "cases.json"), "cases": len(cases),
                      "prepared_datasets": sum(p["status"] == "prepared" for p in preparations),
                      "blocked_preparations": [p for p in preparations if p["status"] != "prepared"]}, indent=2))


if __name__ == "__main__":
    main()
