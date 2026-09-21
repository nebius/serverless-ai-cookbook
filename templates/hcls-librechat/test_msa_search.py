import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location('msa_search', Path(__file__).with_name('msa-search.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def result_value(query='ACDEFG'):
    return {'metrics': {'search_type': 'colabfold'}, 'alignments': {'pdb70_220313': {'a3m': {
        'format': 'a3m', 'alignment': f'>query\n{query}\n>hit-1\nACdDEFG\n>hit-2\nAC-EFG\n'}}}}


def write_operation(path):
    pipeline.save(path, {'structuredContent': {
        'id': 'msa-operation', 'accepted_at': '2026-09-21T00:00:00Z',
        'completed_at': '2026-09-21T00:00:01.25Z'}})


def write_query(path):
    path.write_text('>query fixture\nACDEFG\n')


def test_nested_a3m_contract_materializes_alignment_and_visual_summary(tmp_path):
    query, result, operation = tmp_path / 'query.fasta', tmp_path / 'result.json', tmp_path / 'operation.json'
    write_query(query); result.write_text(json.dumps(result_value())); write_operation(operation)
    output = tmp_path / 'analysis'
    summary = pipeline.materialize(result, operation, query, output, 'msa-search-pdb70')
    assert summary['operation_id'] == 'msa-operation'
    assert summary['database'] == 'pdb70_220313'
    assert summary['alignment']['sequence_count'] == 3
    assert summary['alignment']['aligned_columns'] == 6
    assert summary['timing']['elapsed_seconds'] == 1.25
    assert (output / 'alignment.a3m').read_text() == result_value()['alignments']['pdb70_220313']['a3m']['alignment']
    assert (output / 'msa-summary.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')


@pytest.mark.parametrize('text,match', [
    ('', 'empty'),
    ('>a\nACDEFG\n>b\nACDEF\n', 'query grid'),
    ('>a\nACDEFG\n>b\nAC*EFG\n', 'invalid aligned residue'),
])
def test_invalid_a3m_fails_closed(text, match):
    with pytest.raises(ValueError, match=match):
        pipeline.parse_a3m(text)


def test_query_identity_is_checked_before_artifacts_are_published(tmp_path):
    query, result, operation = tmp_path / 'query.fasta', tmp_path / 'result.json', tmp_path / 'operation.json'
    write_query(query); result.write_text(json.dumps(result_value('AAAAAA'))); write_operation(operation)
    output = tmp_path / 'analysis'
    with pytest.raises(ValueError, match='differs'):
        pipeline.materialize(result, operation, query, output, 'msa-search-pdb70')
    assert not output.exists()


def options(tmp_path):
    query = tmp_path / 'query.fasta'; write_query(query)
    return types.SimpleNamespace(
        query=query, output_dir=tmp_path / 'output', idempotency_key='msa-pipeline-test',
        max_sequences=500, wait_seconds=30, recover_only=False, database='pdb70_220313',
        model='msa-search-pdb70', tool='msa_search_native')


def test_pipeline_uses_one_native_admission_and_materializes_result(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'msa-operation'})
        pipeline.save(target / 'result.json', result_value()); write_operation(target / 'operation.json')
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'msa-operation'
    assert result['query']['length'] == 6
    assert result['alignment']['sequence_count'] == 3
    assert result['alignment']['aligned_columns'] == 6
    assert result['alignment']['mean_coverage'] == pytest.approx(17 / 18)
    assert result['timing']['completed_at'] == '2026-09-21T00:00:01.25Z'
    assert 'non-gap' in result['coverage_definition']
    assert [Path(command[1]).name for command in commands] == ['invoke-native.py']
    payload = json.loads((args.output_dir / 'input.json').read_text())
    assert payload == {'sequence': 'ACDEFG', 'databases': ['pdb70_220313'],
                       'max_msa_sequences': 500, 'output_alignment_formats': ['a3m']}


def test_pending_operation_is_retained_without_duplicate_submission(tmp_path):
    args, commands = options(tmp_path), []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        pipeline.save(target / 'receipt.json', {'state': 'queued', 'operation_id': 'msa-pending'})
        return types.SimpleNamespace(returncode=75, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 75 and result['operation_id'] == 'msa-pending' and len(commands) == 1
