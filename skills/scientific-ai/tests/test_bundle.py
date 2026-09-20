"""Portable package, contract and regression tests; no operator checkout/keys."""
import importlib.util
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


bundle = module(ROOT / 'bundle.py', 'scientific_bundle')
asr = module(ROOT / 'clinical-asr-evaluation/scripts/evaluate.py', 'asr_evaluation')
CONTRACTS = json.loads((Path(__file__).parent / 'contracts.json').read_text())['schemas']


def text(name):
    return (ROOT / name / 'SKILL.md').read_text()


def test_manifest_and_skill_format():
    data = bundle.validate()
    assert len(data['skills']) == 31
    assert len({model for models in data['skills'].values() for model in models}) == 37
    for name in data['skills']:
        assert 'license:' in text(name).split('---')[1]
        assert not re.search(r'`bionemo_[a-z_]+`|`protein_viewer`', text(name))


def test_links_resolve_in_downloadable_bundle():
    for path in ROOT.glob('*/**/*.md'):
        for target in re.findall(r'\]\(([^ )]+)(?:[^)]*)\)', path.read_text()):
            if '://' in target or target.startswith(('#', 'mailto:', '/')):
                continue
            assert (path.parent / target.split('#')[0]).exists(), (path, target)


def test_new_catalog_app_requires_deliberate_workflow_coverage():
    assert bundle.check_catalog({'models': [{'id': 'scvi-scanvi'}]})['unmapped'] == []
    with pytest.raises(ValueError, match='Add workflow coverage'):
        bundle.check_catalog({'models': [{'id': 'unreviewed-new-model'}]})
    with pytest.raises(ValueError):
        bundle.check_catalog({'models': []})


def test_illustrative_json_matches_pinned_native_contracts():
    mapping = {'boltz2': 'boltz2', 'openfold2': 'openfold2', 'openfold3': 'openfold3',
               'genmol': 'genmol', 'molmim': 'molmim', 'msa-search': 'msa-search-pdb70',
               'evo2': 'evo2-40b'}
    for skill, model in mapping.items():
        blocks = re.findall(r'```json\n(.*?)\n```', text(skill), re.S)
        assert blocks, skill
        Draft202012Validator(CONTRACTS[model]).validate(json.loads(blocks[0]))
    value = json.loads((ROOT / 'proteinmpnn/examples/request.json').read_text())
    Draft202012Validator(CONTRACTS['proteinmpnn']).validate(value)
    assert 'ATOM' in value['input_pdb']


def artifact(media):
    return {'artifact_id': '00000000-0000-4000-8000-000000000001',
            'sha256': 'a' * 64, 'size_bytes': 123, 'media_type': media, 'compression': 'none'}


@pytest.mark.parametrize('model,payload', [
    ('cellpose-cpsam-v2', {'image_base64': artifact('image/png'), 'media_type': 'image/png', 'research_only': True}),
    ('scvi-scanvi', {'anndata_base64': artifact('application/x-hdf5'), 'filename': 'input.h5ad',
                     'method': 'scanvi', 'labels_key': 'cell_type', 'unlabeled_category': 'Unknown',
                     'max_epochs': 2, 'n_latent': 10, 'seed': 1, 'research_only': True}),
    ('sam2-1-hiera-large', {'mode': 'prompted-video', 'media_base64': artifact('video/mp4'),
                           'media_type': 'video/mp4', 'points': [{'x': 3, 'y': 4, 'label': 1, 'object_id': 1}]}),
    ('wan2-2-t2v-nim', {'prompt': 'A red cube on a table', 'seconds': 4, 'seed': 1}),
    ('wan2-2-i2v-nim', {'prompt': 'A red cube on a table', 'input_reference': artifact('image/png')}),
    ('nv-segment-ct', {'input_nifti_base64': artifact('application/gzip'), 'label_prompt': [1]}),
    ('magpie-tts-multilingual-357m', {'text': 'Guten Morgen', 'language': 'de', 'voice': 'Sofia'}),
    ('parakeet-realtime-eou-120m-v1', {'audio': artifact('audio/wav')}),
    ('diar-streaming-sortformer-4spk-v2-1', {'audio': artifact('audio/wav')}),
])
def test_new_workflow_payloads_accept_artifacts_not_filenames(model, payload):
    validator = Draft202012Validator(CONTRACTS[model])
    validator.validate(payload)
    assert list(validator.iter_errors({**payload, 'invented_model_option': True}))


