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
