"""Real complete-file diagnostic, separate from public customer acceptance."""

import argparse
import asyncio
import hashlib
import json
import math
import resource
import subprocess
import tempfile
import time
import wave
from pathlib import Path

from .audio import transcribe_file
from .contracts import MODELS, RuntimeProfile, SpeechOptions
from .nemo_runtime import NeMoRuntime


def sentence(path: Path, text: str) -> tuple[bytes, int]:
    subprocess.run(["espeak-ng", "-s", "145", "-w", str(path), text], check=True, capture_output=True)
    with wave.open(str(path), "rb") as handle:
        return handle.readframes(handle.getnframes()), handle.getframerate()


async def probe(model: str, minutes: int) -> None:
    profile = RuntimeProfile(model=model)
    runtime = NeMoRuntime(profile, config_path=Path(
        "/opt/nemo/examples/asr/conf/asr_streaming_inference/cache_aware_rnnt.yaml"))
    await asyncio.to_thread(runtime.load)
    options = SpeechOptions(model=model)
    with tempfile.TemporaryDirectory(prefix="fs2-speech-long-") as directory:
        root = Path(directory)
        text = "The research team reviewed the recording. Every sentence should appear in the complete transcript."
        tail_text = "This is the final sentence. The last word is telescope."
        body, rate = sentence(root / "body.wav", text)
        tail, tail_rate = sentence(root / "tail.wav", tail_text)
        assert rate == tail_rate
        repeats = math.ceil(minutes * 60 / (len(body) / 2 / rate))
        path = root / "long.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            for _ in range(repeats):
                handle.writeframes(body)
            handle.writeframes(tail)
        print(json.dumps({"event": "long_probe_start", "model": model, "minutes_minimum": minutes,
                          "repeated_sentences": repeats, "reference_body": text, "reference_tail": tail_text,
                          "file_bytes": path.stat().st_size, "runtime_load": runtime.timings}), flush=True)
        started = time.monotonic()
        result = await transcribe_file(runtime, path, options)
        expected_audio = (repeats * len(body) + len(tail)) / 2 / rate
        tail_preserved = result["text"].rstrip(". ").lower().endswith("telescope")
        complete_duration = abs(result["audio_seconds"] - expected_audio) < 0.01
        print(json.dumps({"event": "long_probe_complete", "model": model,
                          "audio_seconds": result["audio_seconds"], "expected_audio_seconds": expected_audio,
                          "wall_seconds": time.monotonic() - started,
                          "peak_host_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          "text_sha256": hashlib.sha256(result["text"].encode()).hexdigest(),
                          "transcript": result["text"], "segments": len(result["segments"]),
                          "tail_preserved": tail_preserved, "complete_duration": complete_duration,
                          "customer_acceptance": False}), flush=True)
        if not tail_preserved or not complete_duration:
            raise RuntimeError("long_recording_diagnostic_failed")
        # A second distinct request proves the long session released its state.
        second = await transcribe_file(runtime, root / "tail.wav", options)
        print(json.dumps({"event": "post_long_request", "text": second["text"],
                          "audio_seconds": second["audio_seconds"]}), flush=True)
        if not second["text"].rstrip(". ").lower().endswith("telescope"):
            raise RuntimeError("post_long_session_reuse_failed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--minutes", type=int, choices=range(30, 61), default=30)
    args = parser.parse_args()
    asyncio.run(probe(args.model, args.minutes))


if __name__ == "__main__":
    main()
