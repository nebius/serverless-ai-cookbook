import hashlib
import importlib.util
import json
from pathlib import Path
import types

import pytest

spec = importlib.util.spec_from_file_location('cxr_analysis', Path(__file__).with_name('cxr-analysis.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def options(tmp_path):
    source = tmp_path / 'image.png'
    source.write_bytes(b'\x89PNG\r\n\x1a\nfixture')
    return types.SimpleNamespace(
        source=source, output_dir=tmp_path / 'output', idempotency_key='cxr-pipeline-test',
        question='Describe this research image.', detail='high', max_completion_tokens=256,
        wait_seconds=30, recover_only=False, model='nv-reason-cxr-3b',
        tool='analyze_image_openai_chat',
    )


def artifact(source):
    data = source.read_bytes()
    return {'artifact_id': '11111111-1111-4111-8111-111111111111',
            'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
            'media_type': 'image/png', 'compression': 'none', 'private_extra': 'excluded'}


def test_pipeline_builds_complete_artifact_chat_request_and_retains_summary(tmp_path):
    args = options(tmp_path)
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True)
        if command[1].endswith('upload-artifact.py'):
            pipeline.save(target / 'artifact.json', artifact(args.source))
        else:
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'cxr-operation'})
            pipeline.save(target / 'result.json', {'model': 'nv-reason-cxr-3b', 'choices': [{
                'message': {'content': '<think>private trace</think><answer>Observed research features.</answer>'},
                'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 4}})
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, exit_code = pipeline.run(args, runner)
    assert exit_code == 0 and result['operation_id'] == 'cxr-operation'
    assert result['assistant']['answer'] == 'Observed research features.'
    assert 'private trace' not in json.dumps(result)
    assert [Path(command[1]).name for command in commands] == ['upload-artifact.py', 'invoke-native.py']
    assert '--protocol' in commands[1] and commands[1][commands[1].index('--protocol') + 1] == 'openai-chat'
    payload = json.loads((args.output_dir / 'input.json').read_text())
    url = payload['messages'][1]['content'][1]['image_url']['url']
    assert url == {key: artifact(args.source)[key] for key in pipeline.ARTIFACT_FIELDS}
    assert payload['messages'][1]['content'][0]['text'] == args.question


@pytest.mark.parametrize('content,field', [
    ({'content': 'answer'}, 'content'),
    ({'content': '', 'reasoning_content': 'reasoned answer'}, 'reasoning_content'),
    ({'reasoning': 'fallback answer'}, 'reasoning'),
])
def test_result_content_fallbacks(content, field):
    assert pipeline.assistant_content({'choices': [{'message': content}]}) == (
        next(value for key, value in content.items() if key == field), field)


def test_visible_answer_removes_hidden_reasoning_and_preserves_answer():
    raw = '<think>long private analysis</think>\n<answer> Atelectasis, Lung Opacity </answer>'
    assert pipeline.visible_answer(raw) == 'Atelectasis, Lung Opacity'
    assert pipeline.visible_answer('Research observation only.') == 'Research observation only.'


def test_signature_media_detection_does_not_trust_extension(tmp_path):
    png = tmp_path / 'wrong.jpg'; png.write_bytes(b'\x89PNG\r\n\x1a\n')
    assert pipeline.detected_media_type(png) == 'image/png'
    bad = tmp_path / 'bad.png'; bad.write_bytes(b'not-an-image')
    with pytest.raises(ValueError, match='signature-verified'):
        pipeline.detected_media_type(bad)
