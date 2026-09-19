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
    monkeypatch.setattr(study, 'workflow_module', lambda: SimpleNamespace(NATIVE_REQUIRED=native, NATIVE_OPTIONAL={'tool_name'}, REQUIRED=batch, OPTIONAL={'compression', 'service_class', 'source_artifact'}))
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


def test_explicit_sole_chain_selects_observed_id_not_assumed_a(tmp_path):
    source = tmp_path / 'backbone.pdb'
    source.write_text(backbone('Z'))
    output = tmp_path / 'mpnn'
    output.mkdir()
    args = {**mpnn_args(source), 'chain': {'selection': 'sole-protein-chain'}}
    metadata = prepare('proteinmpnn-input', args, output)
    assert metadata['selection']['chain'] == 'Z'
    assert metadata['arguments']['chain'] == {'selection': 'sole-protein-chain'}
    assert json.loads((output / 'input.json').read_bytes())['input_pdb_chains'] == ['Z']


@pytest.mark.parametrize('text', ['', backbone('A').replace('END\n', 'TER\n') + backbone('B')])
def test_sole_chain_rejects_absent_or_multiple_protein_chains(tmp_path, text):
    source = tmp_path / 'backbone.pdb'
    source.write_text(text)
    with pytest.raises((ValueError, StopIteration)):
        prepare('proteinmpnn-input', {**mpnn_args(source), 'chain': {'selection': 'sole-protein-chain'}}, tmp_path)
    assert not (tmp_path / 'input.json').exists()


