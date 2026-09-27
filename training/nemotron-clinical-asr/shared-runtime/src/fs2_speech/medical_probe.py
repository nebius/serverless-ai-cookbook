"""Full-consultation quality/latency diagnostic; not public endpoint acceptance.

Uses the user's attributed, checksum-pinned medical demo bundle. Never embeds
audio in source control. Retains complete transcripts, alignments and live
events so missing tails and partial/final duplication can be investigated.
"""

import argparse
import asyncio
import hashlib
import json
import time
import wave
from pathlib import Path

from .audio import transcribe_file
from .contracts import ENGLISH_ID, MODELS, NEMO_REVISION, RuntimeProfile, SpeechOptions
from .nemo_runtime import NeMoRuntime
from .stream import run_stream

CASES = (
    ("en-01", "ready/en/day1_consultation01_conversation.wav", "en-US"),
    ("en-02", "ready/en/day1_consultation02_conversation.wav", "en-US"),
    ("de-herzrasen", "ready/de/hhu-herzrasen.wav", "de-DE"),
    ("de-grippaler-infekt", "ready/de/hhu-grippaler-infekt.wav", "de-DE"),
    ("de-polyarthritis", "ready/de/hhu-polyarthritis.wav", "de-DE"),
)


def emit(event, **data):
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


async def paced_recording(runtime, path, options, *, case):
    started = time.monotonic()
    state, finals = {}, []

    async def messages():
        yield json.dumps({"type": "session.start", "options": options.model_dump()})
        state["audio_started"] = time.monotonic()
        with wave.open(str(path), "rb") as audio:
            samples = 0
            while chunk := audio.readframes(320):  # 20 ms, paced as if from a microphone.
                samples += len(chunk) // 2
                due = state["audio_started"] + samples / 16000
                await asyncio.sleep(max(0, due - time.monotonic()))
                yield chunk
        state["finish_sent"] = time.monotonic()
        yield '{"type":"input.finish"}'

    async def receive(event):
        elapsed = time.monotonic() - started
        kind = event["type"]
        if kind == "transcript.partial" and event.get("text"):
            state.setdefault("first_partial_seconds", elapsed)
        elif kind == "transcript.final":
            state.setdefault("first_final_seconds", elapsed)
            finals.append(event)
        elif kind == "session.completed":
            state["completed"] = event
        elif kind == "session.error":
            state["error"] = event["code"]
        emit("live_event", case=case, elapsed_seconds=elapsed, value=event)

    await run_stream(runtime, messages(), receive, max_session_seconds=7500)
    if "completed" not in state:
        raise RuntimeError(state.get("error", "incomplete_session"))
    return {"text": "".join(item["text"] for item in finals).strip(), "segments": finals,
            "audio_seconds": state["completed"]["audio_seconds"],
            "processing_seconds": time.monotonic() - started,
            "first_partial_seconds": state.get("first_partial_seconds"),
            "first_final_seconds": state.get("first_final_seconds"),
            "finalization_seconds": time.monotonic() - state["finish_sent"]}


async def run(args):
    profile = RuntimeProfile(model=args.model)
    runtime = NeMoRuntime(profile, config_path=Path(
        "/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml"))
    emit("medical_probe_start", model=args.model, profile=profile.model_dump(), nemo_revision=NEMO_REVISION,
         model_revision=MODELS[args.model].revision, scope="direct runtime; not public customer acceptance")
    await asyncio.to_thread(runtime.load)
    import torch
    emit("medical_runtime_loaded", timings=runtime.timings, gpu=torch.cuda.get_device_name(),
         torch=torch.__version__, cuda=torch.version.cuda)
    measurements = []
    for case, relative, locale in CASES:
        if args.model == ENGLISH_ID and locale != "en-US":
            continue
        path = args.assets / relative
        with wave.open(str(path), "rb") as audio:
            if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
                raise ValueError("expected prepared PCM16 mono 16 kHz assets")
            seconds = audio.getnframes() / 16000
        with path.open("rb") as handle:
            sha = hashlib.file_digest(handle, "sha256").hexdigest()
        options = SpeechOptions(model=args.model, language=locale, output_granularity="word")
        for mode in ("complete-file", "paced-stream"):
            if mode == "paced-stream" and case not in args.paced_cases:
                continue
            emit("medical_case_start", case=case, mode=mode, file=relative, sha256=sha,
                 expected_audio_seconds=seconds, options=options.model_dump())
            torch.cuda.reset_peak_memory_stats()
            result = (await transcribe_file(runtime, path, options) if mode == "complete-file" else
                      await paced_recording(runtime, path, options, case=case))
            complete = abs(result["audio_seconds"] - seconds) < 1 / 16000
            record = {"case": case, "mode": mode, "sha256": sha, "expected_audio_seconds": seconds,
                      "all_samples_processed": complete, "nonempty": bool(result["text"].strip()),
                      "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated(),
                      "real_time_factor": result["processing_seconds"] / seconds, **result}
            measurements.append(record)
            emit("medical_measurement", **record)
            if not complete or not record["nonempty"]:
                raise RuntimeError("medical_recording_empty_or_incomplete")
    emit("medical_probe_complete", measurements=len(measurements), customer_acceptance=False,
         quality_requires_reference_scoring=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--paced-cases", nargs="*", default=["en-01", "de-herzrasen"])
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
