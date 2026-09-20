---
name: speech-workflows
description: Transcribe English or multilingual recordings, compare ASR models, attribute speakers, or synthesize speech using hosted Nemotron Speech, Parakeet, Sortformer and Magpie Apps. Distinguish complete-recording jobs from real streaming.
license: Apache-2.0 AND CC-BY-4.0
---

# Hosted speech workflows

Read `scientific-gateway`. Use the platform MCP, not NVIDIA NVCF credentials,
local NeMo deployment or an upstream gRPC endpoint. This is a Nebius adaptation
of NVIDIA speech guidance; see the bundle's `NOTICE.md` for pinned sources.

## Select the lane

| Goal | App | Important distinction |
| --- | --- | --- |
| English recording | `nemotron-speech-en-0-6b` | English model; do not send German as if supported |
| German / supported multilingual recording | `nemotron-speech-multilingual-0-6b` | Inspect accepted language codes; do not infer all languages |
| English with end-of-utterance markers | `parakeet-realtime-eou-120m-v1` | An uploaded recording is not microphone streaming |
| Speaker time segments | `diar-streaming-sortformer-4spk-v2-1` | Up to four anonymous speakers, not doctor/patient identity |
| Text to speech | `magpie-tts-multilingual-357m` | Supported language + named voice, not arbitrary voice cloning |

For the selected App, get its exact schema and tool name once. Preserve model
language, source audio and scientific goal. If a model is unavailable to this
key, report that rather than silently substituting it.

## Recording to retained transcript

1. Locate the actual audio in the caller's workspace; record SHA-256, size,
   duration, codec, channel count and sample rate with a file tool. Keep the
   original if a format conversion is necessary. Do not invent a remote path.
2. Use the workspace uploader / installed file client to finalize the recording.
   Put its small reference into the live schema's audio field, not base64 in
   chat. Native Nemotron and voice-family payloads differ: do not copy one
   model's request into another. The schema defines maximum size/duration.
3. Submit once with a stable key; use the durable native study phase for a
   multi-recording batch. Respect caller concurrency, retain all operation IDs,
   and resume queued jobs after client timeouts instead of duplicating them.
4. Save the complete original JSON and transcript file, timing segments and
   metadata. Check declared duration/coverage against the source, including the
   tail of long recordings. A short preview is not the full transcript.
5. Report queue/startup/inference/total times separately when measured; otherwise
   mark the missing timing unavailable. Never infer cold start from total time.

For diarization, preserve overlapping turns and timestamp units. Align ASR and
speaker segments explicitly; unmatched text stays unassigned. Speaker numbers
do not identify people. Do not merge uncertain speakers into a clinical role.

## Streaming and synthesis

The voice service advertises `/v1/voice/stream` for audio streaming and
`/v1/voice/synthesize` for incremental synthesis. These are separate transports,
not an invented `stream:true` on a complete-recording MCP tool. Use only when the
client exposes that transport; otherwise state that this client handles recorded
files. Do not claim a browser microphone UI is installed because the model can
stream. Measure first partial/final latency only for an actual streaming run.

For Magpie, use text/language/voice from the schema, retain the generated WAV,
and check duration, sample rate and nonempty decoded audio. Do not truncate a
long passage to meet a limit. Use an explicitly bounded segmentation plan if
needed, preserving every text span and chunk order.

For measured ASR comparison load `clinical-asr-evaluation`. For a medical draft
load `clinical-documentation` with the full retained transcript file. Neither a
fluent transcript nor generated audio demonstrates clinical correctness.
