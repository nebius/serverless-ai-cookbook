import asyncio
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from scientific_protein_preparation import prepare, structure_helper
import scientific_study as study


def backbone(chain='A', missing=None, gap=False):
    rows = []
    for i in range(3):
        for j, atom in enumerate(('N', 'CA', 'C', 'O')):
            if (i, atom) == missing:
                continue
            residue = i + 1 + (1 if gap and i > 0 else 0)
            rows.append(f'ATOM  {len(rows)+1:5d} {atom:^4} ALA {chain}{residue:4d}    '
                        f'{i * 4 + j:8.3f}{j:8.3f}{i:8.3f}  1.00 90.00           {atom[0]:1s}  ')
    return '\n'.join(rows) + '\nEND\n'


def mpnn_args(path):
    return {'backbone': str(path), 'structure_index': 0, 'chain': 'A',
            'num_sequences': 2, 'seed': 7, 'sampling_temp': 0.2, 'omit_aas': ['X']}


def test_exact_dependent_inputs_preserve_selection_and_request_identity(tmp_path):
    upstream = tmp_path / 'rfdiffusion.json'
    upstream.write_text(json.dumps({'outputs': [{'structure': backbone()}, {'structure': backbone('B')}]}))
    inverse = tmp_path / 'inverse'
    inverse.mkdir()
    metadata = prepare('proteinmpnn-input', mpnn_args(upstream), inverse)
    request = json.loads((inverse / 'input.json').read_bytes())
    assert request == {'input_pdb': backbone(), 'input_pdb_chains': ['A'], 'num_seq_per_target': 2,
                       'random_seed': 7, 'sampling_temp': 0.2, 'omit_AAs': ['X']}
    assert metadata['selection']['available_structures'] == 2
    design = tmp_path / 'mpnn.json'
    design.write_text(json.dumps({'result': {'mfasta': '>input seed=7 designed_chains=[A]\nAAA\n>sample=1 score=0.2\nACD\n>sample=2 score=0.8\nCDE\n'}}))
    refold = tmp_path / 'refold'
    refold.mkdir()
    metadata = prepare('esmfold2-fast-input', {'design_input': str(inverse / 'input.json'),
        'design_result': str(design), 'design_index': 1, 'seed': 19}, refold)
    assert json.loads((refold / 'parameters.json').read_bytes()) == {'sequence': 'CDE', 'seed': 19, 'mode': 'single-sequence'}
    assert json.loads((refold / 'input.json').read_bytes())['sequences'] == [{'id': 'A', 'sequence': 'CDE', 'type': 'protein'}]
    assert metadata['selection']['design_index'] == 1 and metadata['inference_submitted'] is False
    assert 'sample=2' in (refold / 'selected.fasta').read_text()


@pytest.mark.parametrize('pdb', [backbone(missing=(0, 'N')), backbone(gap=True), backbone('B')])
def test_no_silent_gap_chain_or_coordinate_policy(tmp_path, pdb):
    source = tmp_path / 'source.pdb'
    source.write_text(pdb)
    with pytest.raises(ValueError):
        prepare('proteinmpnn-input', mpnn_args(source), tmp_path)
    assert not (tmp_path / 'input.json').exists()


def test_batch_manifest_resolves_only_hash_verified_coordinate_artifact(tmp_path):
    source = tmp_path / 'output-manifest.json'
    pdb = backbone().encode()
    source.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1', 'entries': [
        {'semantic_type': 'summary/v1', 'artifact': {}},
        {'semantic_type': 'protein-structure-pdb/v1', 'artifact': {'media_type': 'chemical/x-pdb', 'compression': 'none',
         'sha256': hashlib.sha256(pdb).hexdigest(), 'size_bytes': len(pdb)}}]}))
    (tmp_path / 'output-01.artifact').write_bytes(pdb)
    out = tmp_path / 'prepared'
    out.mkdir()
    value = prepare('proteinmpnn-input', mpnn_args(source), out)
    assert value['inputs']['selected_artifact']['sha256'] == hashlib.sha256(pdb).hexdigest()
    assert json.loads((out / 'input.json').read_bytes())['input_pdb'] == pdb.decode()
    (tmp_path / 'output-01.artifact').write_bytes(pdb + b'changed')
    with pytest.raises((ValueError, RuntimeError)):
        prepare('proteinmpnn-input', mpnn_args(source), out)


