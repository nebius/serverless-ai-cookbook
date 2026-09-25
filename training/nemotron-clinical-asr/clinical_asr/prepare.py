"""Force-align HUMAN references, then physically cut timestamp-aligned WAVs.

No ASR-generated pseudo-labels and no proportional text/audio splitting.
Original conversation membership is retained through alignment and segmentation.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from . import ALIGN_FILENAME, ALIGN_REPOSITORY, ALIGN_REVISION, NEMO_REVISION
from .common import read_jsonl, sha256_file, write_json


def align_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--viterbi-device", default="cuda", choices=["cpu", "cuda"])
    args = parser.parse_args()
    from huggingface_hub import hf_hub_download
    checkpoint = hf_hub_download(ALIGN_REPOSITORY, ALIGN_FILENAME, revision=ALIGN_REVISION)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "/opt/nemo/tools/nemo_forced_aligner/align.py",
               f"model_path={checkpoint}", f"manifest_filepath={Path(args.manifest).resolve()}",
               f"output_dir={output.resolve()}", "align_using_pred_text=false", "batch_size=1",
               "transcribe_device=cuda", f"viterbi_device={args.viterbi_device}",
               "use_local_attention=true", "use_buffered_chunked_streaming=true",
               "chunk_len_in_secs=1.6", "total_buffer_in_secs=4.0", "chunk_batch_size=8",
               "save_output_file_formats=[ctm]"]
    write_json(output / "alignment-provenance.json", {
        "aligner": ALIGN_REPOSITORY, "aligner_revision": ALIGN_REVISION,
        "aligner_license": "CC-BY-4.0", "nemo_revision": NEMO_REVISION,
        "source_manifest_sha256": sha256_file(args.manifest),
        "human_references": True, "pseudo_labels": False,
        "human_alignment_review": "PENDING", "command": command,
    })
    subprocess.run(command, check=True)


def normalized_word(text):
    return re.sub(r"[^\w]", "", text.casefold())


def grouped_words(words, maximum=30.0, gap=0.7):
    """Greedy word groups; boundaries only between aligned words."""
    group = []
    for word in words:
        start, end, token = word
        if start < 0 or end <= start or (group and start < group[-1][0]):
            raise ValueError("invalid_or_nonmonotonic_alignment")
        if end - start > maximum:
            raise ValueError("one_word_exceeds_duration_limit")
        if group and (end - group[0][0] > maximum - 0.2 or start - group[-1][1] > gap):
            yield group
            group = []
        group.append(word)
    if group:
        yield group


def segment_main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--alignment-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-duration", type=float, default=30.0)
    args = parser.parse_args()
    import soundfile as sf
    output = Path(args.output).resolve()
    (output / "audio").mkdir(parents=True, exist_ok=True)
    manifests = {split: [] for split in ("train", "dev", "test")}
    audit = []
    for item in read_jsonl(args.source_manifest):
        source = Path(item["audio_filepath"])
        conversation = item["conversation_id"]
        split = item["split"]
        if split not in manifests or not re.fullmatch(r"[A-Za-z0-9_-]+", conversation):
            raise ValueError("invalid_conversation_or_split")
        ctm = Path(args.alignment_dir) / "ctm" / "words" / (source.stem.replace(" ", "") + ".ctm")
        words = []
        for line in ctm.read_text().splitlines():
            fields = line.split()
            words.append((float(fields[2]), float(fields[2]) + float(fields[3]), fields[4]))
        if not words:
            raise ValueError(f"missing_words:{conversation}")
        source_tokens = item["text"].split()
        # Fail rather than silently remove original cased/punctuated target text.
        if [normalized_word(w[2]) for w in words] != [normalized_word(w) for w in source_tokens]:
            raise ValueError(f"source_ctm_token_mismatch_requires_review:{conversation}")
        words = [(w[0], w[1], token) for w, token in zip(words, source_tokens)]
        audio, rate = sf.read(source, dtype="int16", always_2d=False)
        if rate != 16000 or audio.ndim != 1:
            raise ValueError("requires_mono_16khz_wav")
        cursor = 0
        for index, group in enumerate(grouped_words(words, args.max_duration)):
            start = max(0.0, group[0][0] - 0.08)
            end = min(len(audio) / rate, group[-1][1] + 0.08)
            duration = end - start
            if duration < 0.5:
                audit.append({"conversation_id": conversation, "reason": "short_segment", "word_start": cursor})
                cursor += len(group)
                continue
            segment_id = f"{conversation}_{index:05d}"
            target = output / "audio" / (segment_id + ".wav")
            sf.write(target, audio[round(start * rate):round(end * rate)], rate, subtype="PCM_16")
            manifests[split].append({
                "id": segment_id, "audio_filepath": str(target), "duration": duration,
                "text": " ".join(w[2] for w in group), "lang": "en-US", "target_lang": "en-US",
                "conversation_id": conversation, "split": split,
                "source_audio_sha256": sha256_file(source) if index == 0 else None,
                "source_start_seconds": start, "source_end_seconds": end,
                "source_word_start": cursor, "source_word_end_exclusive": cursor + len(group),
                "reference_origin": "source_human_transcript", "alignment_review": "PENDING",
            })
            cursor += len(group)
    for split, items in manifests.items():
        with (output / f"{split}.jsonl").open("w") as manifest:
            for item in items:
                manifest.write(json.dumps(item, ensure_ascii=False) + "\n")
    write_json(output / "segmentation-audit.json", {
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "counts": {k: len(v) for k, v in manifests.items()}, "dropped": audit,
        "alignment_review": "PENDING", "token_reconciliation": "exact_normalized_one_to_one",
    })
