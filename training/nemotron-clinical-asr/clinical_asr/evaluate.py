"""Emit real paired predictions using the exact production streaming engine."""
import argparse
import json
import time
import wave
from pathlib import Path

from .assembly import TEXT_ASSEMBLY, assemble_final_fragments
from .common import read_jsonl, sha256_file, write_json
from .contracts import SpeechOptions
from .events import TranscriptEvents
from .framing import PCMFramer
from .families import FAMILIES
from .runtime import NeMoRuntime


def transcribe_wav(runtime, path, options, *, cancelled=lambda: False):
    framer = PCMFramer(runtime.frame_samples)
    events = TranscriptEvents("batch")
    output_events = []
    acoustic_items = []
    first_partial_seconds = None
    start = time.monotonic()
    stream_id = runtime.begin(options)
    try:
        with wave.open(str(path), "rb") as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
                raise ValueError("requires_mono_16khz_pcm16_wav")
            if not 0 < audio.getnframes() / 16000 <= 1800:
                raise ValueError("audio_duration_out_of_range")

            def process(frame):
                nonlocal first_partial_seconds
                if cancelled():
                    raise InterruptedError("cancelled")
                result = runtime.step(stream_id, frame, options)
                acoustic_items.extend({"word" if options.output_granularity == "word" else "text": segment.text,
                                       "start": float(segment.start), "end": float(segment.end)}
                                      for segment in (getattr(result, "final_segments", None) or []))
                for event in events.update(final=result.final_transcript, partial=result.partial_transcript, last=frame.last):
                    value = event.to_dict()
                    value["elapsed_seconds"] = time.monotonic() - start
                    if first_partial_seconds is None and event.text:
                        first_partial_seconds = value["elapsed_seconds"]
                    output_events.append(value)
            while pcm := audio.readframes(16000):
                for frame in framer.push(pcm):
                    process(frame)
            process(framer.finish())
        seconds = time.monotonic() - start
        text = assemble_final_fragments(output_events)
        return {"text": text, "model_id": runtime.model_id, "runtime": runtime.identity,
                "text_assembly": TEXT_ASSEMBLY,
                "audio_seconds": framer.total_samples / 16000, "elapsed_seconds": seconds,
                "first_nonempty_event_seconds": first_partial_seconds,
                "real_time_factor": seconds / (framer.total_samples / 16000), "events": output_events,
                "memory": runtime.memory_snapshot() if hasattr(runtime, "memory_snapshot") else None,
                "words" if options.output_granularity == "word" else "segments": acoustic_items,
                "timing_mode": "unpaced_batch_not_microphone_latency", "diarization": None}
    finally:
        runtime.close(stream_id)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--checkpoint-sha")
    parser.add_argument("--model-id", default="nemotron35-base-en")
    parser.add_argument("--model-family", choices=sorted(FAMILIES), default="nemotron35")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.model_family == "english_specialist" and args.model_id != "nemotron-clinical-en":
        raise ValueError("use_evaluate_english_for_pinned_english_base")
    runtime = NeMoRuntime(checkpoint=args.checkpoint, checkpoint_sha=args.checkpoint_sha,
                          model_id=args.model_id, model_family=args.model_family)
    runtime.load()
    options = SpeechOptions(model=args.model_id)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(args.manifest)
    if args.limit:
        rows = rows[:args.limit]
    with output.open("w") as target:
        for row in rows:
            result = transcribe_wav(runtime, row["audio_filepath"], options)
            result["id"] = row.get("id", row.get("conversation_id"))
            result["input_sha256"] = sha256_file(row["audio_filepath"])
            result["collapse_warning"] = not result["text"].strip() or "<unk>" in result["text"].lower()
            target.write(json.dumps(result, ensure_ascii=False) + "\n")
            target.flush()
    write_json(output.with_suffix(".provenance.json"), {"runtime": runtime.identity, "text_assembly": TEXT_ASSEMBLY,
               "manifest_sha256": sha256_file(args.manifest), "predictions_sha256": sha256_file(output), "rows": len(rows)})
