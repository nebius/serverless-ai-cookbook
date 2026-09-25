#!/usr/bin/env python3
"""Freeze general-English replay and independent regression sets from LibriSpeech."""
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import tarfile
from collections import Counter
from pathlib import Path

from prepare_corpus import digest, json_write, jsonl_write, write_frozen

EXPECTED_MD5 = {"train-clean-100": "2a93770f6d5c6c964bc36631d331a522", "test-clean": "32fa31d27d2e1cad72775fee3f4849a9"}
SEED = "clinical-asr-replay-v1"
EXPECTED_SHA256 = {"train-clean-100": "d4ddd1d5a6ab303066f14971d768ee43278a5f2a0aa43dc716b0e64ecbbbf6e2",
                   "test-clean": "39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23"}


def flac_info(path: Path) -> dict:
    with path.open("rb") as stream:
        header = stream.read(42)
    if header[:4] != b"fLaC" or header[4] & 0x7f != 0 or int.from_bytes(header[5:8], "big") != 34:
        raise ValueError(f"Expected first STREAMINFO block: {path}")
    packed = int.from_bytes(header[18:26], "big")
    sample_rate = packed >> 44
    samples = packed & ((1<<36)-1)
    channels = ((packed >> 41) & 7)+1
    if sample_rate <= 0 or samples <= 0 or channels != 1:
        raise ValueError(f"Unexpected FLAC stream: {path}")
    return {"duration": samples/sample_rate, "sample_rate": sample_rate, "channels": channels}


def choose_hours(rows: list[dict], target: float, seed: str = SEED):
    if target <= 0:
        raise ValueError("Target hours must be positive")
    selected, total = [], 0
    ordered = sorted(rows, key=lambda row: hashlib.sha256(f"{seed}:{row['id']}".encode()).hexdigest())
    for row in ordered:
        selected.append(row)
        total += row["duration"]
        if total >= target*3600:
            break
    if total < target*3600:
        raise ValueError("Insufficient eligible audio for requested duration")
    return selected


def extract_and_inventory(root: Path, source_split: str):
    archive = root/"raw"/f"{source_split}.tar.gz"
    md5 = hashlib.md5()
    with archive.open("rb") as stream:
        while data := stream.read(1024*1024):
            md5.update(data)
    if md5.hexdigest() != EXPECTED_MD5[source_split] or digest(archive) != EXPECTED_SHA256[source_split]:
        raise ValueError(f"Publisher archive MD5 mismatch: {source_split}")
    extracted = root/"raw/extracted"
    done = root/"raw"/f"{source_split}.extracted.json"
    if not done.exists():
        extracted.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive, "r:gz") as tf:
            for item in tf:
                destination = (extracted/item.name).resolve()
                if not destination.is_relative_to(extracted.resolve()) or item.issym() or item.islnk():
                    raise ValueError(f"Unsafe archive member: {item.name}")
                if item.isfile() and (not destination.exists() or destination.stat().st_size != item.size):
                    tf.extract(item, extracted, filter="data")
        json_write(done, {"archive_md5": md5.hexdigest(), "archive_sha256": digest(archive)})
    base = extracted/"LibriSpeech"/source_split
    texts = {}
    for path in base.rglob("*.trans.txt"):
        for line in path.read_text().splitlines():
            identity, text = line.split(" ", 1)
            if identity in texts:
                raise ValueError(f"Duplicate transcript id: {identity}")
            texts[identity] = text
    paths = {path.stem: path for path in base.rglob("*.flac")}
    if set(paths) != set(texts):
        raise ValueError("Unpaired FLAC/transcript files")
    rows = []
    train = source_split == "train-clean-100"
    for identity in sorted(paths):
        source = paths[identity]
        info = flac_info(source)
        if not 0.5 <= info["duration"] <= 30:
            continue
        speaker, chapter, _ = identity.split("-")
        label = "train_clean100" if train else "test_clean"
        rows.append({"id": f"librispeech_{label}_{identity}", "source_utterance_id": identity,
                     "conversation_id": f"librispeech-{'train-clean100' if train else 'test-clean'}:{speaker}:{chapter}",
                     "speaker_id": speaker, "chapter_id": chapter, "source_split": source_split,
                     "source_local_path": str(source), "duration": info["duration"], "source_text": texts[identity],
                     "text": texts[identity].lower(), "target_transform": "lowercase_source_no_punctuation",
                     "source_sample_rate": info["sample_rate"], "lang": "en-US", "target_lang": "en-US",
                     "split": "train" if train else "general_test", "example_exposure": "general_replay_train" if train else "general_regression_test",
                     "license": "CC-BY-4.0", "alignment_source": "original_LibriSpeech_segment", "training_allowed": train})
    return rows, {"archive_md5": md5.hexdigest(), "archive_sha256": digest(archive), "paired_utterances": len(paths),
                  "eligible_utterances": len(rows), "eligible_hours": sum(r["duration"] for r in rows)/3600}


