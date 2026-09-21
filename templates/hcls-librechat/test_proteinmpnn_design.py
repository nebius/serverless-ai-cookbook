import hashlib
import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location(
    'proteinmpnn_design', Path(__file__).with_name('proteinmpnn-design.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def result_value():
    sequences = ['ACDEFG', 'ACDFFG']
    return {
        'mfasta': ('>input seed=42 designed_chains=[\'A\']\nACDEFG\n'
                   '>sample=1 score=0.8 global_score=0.8 seq_recovery=1.0\nACDEFG\n'
                   '>sample=2 score=0.7 global_score=0.7 seq_recovery=0.833333\nACDFFG\n'),
        'scores': [0.8, 0.7],
        'probs': [[([0.05] * 20) + [0.0] for _ in sequence] for sequence in sequences],
    }


def write_operation(path):
    pipeline.save(path, {'structuredContent': {
        'id': 'protein-operation', 'accepted_at': '2026-09-21T00:00:00Z',
        'completed_at': '2026-09-21T00:00:03.5Z'}})


def write_backbone(path):
    path.write_text('ATOM      1  CA  ALA A   1      1.000   2.000   3.000\nEND\n')


def test_real_contract_materializes_logo_table_and_csv(tmp_path):
    backbone, result, operation = tmp_path / 'input.pdb', tmp_path / 'result.json', tmp_path / 'operation.json'
    write_backbone(backbone); result.write_text(json.dumps(result_value())); write_operation(operation)
    output = tmp_path / 'analysis'
    summary = pipeline.materialize(result, operation, backbone, output, 'proteinmpnn')
    assert summary['operation_id'] == 'protein-operation'
    assert summary['probability_shape'] == [2, 6, 21]
    assert summary['timing']['elapsed_seconds'] == 3.5
    assert [row['sample'] for row in summary['designs']] == [2, 1]
    assert (output / 'proteinmpnn-summary.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert (output / 'designs.csv').read_text().splitlines()[1].startswith('1,2,0.7')
    assert json.loads((output / 'summary.json').read_text())['sequence_length'] == 6


@pytest.mark.parametrize('mutation,match', [
    (lambda value: value['scores'].__setitem__(0, 0.1), 'mfasta score'),
    (lambda value: value['probs'][0].pop(), 'matrix length'),
    (lambda value: value.update(mfasta='>input\nACDEFG\n'), 'at least one design'),
])
def test_invalid_returned_contract_fails_closed(mutation, match):
    value = result_value(); mutation(value)
    with pytest.raises(ValueError, match=match):
        pipeline.validate_result(value)


def options(tmp_path):
    backbone = tmp_path / 'input.pdb'; write_backbone(backbone)
    return types.SimpleNamespace(
        backbone=backbone, output_dir=tmp_path / 'output', idempotency_key='protein-pipeline-test',
        seed=42, num_sequences=2, temperature=0.1, chain=['A'], wait_seconds=30,
        recover_only=False, model='proteinmpnn', tool='infer_proteinmpnn_native')


def test_pipeline_is_one_upload_one_admission_then_deterministic_analysis(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1]); target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            raw = args.backbone.read_bytes()
            pipeline.save(target / 'artifact.json', {
                'artifact_id': '11111111-1111-4111-8111-111111111111',
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'chemical/x-pdb', 'compression': 'none'})
        else:
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'protein-operation'})
            pipeline.save(target / 'result.json', result_value()); write_operation(target / 'operation.json')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'protein-operation'
    assert result['sequence_length'] == 6
    assert result['probability_shape'] == [2, 6, 21]
    assert result['ranked_designs'][0] == {
        'rank': 1, 'sample': 2, 'model_score': 0.7, 'global_model_score': 0.7,
        'sequence_recovery': 0.833333, 'sequence': 'ACDFFG'}
    assert result['allowed_result_fields'] == ['model_score', 'global_model_score', 'sequence_recovery']
    assert 'pLDDT' in result['absent_result_fields']
    assert [Path(command[1]).name for command in commands] == ['upload-artifact.py', 'invoke-native.py']
    payload = json.loads((args.output_dir / 'input.json').read_text())
    assert payload['random_seed'] == 42 and payload['num_seq_per_target'] == 2
    assert payload['input_pdb_chains'] == ['A']
    assert payload['input_pdb']['sha256'] == hashlib.sha256(args.backbone.read_bytes()).hexdigest()


def test_pending_operation_never_runs_analysis_or_resubmits(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            raw = args.backbone.read_bytes(); pipeline.save(target / 'artifact.json', {
                'artifact_id': '11111111-1111-4111-8111-111111111111',
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'chemical/x-pdb', 'compression': 'none'})
            return types.SimpleNamespace(returncode=0, stdout='', stderr='')
        pipeline.save(target / 'receipt.json', {'state': 'queued', 'operation_id': 'protein-pending'})
        return types.SimpleNamespace(returncode=75, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 75 and result['operation_id'] == 'protein-pending' and len(commands) == 2
