"""Typed manifest-based design analysis uses the existing batch artifact ABI."""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow, known_output_files


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'design-analysis-test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'design-analysis@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('Saved design analysis submits no inference'))
    raw = (''.join(f'ATOM  {i:5d}  CA  ALA B{i:4d}    {(i - 1) * 3.8:8.3f}{0.:8.3f}{0.:8.3f}  1.00 80.00           C  \n'
                   for i in range(1, 5)) + 'TER\nEND\n').encode()
    (tmp_path / 'output-00.artifact').write_bytes(raw)
    manifest = tmp_path / 'output-manifest.json'
    manifest.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1',
        'entries': [{'name': 'generated.1', 'semantic_type': 'protein-structure/v1', 'artifact': {
            'artifact_id': 'saved-only', 'media_type': 'chemical/x-pdb', 'compression': 'none',
            'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}}]}))
    return tmp_path, manifest


def plan(manifest):
    return {'schema': study.SCHEMA, 'title': 'Saved design evidence', 'steps': [
        {'id': 'measure', 'kind': 'analysis', 'method': 'protein-design-analysis', 'arguments': {
            'manifest_file': str(manifest), 'binder_chain': 'B', 'binder_length_min': 4, 'binder_length_max': 4}}],
        'deliverables': [{'name': name, 'role': role, 'source': {'step': 'measure', 'file': name}}
            for name, role in [('report.md', 'report'), ('measurements.json', 'metrics'), ('inventory.csv', 'data')]]}


def test_saved_artifact_manifest_completes_and_freezes_both_implementations(mounted):
    root, manifest = mounted
    value = plan(manifest)
    accepted = study.submit(value, root / 'complete')
    assert study.submit(value, root / 'complete')['id'] == accepted['id']
    for _ in range(2):
        final = asyncio.run(study.advance(accepted['id']))
    assert final['state'] == 'completed', final
    files = final['steps']['measure']['files']
    contract = describe_workflow(['protein-design-analysis'])['phases']['protein-design-analysis']
    assert set(files) == set(contract['always_on_success']) == known_output_files(value['steps'][0])
    measured = json.loads(Path(files['measurements.json']['path']).read_bytes())
    assert measured['verified_artifacts'] == 1 and measured['coordinate_outputs'] == 1
    assert measured['manifest_sha256'] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert measured['requested_constraints'] == {'binder_chain': 'B', 'binder_length_min': 4, 'binder_length_max': 4}
    assert json.loads(Path(final['manifest']['path']).read_bytes())['operations'] == []
    receipt = json.loads((study.directory(accepted['id']) / 'receipt.json').read_bytes())
    assert {'protein-design-analysis', 'protein-design-evaluator'} <= receipt['implementations'].keys()


def test_modified_manifest_sibling_cannot_publish_success(mounted):
    root, manifest = mounted
    accepted = study.submit(plan(manifest), root / 'tamper-detection')
    (root / 'output-00.artifact').write_bytes(b'changed after immutable manifest admission')
    failed = asyncio.run(study.advance(accepted['id']))
    assert failed['state'] == 'failed' and not failed.get('manifest')
    assert 'Deterministic protein-design-analysis helper failed' in failed['failure']['message']


def test_exact_target_cli_and_paired_reference_validation(mounted):
    root, manifest = mounted
    args = {'manifest_file': str(manifest), 'target_reference': str(root / 'target.pdb'), 'target_chain': 'X',
            'binder_chain': 'B', 'binder_length_min': 4, 'binder_length_max': 6}
    command = study.local_command('protein-design-analysis', args, root / 'scratch')
    assert command[2:] == ['--manifest', str(manifest), '--output-dir', str(root / 'scratch'),
                          '--binder-chain', 'B', '--binder-length-min', '4', '--binder-length-max', '6',
                          '--target-reference', str(root / 'target.pdb'), '--target-chain', 'X']
    assert study.input_references({'kind': 'analysis', 'method': 'protein-design-analysis', 'arguments': args}) == [str(manifest), str(root / 'target.pdb')]
    with pytest.raises(ValueError, match='both target_reference'):
        study.validate_local_arguments('protein-design-analysis', {'manifest_file': str(manifest), 'target_chain': 'X'})
    with pytest.raises(ValueError, match='minimum length exceeds'):
        study.validate_local_arguments('protein-design-analysis', {'manifest_file': str(manifest), 'binder_length_min': 5, 'binder_length_max': 4})


def test_dependent_batch_manifest_is_accepted_without_a_directory_reference():
    args = {'manifest_file': {'step': 'model', 'file': 'output-manifest.json'}}
    step = {'id': 'measure', 'kind': 'analysis', 'method': 'protein-design-analysis', 'arguments': args}
    study.validate_local_arguments(step['method'], args)
    assert study.input_references(step) == [args['manifest_file']]
    study.known_output_reference(args['manifest_file'], {'model': {'kind': 'batch'}})
