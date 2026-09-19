"""Explicit batch-coordinate selection, preserving scientific bytes and evidence."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import scientific_study as study
from test_scientific_study import mounted  # noqa: F401
from test_structure_analysis import analysis, spec
from test_structure_bound_confidence import fixture
from test_structure_output_alias import coordinate_text


def manifest_fixture(root, kind='pdb'):
    raw = coordinate_text(kind).encode()
    prediction, document, manifest, _, path = fixture(root, prediction=raw)
    if kind == 'mmcif':
        manifest['entries'][0]['semantic_type'] = 'protein-structure-mmcif/v1'
        manifest['entries'][0]['artifact']['media_type'] = 'chemical/x-mmcif'
    # A coordinate index is NOT an artifact index: confidence comes first.
    first, second = [(root / f'output-{i:02d}.artifact').read_bytes() for i in range(2)]
    (root / 'output-00.artifact').write_bytes(second)
    (root / 'output-01.artifact').write_bytes(first)
    manifest['entries'].reverse()
    path.write_text(json.dumps(manifest))
    reference = root / 'reference.pdb'
    reference.write_text(coordinate_text('pdb'))
    return path, manifest, reference, prediction, document


def local_plan(path, reference, index=0):
    return {'schema': study.SCHEMA, 'title': 'Manifest-backed comparison', 'steps': [
        {'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': {
            'reference': str(reference), 'prediction': str(path), 'structure_index': index, 'chain_map': ['A:A']}}],
        'deliverables': [{'name': 'report.md', 'role': 'report', 'source': {'step': 'compare', 'file': 'report.md'}},
                         {'name': 'prediction', 'role': 'data', 'source': {'step': 'compare', 'file': 'prediction.structure'}}]}


@pytest.mark.parametrize('kind', ['pdb', 'mmcif'])
def test_manifest_coordinate_role_and_original_format_survive_complete_study(mounted, monkeypatch, kind):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model/provider transport'))
    path, _, reference, raw, document = manifest_fixture(mounted, kind)
    value = local_plan(path, reference)
    original = copy.deepcopy(value)
    accepted = study.submit(value, mounted / 'final')
    for _ in range(2):
        result = asyncio.run(study.advance(accepted['id']))
    assert result['state'] == 'completed' and value == original
    files = result['steps']['compare']['files']
    assert Path(files['prediction.structure']['path']).read_bytes() == raw
    metrics = json.loads(Path(files['metrics.json']['path']).read_bytes())
    selected = metrics['prediction_selection']
    assert selected['structure_index'] == 0 and selected['manifest_entry_index'] == 1
    assert selected['coordinate_format'] == metrics['provenance']['prediction_format'] == kind
    assert selected['selected_artifact']['path'] == str(mounted / 'output-01.artifact')
    assert selected['selected_artifact']['sha256'] == hashlib.sha256(raw).hexdigest()
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    assert metrics['confidence_binding']['status'] == 'exact_structure_sha256_and_size_match'
    assert metrics['model_confidence_not_reference_agreement'] == {
        'confidence_artifacts[0].results[0].metrics.' + k: v for k, v in document['results'][0]['metrics'].items()}


@pytest.mark.parametrize('defect', ['missing-index', 'range', 'negative', 'missing-file',
                                 'hash', 'duplicate-coordinate', 'format', 'media'])
def test_materialized_manifest_errors_rejected_before_admission(mounted, monkeypatch, defect):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model/provider transport'))
    path, manifest, reference, _, _ = manifest_fixture(mounted)
    value = local_plan(path, reference)
    if defect == 'missing-index':
        del value['steps'][0]['arguments']['structure_index']
    elif defect in {'range', 'negative'}:
        value['steps'][0]['arguments']['structure_index'] = 2 if defect == 'range' else -1
    elif defect == 'missing-file':
        (mounted / 'output-01.artifact').rename(mounted / 'retained-original.artifact')
    elif defect == 'hash':
        (mounted / 'output-01.artifact').write_bytes(b'changed')
    elif defect == 'duplicate-coordinate':
        manifest['entries'].append(copy.deepcopy(manifest['entries'][1]))
    elif defect == 'format':
        manifest['entries'][1]['semantic_type'] = 'protein-structure-mmcif/v1'
        manifest['entries'][1]['artifact']['media_type'] = 'chemical/x-mmcif'
    else:
        manifest['entries'][1]['artifact']['media_type'] = 'application/json'
    path.write_text(json.dumps(manifest))
    original = copy.deepcopy(value)
    with pytest.raises((ValueError, RuntimeError, FileNotFoundError)):
        study.submit(value, mounted / 'final')
    assert value == original and study.list_studies() == [] and not (mounted / 'final').exists()


def test_future_manifest_requires_explicit_selection_without_guessing(mounted, monkeypatch):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model/provider transport'))
    reference = mounted / 'reference.pdb'
    reference.write_text(coordinate_text('pdb'))
    value = local_plan(mounted / 'unused', reference)
    value['steps'].insert(0, {'id': 'producer', 'kind': 'preparation', 'method': 'write-json',
        'arguments': {'filename': 'output-manifest.json', 'value': {}}})
    args = value['steps'][1]['arguments']
    args['prediction'] = {'step': 'producer', 'file': 'output-manifest.json'}
    del args['structure_index']
    with pytest.raises(ValueError, match='explicit structure_index'):
        study.submit(value, mounted / 'final')
    assert study.list_studies() == []
    args['structure_index'] = 0
    assert study.validate(value)  # Actual future bytes are checked only once materialized.


def test_noncoordinate_text_has_actionable_error_not_stopiteration():
    with pytest.raises(ValueError, match='No coordinate model found'):
        analysis.load_structure('{"schema":"not-coordinate-data"}')


@pytest.mark.parametrize('complex_id', ['1acb', '2ptc'])
def test_actual_v60_explicit_manifest_selection_replays_only_local_analysis(tmp_path, complex_id):
    names = ['SCIENTIFIC_RETAINED_V60_02_SNAPSHOT', 'SCIENTIFIC_RETAINED_V60_02_REFERENCES']
    if not all(os.environ.get(name) for name in names):
        pytest.skip('Exact private failed v60 plan/output tree and frozen public references are required')
    snapshot, references = [Path(os.environ[name]) for name in names]
    root = snapshot / 'workspace/scientist-02/unattended-20260919-r12/complexes'
    plan_path = root / 'plan/revisions/581faad70c47b38fbf615c10f24df4ada2786d8f0e2ea0315426234efaaf8d4f.json'
    original = plan_path.read_bytes()
    assert hashlib.sha256(original).hexdigest() == plan_path.stem
    plan = json.loads(original)
    args = next(s['arguments'] for s in plan['steps'] if s['id'] == 'struct-protenix-' + complex_id)
    operation = root / 'steps' / args['prediction']['step'] / 'operation'
    manifest = operation / args['prediction']['file']
    reference = references / Path(args['reference']).relative_to('/workspace')
    expected_reference = {'1acb': 'd753d0b47ecf132682365efb19f8aa8be5914412bc04f964fabf1becff833027',
                          '2ptc': '0b3880b05cfba506159267e7e2f3c851b89ea736e9ce822e0c0102d720e26ee9'}
    assert hashlib.sha256(reference.read_bytes()).hexdigest() == expected_reference[complex_id]
    files = [p for p in operation.iterdir() if p.is_file()]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    out = tmp_path / 'offline-only-analysis'
    command = [sys.executable, spec.origin, '--reference', str(reference), '--prediction', str(manifest),
        '--structure-index', str(args['structure_index']), '--confidence-result', str(manifest),
        '--request-file', str(operation / args['request_file']['file']), '--chain-map', *args['chain_map'], '--output-dir', str(out)]
    subprocess.run(command, check=True, capture_output=True, text=True)
    metrics = json.loads((out / 'metrics.json').read_bytes())
    selection = metrics['prediction_selection']
    selected = operation / f"output-{selection['manifest_entry_index']:02d}.artifact"
    assert selection['coordinate_format'] == 'mmcif'
    assert (out / 'prediction.cif').read_bytes() == selected.read_bytes()
    assert metrics['confidence_binding']['status'] == 'exact_structure_sha256_and_size_match'
    assert metrics['mapped_residues'] > 0 and metrics['global_ca_rmsd_angstrom'] > 0
    assert metrics['provenance']['request_sha256'] == hashlib.sha256((operation / args['request_file']['file']).read_bytes()).hexdigest()
    assert {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files} == before
    assert plan_path.read_bytes() == original