def test_protein_only_boltz_cannot_score_ligands():
    payload = json.loads(re.search(r'```json\n(.*?)\n```', text('boltz2'), re.S)[1])
    validator = Draft202012Validator(CONTRACTS['boltz2'])
    assert list(validator.iter_errors({**payload, 'ligands': [{'smiles': 'CCO'}]}))
    assert 'does **not** accept ligands' in text('drug-discovery-pipeline')


def test_contradictions_do_not_reappear():
    assert 'no compatible bridge' not in text('scientific-agent-tutorials')
    assert 'no bundled pipeline tool' not in text('protein-binder-design')
    for name in ['protein-binder-design', 'rfdiffusion', 'scientific-batch']:
        assert 'provenance note' in text(name)
    assert 'not a PDB' in text('rfdiffusion')
    assert 'clinical-documentation' in bundle.manifest()['skills']
    assert 'not a request to put a' in text('imaging-models')
    assert 'base64' in text('speech-workflows')
    assert len(text('proteinmpnn')) < 8000


def test_install_repeat_conflict_and_integrity(tmp_path):
    source = tmp_path / 'source'
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    (source / 'files.sha256.json').write_text(json.dumps(bundle.inventory(source)))
    destination = tmp_path / 'installed'
    result = bundle.install(destination, source)
    assert result['skills'] == 31
    assert bundle.install(destination, source) == result
    assert (destination / 'clinical-documentation/scripts/study_report.py').is_file()
    (destination / 'speech-workflows/SKILL.md').write_text('local customization')
    with pytest.raises(ValueError, match='Existing skill differs'):
        bundle.install(destination, source)
    assert (destination / 'speech-workflows/SKILL.md').read_text() == 'local customization'
    (source / 'speech-workflows/SKILL.md').write_text('tampered')
    with pytest.raises(ValueError):
        bundle.verify(source)


def test_release_archive_is_reproducible_and_self_contained(tmp_path):
    source = tmp_path / 'source'
    shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    (source / 'files.sha256.json').write_text(json.dumps(bundle.inventory(source)))
    one = bundle.build(tmp_path / 'a', source)
    two = bundle.build(tmp_path / 'b', source)
    assert one['sha256'] == two['sha256']
    unpacked = tmp_path / 'unpacked'
    with tarfile.open(one['archive']) as archive:
        archive.extractall(unpacked, filter='data')
    subprocess.run([sys.executable, str(unpacked / 'scientific-ai/bundle.py'), 'verify'], check=True)


def test_asr_negation_dose_and_exact_phrase_metrics():
    result = asr.evaluate('Kein Fieber 5 mg', 'Fieber 50 mg', 'de', ['kein fieber', '5 mg'])
    assert result['wer']['deletions'] == 1
    assert result['wer']['substitutions'] == 1
    assert result['keyword_error_rate'] == 1
    assert result['clinical_correctness'] == 'not_assessed'
    assert asr.evaluate('no pain', 'no pain and pain', 'en', ['no pain'])['keyword_error_rate'] == 0
    with pytest.raises(ValueError):
        asr.evaluate('', 'anything', 'en')
    with pytest.raises(ValueError):
        asr.evaluate('no pain', 'no pain', 'en', ['painkiller'])


def test_asr_cli_preserves_bytes_and_refuses_overwrite(tmp_path):
    reference, hypothesis = tmp_path / 'ref.txt', tmp_path / 'hyp.txt'
    reference.write_bytes('Keine Übelkeit\r\n'.encode())
    hypothesis.write_bytes(reference.read_bytes())
    output = tmp_path / 'metrics.json'
    command = [sys.executable, str(ROOT / 'clinical-asr-evaluation/scripts/evaluate.py'),
               '--reference', str(reference), '--hypothesis', str(hypothesis),
               '--language', 'de', '--output', str(output)]
    subprocess.run(command, check=True)
    result = json.loads(output.read_text())
    assert result['wer']['wer'] == 0 and result['cer']['rate'] == 0
    original = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == original


def test_cer_bit_vectors_match_independent_small_dp_and_long_record():
    def reference(left, right):
        previous = list(range(len(right) + 1))
        for i, a in enumerate(left, 1):
            row = [i]
            for j, b in enumerate(right, 1):
                row.append(min(previous[j] + 1, row[-1] + 1, previous[j-1] + (a != b)))
            previous = row
        return previous[-1]
    samples = [''.join(s) for n in range(5) for s in itertools.product('ab', repeat=n)]
    for left in samples:
        for right in samples:
            assert asr.distance(left, right) == reference(left, right)
    assert asr.distance('Keine Schmerzen ' * 3000, 'Keine Schmerzen ' * 3000 + 'x') == 1
