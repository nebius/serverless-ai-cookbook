#!/usr/bin/env python3
"""Prepare the pinned two-consultation PriMock sample as evaluation-only WAVs."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import wave

from download_public import PRIMOCK_AUDIO, PRIMOCK_BLOBS, PRIMOCK_REVISION, file_hash
from prepare_corpus import digest, json_write, jsonl_write, write_frozen


def textgrid_intervals(text):
    pattern = r'intervals \[\d+\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "((?:""|[^"])*)"'
    return [(float(a), float(b), value.replace('""', '"').strip()) for a, b, value in re.findall(pattern, text)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, help="Default: DATA_ROOT/external/primock57/source")
    parser.add_argument("--container-root", default="/data/clinical-speech")
    args = parser.parse_args()
    dest = args.data_root.resolve() / "external/primock57"
    source = args.source_root or dest / "source"
    for relative, expected in PRIMOCK_BLOBS.items():
        if file_hash(source / relative, "sha1", True) != expected:
            raise ValueError("Pinned PriMock text/license mismatch:" + relative)
    dest.mkdir(parents=True, exist_ok=True)
    write_frozen(dest / "LICENSE.md", (source / "LICENSE.md").read_text())
    (dest / "audio").mkdir(exist_ok=True)
    rows, excluded = [], Counter()
    for identity, expected in PRIMOCK_AUDIO.items():
        audio = source / "audio" / (identity + ".wav")
        if digest(audio) != expected:
            raise ValueError("Pinned PriMock audio mismatch:" + identity)
        grid = source / "transcripts" / (identity + ".TextGrid")
        conversation, speaker = identity.rsplit("_", 1)
        with wave.open(str(audio), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                raise ValueError("Expected original mono16k PCM16 audio")
            frames = wav.getnframes()
            pcm = wav.readframes(frames)
        for index, (start, end, text) in enumerate(textgrid_intervals(grid.read_text())):
            if not text:
                excluded["empty_interval"] += 1
                continue
            if "<" in text or ">" in text:
                excluded["annotation_markup"] += 1
                continue
            if not .5 <= end - start <= 30:
                excluded["duration_outside_0.5_to_30_seconds"] += 1
                continue
            begin, finish = round(start * 16000), round(end * 16000)
            if begin < 0 or finish > frames or finish <= begin:
                raise ValueError("TextGrid outside original audio")
            segment_id = f"primock57_{identity}_{index:03}"
            target = dest / "audio" / (segment_id + ".wav")
            expected_pcm = pcm[begin * 2:finish * 2]
            if target.exists():
                with wave.open(str(target), "rb") as wav:
                    if wav.readframes(wav.getnframes()) != expected_pcm:
                        raise ValueError("Existing prepared external audio changed")
            else:
                with target.open("xb") as stream, wave.open(stream, "wb") as wav:
                    wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                    wav.writeframes(expected_pcm)
            rows.append({"id": segment_id, "conversation_id": conversation, "split": "external_test",
                         "example_exposure": "external_heldout", "audio_filepath": f"{args.container_root.rstrip('/')}/external/primock57/audio/{target.name}",
                         "duration": (finish - begin) / 16000, "text": text, "speaker": speaker,
                         "source_start_seconds": begin / 16000, "source_end_seconds": finish / 16000,
                         "source_audio_sha256": expected, "source_textgrid_sha256": digest(grid), "audio_sha256": digest(target),
                         "lang": "en-US", "target_lang": "en-US", "license": "CC-BY-4.0", "alignment_source": "original_human_TextGrid",
                         "training_allowed": False, "clinical_review": "PENDING"})
    jsonl_write(args.data_root / "manifests/external-test-utterances.jsonl", rows)
    report = {"source": "https://github.com/babylonhealth/primock57", "revision": PRIMOCK_REVISION,
              "license": "CC-BY-4.0", "attribution": "Babylon Health; Papadopoulos Korfiatis, Moramarco, Sarac and Savkov (2022)",
              "changes": "Two consultations; source TextGrid clean intervals only; exact rounded source PCM slices; no mixed-channel diarization claim",
              "conversations": sorted({r["conversation_id"] for r in rows}), "utterances": len(rows),
              "seconds": sum(r["duration"] for r in rows), "excluded_intervals": dict(excluded),
              "human_listening_review": "PENDING", "training_allowed": False}
    json_write(dest / "provenance.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
