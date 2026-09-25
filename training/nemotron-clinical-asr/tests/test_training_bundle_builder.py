import importlib.util
import json
from pathlib import Path
import struct
import tarfile
import wave

import pytest


SPEC = importlib.util.spec_from_file_location('public_bundle_builder', Path(__file__).parents[1] / 'data/build_training_bundle.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def fixture(tmp_path):
    audio = tmp_path / 'data'
    audio.mkdir()
    rows = []
    for index, (corpus, split) in enumerate([
        ('simulated_clinical', 'train'), ('primock57', 'train'), ('librispeech_replay', 'train'),
        ('simulated_clinical', 'dev'), ('primock57', 'dev'),
    ]):
        path = audio / f'{index}.wav'
        with wave.open(str(path), 'wb') as stream:
            stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            stream.writeframes(struct.pack('<h', index + 1) * 16000)
        rows.append(dict(id=f'id-{index}', conversation_id=(
            'librispeech-train-clean100:1:2' if corpus == 'librispeech_replay' else f'conversation-{index}'),
            split=split, text=f'Original Text {index}, retained!', source_text=f'Original Text {index}, retained!',
            duration=1.0, audio_filepath=f'/data/clinical-speech/{index}.wav', training_corpus=corpus,
            audio_sha256=builder.digest(path), audio_bytes=path.stat().st_size, target_lang='en-US'))
    def save():
        train, dev = {}, {}
        for row in rows:
            path = tmp_path / f'{row["training_corpus"]}-{row["split"]}.jsonl'
            path.write_text(json.dumps(row) + '\n')
            (train if row['split'] == 'train' else dev)[row['training_corpus']] = path
        return train, dev
    return audio, rows, save


def run(tmp_path, audio, corpora, output='bundle', **kwargs):
    return builder.build(*corpora, audio_root=audio, container_source_root='/data/clinical-speech',
        output=tmp_path / output, key_prefix='approved/experiment-v1', seed=123, **kwargs)


def test_bundle_exact_members_fields_and_runtime_extraction(tmp_path):
    from clinical_asr.cloud_train import extract_verified_archive
    audio, original, save = fixture(tmp_path)
    result = run(tmp_path, audio, save())
    assert result['archive']['members'] == 5
    assert result['manifests']['mixed']['rows'] == 3
    assert result['manifests']['clinical-only']['rows'] == 2
    emitted = [json.loads(line) for label in ('mixed', 'dev')
               for line in (tmp_path / 'bundle' / f'{label}.jsonl').read_text().splitlines()]
    by_id = {r['id']: r for r in emitted}
    expected = {}
    for row in original:
        derived = by_id[row['id']]
        for key in row.keys() - {'audio_filepath'}:
            assert derived[key] == row[key]
        member = str(Path(derived['audio_filepath']).relative_to(builder.CONTAINER_ROOT))
        expected[member] = {'bytes': row['audio_bytes'], 'sha256': row['audio_sha256']}
    assert extract_verified_archive(tmp_path / 'bundle/audio.tar', tmp_path / 'extracted', expected) == 5
    assert all(builder.digest(tmp_path / 'extracted' / member) == item['sha256'] for member, item in expected.items())
    assert result['waveform_and_reference_text_changes'] is False


def test_deterministic_archive_and_manifests_and_create_only(tmp_path):
    audio, _, save = fixture(tmp_path)
    first = run(tmp_path, audio, save())
    second = run(tmp_path, audio, save(), output='repeat')
    assert first == second
    for name in ('bundle.json', 'audio.tar', 'mixed.jsonl', 'clinical-only.jsonl', 'dev.jsonl'):
        assert builder.digest(tmp_path / 'bundle' / name) == builder.digest(tmp_path / 'repeat' / name)
    with pytest.raises(FileExistsError):
        run(tmp_path, audio, save())


@pytest.mark.parametrize('field,value,error', [
    ('duration', float('nan'), 'approved_'), ('duration', 1.01, 'reference_duration'),
    ('training_allowed', False, 'disallows_training'), ('audio_sha256', '0' * 64, 'audio_hash'),
    ('text', '', 'reference_required'), ('target_lang', 'de-DE', 'reference_required'),
    ('conversation_id', 'librispeech-train-clean100:fake', 'replay_domain'),
])
def test_reject_invalid_train_without_creating_output(tmp_path, field, value, error):
    audio, rows, save = fixture(tmp_path)
    rows[0][field] = value
    with pytest.raises(ValueError, match=error):
        run(tmp_path, audio, save())
    assert not (tmp_path / 'bundle').exists()


@pytest.mark.parametrize('kind', ['conversation', 'audio', 'id'])
def test_reject_train_dev_leakage(tmp_path, kind):
    audio, rows, save = fixture(tmp_path)
    if kind == 'conversation':
        rows[3]['conversation_id'] = rows[0]['conversation_id']
    elif kind == 'id':
        rows[3]['id'] = rows[0]['id']
    else:
        rows[3].update({key: rows[0][key] for key in ('audio_filepath', 'audio_sha256', 'audio_bytes')})
    with pytest.raises(ValueError, match='leakage|unique'):
        run(tmp_path, audio, save())


def test_reject_traversal_and_symlink_audio(tmp_path):
    audio, rows, save = fixture(tmp_path)
    outside = tmp_path / 'outside.wav'
    outside.write_bytes((audio / '0.wav').read_bytes())
    (audio / 'link.wav').symlink_to(outside)
    rows[0]['audio_filepath'] = '/data/clinical-speech/link.wav'
    with pytest.raises(ValueError, match='outside_approved_root'):
        run(tmp_path, audio, save())


def test_reject_same_pcm_with_different_wav_container(tmp_path):
    audio, rows, save = fixture(tmp_path)
    raw = (audio / '0.wav').read_bytes()
    # A harmless extra RIFF chunk changes the file SHA but not decoded PCM.
    raw = raw[:4] + struct.pack('<I', len(raw) - 8 + 12) + raw[8:] + b'JUNK' + struct.pack('<I', 4) + b'test'
    (audio / '3.wav').write_bytes(raw)
    rows[3]['audio_sha256'] = builder.digest(audio / '3.wav')
    rows[3]['audio_bytes'] = len(raw)
    assert rows[3]['audio_sha256'] != rows[0]['audio_sha256']
    with pytest.raises(ValueError, match='identical_PCM_leakage'):
        run(tmp_path, audio, save())


@pytest.mark.parametrize('value', ['', '/', '../x', 'x/../y', 'x/./y', 'x//y', 'x\\y'])
def test_reject_unsafe_prefix(value):
    with pytest.raises(ValueError):
        builder.safe_key(value)


def test_parse_duplicate_corpus_and_explicit_split(tmp_path):
    with pytest.raises(ValueError):
        builder.parse_corpora(['one=x', 'one=y'])
    audio, rows, save = fixture(tmp_path)
    corpora = save()
    rows[0]['split'] = 'test'
    corpora[0]['simulated_clinical'].write_text(json.dumps(rows[0]) + '\n')
    with pytest.raises(ValueError, match='explicit_original_split'):
        run(tmp_path, audio, corpora)
