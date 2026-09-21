#!/usr/bin/env python3
"""Transcribe and diarize one complete recording through two durable operations."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from recording_pipeline import (file_identity, immutable_input, invoke, operation_metadata,
                                publish_bytes, timing, unwrap, upload_source, workspace_urls)
from scientific_receipts import load, save


MEDIA_TYPES = {'.flac': 'audio/flac', '.wav': 'audio/wav', '.mp3': 'audio/mpeg',
               '.mp4': 'audio/mp4', '.ogg': 'audio/ogg', '.webm': 'audio/webm'}
PARAKEET = ('parakeet-realtime-eou-120m-v1', 'infer_parakeet_realtime_eou_120m_v1_native')
SORTFORMER = ('diar-streaming-sortformer-4spk-v2-1', 'infer_diar_streaming_sortformer_4spk_v2_1_native')


def validate_result(path: Path, model: str) -> dict:
    result = unwrap(load(path))
    if result.get('model') != model or not isinstance(result.get('audio_seconds'), (int, float)):
        raise ValueError(f'{model} result has the wrong model identity or duration.')
    if result['audio_seconds'] <= 0 or not isinstance(result.get('events'), list):
        raise ValueError(f'{model} result has no complete recording events.')
    if not isinstance(result.get('text'), str) or not isinstance(result.get('processing_seconds'), (int, float)):
        raise ValueError(f'{model} result has no transcript/processing contract.')
    return result


def decode_audio(path: Path) -> np.ndarray:
    completed = subprocess.run([
        'ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), '-f', 'f32le',
        '-ac', '1', '-ar', '16000', 'pipe:1',
    ], capture_output=True, check=False, timeout=300)
    if completed.returncode or not completed.stdout:
        raise ValueError('Recording could not be decoded for the waveform.')
    audio = np.frombuffer(completed.stdout, dtype='<f4')
    if not len(audio) or not np.isfinite(audio).all():
        raise ValueError('Decoded recording contains no finite audio samples.')
    return audio


def render_timeline(source: Path, asr: dict, diar: dict) -> tuple[bytes, dict]:
    audio = decode_audio(source); duration = len(audio) / 16000
    bins = min(2400, len(audio)); edges = np.linspace(0, len(audio), bins + 1, dtype=int)
    envelope = np.asarray([np.max(np.abs(audio[edges[i]:edges[i + 1]]))
                           if edges[i + 1] > edges[i] else 0 for i in range(bins)])
    times = np.linspace(0, duration, bins, endpoint=False)
    speaker_times, speaker_values = [], []
    for event in diar['events']:
        if event.get('type') != 'speaker.activity':
            continue
        values = np.asarray(event.get('probabilities'), dtype=float)
        if values.ndim != 2 or values.shape[1] != 4 or not np.isfinite(values).all():
            raise ValueError('Sortformer speaker activity has an invalid probability matrix.')
        step = float(event.get('frame_duration_seconds', 0.08))
        start = float(event.get('start_seconds', 0))
        speaker_times.extend(start + np.arange(len(values)) * step)
        speaker_values.extend(values.tolist())
    matrix = np.asarray(speaker_values, dtype=float)
    if not len(matrix):
        raise ValueError('Sortformer result has no speaker activity frames.')
    figure = plt.figure(figsize=(16, 8.5), facecolor='#f4f7f3')
    grid = figure.add_gridspec(2, 1, height_ratios=(1.2, 2.5), hspace=0.25)
    waveform = figure.add_subplot(grid[0])
    waveform.fill_between(times, -envelope, envelope, color='#35c98b', alpha=0.88, linewidth=0)
    waveform.set_xlim(0, duration); waveform.set_ylabel('amplitude'); waveform.set_title('Complete recording waveform')
    activity = figure.add_subplot(grid[1], sharex=waveform)
    colors = ('#35c98b', '#5577d8', '#df7f37', '#a96bc6')
    speaker_times = np.asarray(speaker_times)
    for index in range(4):
        activity.fill_between(speaker_times, index, index + matrix[:, index], color=colors[index], alpha=0.82,
                              label=f'speaker_{index}')
    eou_offsets = [float(event['audio_offset_seconds']) for event in asr['events']
                   if event.get('type') == 'turn.eou' and isinstance(event.get('audio_offset_seconds'), (int, float))]
    for offset in eou_offsets:
        waveform.axvline(offset, color='#24362c', alpha=0.35, linewidth=0.8)
        activity.axvline(offset, color='#24362c', alpha=0.25, linewidth=0.8)
    activity.set_ylim(0, 4); activity.set_yticks(np.arange(4) + 0.5, [f'speaker_{index}' for index in range(4)])
    activity.set_xlabel('recording time (seconds)'); activity.set_title('Anonymous Sortformer speaker activity')
    figure.suptitle('Speech analysis · waveform, EOU boundaries, and anonymous speaker activity',
                    fontsize=16, color='#19241d')
    figure.tight_layout()
    target = io.BytesIO(); figure.savefig(target, format='png', dpi=160, bbox_inches='tight',
                                           metadata={'Software': 'Nebius Scientific AI'})
    plt.close(figure)
    return target.getvalue(), {'decoded_duration_seconds': duration, 'speaker_activity_frames': len(matrix),
                               'eou_marker_count': len(eou_offsets)}


def run_model(*, source: Path, media_type: str, model: str, tool: str, directory: Path,
              key: str, wait_seconds: int, recover_only: bool, runner):
    upload_dir, run_dir = directory / 'upload', directory / 'run'
    artifact, code = upload_source(source=source, model=model, media_type=media_type,
                                   directory=upload_dir, idempotency_key=key + '-source', runner=runner)
    if code == 75:
        return {'state': 'upload_pending'}, code
    input_path = directory / 'input.json'; immutable_input(input_path, {'audio': artifact})
    receipt, code = invoke(model=model, tool=tool, input_path=input_path, directory=run_dir,
                           idempotency_key=key, wait_seconds=wait_seconds,
                           recover_only=recover_only, runner=runner)
    return receipt, code


def run(args, runner=subprocess.run):
    source = args.source.resolve(); media_type = MEDIA_TYPES.get(source.suffix.lower())
    if not source.is_file() or not media_type or not 1 <= source.stat().st_size <= 512 * 1024 * 1024:
        raise ValueError('Speech source must be a supported nonempty recording up to 512 MiB.')
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    asr_receipt, code = run_model(source=source, media_type=media_type, model=PARAKEET[0], tool=PARAKEET[1],
                                  directory=output / 'parakeet', key=args.idempotency_key + '-asr',
                                  wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {'state': 'transcription_pending', 'operation_id': asr_receipt.get('operation_id'),
                'output_dir': str(output)}, code
    diar_receipt, code = run_model(source=source, media_type=media_type, model=SORTFORMER[0], tool=SORTFORMER[1],
                                   directory=output / 'sortformer', key=args.idempotency_key + '-diar',
                                   wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        return {'state': 'diarization_pending', 'operation_id': diar_receipt.get('operation_id'),
                'transcription_operation_id': asr_receipt.get('operation_id'), 'output_dir': str(output)}, code
    asr_dir, diar_dir = output / 'parakeet' / 'run', output / 'sortformer' / 'run'
    asr = validate_result(asr_dir / 'result.json', PARAKEET[0])
    diar = validate_result(diar_dir / 'result.json', SORTFORMER[0])
    if abs(float(asr['audio_seconds']) - float(diar['audio_seconds'])) > 0.1:
        raise ValueError('ASR and diarization did not process the same complete duration.')
    analysis = output / 'analysis'; analysis.mkdir(parents=True, exist_ok=True, mode=0o700)
    transcript = publish_bytes(analysis / 'transcript.txt', (asr['text'].strip() + '\n').encode())
    event_value = {'parakeet': asr['events'], 'sortformer': diar['events']}
    events = publish_bytes(analysis / 'events.json', (json.dumps(event_value, indent=2) + '\n').encode())
    timeline_image, timeline_metrics = render_timeline(source, asr, diar)
    timeline_receipt = publish_bytes(analysis / 'speech-timeline.png', timeline_image)
    asr_operation = operation_metadata(asr_dir / 'operation.json')
    diar_operation = operation_metadata(diar_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/speech-analysis/v1', 'state': 'succeeded',
        'input': {'path': str(source), **file_identity(source), 'media_type': media_type,
                  'audio_seconds': asr['audio_seconds']},
        'transcription': {'model': PARAKEET[0], 'operation_id': asr_operation.get('id') or asr_receipt.get('operation_id'),
                          'processing_seconds': asr['processing_seconds'], 'timing': timing(asr_operation),
                          'text': asr['text'],
                          'final_segment_count': sum(event.get('type') == 'transcript.final' for event in asr['events'])},
        'diarization': {'model': SORTFORMER[0], 'operation_id': diar_operation.get('id') or diar_receipt.get('operation_id'),
                        'processing_seconds': diar['processing_seconds'], 'timing': timing(diar_operation),
                        'anonymous_speakers': ['speaker_0', 'speaker_1', 'speaker_2', 'speaker_3']},
        'timeline_metrics': timeline_metrics,
        'artifacts': {'transcript': transcript, 'events': events, 'timeline': timeline_receipt},
        'limitations': ['Speaker labels are anonymous arrival-order channels, not person identities.',
                        'Parakeet provides finalized segments and model EOU markers, not word-level timestamps.',
                        'The transcript requires domain review before medical or clinical use.'],
    }
    save(analysis / 'summary.json', summary)
    timeline_path = analysis / 'speech-timeline.png'
    transcript_path = analysis / 'transcript.txt'
    summary_path = analysis / 'summary.json'
    return {**summary, 'timeline_path': str(timeline_path),
            'transcript_path': str(transcript_path), 'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(timeline=timeline_path, transcript=transcript_path,
                                             summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--wait-seconds', type=int, default=600)
    parser.add_argument('--recover-only', action='store_true')
    args = parser.parse_args()
    if not 8 <= len(args.idempotency_key) <= 180 or not 0 <= args.wait_seconds <= 3600:
        parser.error('Invalid speech workflow idempotency key or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect both retained upload/run receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
