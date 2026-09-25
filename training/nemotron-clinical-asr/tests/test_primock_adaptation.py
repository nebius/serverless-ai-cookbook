import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import wave

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'data'))
import prepare_primock_adaptation as prep


def grid(values):
    return 'class = "IntervalTier"\nintervals: size = ' + str(len(values)) + '\n' + ''.join(
        f'intervals [{i}]:\nxmin = {start}\nxmax = {end}\ntext = "{text}"\n'
        for i, (start, end, text) in enumerate(values, 1))


def source():
    return {'conversation_id': 'day1_consultation03', 'speaker': 'doctor',
            'audio_samples': 64000, 'textgrid_sha256': 'a' * 64}


def test_exact_public_source_inventory_and_known_exclusions():
    inventory = prep.load_inventory()
    split = prep.split_membership()
    assert len(split['train']) == 40 and len(split['dev']) == 5 and len(split['excluded']) == 12
    assert split['dev'] == ['day1_consultation04', 'day2_consultation01', 'day3_consultation03',
                           'day4_consultation01', 'day5_consultation07']
    assert not set(split['train']) & set(split['dev'])
    assert not (set(split['train']) | set(split['dev'])) & set(split['excluded'])
    assert set(split['excluded']) == set(prep.KNOWN_SAMPLE) | set(prep.RESERVED_EXTERNAL)
    assert {s['conversation_id'] for s in inventory['sources']} == set(split['train']) | set(split['dev'])
    assert len(list(prep.input_files(inventory))) == 181
    assert all(prep.REVISION in url for _, url, _, _ in prep.input_files(inventory))


def test_reference_case_dose_negation_quotes_and_coordinates_preserved():
    text = 'She said ""NOT 2.5 mg""; Sertraline remains UNKNOWN.'
    rows, omitted = prep.reference_rows(source(), grid([(0, .5, text), (.5, 1, '')]))
    assert not omitted.get('duration') and omitted['empty'] == 1
    assert rows[0]['text'] == 'She said "NOT 2.5 mg"; Sertraline remains UNKNOWN.'
    assert rows[0]['id'] == 'primock_adapt_day1_consultation03_doctor_001'
    assert rows[0]['source_start_sample'] == 0 and rows[0]['source_end_sample_exclusive'] == 8000
    assert rows[0]['duration'] == .5 and rows[0]['source_interval_index_one_based'] == 1


@pytest.mark.parametrize('conversation', list(prep.KNOWN_SAMPLE) + list(prep.RESERVED_EXTERNAL) + ['unknown'])
def test_known_or_foreign_conversation_never_admitted(conversation):
    value = source()
    value['conversation_id'] = conversation
    with pytest.raises(ValueError, match='cannot enter'):
        prep.reference_rows(value, grid([(0, 1, 'Do not invent a dose.')]))


def test_sample_rounded_bounds_and_duration_exclusions_match_frozen_rule():
    rows, omitted = prep.reference_rows(source(), grid([(0, .49999, 'eligible after rounding'),
        (.49999, .6, 'too short'), (.6, 1.2, '<unintelligible>'), (1.2, 1.8, '')]))
    assert len(rows) == 1 and rows[0]['duration'] == .5
    assert omitted == {'duration': 1, 'markup': 1, 'empty': 1}


@pytest.mark.parametrize('text', [
    grid([(0, 1, 'a')]).replace('size = 1', 'size = 2'),
    grid([(0, 1, 'a')]).replace('[1]', '[2]'),
    grid([(0, 1, 'a'), (.5, 1.5, 'overlap')]),
    grid([(0, 1, 'a')]) + 'class = "IntervalTier"',
    grid([(0, 1, 'a')]).replace('xmax = 1', 'xmax = nan'),
])
def test_malformed_or_multiple_tier_reference_rejected(text):
    with pytest.raises(ValueError):
        prep.textgrid_intervals(text)


def test_out_of_audio_bounds_is_error_not_silent_clipping():
    with pytest.raises(ValueError, match='exceeds original'):
        prep.reference_rows(source(), grid([(3.5, 4.5, 'missing recording tail')]))


def test_exact_pcm_and_header_without_resampling():
    pcm = bytes(range(256)) * 100
    row = {'source_start_sample': 2000, 'source_end_sample_exclusive': 10000, 'duration': .5}
    raw = prep.clip_bytes(pcm, row)
    with wave.open(io.BytesIO(raw), 'rb') as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getnframes()) == (1, 2, 16000, 8000)
        assert audio.readframes(8000) == pcm[4000:20000]


@pytest.mark.parametrize('delta', [{'source_start_sample': True}, {'source_start_sample': -1},
    {'source_start_sample': 0.5}, {'source_end_sample_exclusive': 20000}, {'duration': .6}])
def test_bad_pcm_geometry_rejected(delta):
    row = {'source_start_sample': 0, 'source_end_sample_exclusive': 8000, 'duration': .5, **delta}
    with pytest.raises(ValueError):
        prep.clip_bytes(bytes(16000), row)


def test_create_only_mismatch_and_symlink_rejected(tmp_path):
    path = tmp_path / 'same.wav'
    prep.frozen_bytes(path, b'original')
    prep.frozen_bytes(path, b'original')
    with pytest.raises(ValueError):
        prep.frozen_bytes(path, b'changed')
    link = tmp_path / 'link.wav'
    link.symlink_to(path)
    with pytest.raises(ValueError):
        prep.frozen_bytes(link, b'original')
    assert path.read_bytes() == b'original'


def test_offline_missing_source_does_not_call_downloader(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected network call')
    monkeypatch.setattr(prep, 'download', forbidden)
    with pytest.raises(ValueError, match='missing or mismatched'):
        prep.verify_inputs(tmp_path, prep.load_inventory())


def test_download_is_explicit_and_only_frozen_public_urls(tmp_path, monkeypatch):
    calls = []
    def recorded(url, path, checksum):
        calls.append((url, checksum))
        raise RuntimeError('stop before network')
    monkeypatch.setattr(prep, 'download', recorded)
    with pytest.raises(RuntimeError, match='stop before'):
        prep.verify_inputs(tmp_path, prep.load_inventory(), allow_download=True)
    assert calls == [(prep.RAW + 'LICENSE.md', prep.load_inventory()['license_sha256'])]


def test_invalid_container_root_before_output_creation(tmp_path):
    for value in ['relative', '/', '/data/../other', '/data//bad']:
        with pytest.raises(ValueError, match='container root'):
            prep.prepare(tmp_path / 'input', tmp_path / 'out', value, prep.load_inventory(), [], {})
    assert not (tmp_path / 'out').exists()
