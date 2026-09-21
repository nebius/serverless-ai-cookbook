import importlib.util
import json
from pathlib import Path
import types


spec = importlib.util.spec_from_file_location(
    'ct_segmentation_batch', Path(__file__).with_name('ct-segmentation-batch.py'))
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def options(tmp_path):
    sources = []
    for name in ('single', 'paired', 'elongated'):
        source = tmp_path / f'{name}.nii.gz'
        source.write_bytes(name.encode())
        sources.append((name, source))
    return types.SimpleNamespace(
        case=sources, output_dir=tmp_path / 'campaign', label_prompt=[1],
        idempotency_key='recording-ct-batch', wait_seconds=30, recover_only=False,
    )


def successful_case(command):
    name = Path(command[command.index('--output-dir') + 1]).name
    value = {
        'state': 'succeeded', 'operation_id': f'operation-{name}',
        'model': 'nv-segment-ct', 'model_seconds': 0.1,
        'label_voxel_counts': {'0': 100, '1': 20},
        'workspace_urls': {
            'segmentation': f'/demos?file={name}/segmentation.nii.gz',
            'overlay': f'/demos?file={name}/overlay.png',
        },
    }
    return types.SimpleNamespace(returncode=0, stdout=json.dumps(value) + '\n', stderr='')


def test_campaign_runs_each_case_once_and_publishes_report_heatmap_and_urls(tmp_path):
    args = options(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return successful_case(command)

    result, code = batch.run(args, runner)
    assert code == 0
    assert result['state'] == 'succeeded'
    assert result['succeeded_count'] == 3
    assert [case['case'] for case in result['cases']] == ['single', 'paired', 'elongated']
    assert len(commands) == 3
    assert all(Path(command[1]).name == 'ct-segmentation.py' for command in commands)
    assert (args.output_dir / 'case-label-voxel-heatmap.png').is_file()
    assert (args.output_dir / 'report.md').is_file()
    assert (args.output_dir / 'batch.json').is_file()


def test_campaign_retains_success_pending_and_failure_without_resubmitting(tmp_path):
    args = options(tmp_path)
    outcomes = iter([
        successful_case(['--output-dir', str(args.output_dir / 'cases' / 'single')]),
        types.SimpleNamespace(returncode=75, stdout='{"state":"queued","operation_id":"op-q"}\n', stderr=''),
        types.SimpleNamespace(returncode=1, stdout='{"state":"error","error_type":"RemoteFailure"}\n', stderr=''),
    ])

    result, code = batch.run(args, lambda command, **kwargs: next(outcomes))
    assert code == 1
    assert result['state'] == 'failed'
    assert result['succeeded_count'] == 1
    assert result['pending_count'] == 1
    assert result['failed_count'] == 1
    assert [case['state'] for case in result['cases']] == ['succeeded', 'queued', 'error']


def test_case_parser_requires_safe_name_and_absolute_path():
    assert batch.parse_case('case=/tmp/input.nii.gz') == ('case', Path('/tmp/input.nii.gz'))
