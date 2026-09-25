#!/usr/bin/env python3
"""Audit the original CC0 corpus and freeze conversation-level ASR splits.

This produces full-conversation inputs for forced alignment, not directly usable
short-utterance training data. No proportional/approximate audio segmentation.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import subprocess
import unicodedata
import zipfile
import zlib
from collections import Counter
from pathlib import Path

SOURCE_URL = "https://springernature.figshare.com/articles/dataset/Collection_of_simulated_medical_exams/16550013"
DOWNLOAD_URL = "https://ndownloader.figshare.com/files/30598530"
SEED = "clinical-asr-v1"
ARCHIVE_SHA256 = "20ef65540768d49ab6368672994aaef6acb21117d139e5d91e76a32432da951e"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_transcript(text: str) -> tuple[str, list[dict], list[str]]:
    """Remove speaker markers, preserve words/case/punctuation and uncertainty."""
    text = unicodedata.normalize("NFC", text).replace("\ufeff", "")
    turns, warnings = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(D|P|Doctor|Patient)\s*[:;]\s*(.*)$", line, re.I)
        if match:
            speaker = "doctor" if match[1].lower() in ("d", "doctor") else "patient"
            if match[2].strip():
                turns.append({"speaker": speaker, "text": match[2].strip()})
        elif turns:
            turns[-1]["text"] += " " + line
            warnings.append("unlabelled_continuation_line")
        else:
            turns.append({"speaker": "unknown", "text": line})
            warnings.append("unlabelled_initial_line")
    target = re.sub(r"\s+", " ", " ".join(turn["text"] for turn in turns)).strip()
    if re.search(r"\[(?:inaudible|unclear)|\binaudible\b", target, re.I):
        warnings.append("uncertainty_marker_present")
    return target, turns, sorted(set(warnings))


def decode_transcript(raw: bytes) -> tuple[str, str]:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16"), "utf-16"
    try:
        return raw.decode("utf-8-sig"), "utf-8-sig"
    except UnicodeDecodeError:
        decoded = raw.decode("cp1252")
        if "\x00" in decoded:
            raise ValueError("Undetected binary/UTF-16 transcript; refusing noisy training text")
        return decoded, "cp1252"


def json_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frozen(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def write_frozen(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text() != text:
            raise ValueError(f"Refusing to replace different prepared output: {path}")
        return
    with path.open("x") as stream:
        stream.write(text)


def jsonl_write(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_frozen(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))


def safe_extract(archive: Path, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            destination = (root / info.filename).resolve()
            if not destination.is_relative_to(root.resolve()):
                raise ValueError(f"Unsafe archive member: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive symlinks are not supported")
            if info.is_dir():
                continue
            if not destination.exists():
                zf.extract(info, root)
            else:
                checksum = 0
                with destination.open("rb") as stream:
                    for block in iter(lambda: stream.read(1024 * 1024), b""):
                        checksum = zlib.crc32(block, checksum)
                if destination.stat().st_size != info.file_size or checksum != info.CRC:
                    raise ValueError(f"Existing extracted file differs: {destination}")


def inspect_audio(path: Path) -> dict:
    output = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=sample_rate,channels,codec_name",
        "-of", "json", str(path)], text=True)
    probe = json.loads(output)
    return {"duration": float(probe["format"]["duration"]), "streams": probe["streams"]}


def freeze_splits(ids: list[str], path: Path, seed: str = SEED) -> dict:
    if len(ids) != len(set(ids)) or len(ids) < 20:
        raise ValueError("At least 20 unique conversation IDs required")
    ordered = sorted(ids, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest())
    n_test = round(len(ordered) * 0.10)
    n_dev = round(len(ordered) * 0.10)
    splits = {"test": sorted(ordered[:n_test]), "dev": sorted(ordered[n_test:n_test+n_dev]),
              "train": sorted(ordered[n_test+n_dev:])}
    payload = {"schema_version": 1, "seed": seed, "algorithm": "sha256(seed:conversation_id), first test then dev then train",
               "unit": "whole_conversation", "speaker_disjoint": False,
               "speaker_disjoint_note": "Original corpus supplies role labels, not stable actor identities. Do not claim actor-disjoint evaluation.",
               "splits": splits}
    if path.exists() and json.loads(path.read_text()) != payload:
        raise ValueError("Refusing to change an existing frozen split manifest")
    json_write(path, payload)
    return splits


def process_pair(item, root: Path, container_root: str, convert: bool) -> dict:
    identity, audio, transcript = item
    raw = transcript.read_bytes()
    decoded, encoding = decode_transcript(raw)
    target, turns, warnings = normalize_transcript(decoded)
    if not target:
        raise ValueError(f"Empty transcript: {identity}")
    info = inspect_audio(audio)
    converted = root / "prepared/audio" / f"{identity}.wav"
    if convert:
        converted.parent.mkdir(parents=True, exist_ok=True)
        if not converted.exists():
            temporary = converted.with_suffix(".partial.wav")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(audio), "-ac", "1", "-ar", "16000",
                            "-c:a", "pcm_s16le", str(temporary)], check=True)
            temporary.replace(converted)
    json_write(root / "prepared/turns" / f"{identity}.json", {
        "conversation_id": identity, "timestamp_status": "absent_in_original", "human_verbatim_audit": "PENDING", "turns": turns})
    return {"id": identity, "conversation_id": identity, "category": identity[:3],
            "audio_filepath": f"{container_root.rstrip('/')}/prepared/audio/{identity}.wav",
            "local_audio_filepath": str(converted), "duration": info["duration"], "text": target,
            "lang": "en-US", "target_lang": "en-US", "source_audio_sha256": digest(audio),
            "source_transcript_sha256": digest(transcript), "transcript_encoding": encoding,
            "audio_sha256": digest(converted) if converted.exists() else None,
            "source_audio_streams": info["streams"], "turn_count": len(turns), "word_count": len(target.split()),
            "warnings": warnings, "license": "CC0-1.0", "alignment_status": "PENDING_FORCED_ALIGNMENT",
            "human_verbatim_audit": "PENDING"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Dedicated writable prepared-data directory")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--container-root", default="/data/clinical-speech")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", default=SEED)
    parser.add_argument("--no-convert", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    archive = args.archive or root / "raw/simulated-medical-exams-16550013-v1.zip"
    if args.workers < 1 or digest(archive) != ARCHIVE_SHA256:
        raise ValueError("Invalid workers or pinned public archive SHA256 mismatch")
    extracted = root / "raw/extracted"
    safe_extract(archive, extracted)
    audio = {p.stem: p for p in extracted.rglob("*.mp3")}
    transcripts = {p.stem: p for p in extracted.rglob("*.txt")}
    if len(audio) != 272 or set(audio) != set(transcripts):
        raise ValueError(f"Unpaired sources: audio-only={set(audio)-set(transcripts)}, text-only={set(transcripts)-set(audio)}")
    splits = freeze_splits(sorted(audio), root / "manifests/conversation-splits.json", args.seed)
    split_for = {identity: split for split, ids in splits.items() for identity in ids}
    items = [(identity, audio[identity], transcripts[identity]) for identity in sorted(audio)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        rows = list(executor.map(lambda x: process_pair(x, root, args.container_root, not args.no_convert), items))
    for row in rows:
        row["split"] = split_for[row["id"]]
    jsonl_write(root / "manifests/conversation-inventory.jsonl", rows)
    for split in ("train", "dev", "test"):
        selected = [row for row in rows if row["split"] == split]
        jsonl_write(root / f"manifests/{split}-conversations.jsonl", selected)
        minimal = [{k: row[k] for k in ("audio_filepath", "duration", "text", "lang", "target_lang", "conversation_id", "split")} for row in selected]
        jsonl_write(root / f"manifests/{split}-nfa.jsonl", minimal)
    jsonl_write(root / "manifests/train-dev-alignment.jsonl", [
        {k: row[k] for k in ("audio_filepath", "duration", "text", "lang", "target_lang", "conversation_id", "split")}
        for row in rows if row["split"] in {"train", "dev"}])
    # Entire source conversation is retained for alignment; these are NOT short training examples.
    pilot = sorted((r for r in rows if r["split"] == "train"), key=lambda r: r["duration"])[:4]
    pilot += sorted((r for r in rows if r["split"] == "dev"), key=lambda r: r["duration"])[:2]
    jsonl_write(root / "manifests/pilot-alignment.jsonl", [
        {k: row[k] for k in ("audio_filepath", "duration", "text", "lang", "target_lang", "conversation_id", "split")} for row in pilot])
    report = {"schema_version": 1, "source": SOURCE_URL, "download_url": DOWNLOAD_URL, "license": "CC0-1.0",
              "license_source": "https://api.figshare.com/v2/articles/16550013", "archive_sha256": digest(archive), "archive_bytes": archive.stat().st_size,
              "preparation_seed": args.seed, "ffmpeg_version": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[0],
              "paired_conversations": len(rows), "duration_hours": sum(r["duration"] for r in rows)/3600,
              "source_categories": dict(Counter(r["category"] for r in rows)),
              "split_summary": {s: {"conversations": len(splits[s]), "hours": sum(r["duration"] for r in rows if r["split"] == s)/3600,
                                     "categories": dict(Counter(r["category"] for r in rows if r["split"] == s))} for s in splits},
              "pilot_alignment_ids": [r["id"] for r in pilot],
              "warnings": ["Source transcripts are cleaned, not certified verbatim. Human audit pending.",
                           "No timestamps supplied: forced alignment required before 0.5–30 second training segmentation.",
                           "Conversation-disjoint only; actor identities not available.",
                           "No model measurements have been performed by this preparation step."],
              "warning_counts": dict(Counter(w for r in rows for w in r["warnings"]))}
    json_write(root / "provenance.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
