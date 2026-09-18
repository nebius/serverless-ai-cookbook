#!/usr/bin/env python3
"""Genomics, image interpretation and scientific-assistant qualification cases."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from datasets import digest, fetch, write_json


def evo_cases(output: Path) -> list[dict]:
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id=NC_000932.1&rettype=fasta&retmode=text"
    raw, source = fetch(url, output / "references/arabidopsis-chloroplast-NC_000932.1.fasta")
    sequence = "".join(line.strip() for line in raw.decode().splitlines() if not line.startswith(">"))
    if len(sequence) != 154478 or set(sequence) - set("ACGT"):
        raise ValueError("Version-pinned Arabidopsis reference differs from the published genome.")
    source["path"] = str(Path(source["path"]).relative_to(output))
    cases = []
    for start in (1000, 35000, 70000, 110000):
        for prompt_length, output_length in ((256, 64), (1024, 128), (4096, 256), (8192, 512)):
            for seed in (1, 7):
                case_id = f"evo2-chloroplast-pos{start}-p{prompt_length}-n{output_length}-s{seed}"
                cases.append({"case_id": case_id, "persona": "plant-genomics-researcher", "model_id": "evo2-40b",
                    "tool": "generate_dna_native", "mode": "native", "arguments": {
                        "sequence": sequence[start:start + prompt_length], "num_tokens": output_length,
                        "temperature": 0.7, "top_k": 4, "top_p": 0.95, "random_seed": seed,
                        "enable_logits": False, "enable_sampled_probs": False, "enable_elapsed_ms_per_token": True},
                    "expected": {"evaluator": "dna_continuation", "num_tokens": output_length,
                        "reference_continuation": sequence[start + prompt_length:start + prompt_length + output_length]},
                    "provenance": {"dataset_id": "arabidopsis-chloroplast-NC_000932.1", "source_url": url,
                        "paper_url": "https://pubmed.ncbi.nlm.nih.gov/10574454/", "sources": [source],
                        "position_zero_based": start, "prompt_bases": prompt_length,
                        "protocol_deviation": "Public benign plant genome continuation. Training overlap unknown; stochastic generation need not equal the reference. No gene-function, variant-effect or experimental-fitness claim."},
                    "workload": {"unique_input_id": f"arabidopsis-{start}-{prompt_length}", "repetition": 1,
                        "seed": seed, "priority": "batch"}})
    return cases


def qwen_cases(source_manifest: Path) -> list[dict]:
    source_cases = [case for case in json.loads(source_manifest.read_text())["cases"]
                    if case["model_id"] == "openfold2" and case["workload"]["repetition"] == 1]
    cases = []
    for source in source_cases:
        pdb_id = source["provenance"]["pdb_id"]
        name = source["provenance"]["label"]
        length = len(source["arguments"]["sequence"])
        chain = source["expected"]["reference_chain"]
        answer = {"pdb_id": pdb_id, "name": name, "chain": chain, "residue_count": length,
                  "experimental_reference_available": True, "validated_binding": False}
        facts = {"source": source["provenance"]["source_url"], "PDB accession": pdb_id, "protein": name,
                 "chain identifier": chain, "canonical amino-acid count": length,
                 "reference": "Experimental structure", "binding experiment": "Not performed in this study"}
        for mode in ("chat", "json-object", "tool-call"):
            case_id = f"qwen3-8b-study-extraction-{pdb_id.lower()}-{mode}"
            fields = "pdb_id, name, chain, residue_count (integer), experimental_reference_available (boolean), validated_binding (boolean)"
            arguments = {"messages": [{"role": "system", "content": "You are a scientific data curator. Use only supplied facts; never turn missing experimental evidence into a claim. /no_think"},
                {"role": "user", "content": f"Extract these study facts into a JSON object with fields {fields}. Return only the JSON object. Facts: {json.dumps(facts)}"}],
                "temperature": 0, "max_completion_tokens": 2048, "stream": False}
            expected = {"evaluator": "chat_json", "reference_answer": answer}
            if mode == "json-object":
                arguments["response_format"] = {"type": "json_object"}
            elif mode == "tool-call":
                function = {"name": "save_study_record", "description": "Save the exact supplied study record; no invented binding evidence.",
                    "parameters": {"type": "object", "properties": {
                        key: {"type": "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "string"}
                        for key, value in answer.items()}, "required": list(answer), "additionalProperties": False}}
                arguments.update(tools=[{"type": "function", "function": function}], tool_choice={"type": "function", "function": {"name": function["name"]}})
                expected.update(evaluator="chat_tool_call", tool_name=function["name"])
            cases.append({"case_id": case_id, "persona": "scientific-data-curator", "model_id": "qwen3-8b",
                "tool": "qwen3_8b_chat_openai_chat", "mode": "native", "arguments": arguments, "expected": expected,
                "provenance": {"dataset_id": f"rcsb-{pdb_id.lower()}-curation", "source_url": source["provenance"]["source_url"],
                    "protocol_deviation": "Controlled extraction of supplied published metadata, not literature discovery or full research replication. Three output modes have the same target fields."},
                "workload": {"unique_input_id": f"rcsb-{pdb_id.lower()}-curation", "repetition": 1, "seed": None, "priority": "interactive"}})
    return cases


def illustration_cases() -> list[dict]:
    prompts = [
        ("plant-cell", "A clean scientific communication illustration of a plant cell with a cell wall, green chloroplasts and a large central vacuole, no text labels, white background"),
        ("protein-fold", "A conceptual folded protein ribbon with alpha helices and beta sheets, blue and orange ribbons, white background, scientific magazine illustration, no text"),
        ("cryo-grid", "A conceptual illustration of a cryo electron microscopy sample grid on a dark blue laboratory background, no text"),
        ("dna-helix", "An artistic double helix of DNA with paired ladder rungs, green and teal, clean white background, no text"),
        ("microscope", "A microscope and labelled sample tubes on a tidy modern research laboratory bench, editorial scientific illustration, no people"),
        ("study-workflow", "Three connected panels showing a protein ribbon, a computing server and a plotted chart, scientific research workflow illustration, no words")]
    return [{"case_id": f"sdxl-{name}-s{seed}-steps{steps}", "persona": "scientific-communication-researcher",
        "model_id": "sdxl", "tool": "generate_image_native", "mode": "native",
        "arguments": {"prompt": prompt, "negative_prompt": "watermark, blurry, unreadable text", "seed": seed,
            "steps": steps, "guidance": 5, "width": 512, "height": 512, "response_format": "b64_json"},
        "expected": {"evaluator": "generated_image", "size": [512, 512], "visual_review_prompt": prompt},
        "provenance": {"dataset_id": "scientific-communication-controlled-prompts", "source_url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0",
            "protocol_deviation": "Original illustration prompts, not observed biological data. Automated checks cover PNG integrity and nonblank content; prompt adherence needs visual review and diagrams are not anatomical ground truth."},
        "workload": {"unique_input_id": name, "repetition": 1, "seed": seed, "priority": "batch"}}
        for name, prompt in prompts for seed in (1, 7, 42) for steps in (20, 40)]


def cxr_cases(output: Path, count: int = 20) -> list[dict]:
    dataset = "BahaaEldin0/NIH-Chest-Xray-14"
    revision = "932bcdba9d7d9590704d4f20bc70fc2c3a1bbad7"
    url = "https://datasets-server.huggingface.co/rows?dataset=BahaaEldin0%2FNIH-Chest-Xray-14&config=default&split=test&offset=0&length=100"
    folder = output / "references/nih-cxr-mirror"
    data, receipt = fetch(url, folder / "public-rows.json")
    rows = json.loads(data)["rows"]
    allowed = ["Atelectasis", "Cardiomegaly", "Effusion", "Infiltration", "Mass", "Nodule", "Pneumonia",
               "Pneumothorax", "Consolidation", "Edema", "Emphysema", "Fibrosis", "Pleural_Thickening", "Hernia", "No Finding"]
    # Pick first-occurring examples of distinct labels, then fill in source order.
    selected, seen_labels, seen_patients = [], set(), set()
    for row in rows:
        labels = set(row["row"]["label"])
        if labels - seen_labels and row["row"]["Patient ID"] not in seen_patients:
            selected.append(row)
            seen_labels.update(labels)
            seen_patients.add(row["row"]["Patient ID"])
    for row in rows:
        if len(selected) >= count:
            break
        if row["row"]["Patient ID"] not in seen_patients:
            selected.append(row)
            seen_patients.add(row["row"]["Patient ID"])
    cases = []
    for row in selected[:count]:
        index, values = row["row_idx"], row["row"]
        image_url = values["image"]["src"]
        if f"/--/{revision}/--/" not in image_url:
            raise ValueError("Public NIH mirror revision changed; choose a new explicitly versioned study.")
        image_path = folder / f"row-{index}.jpg"
        image_bytes, image_receipt = fetch(image_url, image_path)
        if set(values["label"]) - set(allowed):
            raise ValueError("Unrecognized NIH source label.")
        # The upload holds a frozen image: the model never depends on the expiring
        # public image URL, and reference finding labels are never in its prompt.
        prompt = ("This is a deidentified public research chest X-ray, not a clinical encounter. "
                  "Assess the visible image. Return only a JSON object with 'findings': a list containing only visible findings from "
                  + json.dumps(allowed) + ". Use 'No Finding' only when none of the listed findings are visible. "
                  "Include a short 'limitations' string describing uncertainty; do not infer unseen clinical history.")
        cases.append({"case_id": f"nv-reason-cxr-nih-test-row{index}", "persona": "medical-imaging-researcher",
            "model_id": "nv-reason-cxr-3b", "tool": "analyze_image_openai_chat", "mode": "native",
            "arguments": {"messages": [{"role": "user", "content": [{"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"detail": "high"}}]}],
                "temperature": 0, "max_completion_tokens": 4096, "response_format": {"type": "json_object"}, "stream": False},
            "preparation": {"artifact_fields": [{"field": ["messages", 0, "content", 1, "image_url", "url"],
                "transport": "artifact", "local_path": str(image_path.relative_to(output)), "media_type": "image/jpeg",
                "compression": "none", "sha256": digest(image_bytes), "size_bytes": len(image_bytes)}]},
            "expected": {"evaluator": "cxr_findings", "reference_findings": values["label"], "allowed_findings": allowed},
            "provenance": {"dataset_id": f"nih-cxr-mirror-test-row{index}", "source_url": "https://nihcc.app.box.com/v/ChestXray-NIHCC",
                "paper_url": "https://openaccess.thecvf.com/content_cvpr_2017/html/Wang_ChestX-Ray8_Hospital-Scale_Chest_CVPR_2017_paper.html",
                "mirror": dataset, "mirror_revision": revision, "image_sha256": digest(image_bytes), "rows_sha256": digest(data),
                "license_attribution": "NIH Clinical Center; unrestricted image use with dataset link and Wang et al., CVPR2017 citation; see Google public-dataset documentation.",
                "protocol_deviation": "Frozen public mirror JPEG, not original diagnostic DICOM. Labels are report-mined weak labels, not adjudicated expert labels. Compare findings descriptively only; no clinical qualification or paper reproduction. Mirror split does not establish model-training independence."},
            "workload": {"unique_input_id": f"nih-cxr-mirror-patient{values['Patient ID']}-row{index}", "repetition": 1,
                         "seed": None, "priority": "batch"}})
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--structure-manifest", required=True, type=Path)
    args = parser.parse_args()
    cases, preparations = [], []
    for name, function in (("evo2", lambda: evo_cases(args.output)), ("qwen", lambda: qwen_cases(args.structure_manifest)),
                           ("sdxl", illustration_cases), ("cxr", lambda: cxr_cases(args.output))):
        try:
            prepared = function()
            cases.extend(prepared)
            preparations.append({"study": name, "status": "prepared", "cases": len(prepared)})
        except Exception as error:
            preparations.append({"study": name, "status": "blocked_preparation", "error": str(error)})
    write_json(args.output / "cases.json", {"schema_version": 1, "study_id": "general-science-apps-v1",
        "created_at": datetime.now(timezone.utc).isoformat(), "cases": cases, "preparations": preparations})
    print(json.dumps({"manifest": str(args.output / "cases.json"), "cases": len(cases), "preparations": preparations}, indent=2))


if __name__ == "__main__":
    main()
