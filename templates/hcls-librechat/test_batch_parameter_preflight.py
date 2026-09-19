"""Local request-shape errors stay actionable and cannot reserve uploads."""
import argparse
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('parameter_batch', ROOT / 'scripts/scientific-batch-acceptance.py')
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)

PARAMETERS = {'checkpoint': 'protenix-v2', 'msa_mode': 'none', 'sample_count': 1, 'model_seeds': [7]}
SCHEMA = {'type': 'object', 'properties': {'parameters': {
    'type': 'object', 'additionalProperties': False, 'required': list(PARAMETERS),
    'properties': {'checkpoint': {'const': 'protenix-v2'}, 'msa_mode': {'enum': ['none', 'precomputed']},
                   'sample_count': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                   'model_seeds': {'type': 'array', 'minItems': 1, 'items': {'type': 'integer'}}}}}}
ARGS = argparse.Namespace(media_type='application/json', compression='none')


def test_full_envelope_is_not_silently_unwrapped():
    wrong = {'schema': 'fs2-serve.nebius.ai/scientific-run-request/v1',
             'operation': 'predict-complex-structure', 'service_class': 'customer-batch',
             'parameters': copy.deepcopy(PARAMETERS)}
    original = copy.deepcopy(wrong)
    with pytest.raises(batch.ParameterPreflightError, match='full scientific-run request envelope') as exc:
        batch.preflight_parameters(SCHEMA, wrong, b'{}', ARGS)
    assert 'Root-object shape' in str(exc.value) and 'checkpoint' in str(exc.value)
    assert 'No upload or inference' in str(exc.value)
    assert wrong == original
    batch.preflight_parameters(SCHEMA, wrong['parameters'], b'{}', ARGS)


@pytest.mark.parametrize('value', [None, [], 'string', 3, {},
    {**PARAMETERS, 'sample_count': 0}, {**PARAMETERS, 'model_seeds': ['7']},
    {**PARAMETERS, 'unknown': True}, {**PARAMETERS, 'source': None}])
def test_invalid_types_fields_and_bounds_are_rejected(value):
    with pytest.raises(batch.ParameterPreflightError):
        batch.preflight_parameters(SCHEMA, value, b'{}', ARGS)


def test_root_schema_references_remain_resolvable():
    schema = {'$defs': {'model': SCHEMA['properties']['parameters']},
              'properties': {'parameters': {'$ref': '#/$defs/model'}}}
    batch.preflight_parameters(schema, PARAMETERS, b'{}', ARGS)
    with pytest.raises(batch.ParameterPreflightError):
        batch.preflight_parameters(schema, {**PARAMETERS, 'sample_count': 0}, b'{}', ARGS)


def test_uploaded_bundle_uses_only_validation_reference_and_does_not_edit_input():
    schema = {'properties': {'parameters': {'type': 'object', 'required': ['source'], 'properties': {
        'source': {'type': 'object', 'required': ['kind', 'artifact_id', 'sha256', 'size_bytes'],
                   'properties': {'kind': {'const': 'uploaded-bundle'}, 'artifact_id': {'type': 'string'},
                                  'size_bytes': {'const': 2}, 'sha256': {'const': batch.digest(b'{}')}}}}}}}
    original = {'source': {'kind': 'uploaded-bundle'}}
    batch.preflight_parameters(schema, original, b'{}', ARGS)
    assert original == {'source': {'kind': 'uploaded-bundle'}}


@pytest.mark.parametrize('nested', [False, True])
def test_exact_validation_error_survives_async_context_teardown(monkeypatch, nested):
    leaf = batch.ParameterPreflightError('specific local invalid parameter file')
    async def fail(args):
        inner = ExceptionGroup('inner', [leaf]) if nested else leaf
        raise ExceptionGroup('MCP cleanup', [inner])
    monkeypatch.setattr(batch, '_run', fail)
    with pytest.raises(batch.ParameterPreflightError) as exc:
        asyncio.run(batch.run(None))
    assert exc.value is leaf and isinstance(exc.value.__cause__, ExceptionGroup)


@pytest.mark.parametrize('leaves', [[RuntimeError('native workload failed')],
    [batch.ParameterPreflightError('invalid'), OSError('transport also failed')],
    [ValueError('unrelated validation')]])
def test_other_or_mixed_failures_are_not_relabelled(monkeypatch, leaves):
    group = ExceptionGroup('original', leaves)
    async def fail(args):
        raise group
    monkeypatch.setattr(batch, '_run', fail)
    with pytest.raises(ExceptionGroup) as exc:
        asyncio.run(batch.run(None))
    assert exc.value is group


def test_preflight_fails_before_first_upload_and_preserves_receipt(tmp_path, monkeypatch):
    calls = []
    class Context:
        async def __aenter__(self): return self
        async def __aexit__(self, kind, error, trace):
            if isinstance(error, batch.ParameterPreflightError):
                raise ExceptionGroup('realistic async teardown', [error])
            return False
    class MCP(Context):
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name='submit_fixture', input_schema=SCHEMA,
                model_dump=lambda **kwargs: {'name': 'submit_fixture', 'inputSchema': SCHEMA})])
    async def discovered(connection, name, arguments):
        calls.append(name)
        assert name == 'get_model_schema'
        return {'contracts': [{'protocol': 'scientific-batch-v1'}]}
    async def forbidden(*args, **kwargs):
        calls.append('UPLOAD')
        raise AssertionError('Upload before parameter validation')
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://fixture.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'unit-test-only')
    monkeypatch.setattr(batch.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(batch, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, 'Client', lambda *args, **kwargs: MCP())
    monkeypatch.setattr(batch, 'call', discovered)
    monkeypatch.setattr(batch, 'upload', forbidden)
    source, params = tmp_path / 'source', tmp_path / 'parameters.json'
    source.write_bytes(b'{}')
    params.write_text(json.dumps({'operation': 'predict-complex-structure', 'parameters': PARAMETERS}))
    args = argparse.Namespace(source=source, parameters=params, model='fixture', output=tmp_path / 'run',
        idempotency_key='original', tool='submit_fixture', operation='predict-complex-structure',
        media_type='application/json', compression='none')
    with pytest.raises(batch.ParameterPreflightError, match='full scientific-run request envelope'):
        asyncio.run(batch.run(args))
    assert calls == ['get_model_schema']
    receipt = batch.load_receipt(args.output / 'receipt.json')
    assert receipt['state'] == 'prepared' and 'operation_id' not in receipt
    assert 'source_artifact' not in receipt and 'manifest_artifact' not in receipt
    retained = json.loads((args.output / 'parameter-preflight-error.json').read_bytes())
    assert retained['code'] == 'invalid_parameter_file'
    assert retained['uploads_submitted_this_invocation'] is False
    assert retained['inference_submitted_this_invocation'] is False


def test_cancellation_is_not_changed(monkeypatch):
    async def fail(args):
        raise asyncio.CancelledError()
    monkeypatch.setattr(batch, '_run', fail)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(batch.run(None))