@pytest.mark.parametrize('fasta', ['>input seed=1\nAAA\n>sample=1\nAC\n',
                                  '>input seed=1\nCCC\n>sample=1\nACD\n',
                                  '>input seed=1\nAAA\n>sample=1\nA/X\n'])
def test_refold_requires_matching_original_and_complete_canonical_design(tmp_path, fasta):
    (tmp_path / 'request.json').write_text(json.dumps({'input_pdb': backbone(), 'input_pdb_chains': ['A']}))
    (tmp_path / 'result.json').write_text(json.dumps({'mfasta': fasta}))
    with pytest.raises(ValueError):
        prepare('esmfold2-fast-input', {'design_input': str(tmp_path / 'request.json'),
            'design_result': str(tmp_path / 'result.json'), 'design_index': 0, 'seed': 1}, tmp_path)
    assert not (tmp_path / 'parameters.json').exists()


def test_worker_chain_uses_prepared_content_not_paths_as_model_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'test-key')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'scientist@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    # Core execution is real; the remote transport is replaced with deterministic
    # recorded-shaped responses. Transport identity/recovery has separate tests.
    native = {'model', 'input', 'output', 'idempotency_key'}
    batch = {'model', 'tool', 'operation', 'media_type', 'entry_name', 'semantic_type', 'idempotency_key', 'display_name', 'source', 'parameters', 'output'}
    monkeypatch.setattr(study, 'workflow_module', lambda: SimpleNamespace(NATIVE_REQUIRED=native, REQUIRED=batch, OPTIONAL={'compression', 'service_class', 'source_artifact'}))
    source = tmp_path / 'rf.json'
    source.write_text('{}')
    args = mpnn_args(source)
    args['backbone'] = {'step': 'rf', 'file': 'output-manifest.json'}
    steps = [
        {'id': 'rf', 'kind': 'batch', 'model': 'rfdiffusion', 'tool': 'submit_rfdiffusion',
         'operation': 'design-backbone', 'media_type': 'application/json', 'entry_name': 'design_constraint',
         'semantic_type': 'rfdiffusion-design-constraint/v1', 'idempotency_key': 'rf-frozen', 'display_name': 'Frozen backbone design',
         'source': str(source), 'parameters': str(source)},
        {'id': 'mpnn-prep', 'kind': 'preparation', 'method': 'proteinmpnn-input', 'arguments': args},
        {'id': 'mpnn', 'kind': 'native', 'model': 'proteinmpnn', 'input': {'step': 'mpnn-prep', 'file': 'input.json'}, 'idempotency_key': 'mpnn-frozen'},
        {'id': 'fold-prep', 'kind': 'preparation', 'method': 'esmfold2-fast-input', 'arguments': {
            'design_input': {'step': 'mpnn-prep', 'file': 'input.json'}, 'design_result': {'step': 'mpnn', 'file': 'result.json'}, 'design_index': 0, 'seed': 19}},
        {'id': 'fold', 'kind': 'batch', 'model': 'esmfold2-fast', 'tool': 'submit_esmfold2_fast',
         'operation': 'predict-protein-structure', 'media_type': 'application/json', 'entry_name': 'esmfold2-fast-input',
         'semantic_type': 'esmfold2-fast-input-json/v1', 'idempotency_key': 'fold-frozen', 'display_name': 'Explicit design refolding',
         'source': {'step': 'fold-prep', 'file': 'input.json'}, 'parameters': {'step': 'fold-prep', 'file': 'parameters.json'}},
        {'id': 'correspondence', 'kind': 'preparation', 'method': 'design-refold-correspondence', 'arguments': {
            'design_input': {'step': 'mpnn-prep', 'file': 'input.json'}, 'design_result': {'step': 'mpnn', 'file': 'result.json'},
            'refold_input': {'step': 'fold-prep', 'file': 'input.json'}, 'refold_parameters': {'step': 'fold-prep', 'file': 'parameters.json'},
            'prediction': {'step': 'fold', 'file': 'result.json'}, 'design_index': 0, 'structure_index': 0, 'prediction_chain': 'A'}},
        {'id': 'analysis', 'kind': 'analysis', 'method': 'structure', 'arguments': {
            'reference': {'step': 'correspondence', 'file': 'reference.pdb'}, 'result': {'step': 'correspondence', 'file': 'prediction-result.json'},
            'chain_map': ['A:A'], 'residue_map': {'step': 'correspondence', 'file': 'residue-map.json'},
            'request_file': {'step': 'fold-prep', 'file': 'parameters.json'}}},
        {'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {'title': 'Design and refold study', 'sections': [
            {'title': 'Explicit positional correspondence', 'file': {'step': 'correspondence', 'file': 'report.md'}, 'format': 'markdown'},
            {'title': 'Measured structural agreement', 'file': {'step': 'analysis', 'file': 'report.md'}, 'format': 'markdown'}]}}]
    value = {'schema': study.SCHEMA, 'title': 'Dependent RF design and refold', 'steps': steps,
             'deliverables': [{'name': 'Methods and measured results', 'role': 'report', 'source': {'step': 'report', 'file': 'report.md'}},
                              {'name': 'Metrics', 'role': 'metrics', 'source': {'step': 'analysis', 'file': 'metrics.json'}},
                              {'name': 'Explicit correspondence', 'role': 'provenance', 'source': {'step': 'correspondence', 'file': 'residue-map.json'}},
                              {'name': 'Selected sequence', 'role': 'data', 'source': {'step': 'fold-prep', 'file': 'selected.fasta'}},
                              {'name': 'Refold', 'role': 'data', 'source': {'step': 'fold', 'file': 'result.json'}}]}
    seen = []

    async def remote(step, record):
        resolved = study.resolve(step, record)
        seen.append(step['idempotency_key'])
        if step['id'] == 'rf':
            folder = tmp_path / 'saved-rf'
            folder.mkdir()
            pdb = folder / 'output-00.artifact'
            pdb.write_text(backbone())
            manifest = folder / 'output-manifest.json'
            manifest.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1', 'entries': [
                {'semantic_type': 'protein-structure-pdb/v1', 'artifact': {'media_type': 'chemical/x-pdb', 'compression': 'none',
                 **study.measure(pdb)}}]}))
            return {'state': 'completed', 'operation_id': 'rf-accepted', 'files': {
                'output-manifest.json': study.measure(manifest), 'output-00.artifact': study.measure(pdb)}}
        elif step['id'] == 'mpnn':
            request = json.loads(Path(resolved['input']).read_bytes())
            assert request['input_pdb'] == backbone() and request['random_seed'] == 7
            result = {'mfasta': '>input seed=7\nAAA\n>sample=1\nACD\n'}
        else:
            assert json.loads(Path(resolved['source']).read_bytes())['sequences'][0]['sequence'] == 'ACD'
            assert json.loads(Path(resolved['parameters']).read_bytes())['seed'] == 19
            names = ['ALA', 'CYS', 'ASP']
            predicted = '\n'.join(line[:17] + names[int(line[22:26]) - 1] + line[20:]
                                  if line.startswith('ATOM') else line for line in backbone().splitlines()) + '\n'
            result = {'structure': predicted, 'confidence': 0.8}
        path = tmp_path / (step['id'] + '-result.json')
        path.write_text(json.dumps(result))
        return {'state': 'completed', 'operation_id': step['id'] + '-accepted', 'files': {'result.json': study.measure(path)}}

    started = study.submit(value, tmp_path / 'study')
    for _ in range(len(steps) + 1):
        finished = asyncio.run(study.advance(started['id'], model_runner=remote))
    assert finished['state'] == 'completed'
    assert seen == ['rf-frozen', 'mpnn-frozen', 'fold-frozen']
    assert len(finished['completed_steps']) == 8
    assert json.loads(Path(finished['manifest']['path']).read_bytes())['operations'] == ['rf-accepted', 'mpnn-accepted', 'fold-accepted']
    metrics = json.loads(Path(finished['steps']['analysis']['files']['metrics.json']['path']).read_bytes())
    assert metrics['mapped_residues'] == 3 and metrics['matched_identical_residues'] == 1
    assert metrics['correspondence_method'] == 'explicit-provenance'
    assert metrics['model_confidence_not_reference_agreement'] == {'retained_source_result.confidence': 0.8}


