from copy import deepcopy
from types import SimpleNamespace
import hashlib
import json
import os
import subprocess
import sys

import pytest

from clinical_asr.initialization import checked_path, validate_options, validate_signatures, check_baseline_result


def test_default_upstream_unchanged():
    assert validate_options(None, None, model_family='nemotron35') is False
    assert validate_options(None, None, model_family='english_specialist') is False
    assert validate_options('/p.nemo', 'a'*64, model_family='english_specialist') is True


@pytest.mark.parametrize('path,digest,family,resume', [
    ('/p.nemo', None, 'english_specialist', None),
    (None, 'a'*64, 'english_specialist', None),
    ('', 'a'*64, 'english_specialist', None),
    ('/p.nemo', 'not-a-sha', 'english_specialist', None),
    ('/p.nemo', 'g'*64, 'english_specialist', None),
    ('/p.nemo', 'a'*64, 'nemotron35', None),
    ('/p.nemo', 'a'*64, 'english_specialist', 'some-resume'),
])
def test_invalid_initialization_fails(path, digest, family, resume):
    with pytest.raises(ValueError):
        validate_options(path, digest, model_family=family, resume_pointer=resume)


def test_exact_parent_bytes(tmp_path):
    path = tmp_path/'parent.nemo'
    path.write_bytes(b'unit-test-not-actual-model')
    assert checked_path(str(path), hashlib.sha256(path.read_bytes()).hexdigest()) == path
    with pytest.raises(ValueError, match='sha256'):
        checked_path(str(path), 'a'*64)


def signature():
    return {'model_class': 'EncDecRNNTBPEModel', 'tokenizer_sha256': 'a'*64,
            'architecture_sha256': 'b'*64,
            'state_schema': {'encoder.weight': {'shape': [3, 4], 'dtype': 'torch.float32'}}}


@pytest.mark.parametrize('key', ['model_class', 'tokenizer_sha256', 'architecture_sha256', 'state_schema'])
def test_model_identity_changes_fail(key):
    first = signature()
    assert validate_signatures(first, deepcopy(first)) is None
    second = deepcopy(first)
    second[key] = {'other': 'shape'} if key == 'state_schema' else 'different'
    with pytest.raises(ValueError, match=key):
        validate_signatures(first, second)
    del second[key]
    with pytest.raises(ValueError, match=key):
        validate_signatures(first, second)


@pytest.mark.skipif(os.getenv('RUN_NATIVE_NEMO_TESTS') != '1', reason='actual torch/OmegaConf image needed')
def test_restore_checks_actual_tensor_and_tokenizer_before_return(tmp_path):
    import torch
    from omegaconf import OmegaConf
    from clinical_asr.initialization import restore_parent

    class EncDecRNNTBPEModel:
        def __init__(self, token=b'actual-unit-test-tokenizer', weight=2.0):
            self.tokenizer = SimpleNamespace(tokenizer=SimpleNamespace(serialized_model_proto=lambda: token))
            self.cfg = OmegaConf.create(dict.fromkeys(['preprocessor', 'encoder', 'decoder', 'joint', 'decoding'], {'context': 70}))
            self.weight = torch.tensor([weight], dtype=torch.float32)
        def state_dict(self):
            return {'encoder.weight': self.weight}
    path = tmp_path/'parent.nemo'
    path.write_bytes(b'unit-test-model-only')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    calls = []
    parent = EncDecRNNTBPEModel(weight=3.0)
    def restore(file, *, map_location):
        calls.append((file, map_location))
        return parent
    model, receipt = restore_parent(EncDecRNNTBPEModel(), str(path), digest,
                                    model_family='english_specialist', restore=restore)
    assert model is parent and calls == [(str(path), 'cpu')]
    assert receipt['optimizer_restored'] is False and receipt['step_counter_restored'] is False
    assert receipt['mode'] == 'parent_weights_fresh_optimizer'
    assert receipt['parent_exposure_in_current_ledger'] is False
    parent.tokenizer.tokenizer.serialized_model_proto = lambda: b'changed'
    with pytest.raises(ValueError, match='tokenizer'):
        restore_parent(EncDecRNNTBPEModel(), str(path), digest,
                       model_family='english_specialist', restore=restore)
    parent = EncDecRNNTBPEModel(weight=float('nan'))
    with pytest.raises(ValueError, match='nonfinite'):
        restore_parent(EncDecRNNTBPEModel(), str(path), digest,
                       model_family='english_specialist', restore=restore)


