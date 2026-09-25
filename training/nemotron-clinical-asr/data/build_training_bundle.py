#!/usr/bin/env python3
"""Build, never upload, an immutable cloud-train bundle from approved manifests.

No alignment, transcript normalization, split assignment or hidden exclusions.
The caller supplies existing train/dev splits and local mono16k PCM16 WAVs.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import tarfile
import wave

CONTAINER_ROOT = Path('/data/clinical-speech/round2-bundle')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def safe_key(value):
    if not value or value.startswith('/') or '\\' in value or any(p in ('', '.', '..') for p in value.rstrip('/').split('/')):
        raise ValueError('relative_object_key_required')
    return value.rstrip('/')


def parse_corpora(values):
    result = {}
    for value in values:
        name, separator, path = value.partition('=')
        if not separator or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name) or name in result:
            raise ValueError('unique_safe_corpus_equals_manifest_required')
        result[name] = Path(path).resolve()
    return result


def inspect_rows(corpora, split, audio_root, container_source_root):
    rows, sources = [], {}
    for corpus, manifest in sorted(corpora.items()):
        values = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
        if not values:
            raise ValueError('empty_corpus_manifest')
        for original in values:
            row = dict(original)
            if row.get('split') != split or not isinstance(row.get('id'), str) or not row['id']:
                raise ValueError('explicit_original_split_and_id_required')
            if not isinstance(row.get('conversation_id'), str) or not row['conversation_id']:
                raise ValueError('original_conversation_id_required')
            if split == 'train' and row.get('training_allowed') is False:
                raise ValueError('source_explicitly_disallows_training')
            if row.get('training_corpus', corpus) != corpus:
                raise ValueError('cannot_relabel_existing_corpus')
            if not isinstance(row.get('text'), str) or not row['text'].strip() or row.get('target_lang', 'en-US') != 'en-US':
                raise ValueError('nonempty_english_reference_required')
            duration = row.get('duration')
            if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or not .5 <= duration <= 30:
                raise ValueError('approved_0point5_to30second_clips_required_no_silent_filter')
            relative = Path(row['audio_filepath']).relative_to(container_source_root)
            source = (audio_root / relative).resolve()
            if not source.is_relative_to(audio_root) or not source.is_file():
                raise ValueError('audio_outside_approved_root_or_missing')
            with wave.open(str(source), 'rb') as stream:
                if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth(), stream.getcomptype()) != (16000, 1, 2, 'NONE'):
                    raise ValueError('original_mono16k_PCM16_required')
                frames = stream.getnframes()
                pcm = stream.readframes(frames)
                if len(pcm) != frames * 2:
                    raise ValueError('truncated_audio')
                pcm_checksum = hashlib.sha256(pcm).hexdigest()
            seconds = frames / 16000
            if not .5 <= seconds <= 30 or abs(seconds - duration) > 1 / 16000 + 1e-9:
                raise ValueError('reference_duration_does_not_match_exact_PCM')
            checksum, size = digest(source), source.stat().st_size
            if row.get('audio_sha256', checksum) != checksum or row.get('audio_bytes', size) != size:
                raise ValueError('approved_audio_hash_or_size_changed')
            if row.get('audio_pcm_sha256', pcm_checksum) != pcm_checksum:
                raise ValueError('approved_PCM_hash_changed')
            is_replay = row['conversation_id'].startswith('librispeech-train-clean100:')
            if is_replay != (corpus == 'librispeech_replay') or (split == 'dev' and is_replay):
                raise ValueError('replay_domain_must_match_original_LibriSpeech_training_provenance')
            member = 'audio/' + corpus + '/' + hashlib.sha256(row['id'].encode()).hexdigest() + '.wav'
            if member in sources:
                raise ValueError('duplicate_immutable_id')
            sources[member] = source
            row.update(audio_filepath=str(CONTAINER_ROOT / member), audio_sha256=checksum,
                       audio_pcm_sha256=pcm_checksum, audio_bytes=size, training_corpus=corpus, target_lang='en-US')
            rows.append(row)
    return rows, sources


def validate_splits(train, dev):
    ids = [r['id'] for r in train + dev]
    if len(set(ids)) != len(ids):
        raise ValueError('globally_unique_train_dev_ids_required')
    if {r['conversation_id'] for r in train} & {r['conversation_id'] for r in dev}:
        raise ValueError('conversation_leakage_between_train_and_dev')
    if {r['audio_sha256'] for r in train} & {r['audio_sha256'] for r in dev}:
        raise ValueError('identical_audio_leakage_between_train_and_dev')
    if {r['audio_pcm_sha256'] for r in train} & {r['audio_pcm_sha256'] for r in dev}:
        raise ValueError('identical_PCM_leakage_between_train_and_dev')


def build(train_corpora, dev_corpora, *, audio_root, container_source_root, output, key_prefix, seed):
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('explicit_unsigned32_seed_required')
    if 'librispeech_replay' not in train_corpora or len(train_corpora) < 2:
        raise ValueError('mixed_bundle_requires_clinical_corpus_and_LibriSpeech_replay')
    if not dev_corpora or not set(dev_corpora) <= set(train_corpora):
        raise ValueError('explicit_development_corpora_required')
    key_prefix = safe_key(key_prefix)
    audio_root = Path(audio_root).resolve()
    source_hashes = {split: {name: {'sha256': digest(path)} for name, path in value.items()}
        for split, value in [('train', train_corpora), ('dev', dev_corpora)]}
    train, train_sources = inspect_rows(train_corpora, 'train', audio_root, Path(container_source_root))
    dev, dev_sources = inspect_rows(dev_corpora, 'dev', audio_root, Path(container_source_root))
    validate_splits(train, dev)
    order = lambda row: hashlib.sha256(f'{seed}\0{row["id"]}'.encode()).hexdigest()
    train, dev = sorted(train, key=order), sorted(dev, key=order)
    manifests = {'mixed': train, 'clinical-only': [r for r in train if r['training_corpus'] != 'librispeech_replay'], 'dev': dev}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    objects = {}
    for label, values in manifests.items():
        path = output / (label + '.jsonl')
        with path.open('x') as stream:
            for row in values:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        objects[label] = {'key': key_prefix + '/' + path.name, 'sha256': digest(path),
                          'bytes': path.stat().st_size, 'rows': len(values), 'audio_seconds': sum(r['duration'] for r in values)}
    all_rows = {str(Path(row['audio_filepath']).relative_to(CONTAINER_ROOT)): row for row in train + dev}
    sources = {**train_sources, **dev_sources}
    archive = output / 'audio.tar'
    with tarfile.open(archive, 'x', format=tarfile.PAX_FORMAT) as stream:
        for member, source in sorted(sources.items()):
            row = all_rows[member]
            info = tarfile.TarInfo(member)
            info.size, info.mode, info.mtime = row['audio_bytes'], 0o644, 0
            with source.open('rb') as data:
                stream.addfile(info, data)
    # Full readback catches source mutation during archive construction, not just
    # manifest membership. No large data or model file is shipped in the repo.
    seen = set()
    with tarfile.open(archive, 'r|') as stream:
        for member in stream:
            if member.name in seen or member.name not in all_rows or not member.isfile():
                raise ValueError('archive_membership_mismatch')
            seen.add(member.name)
            h = hashlib.sha256()
            with stream.extractfile(member) as data:
                for part in iter(lambda: data.read(8 * 1024 * 1024), b''):
                    h.update(part)
            if member.size != all_rows[member.name]['audio_bytes'] or h.hexdigest() != all_rows[member.name]['audio_sha256']:
                raise ValueError('archive_full_readback_mismatch')
    if seen != set(sources):
        raise ValueError('archive_incomplete')
    if any(digest(path) != source_hashes[split][name]['sha256'] for split, value in
           [('train', train_corpora), ('dev', dev_corpora)] for name, path in value.items()):
        raise ValueError('source_manifest_changed_during_preparation')
    bundle = {'schema': 'clinical-speech/prealigned-training-bundle/v1', 'seed': seed,
        'archive': {'key': key_prefix + '/audio.tar', 'sha256': digest(archive), 'bytes': archive.stat().st_size, 'members': len(seen)},
        'manifests': objects, 'source_manifests': source_hashes,
        'component_train_hours': {name: sum(r['duration'] for r in train if r['training_corpus'] == name) / 3600 for name in train_corpora},
        'component_dev_rows': dict(Counter(r['training_corpus'] for r in dev)),
        'archive_full_readback_verified': True, 'waveform_and_reference_text_changes': False,
        'changes': 'Added verified size/hash/corpus metadata and rebased audio paths; SHA256(seed NUL originalID) order; original splits/text/audio retained.',
        'clinical_validation': 'NOT_PERFORMED', 'speaker_disjointness': 'NOT_ESTABLISHED', 'pretraining_overlap': 'UNKNOWN',
        'reproduction_scope': 'New approved-input experiment, not automatic reproduction of a historical benchmark or checkpoint'}
    with (output / 'bundle.json').open('x') as stream:
        json.dump(bundle, stream, indent=2, ensure_ascii=False)
    return bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-corpus', action='append', required=True, help='NAME=original-training-manifest.jsonl; repeat')
    parser.add_argument('--dev-corpus', action='append', required=True, help='NAME=original-development-manifest.jsonl; repeat')
    parser.add_argument('--audio-root', type=Path, required=True)
    parser.add_argument('--container-source-root', default='/data/clinical-speech')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--key-prefix', required=True, help='Fresh user-owned object-storage prefix; no bucket or upload is inferred')
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    bundle = build(parse_corpora(args.train_corpus), parse_corpora(args.dev_corpus), audio_root=args.audio_root,
        container_source_root=args.container_source_root, output=args.output, key_prefix=args.key_prefix, seed=args.seed)
    print(json.dumps({'bundle': str(args.output / 'bundle.json'), 'bundle_sha256': digest(args.output / 'bundle.json'),
        'waveforms_verified': bundle['archive']['members'], 'uploaded': False}))


if __name__ == '__main__':
    main()