def test_preparation_schema_uses_actual_native_bounds():
    from jsonschema import Draft202012Validator
    from scientific_study_schema import STEPS
    schema = next(item for item in STEPS if item['properties'].get('method', {}).get('const') == 'proteinmpnn-input')
    args = mpnn_args('/workspace/a.pdb')
    validator = Draft202012Validator(schema)
    assert validator.is_valid({'id': 'prep', 'kind': 'preparation', 'method': 'proteinmpnn-input', 'arguments': args})
    args['num_sequences'] = 9
    assert not validator.is_valid({'id': 'prep', 'kind': 'preparation', 'method': 'proteinmpnn-input', 'arguments': args})


def correspondence_fixture(tmp_path):
    reference = tmp_path / 'reference.pdb'
    reference.write_text(backbone())
    inverse = tmp_path / 'inverse'
    inverse.mkdir()
    prepare('proteinmpnn-input', mpnn_args(reference), inverse)
    designs = tmp_path / 'designs.json'
    designs.write_text(json.dumps({'mfasta': '>input seed=7\nAAA\n>sample=1\nCDE\n>sample=2\nACD\n'}))
    fold = tmp_path / 'fold'
    fold.mkdir()
    prepare('esmfold2-fast-input', {'design_input': str(inverse / 'input.json'),
        'design_result': str(designs), 'design_index': 0, 'seed': 19}, fold)
    # Same geometry, entirely changed sequence. A sequence-identity-only fit
    # cannot map this design, but actual query-position provenance can.
    prediction = tmp_path / 'prediction.json'
    names = ['CYS', 'ASP', 'GLU']
    predicted = '\n'.join(line[:17] + names[int(line[22:26]) - 1] + line[20:]
                          if line.startswith('ATOM') else line for line in backbone().splitlines()) + '\n'
    prediction.write_text(json.dumps({'structure': predicted, 'confidence': 0.7}))
    args = {'design_input': str(inverse / 'input.json'), 'design_result': str(designs),
            'refold_input': str(fold / 'input.json'), 'refold_parameters': str(fold / 'parameters.json'),
            'prediction': str(prediction), 'design_index': 0, 'structure_index': 0, 'prediction_chain': 'A'}
    return args