def convert(row, root, container_root):
    target_split = "train" if row["split"] == "train" else "test"
    path = root/"audio"/target_split/(row["source_utterance_id"]+".wav")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temp = path.with_suffix(".partial.wav")
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", row["source_local_path"], "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(temp)], check=True)
        temp.replace(path)
    return {**row, "audio_filepath": f"{container_root}/replay/audio/{target_split}/{path.name}",
            "source_audio_sha256": digest(Path(row["source_local_path"])), "audio_sha256": digest(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--container-root", default="/data/clinical-speech")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--train-hours", type=float, default=10)
    parser.add_argument("--pilot-train-hours", type=float, default=2)
    parser.add_argument("--regression-minutes", type=float, default=30)
    parser.add_argument("--seed", default=SEED)
    args = parser.parse_args()
    if not 0 < args.pilot_train_hours <= args.train_hours or args.workers < 1 or args.regression_minutes <= 0:
        raise ValueError("Invalid durations or worker count")
    root = args.data_root/"replay"
    train, train_source = extract_and_inventory(root, "train-clean-100")
    test, test_source = extract_and_inventory(root, "test-clean")
    train = choose_hours(train, args.train_hours, args.seed)
    if {r["speaker_id"] for r in train} & {r["speaker_id"] for r in test}:
        raise ValueError("Training and test speaker overlap")
    split_path = root/"frozen-selection.json"
    selection = {"seed": args.seed, "selection": "sha256(seed:id) order until target hours, whole native utterances",
                 "target_train_hours": args.train_hours, "train_ids": [r["id"] for r in train], "test_ids": [r["id"] for r in test]}
    if split_path.exists() and json.loads(split_path.read_text()) != selection:
        raise ValueError("Refusing to change frozen replay selection")
    json_write(split_path, selection)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(lambda row: convert(row, root, args.container_root), train+test))
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "general_test"]
    pilot_train = choose_hours(train, args.pilot_train_hours, args.seed)
    pilot_test = choose_hours(test, args.regression_minutes / 60, args.seed)
    outputs = {"replay-train": train, "replay-train-pilot": pilot_train,
               "general-test-clean": test, "general-test-clean-pilot": pilot_test}
    for name, selected in outputs.items():
        jsonl_write(args.data_root/"manifests"/f"{name}.jsonl", selected)
    report = {"source": "https://www.openslr.org/12/", "license": "CC-BY-4.0",
              "attribution": "LibriSpeech: Vassil Panayotov, Guoguo Chen, Daniel Povey and Sanjeev Khudanpur; read LibriVox audiobooks.",
              "sources": {"train-clean-100": train_source, "test-clean": test_source},
              "outputs": {name: {"utterances": len(value), "hours": sum(r["duration"] for r in value)/3600,
                                  "speakers": len({r["speaker_id"] for r in value})} for name, value in outputs.items()},
              "train_test_speakers_disjoint": True, "target_transform": "lowercase_source_no_punctuation",
              "limitations": ["Read English audiobooks, not clinical conversational speech.",
                              "May have appeared in original base-model pretraining; independent of this fine-tuning only.",
                              "No fabricated punctuation or title casing; style retention requires separate evaluation.",
                              "No effect on fixed clinical train/dev/test membership."]}
    json_write(root/"provenance.json", report)
    license_path = root/"raw/extracted/LibriSpeech/LICENSE.TXT"
    if license_path.exists():
        write_frozen(root / "LICENSE.TXT", license_path.read_text())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
