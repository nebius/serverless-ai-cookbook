"""No-cloud regression checks for isolated candidate credential reuse."""
import argparse
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('deploy_scientists', Path(__file__).with_name('deploy-scientist-workbenches.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(tmp_path):
    person = {'id': 'scientist-01', 'tenant_id': 'lab', 'principal_id': 'principal',
              'bucket_name': 'lab-bucket', 'email': 'scientist@example.invalid', 'password': 'fixture',
              'api_key': 'fixture', 's3_access_key_id': 'fixture', 's3_secret_access_key': 'fixture'}
    manifest = {'project_id': 'project-fixture', 'subnet_id': 'subnet-fixture',
                'token_factory_secret_selector': 'secret-provider', 'tavily_secret_selector': 'secret-search'}
    args = argparse.Namespace(output=tmp_path / 'new', source_deployments=tmp_path / 'old',
                              profile='fixture', name_prefix='qualification-v13', image='example/image:v13', wait_seconds=0)
    source = {key: person[key] for key in ('tenant_id', 'principal_id', 'bucket_name', 'email')}
    source.update(scientist_id=person['id'], project_id=manifest['project_id'], secret_id='secret-existing')
    path = args.source_deployments / person['id'] / 'deployment.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(source))
    return manifest, person, args, source, path


@pytest.mark.parametrize('field', ['scientist_id', 'tenant_id', 'principal_id', 'bucket_name', 'email', 'project_id'])
def test_source_identity_mismatch_fails_before_cloud_mutation(tmp_path, monkeypatch, field):
    manifest, person, args, source, path = fixture(tmp_path)
    source[field] = 'different'
    path.write_text(json.dumps(source))
    monkeypatch.setattr(module, 'cloud', lambda *args, **kwargs: pytest.fail('Cloud called on mismatched identity'))
    with pytest.raises(RuntimeError, match='identity differs'):
        module.deploy(manifest, person, args)


def test_secret_project_is_verified_without_reading_or_creating_payload(tmp_path, monkeypatch):
    manifest, person, args, _, _ = fixture(tmp_path)
    calls = []
    def cloud(cli, arguments, *rest, **kwargs):
        calls.append(arguments)
        return {'metadata': {'id': 'secret-existing', 'parent_id': 'wrong-project'}}
    monkeypatch.setattr(module, 'cloud', cloud)
    with pytest.raises(RuntimeError, match='different project'):
        module.deploy(manifest, person, args)
    assert calls == [['mysterybox', 'secret', 'get', '--id', 'secret-existing']]


def test_candidate_records_verified_reuse_before_creating_distinct_endpoint(tmp_path, monkeypatch):
    manifest, person, args, _, _ = fixture(tmp_path)
    monkeypatch.setattr(module, 'cloud', lambda *args, **kwargs: {
        'metadata': {'id': 'secret-existing', 'parent_id': manifest['project_id']}})
    def command(command, environment):
        assert environment['ENDPOINT_NAME'] == 'qualification-v13-scientist-01'
        assert environment['SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR'] == 'secret-existing'
        raise RuntimeError('fixture-stopped-before-cloud')
    monkeypatch.setattr(module, 'deploy_command', command)
    with pytest.raises(RuntimeError, match='fixture-stopped'):
        module.deploy(manifest, person, args)
    state = json.loads((args.output / person['id'] / 'deployment.json').read_text())
    assert state['secret_id'] == 'secret-existing'
    assert state['endpoint_name'] == 'qualification-v13-scientist-01'


def test_comparison_model_is_pinned_and_not_silently_replaced(tmp_path, monkeypatch):
    manifest, person, args, _, _ = fixture(tmp_path)
    args.chat_model = 'provider/verified-candidate'
    args.context_tokens = 131072
    monkeypatch.setattr(module, 'cloud', lambda *args, **kwargs: {
        'metadata': {'id': 'secret-existing', 'parent_id': manifest['project_id']}})
    def command(command, environment):
        assert environment['SCIENTIFIC_CHAT_MODEL'] == args.chat_model
        assert environment['SCIENTIFIC_CHAT_MAX_CONTEXT_TOKENS'] == '131072'
        raise RuntimeError('fixture-stopped-before-cloud')
    monkeypatch.setattr(module, 'deploy_command', command)
    with pytest.raises(RuntimeError, match='fixture-stopped'):
        module.deploy(manifest, person, args)
    state_path = args.output / person['id'] / 'deployment.json'
    assert json.loads(state_path.read_text())['chat_model'] == args.chat_model
    assert json.loads(state_path.read_text())['context_tokens'] == 131072
    args.context_tokens = 1048576
    with pytest.raises(RuntimeError, match='Recorded context ceiling differs'):
        module.deploy(manifest, person, args)
    args.context_tokens = 131072
    args.chat_model = 'provider/different-candidate'
    with pytest.raises(RuntimeError, match='Recorded chat model differs'):
        module.deploy(manifest, person, args)


def existing_endpoint(tmp_path):
    manifest, person, args, source, _ = fixture(tmp_path)
    args.wait_seconds = 1800
    state = {**source, 'image': args.image, 'endpoint_id': 'endpoint-fixture',
             'endpoint_name': args.name_prefix + '-' + person['id'], 'state': 'endpoint_created'}
    path = args.output / person['id'] / 'deployment.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(state))
    return manifest, person, args, path


@pytest.mark.parametrize('with_url', [False, True])
def test_terminal_provider_error_is_preserved_before_login_or_wait(tmp_path, monkeypatch, with_url):
    manifest, person, args, path = existing_endpoint(tmp_path)
    endpoint = {'metadata': {'id': 'endpoint-fixture'}, 'status': {
        'state': 'ERROR', 'reason': 'StartFailed', 'details': {'message': 'Could not pull image'},
        'public_endpoints': ['https://fixture.invalid'] if with_url else []}}
    calls = []
    def cloud(cli, arguments, *rest, **kwargs):
        calls.append(arguments)
        return endpoint
    monkeypatch.setattr(module, 'cloud', cloud)
    monkeypatch.setattr(module, 'deploy_command', lambda *a: pytest.fail('No create retry allowed'))
    monkeypatch.setattr(module.httpx, 'Client', lambda *a, **k: pytest.fail('No login after terminal ERROR'))
    monkeypatch.setattr(module.time, 'sleep', lambda *a: pytest.fail('No wait after terminal ERROR'))
    with pytest.raises(RuntimeError, match='terminal ERROR'):
        module.deploy(manifest, person, args)
    assert calls == [['ai', 'endpoint', 'get', 'endpoint-fixture']]
    state = json.loads(path.read_text())
    assert state['state'] == 'endpoint_error' and state['endpoint_state'] == 'ERROR'
    assert state['endpoint_id'] == 'endpoint-fixture'
    assert state['provider_status'] == endpoint['status']
    receipt = Path(state['provider_error_receipt'])
    assert json.loads(receipt.read_text()) == endpoint
    assert receipt.stat().st_mode & 0o777 == 0o600
    assert path.stat().st_mode & 0o777 == 0o600


def test_starting_provider_still_uses_existing_wait_budget(tmp_path, monkeypatch):
    manifest, person, args, path = existing_endpoint(tmp_path)
    monkeypatch.setattr(module, 'cloud', lambda *a, **k: {'status': {'state': 'STARTING'}})
    moments = iter([0, 0, 1801])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(moments))
    sleeps = []
    monkeypatch.setattr(module.time, 'sleep', sleeps.append)
    with pytest.raises(RuntimeError, match='not ready before setup deadline'):
        module.deploy(manifest, person, args)
    assert sleeps == [10]
    state = json.loads(path.read_text())
    assert state['state'] == 'endpoint_created' and state['endpoint_state'] == 'STARTING'
    assert not (path.parent / 'endpoint-terminal-error.json').exists()


@pytest.mark.parametrize('public_ip', ['true', 'false'])
def test_deploy_helper_preserves_explicit_network_setting_without_implicit_ssh(tmp_path, monkeypatch, public_ip):
    manifest, person, args, _, _ = fixture(tmp_path)
    monkeypatch.setenv('SERVERLESS_PUBLIC_IP', public_ip)
    monkeypatch.delenv('SSH_PUBLIC_KEY_FILE', raising=False)
    monkeypatch.setattr(module, 'cloud', lambda *args, **kwargs: {
        'metadata': {'id': 'secret-existing', 'parent_id': manifest['project_id']}})
    def command(command, environment):
        assert environment['SERVERLESS_PUBLIC_IP'] == public_ip
        assert 'SSH_PUBLIC_KEY_FILE' not in environment
        raise RuntimeError('fixture-stopped-before-cloud')
    monkeypatch.setattr(module, 'deploy_command', command)
    with pytest.raises(RuntimeError, match='fixture-stopped'):
        module.deploy(manifest, person, args)
