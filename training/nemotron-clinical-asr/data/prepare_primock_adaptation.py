#!/usr/bin/env python3
"""Prepare the fixed PriMock40/5 adaptation split, excluding all12 known cases.

Offline by default. --download explicitly fetches pinned public inputs. No ASR,
forced alignment, clinical adjudication, cloud upload or model invocation occurs.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import wave

from download_public import download, file_hash

REVISION = 'cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5'
INVENTORY_SHA = '3d636cdd09d6936bb6ba571d16aec301559a5609af56616e56b40b00c5ee7e83'
SEED = 'primock-adaptation-v1:20260926:'
KNOWN_SAMPLE = ('day1_consultation01', 'day1_consultation02')
RESERVED_EXTERNAL = ('day1_consultation06', 'day1_consultation13', 'day2_consultation05',
    'day2_consultation10', 'day3_consultation04', 'day3_consultation07', 'day4_consultation06',
    'day4_consultation09', 'day5_consultation01', 'day5_consultation02')
RAW = f'https://raw.githubusercontent.com/babylonhealth/primock57/{REVISION}/'
MEDIA = f'https://media.githubusercontent.com/media/babylonhealth/primock57/{REVISION}/'


def split_membership():
    all_names = {f'day{day}_consultation{number:02}'
                 for day, count in [(1, 15), (2, 10), (3, 10), (4, 10), (5, 12)]
                 for number in range(1, count + 1)}
    excluded = set(KNOWN_SAMPLE) | set(RESERVED_EXTERNAL)
    available = all_names - excluded
    rank = lambda name: (hashlib.sha256((SEED + name).encode()).hexdigest(), name)
    dev = {min((name for name in available if name.startswith(f'day{day}_')), key=rank)
           for day in range(1, 6)}
    return {'train': sorted(available - dev), 'dev': sorted(dev), 'excluded': sorted(excluded)}


def load_inventory():
    path = Path(__file__).with_name('primock_adaptation_sources.json')
    if file_hash(path) != INVENTORY_SHA:
        raise ValueError('Pinned public source inventory changed')
    value = json.loads(path.read_text())
    split = split_membership()
    if value['revision'] != REVISION or value['license'] != 'CC-BY-4.0' or value['split_seed_label'] != SEED:
        raise ValueError('Source revision/license/split rule mismatch')
    for key in ['train', 'dev']:
        if value[key + '_conversations'] != split[key]:
            raise ValueError('Frozen conversation split mismatch')
    if value['excluded_conversations'] != split['excluded']:
        raise ValueError('Known evaluation exclusions changed')
    expected = {name + '_' + role for name in split['train'] + split['dev'] for role in ['doctor', 'patient']}
    sources = value['sources']
    if len(sources) != 90 or {row['source_id'] for row in sources} != expected:
        raise ValueError('Expected exactly90 unique train/dev speaker sources')
    for row in sources:
        if row['source_id'] != row['conversation_id'] + '_' + row['speaker']:
            raise ValueError('Source name/speaker mismatch')
        for key in ['audio_sha256', 'textgrid_sha256', 'lfs_pointer_sha256']:
            if not re.fullmatch('[0-9a-f]{64}', row[key]):
                raise ValueError('Invalid pinned source hash')
        for key in ['audio_bytes', 'audio_samples', 'textgrid_bytes']:
            if type(row[key]) is not int or row[key] <= 0:
                raise ValueError('Invalid source size')
    return value


def textgrid_intervals(text):
    if text.count('class = "IntervalTier"') != 1:
        raise ValueError('Exactly one original speaker IntervalTier required')
    declared = re.findall(r'intervals:\s*size\s*=\s*(\d+)', text)
    pattern = r'intervals \[(\d+)\]:\s*xmin = ([\d.]+)\s*xmax = ([\d.]+)\s*text = "((?:""|[^"])*)"'
    matches = re.findall(pattern, text)
    if len(declared) != 1 or int(declared[0]) != len(matches):
        raise ValueError('Malformed or truncated TextGrid interval list')
    values = []
    previous_end = 0.0
    for expected_index, (index, start, end, value) in enumerate(matches, 1):
        first, last = float(start), float(end)
        if int(index) != expected_index or not all(math.isfinite(v) for v in [first, last]) or not 0 <= previous_end <= first <= last:
            raise ValueError('Nonsequential or invalid human interval coordinates')
        values.append((int(index), first, last, value.replace('""', '"').strip()))
        previous_end = last
    return values


def reference_rows(source, text):
    membership = split_membership()
    name = source['conversation_id']
    if name in membership['excluded'] or name not in membership['train'] + membership['dev']:
        raise ValueError('Evaluation/unknown conversation cannot enter adaptation')
    split = 'train' if name in membership['train'] else 'dev'
    rows, omitted = [], Counter()
    for index, start, end, words in textgrid_intervals(text):
        first, last = round(start * 16000), round(end * 16000)
        reason = 'empty' if not words else 'markup' if '<' in words or '>' in words else 'duration' if not 8000 <= last - first <= 480000 else None
        if reason:
            omitted[reason] += 1
            continue
        if not 0 <= first < last <= source['audio_samples']:
            raise ValueError('Human interval exceeds original PCM; never silently clip')
        rows.append({'id': f'primock_adapt_{name}_{source["speaker"]}_{index:03}',
            'conversation_id': name, 'split': split, 'speaker': source['speaker'],
            'text': words, 'lang': 'en-US', 'target_lang': 'en-US',
            'source_interval_index_one_based': index, 'source_start_seconds': start, 'source_end_seconds': end,
            'source_start_sample': first, 'source_end_sample_exclusive': last,
            'source_textgrid_sha256': source['textgrid_sha256'], 'duration': (last - first) / 16000,
            'license': 'CC-BY-4.0', 'alignment_source': 'original_human_TextGrid'})
    return rows, omitted


def frozen_bytes(path, raw):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Refusing symlink output')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as target:
            target.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise ValueError('Existing prepared output differs; no overwrite')


def clip_bytes(pcm, row):
    first, last = row['source_start_sample'], row['source_end_sample_exclusive']
    if type(first) is not int or type(last) is not int or len(pcm) % 2 or not 0 <= first < last <= len(pcm) // 2:
        raise ValueError('Exact integer PCM bounds required')
    if not 8000 <= last - first <= 480000 or row['duration'] != (last - first) / 16000:
        raise ValueError('Frozen duration/sample rule mismatch')
    target = io.BytesIO()
    with wave.open(target, 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(pcm[first * 2:last * 2])
    return target.getvalue()


def input_files(inventory):
    yield 'LICENSE.md', RAW + 'LICENSE.md', inventory['license_sha256'], inventory['license_bytes']
    for source in inventory['sources']:
        name = source['source_id']
        yield f'transcripts/{name}.TextGrid', RAW + f'transcripts/{name}.TextGrid', source['textgrid_sha256'], source['textgrid_bytes']
        yield f'audio/{name}.wav', MEDIA + f'audio/{name}.wav', source['audio_sha256'], source['audio_bytes']


def verify_inputs(source_root, inventory, allow_download=False):
    for relative, url, checksum, size in input_files(inventory):
        path = source_root / relative
        if allow_download:
            download(url, path, checksum)
        if not path.is_file() or path.stat().st_size != size or file_hash(path) != checksum:
            raise ValueError('Pinned source missing or mismatched: ' + relative)
    references, omitted = [], Counter()
    for source in inventory['sources']:
        with wave.open(str(source_root / 'audio' / (source['source_id'] + '.wav')), 'rb') as audio:
            if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype(), audio.getnframes()) != (1, 2, 16000, 'NONE', source['audio_samples']):
                raise ValueError('Original mono16k PCM16 geometry mismatch')
        grid = (source_root / 'transcripts' / (source['source_id'] + '.TextGrid')).read_text()
        rows, excluded = reference_rows(source, grid)
        references.extend(rows)
        omitted.update(excluded)
    if len(references) != 3507 or len({r['id'] for r in references}) != 3507 or Counter(r['split'] for r in references) != {'train': 3118, 'dev': 389}:
        raise ValueError('Frozen reference membership/count changed')
    return references, omitted


def prepare(source_root, output, container_root, inventory, references, omitted):
    prefix = PurePosixPath(container_root)
    if not prefix.is_absolute() or '..' in prefix.parts or str(prefix) == '/' or str(prefix) != container_root.rstrip('/'):
        raise ValueError('Canonical absolute container root required')
    if source_root.resolve() == output.resolve():
        raise ValueError('Prepared output must be separate from original source')
    frozen_bytes(output / 'LICENSE.md', (source_root / 'LICENSE.md').read_bytes())
    sources = {s['source_id']: s for s in inventory['sources']}
    grouped = {}
    for row in references:
        grouped.setdefault(row['conversation_id'] + '_' + row['speaker'], []).append(row)
    results = []
    for name, rows in grouped.items():
        source = sources[name]
        with wave.open(str(source_root / 'audio' / (name + '.wav')), 'rb') as audio:
            pcm = audio.readframes(audio.getnframes())
        if len(pcm) != source['audio_samples'] * 2:
            raise ValueError('Truncated original PCM payload')
        for row in rows:
            raw = clip_bytes(pcm, row)
            target = output / 'audio' / (row['id'] + '.wav')
            frozen_bytes(target, raw)
            results.append({**row, 'audio_filepath': str(prefix / 'audio' / target.name),
                'audio_sha256': hashlib.sha256(raw).hexdigest(), 'audio_bytes': len(raw),
                'source_audio_sha256': source['audio_sha256'], 'source_audio_samples': source['audio_samples'],
                'source_audio_url': MEDIA + 'audio/' + name + '.wav', 'training_corpus': 'primock57',
                'adaptation': 'Exact mono16k PCM slice at rounded original human TextGrid sample bounds; no ASR/text repair'})
    manifests = {}
    for split in ['train', 'dev']:
        selected = [row for row in results if row['split'] == split]
        raw = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in selected).encode()
        frozen_bytes(output / (split + '.jsonl'), raw)
        manifests[split] = {'path': split + '.jsonl', 'sha256': hashlib.sha256(raw).hexdigest(),
            'rows': len(selected), 'seconds': sum(row['duration'] for row in selected),
            'conversations': len({row['conversation_id'] for row in selected})}
    provenance = {'status': 'PREPARED_NOT_QUALIFIED', 'source': inventory['repository'], 'revision': REVISION,
        'license': inventory['license'], 'attribution': inventory['attribution'],
        'license_sha256': inventory['license_sha256'], 'public_source_inventory_sha256': INVENTORY_SHA,
        'script_sha256': file_hash(Path(__file__)), 'split': split_membership(), 'split_seed_label': SEED,
        'known_case_exclusions': list(KNOWN_SAMPLE), 'reserved_external_exclusions': list(RESERVED_EXTERNAL),
        'manifests': manifests, 'excluded_intervals': dict(omitted),
        'changes': 'Speaker-channel clean human intervals0.5–30s; exact rounded PCM slices; no text repair/resampling.',
        'speaker_disjointness': 'NOT_ESTABLISHED', 'pretraining_exclusion': 'NOT_ESTABLISHED',
        'evaluation_blindness': 'NOT_CLAIMED', 'clinical_validation': 'NOT_PERFORMED',
        'mixed_channel_diarization': 'NOT_QUALIFIED', 'predictions_used': False, 'cloud_upload_performed': False}
    frozen_bytes(output / 'provenance.json', (json.dumps(provenance, indent=2) + '\n').encode())
    return provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, help='Default OUTPUT_ROOT/source; audio/, transcripts/, LICENSE.md layout')
    parser.add_argument('--container-root', default='/data/clinical-speech/primock-adaptation')
    parser.add_argument('--download', action='store_true', help='Explicit public HTTPS download; omitted means offline only')
    parser.add_argument('--verify-only', action='store_true', help='Validate original inputs/reference membership; do not create clips')
    args = parser.parse_args()
    inventory = load_inventory()
    source = args.source_root or args.output_root / 'source'
    references, excluded = verify_inputs(source, inventory, allow_download=args.download)
    if args.verify_only:
        print(json.dumps({'status': 'SOURCE_AND_REFERENCE_VALIDATED_ONLY', 'rows': len(references),
            'split': split_membership(), 'network_authorized': args.download, 'clips_created': False}))
        return
    print(json.dumps(prepare(source, args.output_root, args.container_root, inventory, references, excluded), indent=2))


if __name__ == '__main__':
    main()