def test_correspondence_selects_actual_returned_chain_and_analysis_uses_hashbound_map(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    args = correspondence_fixture(tmp_path)
    path = Path(args['prediction'])
    data = json.loads(path.read_bytes())
    data['structure'] = '\n'.join(line[:21] + 'Z' + line[22:] if line.startswith('ATOM') else line
                                 for line in data['structure'].splitlines()) + '\n'
    path.write_text(json.dumps(data))
    args['prediction_chain'] = {'selection': 'sole-protein-chain'}
    output = tmp_path / 'correspondence'
    output.mkdir()
    metadata = prepare('design-refold-correspondence', args, output)
    assert metadata['selection']['prediction_chain'] == 'Z'
    analysis = {'reference': str(output / 'reference.pdb'), 'result': str(output / 'prediction-result.json'),
                'residue_map': str(output / 'residue-map.json')}
    study.validate_local_arguments('structure', analysis)
    record = {'output_directory': str(tmp_path / 'study'), 'steps': {}}
    result = study.run_local({'id': 'compare', 'kind': 'analysis', 'method': 'structure', 'arguments': analysis}, record)
    metrics = json.loads(Path(result['files']['metrics.json']['path']).read_bytes())
    assert metrics['mapped_residues'] == 3 and metrics['matched_identical_residues'] == 0
    from scientific_study_schema import PHASE_OUTPUTS
    assert set(PHASE_OUTPUTS['structure'][0]) <= result['files'].keys()
    with pytest.raises(ValueError, match='contradicts'):
        study.local_command('structure', {**analysis, 'chain_map': ['A:A']}, tmp_path)
    # Deriving chain labels never bypasses the existing exact byte-hash gate.
    (output / 'reference.pdb').write_text(backbone('A') + 'REMARK changed\n')
    with pytest.raises(RuntimeError, match='helper failed'):
        study.run_local({'id': 'bad-hash', 'kind': 'analysis', 'method': 'structure', 'arguments': analysis}, record)


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
    # Artifact confidence needs the versioned structure-hash join; a legacy
    # arbitrary metric object is retained but is not unbound sample evidence.
    assert structure_helper().confidence_fields(retained) == {}
    assert retained['retained_source_result']['confidence_artifact_sources'][0]['raw_json'] == confidence_bytes.decode()
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


def direct_prediction_manifest_fixture(tmp_path):
    args = correspondence_fixture(tmp_path)
    prediction = json.loads(Path(args['prediction']).read_bytes())['structure'].encode()
    direct = tmp_path / 'selected.pdb'
    direct.write_bytes(prediction)
    args['prediction'] = str(direct)
    document = {'schema': 'fs2.nebius.ai/structure-confidence/v1', 'runtime_id': 'test-refold',
        'model_revision': 'recorded-revision', 'input_identity': {'artifact_id': 'input-id', 'sha256': 'input-sha'},
        'seeds': [19], 'samples_per_seed': 1, 'results': [{'seed': 19, 'sample_index': 0,
            'structure': {'sha256': hashlib.sha256(prediction).hexdigest(), 'bytes': len(prediction)},
            'metrics': {'plddt_mean': 0.7201, 'ptm': 0.4071, 'iptm': 0.0}}]}
    # Another coordinate comes first: the manifest index must not change the
    # caller's already selected direct structure or structure_index=0.
    rows = [(backbone('B').encode(), 'protein-structure-pdb/v1', 'chemical/x-pdb'),
            (prediction, 'protein-structure-pdb/v1', 'chemical/x-pdb'),
            (json.dumps(document, indent=3).encode(), 'structure-confidence-json/v1', 'application/json')]
    entries = []
    for index, (raw, semantic, media) in enumerate(rows):
        (tmp_path / f'output-{index:02d}.artifact').write_bytes(raw)
        entries.append({'semantic_type': semantic, 'artifact': {'media_type': media,
            'compression': 'none', 'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw)}})
    manifest = tmp_path / 'output-manifest.json'
    manifest.write_text(json.dumps({'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1',
                                    'manifest_id': 'explicit-producer', 'entries': entries}))
    return args, manifest, document


def test_direct_correspondence_explicit_confidence_preserves_bytes_index_and_geometry(tmp_path):
    args, manifest, document = direct_prediction_manifest_fixture(tmp_path)
    before, after = tmp_path / 'before', tmp_path / 'after'
    before.mkdir()
    after.mkdir()
    prepare('design-refold-correspondence', args, before)
    metadata = prepare('design-refold-correspondence', {**args, 'confidence_result': str(manifest)}, after)
    for name in ('reference.pdb', 'prediction.structure', 'residue-map.json'):
        assert (before / name).read_bytes() == (after / name).read_bytes()
    assert (after / 'prediction.structure').read_bytes() == Path(args['prediction']).read_bytes()
    assert metadata['selection']['structure_index'] == 0
    assert metadata['selection']['available_structures'] == 1
    envelope = json.loads((after / 'prediction-result.json').read_bytes())
    raw = (tmp_path / 'output-02.artifact').read_bytes()
    retained = envelope['retained_source_result']
    assert retained['confidence_artifact_sources'] == [{'manifest_entry_index': 2, 'raw_json': raw.decode()}]
    fields, binding = structure_helper().bound_confidence(envelope, Path(args['prediction']).read_bytes())
    assert fields == {f'confidence_artifacts[2].results[0].metrics.{key}': value
                      for key, value in document['results'][0]['metrics'].items()}
    assert binding == metadata['selection']['confidence_binding']
    assert binding['seed'] == 19 and binding['sample_index'] == 0
    assert binding['confidence_artifact_sha256'] == hashlib.sha256(raw).hexdigest()
    assert metadata['inputs']['confidence_result']['sha256'] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert metadata['inputs']['paired_selected_artifact']['sha256'] == hashlib.sha256(Path(args['prediction']).read_bytes()).hexdigest()


@pytest.mark.parametrize('change', ['wrong-coordinate', 'duplicate-coordinate', 'coordinate-bytes',
                                  'confidence-bytes', 'duplicate-sample', 'wrong-sample-size',
                                  'invalid-schema', 'wrong-media'])
def test_direct_confidence_rejects_mismatch_or_ambiguity_without_publishing(tmp_path, change):
    args, manifest, document = direct_prediction_manifest_fixture(tmp_path)
    value = json.loads(manifest.read_bytes())
    if change == 'wrong-coordinate':
        value['entries'][1]['artifact']['sha256'] = '0' * 64
    elif change == 'duplicate-coordinate':
        value['entries'].append(value['entries'][1])
    elif change == 'coordinate-bytes':
        (tmp_path / 'output-01.artifact').write_bytes(b'changed')
    elif change == 'confidence-bytes':
        (tmp_path / 'output-02.artifact').write_bytes(b'changed')
    elif change == 'wrong-media':
        value['entries'][1]['artifact']['media_type'] = 'text/plain'
    elif change == 'invalid-schema':
        value['schema'] = 'untyped'
    else:
        if change == 'duplicate-sample':
            document['results'].append(document['results'][0])
        else:
            document['results'][0]['structure']['bytes'] += 1
        raw = json.dumps(document).encode()
        (tmp_path / 'output-02.artifact').write_bytes(raw)
        value['entries'][2]['artifact'].update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    manifest.write_text(json.dumps(value))
    output = tmp_path / 'out'
    output.mkdir()
    with pytest.raises((ValueError, RuntimeError)):
        prepare('design-refold-correspondence', {**args, 'confidence_result': str(manifest)}, output)
    assert not (output / 'prediction-result.json').exists()
    assert not (output / 'residue-map.json').exists()


def test_direct_manifest_without_confidence_remains_explicitly_unavailable(tmp_path):
    args, manifest, _ = direct_prediction_manifest_fixture(tmp_path)
    value = json.loads(manifest.read_bytes())
    value['entries'] = value['entries'][:2]
    manifest.write_text(json.dumps(value))
    output = tmp_path / 'out'
    output.mkdir()
    metadata = prepare('design-refold-correspondence', {**args, 'confidence_result': str(manifest)}, output)
    envelope = json.loads((output / 'prediction-result.json').read_bytes())
    fields, binding = structure_helper().bound_confidence(envelope, Path(args['prediction']).read_bytes())
    assert fields == {} and binding['status'] == 'unavailable_no_confidence_artifact'
    assert metadata['selection']['confidence_binding'] == binding
    assert (output / 'prediction.structure').read_bytes() == Path(args['prediction']).read_bytes()


def test_direct_confidence_preserves_coordinate_line_endings(tmp_path):
    args, manifest, document = direct_prediction_manifest_fixture(tmp_path)
    raw = Path(args['prediction']).read_bytes().replace(b'\n', b'\r\n')
    Path(args['prediction']).write_bytes(raw)
    (tmp_path / 'output-01.artifact').write_bytes(raw)
    document['results'][0]['structure'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    confidence = json.dumps(document).encode()
    (tmp_path / 'output-02.artifact').write_bytes(confidence)
    value = json.loads(manifest.read_bytes())
    for index, content in [(1, raw), (2, confidence)]:
        value['entries'][index]['artifact'].update(sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content))
    manifest.write_text(json.dumps(value))
    output = tmp_path / 'out'
    output.mkdir()
    prepare('design-refold-correspondence', {**args, 'confidence_result': str(manifest)}, output)
    assert (output / 'prediction.structure').read_bytes() == raw
    fields, _ = structure_helper().bound_confidence(json.loads((output / 'prediction-result.json').read_bytes()), raw)
    assert fields['confidence_artifacts[2].results[0].metrics.iptm'] == 0


def test_retained_v58_direct_coordinate_confidence_does_not_change_original_geometry(tmp_path):
    import os
    root = os.environ.get('SCIENTIFIC_RETAINED_V58_04')
    if not root:
        pytest.skip('Optional protected actual v58/04 final directory not mounted.')
    final = Path(root)
    assert final.is_dir()
    originals = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in final.rglob('*') if path.is_file()}
    correspondence, = (final / 'steps/correspondence').glob('generation-*')
    actual = json.loads((correspondence / 'provenance.json').read_bytes())
    live_root = Path('/workspace/scientist-04/unattended-20260919-r10/design-refold/final')
    args = {key: str(final / Path(value).relative_to(live_root)) if isinstance(value, str) and value.startswith(str(live_root) + '/') else value
            for key, value in actual['arguments'].items()}
    assert Path(args['prediction']).name == 'output-00.artifact' and args['structure_index'] == 0
    args['confidence_result'] = str(final / 'steps/esm-refold/operation/output-manifest.json')
    metadata = prepare('design-refold-correspondence', args, tmp_path)
    for name in ('reference.pdb', 'prediction.structure', 'residue-map.json'):
        assert (tmp_path / name).read_bytes() == (correspondence / name).read_bytes()
    envelope = json.loads((tmp_path / 'prediction-result.json').read_bytes())
    fields, binding = structure_helper().bound_confidence(envelope, (tmp_path / 'prediction.structure').read_bytes())
    raw = (final / 'steps/esm-refold/operation/output-01.artifact').read_bytes()
    native = json.loads(raw)['results'][0]
    assert fields == {f'confidence_artifacts[1].results[0].metrics.{key}': value for key, value in native['metrics'].items()}
    assert binding['confidence_artifact_sha256'] == hashlib.sha256(raw).hexdigest()
    assert binding['seed'] == native['seed'] and binding['sample_index'] == native['sample_index']
    assert metadata['selection']['confidence_binding'] == binding
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in originals.items())