@pytest.mark.parametrize('command,location', [('train', '--initial-checkpoint'), ('cloud-train', '--initial-checkpoint-key')])
def test_real_cli_advertises_explicit_parent_and_fourth_corpus(command, location):
    result = subprocess.run([sys.executable, '-m', 'clinical_asr', command, '--help'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert location in result.stdout and '--initial-checkpoint-sha256' in result.stdout
    assert 'eka_medical_narration' in result.stdout


def test_four_source_calibration_does_not_change_any_reference(tmp_path):
    from clinical_asr.balanced import prepare_inputs
    fractions = {'simulated_clinical': .35, 'primock57': .30, 'eka_medical_narration': .05, 'librispeech_replay': .30}
    rows = [{'id': name, 'training_corpus': name, 'split': 'train', 'duration': seconds,
             'text': 'Unmodified fixture.', 'target_lang': 'en-US', 'audio_sha256': 'a'*64,
             'audio_filepath': '/no-audio-read/'+name+'.wav'}
            for name, seconds in zip(fractions, [3.77, 3.63, 3.88, 12.72])]
    cfg, receipt = prepare_inputs(rows, fractions, tmp_path/'calibration', seed=20260926)
    got = [json.loads(line) for item in receipt['manifests'] for line in open(item['path'])]
    assert sorted(got, key=lambda x:x['id']) == sorted(rows, key=lambda x:x['id'])
    means = {x['corpus']: x['mean_duration_seconds'] for x in receipt['manifests']}
    seconds = {x['tags']['training_corpus']: x['weight']*means[x['tags']['training_corpus']] for x in cfg['input_cfg']}
    assert {k: v/sum(seconds.values()) for k,v in seconds.items()} == pytest.approx(fractions)
    assert len(cfg['input_cfg']) == 4 and receipt['sampling_probability_is_duration_guarantee'] is False


def test_parent_full_dev_baseline_is_separate_and_finite():
    assert check_baseline_result([{'val_wer': .22}], examples=3770, batches=3770,
                                 expected_examples=3770, global_step=0) == .22


@pytest.mark.parametrize('change', ['nan', 'inf', 'negative', 'bool', 'missing', 'two_loaders', 'empty',
                                     'partial_examples', 'partial_batches', 'optimized', 'wrong_expected'])
def test_baseline_gaps_fail(change):
    results = [{'val_wer': .22}]
    kw = dict(examples=3770, batches=3770, expected_examples=3770, global_step=0)
    if change in ['nan', 'inf', 'negative', 'bool']:
        results[0]['val_wer'] = {'nan': float('nan'), 'inf': float('inf'), 'negative': -.1, 'bool': True}[change]
    if change == 'missing': results = [{}]
    if change == 'two_loaders': results *= 2
    if change == 'empty': results = []
    if change == 'partial_examples': kw['examples'] = 3769
    if change == 'partial_batches': kw['batches'] = 3769
    if change == 'optimized': kw['global_step'] = 1
    if change == 'wrong_expected': kw['expected_examples'] = 0
    with pytest.raises(ValueError):
        check_baseline_result(results, **kw)


@pytest.mark.skipif(os.getenv('RUN_NATIVE_NEMO_TESTS') != '1', reason='actual Lightning callback API, fake validation only')
@pytest.mark.parametrize('bad_metric', [False, True])
def test_separate_baseline_trainer_never_seeds_checkpoint_or_optimizer(monkeypatch, bad_metric):
    import lightning.pytorch as pl
    import torch
    from clinical_asr.initialization import validate_parent_development
    calls = []
    main_trainer = object()
    class Model:
        def set_trainer(self, trainer):
            calls.append(trainer)
    class ValidationOnly:
        global_step = 0
        def __init__(self, **kw):
            assert kw['enable_checkpointing'] is False and kw['logger'] is False
            assert kw['limit_val_batches'] == 1.0 and kw['num_sanity_val_steps'] == 0
            assert len(kw['callbacks']) == 1
            self.coverage = kw['callbacks'][0]
        def validate(self, model, *, verbose):
            batch = (None, torch.tensor([16000]), None, None)
            for index in range(4):
                self.coverage.on_validation_batch_end(self, model, None, batch, index)
            return [{'val_wer': float('nan') if bad_metric else .2}]
    monkeypatch.setattr(pl, 'Trainer', ValidationOnly)
    if bad_metric:
        with pytest.raises(ValueError, match='finite'):
            validate_parent_development(Model(), main_trainer=main_trainer, expected_examples=4, model_family='english_specialist')
    else:
        receipt = validate_parent_development(Model(), main_trainer=main_trainer, expected_examples=4, model_family='english_specialist')
        assert receipt['candidate_checkpoint_selection_affected'] is False
        assert receipt['examples'] == receipt['batches'] == 4 and receipt['optimizer_updates'] == 0
    assert isinstance(calls[0], ValidationOnly) and calls[-1] is main_trainer


@pytest.mark.skipif(os.getenv('RUN_NATIVE_NEMO_TESTS') != '1', reason='exact native NeMo sampler, CPU only')
def test_four_source_actual_native_sampler(tmp_path):
    from collections import Counter
    from itertools import islice
    import wave
    from omegaconf import OmegaConf
    from nemo.collections.common.data.lhotse.dataloader import get_lhotse_dataloader_from_config
    from clinical_asr.balanced import prepare_inputs
    fractions = {'simulated_clinical': .35, 'primock57': .30, 'eka_medical_narration': .05, 'librispeech_replay': .30}
    rows = []
    for corpus, mean in zip(fractions, [3.8, 3.6, 3.9, 12.7]):
        for j, factor in enumerate([.5, .75, 1, 1.25, 1.5]):
            seconds = mean*factor
            path = tmp_path/(corpus+str(j)+'.wav')
            with wave.open(str(path), 'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
                stream.writeframes(b'\0\0'*round(seconds*16000))
            rows.append({'id': corpus+str(j), 'training_corpus': corpus, 'split': 'train',
                         'duration': seconds, 'text': 'Synthetic sampler fixture only.',
                         'target_lang': 'en-US', 'audio_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'audio_filepath': str(path)})
    cfg, _ = prepare_inputs(rows, fractions, tmp_path/'native-four', seed=20260926)
    cfg.update(sample_rate=16000, use_lhotse=True, is_tarred=False, num_workers=0,
               pin_memory=False, text_field='text', lang_field='target_lang', shuffle=True,
               batch_size=16, batch_duration=120, num_buckets=10, min_duration=.5, max_duration=30)
    class MetadataOnly:
        def __getitem__(self, cuts):
            return cuts
    loader = get_lhotse_dataloader_from_config(OmegaConf.create(cfg), 0, 1, MetadataOnly())
    totals, window = Counter(), Counter()
    windows, maxcuts, padded = [], 0, 0
    for step, batch in enumerate(islice(loader, 1000), 1):
        cuts = list(batch)
        maxcuts = max(maxcuts, len(cuts))
        padded = max(padded, len(cuts)*max(c.duration for c in cuts))
        for cut in cuts:
            totals[cut.training_corpus] += cut.duration
            window[cut.training_corpus] += cut.duration
        if step % 50 == 0:
            windows.append(dict(window)); window.clear()
    observed = {k: v/sum(totals.values()) for k,v in totals.items()}
    print('FOUR_SOURCE_NATIVE_CPU', json.dumps({'observed_fractions': observed, 'windows50': windows,
          'max_cuts': maxcuts, 'max_padded_seconds': padded, 'audio_fixture': 'synthetic silence, no model'}))
    assert len(windows) == 20 and all(set(x) == set(fractions) and min(x.values()) > 0 for x in windows)
    assert maxcuts <= 16 and all(abs(observed[k]-fractions[k]) < .025 for k in fractions)
