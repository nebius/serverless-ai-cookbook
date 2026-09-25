"""Real managed-ingress probe; paced WS timings, durable batch and typed MCP.

Run only against the new endpoint and approved synthetic/de-identified input.
The evidence JSON contains transcript text but never bearer credentials.
"""
import argparse
import asyncio
import json
import os
import time
import wave
from pathlib import Path
from uuid import uuid4

from .common import sha256_file, write_json


async def main_async(args):
    import httpx
    import websockets
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    endpoint = os.environ["ASR_ENDPOINT"].rstrip("/")
    if not endpoint.startswith("https://"):
        raise ValueError("managed_probe_requires_https")
    headers = {"Authorization": "Bearer " + os.environ["API_BEARER_TOKEN"]}
    result = {"input_sha256": sha256_file(args.audio), "model": args.model,
              "wall_started_at_unix": time.time(), "endpoint_origin": endpoint,
              "test_type": "real_remote_model_not_mock"}
    # The application health route is public for internal probes, but managed
    # ingress can require the endpoint bearer even for readiness requests.
    async with httpx.AsyncClient(timeout=120, headers=headers) as client:
        response = await client.get(endpoint + "/readyz")
        response.raise_for_status()
        result["ready"] = response.json()
        with open(args.audio, "rb") as audio:
            response = await client.post(endpoint + "/v1/artifacts", headers=headers,
                                         files={"file": ("probe.wav", audio, "audio/wav")})
        response.raise_for_status()
        artifact = response.json()
        request = {"audio_artifact": artifact["artifact"], "idempotency_key": "probe-" + str(uuid4()),
                   "options": {"model": args.model, "output_granularity": "word"}}
        response = await client.post(endpoint + "/v1/transcriptions", headers=headers, json=request)
        response.raise_for_status()
        operation = response.json()
        result["operation_id"] = operation["id"]
        replay = await client.post(endpoint + "/v1/transcriptions", headers=headers, json=request)
        replay.raise_for_status()
        if replay.json()["id"] != operation["id"]:
            raise RuntimeError("idempotency_identity_changed")
        deadline = time.monotonic() + 600
        while operation["status"] not in {"succeeded", "failed", "cancelled"}:
            if time.monotonic() > deadline:
                raise TimeoutError("batch_poll_deadline")
            await asyncio.sleep(0.2)
            response = await client.get(endpoint + "/v1/operations/" + operation["id"], headers=headers)
            response.raise_for_status()
            operation = response.json()
        result["batch"] = operation
        if operation["status"] != "succeeded" or not operation["result"]["text"].strip():
            raise RuntimeError("batch_failed_or_empty")

    async with streamablehttp_client(endpoint + "/mcp", headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            result["mcp_tools"] = [tool.name for tool in tools.tools]
            polled = await session.call_tool("get_clinical_transcription", {"operation_id": operation["id"]})
            if polled.isError:
                raise RuntimeError("mcp_poll_failed")
            result["mcp_polled_same_operation"] = operation["id"] in polled.model_dump_json()

    with wave.open(args.audio, "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("requires_mono16k_pcm16")
        pcm = audio.readframes(audio.getnframes())
    ws_url = "wss://" + endpoint[len("https://"):] + "/v1/audio/stream"
    events = []
    async with websockets.connect(ws_url, additional_headers=headers, open_timeout=30, close_timeout=10,
                                  max_size=1024 * 1024) as socket:
        await socket.send(json.dumps({"type": "session.start", "options": {"model": args.model,
            "output_granularity": "word"}, "audio": {"encoding": "pcm_s16le", "sample_rate_hz": 16000, "channels": 1}}))
        ready = json.loads(await asyncio.wait_for(socket.recv(), 60))
        if ready["type"] != "session.ready":
            raise RuntimeError("stream_not_admitted")
        start = time.monotonic()
        finished_input = None

        async def send_audio():
            nonlocal finished_input
            # Real-time pacing: 100ms of PCM per packet, no transcript playback.
            for offset in range(0, len(pcm), 3200):
                target = start + offset / 32000
                await asyncio.sleep(max(0.0, target - time.monotonic()))
                await socket.send(pcm[offset:offset + 3200])
            await asyncio.sleep(max(0.0, start + len(pcm) / 32000 - time.monotonic()))
            finished_input = time.monotonic()
            await socket.send('{"type":"input.finish"}')

        sender = asyncio.create_task(send_audio())
        try:
            async with asyncio.timeout(len(pcm) / 32000 + 180):
                async for raw in socket:
                    event = json.loads(raw)
                    event["client_elapsed_seconds"] = time.monotonic() - start
                    events.append(event)
                    if event["type"] == "session.error":
                        raise RuntimeError("stream_error:" + event["code"])
                    if event["type"] == "session.completed":
                        break
            await sender
        finally:
            if not sender.done():
                sender.cancel()
        if not events or events[-1]["type"] != "session.completed":
            raise RuntimeError("stream_missing_final_completion")
        partials = [event for event in events if event["type"] == "transcript.partial" and event.get("text")]
        result["stream"] = {"events": events, "audio_seconds": len(pcm) / 32000,
            "first_nonempty_partial_seconds": partials[0]["client_elapsed_seconds"] if partials else None,
            "final_after_audio_seconds": time.monotonic() - finished_input,
            "partial_before_audio_finished": bool(partials and partials[0]["client_elapsed_seconds"] < len(pcm) / 32000),
            "timing_mode": "client_paced_realtime_PCM"}
    write_json(args.output, result)
    print(json.dumps({"evidence": args.output, "operation_id": operation["id"],
                      "batch_nonempty": True, "stream_completed": True,
                      "early_partial": result["stream"]["partial_before_audio_finished"]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", required=True)
    parser.add_argument("--model", default="nemotron-clinical-en")
    parser.add_argument("--output", required=True)
    asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    main()
