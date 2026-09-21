import importlib.util
import json
from pathlib import Path
import types

from PIL import Image


spec = importlib.util.spec_from_file_location(
    'recording_batch', Path(__file__).with_name('recording-batch.py'))
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def options(tmp_path, workflow='cxr'):
    source = tmp_path / 'case.png'
    Image.new('RGB', (24, 24), 'blue').save(source)
    return types.SimpleNamespace(
        workflow=workflow, case=[('case-a', source)], glob=None,
        output_dir=tmp_path / 'campaign', idempotency_key='recording-batch-test',
        wait_seconds=30, max_workers=1, recover_only=False, seed=[11], num_sequences=8,
        temperature=0.1, max_sequences=500, max_masks=32, batch_key='batch',
        method='scvi', labels_key=None, unlabeled_category='Unknown', max_epochs=20,
        n_latent=10, max_completion_tokens=768, prompt='make a lab', negative_prompt='',
        num_steps=35, guidance=7, resolution=720, control_weight=1.0,
    )


def test_cxr_campaign_uses_single_case_helper_and_publishes_customer_outputs(tmp_path):
    args = options(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        result = {'state': 'succeeded', 'operation_id': 'op-cxr', 'model': 'nv-reason-cxr-3b',
                  'source_path': str(args.case[0][1]), 'assistant': {'answer': 'No acute finding.'},
                  'workspace_urls': {'summary': '/demos?file=summary.json'}}
        return types.SimpleNamespace(returncode=0, stdout=json.dumps(result) + '\n', stderr='')

    result, code = batch.run(args, runner)
    assert code == 0 and result['state'] == 'succeeded'
    assert Path(commands[0][1]).name == 'cxr-analysis.py'
    assert (args.output_dir / 'batch.json').is_file()
    assert (args.output_dir / 'measurements.csv').is_file()
    assert (args.output_dir / 'report.md').is_file()
    assert (args.output_dir / 'gallery.png').is_file()


def test_campaign_records_mixed_terminal_states_without_hidden_retry(tmp_path):
    args = options(tmp_path)
    second = tmp_path / 'case-b.png'; Image.new('RGB', (16, 16), 'red').save(second)
    third = tmp_path / 'case-c.png'; Image.new('RGB', (16, 16), 'green').save(third)
    args.case.extend([('case-b', second), ('case-c', third)])
    outcomes = iter([
        types.SimpleNamespace(returncode=0, stdout='{"state":"succeeded","operation_id":"one"}\n', stderr=''),
        types.SimpleNamespace(returncode=75, stdout='{"state":"queued","operation_id":"two"}\n', stderr=''),
        types.SimpleNamespace(returncode=1, stdout='{"state":"error","error_type":"RemoteFailure"}\n', stderr=''),
    ])
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return next(outcomes)

    result, code = batch.run(args, runner)
    assert code == 1 and result['state'] == 'failed'
    assert (result['succeeded_count'], result['pending_count'], result['failed_count']) == (1, 1, 1)
    assert len(calls) == 3


def test_cosmos_campaign_expands_source_seed_cross_product(tmp_path):
    args = options(tmp_path, 'cosmos-transfer')
    args.seed = [11, 22, 33]
    expanded = batch.campaign_cases(args)
    assert [item[0] for item in expanded] == ['case-a-seed-11', 'case-a-seed-22', 'case-a-seed-33']
    assert [item[2] for item in expanded] == [11, 22, 33]


def test_discovery_is_sorted_deduplicated_and_workspace_bounded(tmp_path, monkeypatch):
    args = options(tmp_path)
    args.case = None
    args.glob = ['/workspace/examples/**/*.png']
    monkeypatch.setattr(batch.glob, 'glob', lambda pattern, recursive: [
        '/workspace/examples/b/image.png', '/workspace/examples/a/image.png',
        '/workspace/examples/a/image.png'])
    monkeypatch.setattr(Path, 'is_file', lambda self: True)
    found = batch.sources(args)
    assert [str(path) for _, path in found] == [
        '/workspace/examples/a/image.png', '/workspace/examples/b/image.png']
    assert len({name for name, _ in found}) == 2
