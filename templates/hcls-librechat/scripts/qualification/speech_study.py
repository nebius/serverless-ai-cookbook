#!/usr/bin/env python3
"""Prepare public speech studies and reuse the platform's attributed WER scorer.

Quality metrics are research measurements, not clinical validation. Distinct
clips, repeated measurements and perturbations retain separate provenance.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import wave

from manage_campaign import save

MODELS = ("nemotron-speech-en-0-6b", "nemotron-speech-multilingual-0-6b", "parakeet-realtime-eou-120m-v1")
PARQUET_SHA = "494a635916ceaed914f6238fb7acf37e38a1e8432c30663a2f6f484dbdec58e0"


def scorer(path, expected_sha=None):
    if expected_sha and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        raise ValueError("Scientific speech scorer source changed")
    spec = importlib.util.spec_from_file_location("scientific_speech_scorer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audio_duration(path):
    if path.suffix == ".wav":
        with wave.open(str(path)) as stream:
            return stream.getnframes() / stream.getframerate()
    data = subprocess.check_output(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                                    "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"])
    return len(data) / 32000


def prepare(args):
    import pyarrow.parquet as pq
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    audio_dir = args.output / "audio"
    audio_dir.mkdir(exist_ok=True, mode=0o700)
    module = scorer(args.scorer)
    examples = []
    for number in ("01", "02"):
        source = args.assets / f"ready/en/day1_consultation{number}_conversation.wav"
        target = audio_dir / f"primock57-en-{number}.flac"
        if not target.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-c:a", "flac", str(target)], check=True)
        reference, provenance = module.reference(args.assets, "en-" + number)
        examples.append({"id": "primock57-en-" + number, "path": target, "language": "en",
                         "media_type": "audio/flac", "reference": reference,
                         "provenance": {"dataset": "PriMock57", "revision": "cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5",
                                        "source": "https://github.com/babylonhealth/primock57", "license": "CC-BY-4.0",
                                        "reference_alignment_limitation": "Overlapping speaker turns ordered by interval onset",
                                        **provenance}})
        # Exercise the same real consultation at reduced gain and with a
        # reproducible low-pass telephone-like signal, without changing labels.
        for variant, filters in (("quiet", "volume=0.15"), ("bandlimited", "highpass=f=300,lowpass=f=3400")):
            changed = audio_dir / f"primock57-en-{number}-{variant}.flac"
            if not changed.exists():
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(source), "-af", filters,
                                "-c:a", "flac", str(changed)], check=True)
            examples.append({**examples[-1 if variant == "quiet" else -2], "id": f"primock57-en-{number}-{variant}",
                             "path": changed, "perturbation": filters})
    parquet = args.assets / "references/de/multimed/test.parquet"
    if hashlib.sha256(parquet.read_bytes()).hexdigest() != PARQUET_SHA:
        raise ValueError("MultiMed test parquet changed")
    rows = pq.read_table(parquet).to_pylist()
    indices = sorted(set(round(index * (len(rows)-1) / (args.german_clips-1)) for index in range(args.german_clips)) | {193})
    for index in indices:
        row = rows[index]
        target = audio_dir / f"multimed-de-{index:04d}.ogg"
        if not target.exists():
            target.write_bytes(row["audio"]["bytes"])
            target.chmod(0o600)
        examples.append({"id": f"multimed-de-{index:04d}", "path": target, "language": "de",
                         "media_type": "audio/ogg", "reference": row["text"],
                         "provenance": {"dataset": "MultiMed", "revision": "459d0ab6db332904f9d7b76a8baabf3333958fa8",
                                        "source": "https://huggingface.co/datasets/leduckhai/MultiMed",
                                        "license": "MIT (publisher label)", "row": index, "parquet_sha256": PARQUET_SHA}})
    cases = []
    for example in examples:
        data = example["path"].read_bytes()
        duration = audio_duration(example["path"])
        for model in MODELS:
            if example["language"] != "en" and model != MODELS[1]:
                continue
            arguments = {}
            if model != MODELS[2]:
                arguments["options"] = {"model": model.replace("0-6b", "0.6b"), "language": example["language"],
                                        "output_granularity": "word"}
            for repeat in range(1, args.repetitions + 1):
                case_id = f"{model}-{example['id']}-r{repeat}"
                cases.append({"case_id": case_id, "persona": "medical-nlp-researcher", "model_id": model,
                    "tool": "infer_" + model.replace("-", "_") + "_native", "mode": "native", "arguments": arguments,
                    "preparation": {"artifact_fields": [{"field": "audio", "transport": "artifact",
                        "local_path": str(example["path"].relative_to(args.output)), "media_type": example["media_type"],
                        "compression": "none", "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}]},
                    "expected": {"evaluator": "speech_transcription", "reference_text": example["reference"],
                                 "audio_seconds": duration, "language": example["language"], "scorer_path": str(args.scorer.resolve()),
                                 "scorer_sha256": hashlib.sha256(args.scorer.read_bytes()).hexdigest()},
                    "provenance": {**example["provenance"], "perturbation": example.get("perturbation"), "clinical_validation": False},
                    "workload": {"unique_input_id": example["id"], "repetition": repeat, "priority": "batch"}})
    save(args.output / "cases.json", {"schema_version": 1, "study_id": "speech-public-customer-mcp", "cases": cases})
    print(json.dumps({"cases": len(cases), "source_clips_and_variants": len(examples), "path": str(args.output / "cases.json")}), flush=True)


def evaluate(case, result):
    expected = case["expected"]
    module = scorer(Path(expected["scorer_path"]), expected["scorer_sha256"])
    value = result.get("result", result)
    text = value.get("text") if isinstance(value, dict) else None
    duration = value.get("audio_seconds") if isinstance(value, dict) else None
    duration_matches = isinstance(duration, (int, float)) and abs(duration - expected["audio_seconds"]) <= 0.01
    reference_words = module.words(expected["reference_text"])
    quality = module.alignment(expected["reference_text"], text or "") if reference_words else None
    return {"case_id": case["case_id"], "evaluator": expected["evaluator"],
            "service_semantic_pass": isinstance(text, str) and bool(text.strip()) and duration_matches,
            "full_duration": duration_matches, "expected_audio_seconds": expected["audio_seconds"],
            "returned_audio_seconds": duration, "processing_seconds": value.get("processing_seconds"),
            "quality": quality, "clinical_validation": False,
            "quality_limitation": "Not a medical safety/clinical suitability assessment; WER is lexical agreement"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--scorer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--german-clips", type=int, default=100)
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    if not 2 <= args.german_clips <= 1091 or not 1 <= args.repetitions <= 3:
        parser.error("Select 2..1091 German clips and 1..3 explicit repetitions")
    prepare(args)
