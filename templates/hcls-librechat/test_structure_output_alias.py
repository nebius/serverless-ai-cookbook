"""Stable coordinate references preserve actual PDB/mmCIF bytes and paths."""
import asyncio
import copy
import hashlib
import io
import json
import os
from pathlib import Path

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow
from test_scientific_study import mounted  # noqa: F401


def coordinate_text(kind):
    from Bio.PDB import MMCIFIO, PDBParser
    from test_structure_analysis import COORDS, pdb
    text = pdb({'A': COORDS})
    if kind == 'pdb':
        return text.replace('\n', '\r\n')
    writer = MMCIFIO()
    writer.set_structure(PDBParser(QUIET=True).get_structure('exact', io.StringIO(text)))
    stream = io.StringIO()
    writer.save(stream)
    return '# preserve this exact comment\n\n' + stream.getvalue()


def plan(folder, kind='pdb'):
    reference = folder / 'reference.pdb'
    prediction = folder / 'original.coordinates'
    reference.write_text(coordinate_text('pdb'))
    prediction.write_bytes(coordinate_text(kind).encode())
    return {'schema': study.SCHEMA, 'title': 'Exact format-independent structure', 'steps': [
        {'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': {
            'reference': str(reference), 'prediction': str(prediction), 'chain_map': ['A:A']}},
        {'id': 'downstream', 'kind': 'analysis', 'method': 'structure', 'arguments': {
            'reference': str(reference), 'prediction': {'step': 'compare', 'file': 'prediction.structure'},
            'chain_map': ['A:A']}},
        {'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
            'title': 'Measured comparison', 'sections': [{'title': 'Measurements', 'format': 'markdown',
                'file': {'step': 'downstream', 'file': 'report.md'}}]}}],
        'deliverables': [
            {'name': 'coordinates', 'role': 'data', 'source': {'step': 'compare', 'file': 'prediction.structure'}},
            {'name': 'report.md', 'role': 'report', 'source': {'step': 'report', 'file': 'report.md'}}]}


@pytest.mark.parametrize('kind,extension', [('pdb', '.pdb'), ('mmcif', '.cif')])
def test_study_alias_retains_actual_format_path_bytes_and_downstream_publication(mounted, monkeypatch, kind, extension):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model/provider transport'))
    value = plan(mounted, kind)
    original = copy.deepcopy(value)
    expected = (mounted / 'original.coordinates').read_bytes()
    accepted = study.submit(value, mounted / 'final')
    for _ in range(len(value['steps']) + 1):
        result = asyncio.run(study.advance(accepted['id']))
    assert result['state'] == 'completed', result
    assert value == original
    for step_id in ('compare', 'downstream'):
        files = result['steps'][step_id]['files']
        alias = files['prediction.structure']
        actual = files['prediction' + extension]
        assert alias['path'] == actual['path'] and Path(alias['path']).suffix == extension
        assert alias['coordinate_format'] == kind and alias['original_file'] == 'prediction' + extension
        assert alias['sha256'] == actual['sha256'] == hashlib.sha256(expected).hexdigest()
        assert Path(alias['path']).read_bytes() == expected
        assert not Path(alias['path']).with_name('prediction.structure').exists()
        metrics = json.loads(Path(files['metrics.json']['path']).read_bytes())
        assert metrics['provenance']['prediction_format'] == kind
        assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    artifact = next(row for row in result['artifacts'] if row['name'] == 'coordinates')
    assert Path(artifact['path']).suffix == extension  # viewer/MIME use original path
    assert Path(artifact['path']).read_bytes() == expected
    assert not artifact['path'].endswith('.structure')
    descriptor = describe_workflow(['structure'])['phases']['structure']
    assert 'prediction.structure' in descriptor['always_on_success']
    assert descriptor['future_file_references']['prediction' + extension] == 'prediction.structure'


@pytest.mark.parametrize('filename', ['prediction.pdb', 'prediction.cif'])
@pytest.mark.parametrize('location', ['input', 'deliverable'])
def test_required_future_format_guess_fails_before_admission(mounted, monkeypatch, filename, location):
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model/provider transport'))
    value = plan(mounted)
    target = value['steps'][1]['arguments']['prediction'] if location == 'input' else value['deliverables'][0]['source']
    target['file'] = filename
    original = copy.deepcopy(value)
    with pytest.raises(ValueError, match='prediction.structure'):
        study.submit(value, mounted / 'final')
    assert value == original and study.list_studies() == []
    assert not (mounted / 'final').exists()


def test_other_conditional_contracts_and_materialized_files_unchanged(mounted):
    study.known_output_reference({'step': 'native', 'file': 'result.mp4'}, {'native': {'kind': 'native'}})
    study.known_output_reference({'step': 'batch', 'file': 'output-01.artifact'}, {'batch': {'kind': 'batch'}})
    study.known_output_reference(str(mounted / 'existing.cif'), {})
    assert 'prediction.cif' in describe_workflow(['structure'])['phases']['structure']['possible_exact_files']


def test_actual_v60_plan_rejected_without_changing_retained_bytes(mounted, monkeypatch):
    root = os.environ.get('SCIENTIFIC_RETAINED_V60_01_SNAPSHOT')
    if not root:
        pytest.skip('Exact private v60 failed-plan replay supplied by qualification gate')
    snapshot = Path(root)
    plans = snapshot / 'workspace/scientist-01/unattended-20260919-r12/ubiquitin/draft/revisions'
    candidates = [p for p in plans.glob('*.json') if any(
        x.get('source') == {'step': 'compare', 'file': 'prediction.cif'}
        for x in json.loads(p.read_bytes()).get('deliverables', []))]
    assert candidates, 'Retained failing required CIF declaration must exist'
    original_path = study.path_in_workspace

    def exact_retained_path(value):
        path = Path(value)
        if path.is_absolute() and str(path).startswith('/workspace/scientist-01/'):
            mapped = snapshot / 'workspace' / path.relative_to('/workspace')
            assert mapped.resolve().is_relative_to(snapshot.resolve())
            return mapped
        return original_path(value)

    monkeypatch.setattr(study, 'path_in_workspace', exact_retained_path)
    monkeypatch.setattr(study, 'run_model', lambda *a, **k: pytest.fail('Retained replay cannot admit inference'))
    for path in candidates:
        raw = path.read_bytes()
        value = json.loads(raw)
        with pytest.raises(ValueError, match='prediction.structure'):
            study.submit(value, mounted / ('rejected-' + path.stem))
        assert path.read_bytes() == raw
    assert study.list_studies() == []
