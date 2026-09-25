"""Opt-in renewable corpus sampling, with duration targets rather than promises.

NeMo's weighted input_cfg mux samples CUTS. Inverse-mean-duration calibration
targets PCM-duration shares in expectation; actual completed-batch shares must
still be audited. This module does not alter audio, references or any default.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

from .common import sha256_file, write_json


def parse_fractions(value, *, model_family, resume_pointer=None):
    if value is None:
        return None
    if model_family != 'english_specialist' or resume_pointer:
        raise ValueError('renewable_sampling_requires_fresh_english_family')
    fractions = json.loads(value)
    if not isinstance(fractions, dict) or len(fractions) < 2:
        raise ValueError('at_least_two_explicit_corpus_targets_required')
    if any(not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', key) for key in fractions):
        raise ValueError('safe_corpus_names_required')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           or not 0 < value < 1 for value in fractions.values()) or not math.isclose(sum(fractions.values()), 1, abs_tol=1e-9):
        raise ValueError('positive_finite_duration_fractions_must_sum_to_one')
    return fractions


def calibrate(rows, fractions):
    if not rows or not fractions:
        raise ValueError('nonempty_training_rows_and_corpus_targets_required')
    if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', key) for key in fractions):
        raise ValueError('safe_corpus_names_required')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           or not 0 < value < 1 for value in fractions.values()) or not math.isclose(sum(fractions.values()), 1, abs_tol=1e-9):
        raise ValueError('positive_finite_duration_fractions_must_sum_to_one')
    groups, seen = defaultdict(list), set()
    for row in rows:
        if row.get('split') != 'train' or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in seen:
            raise ValueError('unique_explicit_train_rows_required')
        seconds = row.get('duration')
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0.5 <= seconds <= 30:
            raise ValueError('same_eligible_training_duration_range_required')
        if not row.get('text', '').strip() or row.get('target_lang') != 'en-US':
            raise ValueError('paired_english_reference_required')
        if not re.fullmatch(r'[0-9a-f]{64}', row.get('audio_sha256', '')):
            raise ValueError('exact_training_audio_hash_required')
        seen.add(row['id'])
        groups[row.get('training_corpus')].append(row)
    if set(groups) != set(fractions):
        raise ValueError('every_and_only_present_corpus_requires_explicit_fraction')
    means = {key: sum(x['duration'] for x in group) / len(group) for key, group in groups.items()}
    rates = {key: fractions[key] / means[key] for key in groups}
    normalizer = sum(rates.values())
    return groups, {key: {'rows': len(groups[key]), 'unique_audio_seconds': sum(x['duration'] for x in groups[key]),
        'mean_duration_seconds': means[key], 'target_audio_fraction': fractions[key],
        'cut_selection_probability': rates[key] / normalizer} for key in sorted(groups)}


def prepare_inputs(rows, fractions, output, *, seed):
    groups, statistics = calibrate(rows, fractions)
    if type(seed) is not int or seed < 0:
        raise ValueError('explicit_nonnegative_integer_seed_required')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    inputs, manifests = [], []
    for corpus in sorted(groups):
        # Shuffle the finite cycle without duplicating/changing any reference;
        # native mux.repeat(preserve_id=True) performs renewable draws later.
        ordered = sorted(groups[corpus], key=lambda row: hashlib.sha256(f'{seed}\0{row["id"]}'.encode()).hexdigest())
        path = output / (corpus + '.jsonl')
        with path.open('x') as stream:
            for row in ordered:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        inputs.append({'type': 'nemo', 'manifest_filepath': str(path),
            'weight': statistics[corpus]['cut_selection_probability'], 'tags': {'training_corpus': corpus}})
        manifests.append({'corpus': corpus, 'path': str(path), 'sha256': sha256_file(path), **statistics[corpus]})
    config = {'input_cfg': inputs, 'manifest_filepath': None,
        'force_finite': False, 'metadata_only': False, 'max_open_streams': None,
        'reweight_temperature': 1.0, 'seed': seed, 'shard_seed': seed,
        'concurrent_bucketing': False, 'fault_tolerant_audio_loading': False,
        'use_bucketing': True,
        'bucket_buffer_size': 200, 'shuffle_buffer_size': 200,
        'num_cuts_for_bins_estimate': 1000}
    receipt = {'schema': 'clinical-speech/renewable-duration-calibration/v1', 'seed': seed,
        'manifests': manifests, 'config_override': config,
        'method': 'Native NeMo input_cfg mux; each finite corpus repeated with original IDs; cut probability proportional to target_PCM_fraction/mean_clip_duration',
        'audio_and_reference_fields_changed': False, 'sampling_probability_is_duration_guarantee': False,
        'pinned_lhotse_effective_bucket_buffer_cuts': 400,
        'buffer_note': 'Pinned Lhotse adds deprecated shuffle_buffer_size to bucket_buffer_size; small inventory limits measured finite-prefix backlog. No vendor patch.',
        'actual_completed_batch_exposure_required': True, 'resume_qualification': 'NOT_CLAIMED'}
    write_json(output / 'calibration.json', receipt)
    return config, receipt
