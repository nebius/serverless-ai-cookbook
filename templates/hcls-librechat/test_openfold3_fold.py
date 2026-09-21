import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location('openfold3_fold', Path(__file__).with_name('openfold3-fold.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def options(tmp_path):
    fasta = tmp_path / 'query.fasta'
    fasta.write_text('>ubiquitin\nACDEFGHIKLMNPQRSTVWY\n')
    return types.SimpleNamespace(
        fasta=fasta, output_dir=tmp_path / 'output', idempotency_key='openfold3-test-key',
        request_id='recording-openfold3', input_id='protein', chain_id='A', wait_seconds=30,
        recover_only=False, model='openfold3', tool='infer_openfold3_native')


def result_value():
    return {'request_id': 'recording-openfold3', 'outputs': [{
        'input_id': 'protein',
        'runtime_metrics': {'inference_seconds': 12.25, 'runtime_origin': 'upstream-source-preview2'},
        'structures_with_scores': [{
            'format': 'cif', 'name': 'sample',
            'source': 'aqlaboratory/openfold-3 Preview2 0.4.2; of3-p2-155k (not NVIDIA NIM)',
            'structure': 'data_sample\n#\nloop_\n_atom_site.group_PDB\n_atom_site.id\nATOM 1\n' + ('#' * 80),
            'confidence_score': 0.81, 'complex_plddt_score': 0.77,
            'complex_pde_score': 0.22, 'ptm_score': 0.72, 'iptm_score': 0.0,
        }],
    }]}


def write_operation(path):
    pipeline.save(path, {'structuredContent': {
        'id': 'openfold3-operation', 'accepted_at': '2026-09-21T00:00:00Z',
        'completed_at': '2026-09-21T00:00:14.5Z'}})


def test_pipeline_admits_once_and_materializes_exact_scores_and_cif(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'openfold3-operation'})
        pipeline.save(target / 'result.json', result_value()); write_operation(target / 'operation.json')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'openfold3-operation'
    assert result['scores']['complex_plddt_score'] == 0.77
    assert result['runtime_metrics']['inference_seconds'] == 12.25
    assert result['timing']['elapsed_seconds'] == 14.5
    assert (args.output_dir / 'analysis' / 'structure.cif').read_text().startswith('data_sample')
    assert [Path(command[1]).name for command in commands] == ['invoke-native.py']
    assert json.loads((args.output_dir / 'input.json').read_text())['inputs'][0]['molecules'][0]['sequence'] == 'ACDEFGHIKLMNPQRSTVWY'


def test_pending_openfold3_never_materializes_or_submits_a_fallback(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        pipeline.save(target / 'receipt.json', {'state': 'running', 'operation_id': 'openfold3-pending'})
        return types.SimpleNamespace(returncode=75, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 75 and result['operation_id'] == 'openfold3-pending'
    assert len(commands) == 1 and not (args.output_dir / 'analysis').exists()


@pytest.mark.parametrize('mutation,match', [
    (lambda value: value['outputs'][0]['structures_with_scores'].append({}), 'exactly one'),
    (lambda value: value['outputs'][0]['structures_with_scores'][0].pop('ptm_score'), 'ptm_score'),
    (lambda value: value.update(request_id='other'), 'request_id'),
])
def test_result_contract_fails_closed(mutation, match):
    value = result_value(); mutation(value)
    with pytest.raises(ValueError, match=match):
        pipeline.validate_result(value, 'recording-openfold3', 'protein')
