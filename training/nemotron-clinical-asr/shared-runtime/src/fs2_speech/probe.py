"""Task-owned direct-runtime diagnostic; never substitutes for public acceptance.

Synthesizes non-customer English audio, sends bounded frames to the same NeMo
streaming adapter for file-speed and real-time-paced runs, and retains every run.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from uuid import uuid4

from .contracts import MODELS, NEMO_REVISION, RuntimeProfile, SpeechOptions
from .events import TranscriptEvents
from .framing import PCMFramer
from .nemo_runtime import NeMoRuntime

FIXTURE = (
    "Welcome to the scientific artificial intelligence platform. "
    "This is a speech recognition test. We are checking that every spoken word "
    "is transcribed, including the very last word. The final word is telescope."
)


def emit(event: str, **data: object) -> None:
    print(json.dumps({"event": event, **data}, ensure_ascii=False), flush=True)


def run_recording(runtime: NeMoRuntime, options: SpeechOptions, path: Path, *, paced: bool) -> dict:
    import torch

    stream_id = runtime.begin(options)
    events = TranscriptEvents(str(uuid4()))
    framer = PCMFramer(runtime.frame_samples)
    finals: list[str] = []
    first_partial: float | None = None
    first_final: float | None = None
    step_seconds: list[float] = []
    event_count = 0
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()

    def process(frame):
        nonlocal first_partial, first_final, event_count
        begin = time.monotonic()
        output = runtime.step(stream_id, frame, options)
        torch.cuda.synchronize()
        step_seconds.append(time.monotonic() - begin)
        emitted = events.update(final=output.final_transcript, partial=output.partial_transcript, last=frame.last)
        for event in emitted:
            event_count += 1
            elapsed = time.monotonic() - started
            if event.type == "transcript.partial" and event.text and first_partial is None:
                first_partial = elapsed
            if event.type == "transcript.final":
                first_final = first_final if first_final is not None else elapsed
                finals.append(event.text)
            emit("transcript_event", elapsed_seconds=elapsed, before_end_of_stream=not frame.last, **event.to_dict())

    try:
        with wave.open(str(path), "rb") as audio:
            if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
                raise ValueError("probe requires 16kHz mono PCM16 WAV")
            while pcm := audio.readframes(320):  # 20 ms network-sized messages
                if paced:
                    deadline = started + (framer.total_samples + len(pcm) // 2) / 16000
                    time.sleep(max(0.0, deadline - time.monotonic()))
                for frame in framer.push(pcm):
                    process(frame)
            last_audio_at = time.monotonic()
            process(framer.finish())
        elapsed = time.monotonic() - started
        transcript = "".join(finals).strip()
        audio_seconds = framer.total_samples / 16000
        words = set(re.findall(r"[a-z]+", transcript.lower()))
        required = {"speech", "recognition", "test", "telescope"}
        return {
            "paced": paced,
            "audio_seconds": audio_seconds,
            "wall_seconds": elapsed,
            "model_step_seconds": step_seconds,
            "first_partial_seconds": first_partial,
            "first_final_seconds": first_final,
            "finalization_seconds": time.monotonic() - last_audio_at,
            "real_time_factor": elapsed / audio_seconds,
            "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated(),
            "peak_gpu_reserved_bytes": torch.cuda.max_memory_reserved(),
            "transcript": transcript,
            "event_count": event_count,
            "required_words_present": sorted(words & required),
            "passed_diagnostic": required <= words and first_partial is not None,
        }
    finally:
        runtime.close(stream_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--chunk-ms", type=int, default=560)
    parser.add_argument("--precision", choices=["float32", "bfloat16", "float16"], default="float32")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--config", type=Path, default=Path(
        "/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml",
    ))
    parser.add_argument("--cache-dir", default=None)
    args = parser.parse_args()
    if args.repetitions < 3:
        parser.error("retain at least three measured repetitions")
    profile = RuntimeProfile(model=args.model, chunk_size_ms=args.chunk_ms, precision=args.precision)
    options = SpeechOptions(model=args.model, language="en-US", chunk_size_ms=args.chunk_ms)
    runtime = NeMoRuntime(profile, config_path=args.config, cache_dir=args.cache_dir)
    emit("probe_start", scope="direct-runtime diagnostic, not customer acceptance", profile=profile.model_dump(),
         nemo_revision=NEMO_REVISION, checkpoint_revision=MODELS[args.model].revision)
    runtime.load()
    import torch

    emit("runtime_loaded", timings=runtime.timings, torch=torch.__version__, cuda=torch.version.cuda,
         device=torch.cuda.get_device_name(), compute_capability=torch.cuda.get_device_capability(),
         frame_samples=runtime.frame_samples)
    with tempfile.TemporaryDirectory(prefix="fs2-speech-probe-") as directory:
        raw = Path(directory) / "synthetic.wav"
        audio = Path(directory) / "synthetic-16k.wav"
        subprocess.run(["espeak-ng", "-v", "en-us", "-s", "145", "-w", str(raw), FIXTURE], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(raw), "-ar", "16000", "-ac", "1",
                        "-c:a", "pcm_s16le", str(audio)], check=True)
        emit("fixture", text=FIXTURE, sha256=hashlib.sha256(audio.read_bytes()).hexdigest(), source="espeak-ng")
        # Warmup is explicitly separated from measured repetitions.
        warmup = run_recording(runtime, options, audio, paced=False)
        emit("warmup", **warmup)
        results = []
        for paced in (False, True):
            for repetition in range(args.repetitions):
                result = run_recording(runtime, options, audio, paced=paced)
                results.append(result)
                emit("measurement", repetition=repetition, **result)
        passed = all(result["passed_diagnostic"] for result in [warmup, *results])
        emit("probe_complete", passed_diagnostic=passed, customer_acceptance=False, measurements=len(results))
        if not passed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