def test_correspondence_covers_changed_sequence_positions_with_exact_hashes(tmp_path):
    args = correspondence_fixture(tmp_path)
    output = tmp_path / 'correspondence'
    output.mkdir()
    metadata = prepare('design-refold-correspondence', args, output)
    correspondence = json.loads((output / 'residue-map.json').read_bytes())
    reference = (output / 'reference.pdb').read_text()
    prediction = (output / 'prediction.structure').read_text()
    assert metadata['selection']['mapped_residues'] == 3
    assert correspondence['reference_sha256'] == hashlib.sha256(reference.encode()).hexdigest()
    assert correspondence['prediction_sha256'] == hashlib.sha256(prediction.encode()).hexdigest()
    metrics, _ = structure_helper().compare(reference, prediction, [('A', 'A')], residue_correspondence=correspondence)
    assert metrics['correspondence_method'] == 'explicit-provenance'
    assert metrics['mapped_residues'] == 3 and metrics['matched_identical_residues'] == 0
    assert metrics['global_ca_rmsd_angstrom'] < 1e-12
    assert structure_helper().confidence_fields(json.loads((output / 'prediction-result.json').read_bytes())) == {'retained_source_result.confidence': 0.7}


def test_correspondence_consumes_published_mmcif_and_confidence_without_new_transport(tmp_path):
    import io
    from Bio.PDB import MMCIFIO, PDBParser
    args = correspondence_fixture(tmp_path)
    value = json.loads(Path(args['prediction']).read_bytes())
    writer = MMCIFIO()
    writer.set_structure(PDBParser(QUIET=True).get_structure('prediction', io.StringIO(value['structure'])))
    output_text = io.StringIO()
    writer.save(output_text)
    coordinate_bytes = output_text.getvalue().encode()
    confidence_bytes = b'{"ptm":0.75}'
    entries = []
    for index, (data, role, media) in enumerate([
        (coordinate_bytes, 'protein-structure-mmcif/v1', 'chemical/x-mmcif'),
        (confidence_bytes, 'structure-confidence-json/v1', 'application/json')]):
        (tmp_path / f'output-{index:02d}.artifact').write_bytes(data)
        entries.append({'semantic_type': role, 'artifact': {'media_type': media, 'compression': 'none',
            'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)}})
    manifest = tmp_path / 'output-manifest.json'
    manifest.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1', 'entries': entries}))
    args['prediction'] = str(manifest)
    output = tmp_path / 'correspondence'
    output.mkdir()
    metadata = prepare('design-refold-correspondence', args, output)
    assert metadata['selection']['mapped_residues'] == 3
    assert (output / 'prediction.structure').read_bytes() == coordinate_bytes
    retained = json.loads((output / 'prediction-result.json').read_bytes())
    assert structure_helper().confidence_fields(retained) == {'retained_source_result.confidence_artifacts[0].ptm': 0.75}
    (tmp_path / 'output-01.artifact').write_bytes(b'{"ptm":1}')
    with pytest.raises((ValueError, RuntimeError)):
        prepare('design-refold-correspondence', args, output)


@pytest.mark.parametrize('change', ['wrong-design', 'wrong-query', 'wrong-parameter-sequence', 'missing-ca', 'wrong-returned-sequence', 'wrong-chain'])
def test_correspondence_rejects_unproven_or_incomplete_mapping(tmp_path, change):
    args = correspondence_fixture(tmp_path)
    if change == 'wrong-design':
        args['design_index'] = 1
    elif change == 'wrong-chain':
        args['prediction_chain'] = 'B'
    elif change == 'wrong-query':
        path = Path(args['refold_input'])
        value = json.loads(path.read_bytes())
        value['sequences'][0]['sequence'] = 'ACD'
        path.write_text(json.dumps(value))
    elif change == 'wrong-parameter-sequence':
        path = Path(args['refold_parameters'])
        value = json.loads(path.read_bytes())
        value['sequence'] = 'ACD'
        path.write_text(json.dumps(value))
    else:
        path = Path(args['prediction'])
        value = json.loads(path.read_bytes())
        value['structure'] = (value['structure'].replace('CYS', 'ALA') if change == 'wrong-returned-sequence' else
                              '\n'.join(line for line in value['structure'].splitlines() if not (line.startswith('ATOM') and line[12:16].strip() == 'CA' and int(line[22:26]) == 1)))
        path.write_text(json.dumps(value))
    output = tmp_path / 'correspondence'
    output.mkdir()
    with pytest.raises(ValueError):
        prepare('design-refold-correspondence', args, output)
    assert not (output / 'residue-map.json').exists()
