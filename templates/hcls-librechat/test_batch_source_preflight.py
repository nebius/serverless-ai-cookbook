"""Transport metadata binds original bytes, never edits a scientific request."""
import argparse
import asyncio
import copy
import gzip
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest
import scientific_study

spec = importlib.util.spec_from_file_location(
    'source_preflight_workflow', Path(scientific_study.__file__).with_name('scientific-workflow.py'))
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)
batch = workflow.batch


def contract(allowed=('gzip',)):
    return {'input_artifact_contract': {'entry': {'name': 'campaign-input',
        'semantic_type': 'fixture/v1', 'media_type': 'application/gzip',
        'allowed_compressions': list(allowed)}}}


def arguments(compression=None):
    return argparse.Namespace(operation='design', entry_name='campaign-input',
        semantic_type='fixture/v1', media_type='application/gzip', compression=compression)


@pytest.mark.parametrize('encoding,source', [('gzip', gzip.compress(b'original bytes')),
    ('zstd', bytes.fromhex('28b52ffd') + b'signature-only fixture')])
def test_omitted_compression_requires_exact_sole_contract_and_byte_signature(encoding, source):
    args = arguments()
    parameters = {'seed': 17}
    original = copy.deepcopy(parameters)
    resolved, provenance = batch.resolve_source_compression(contract([encoding]), parameters, args, source)
    assert args.compression is None and resolved is not args
    assert resolved.compression == encoding
    assert provenance['selection'] == 'published-single-encoding-and-source-signature'
    batch.preflight_source(contract([encoding]), parameters, resolved, len(source))
    assert parameters == original


@pytest.mark.parametrize('policy', [{}, contract(['none']), contract(['none', 'gzip'])])
def test_ordinary_plain_input_omission_preserves_none(policy):
    args = arguments()
    resolved, provenance = batch.resolve_source_compression(policy, {}, args, b'{"unchanged":true}')
    assert resolved.compression == 'none' and args.compression is None
    assert provenance['selection'] == 'legacy-uncompressed-default'
    batch.preflight_source(policy, {}, resolved, 18)


@pytest.mark.parametrize('explicit', ['none', 'gzip', 'zstd'])
def test_explicit_choices_are_never_overridden(explicit):
    args = arguments(explicit)
    resolved, provenance = batch.resolve_source_compression(contract(), {}, args, gzip.compress(b'x'))
    assert resolved is args and resolved.compression == explicit
    assert provenance == {'selection': 'explicit', 'compression': explicit}
    if explicit != 'gzip':
        with pytest.raises(batch.SourcePreflightError, match='compression must be'):
            batch.preflight_source(contract(), {}, resolved, 25)


@pytest.mark.parametrize('policy', [{}, contract(['none']), contract(['none', 'gzip']), contract(['zstd'])])
def test_compressed_omission_without_unique_matching_contract_rejects(policy):
    with pytest.raises(batch.SourcePreflightError, match='specify it explicitly'):
        batch.resolve_source_compression(policy, {}, arguments(), gzip.compress(b'original'))


def test_noncompressed_bytes_never_become_gzip_from_media_type_or_filename():
    args = arguments()
    args.source = Path('/irrelevant/looks-compressed.tar.gz')
    resolved, _ = batch.resolve_source_compression(contract(), {}, args, b'plain original bytes')
    assert resolved.compression == 'none'
    with pytest.raises(batch.SourcePreflightError, match="received 'none'"):
        batch.preflight_source(contract(), {}, resolved, 20)


@pytest.mark.parametrize('selector', ['operation', 'parameters.source.kind'])
def test_resolution_uses_the_existing_selected_role_not_another_contract(selector):
    entry = contract()['input_artifact_contract']['entry']
    if selector == 'operation':
        policy = {'operation_parameter': selector, 'operations': {'design': entry, 'other': {**entry, 'compression': 'none'}}}
    else:
        policy = {'source_kind_parameter': selector, 'source_kinds': {'uploaded-bundle': entry}}
    resolved, _ = batch.resolve_source_compression({'input_artifact_contract': policy},
        {'source': {'kind': 'uploaded-bundle'}}, arguments(), gzip.compress(b'x'))
    assert resolved.compression == 'gzip'


def install_mock_context(tmp_path, monkeypatch, explicit, allowed=('gzip',), stop_at_parameters=False):
    """Real AnyIO TaskGroups reproduce SDK teardown; no network/HTTP transport."""
    calls = []
    class Context:
        async def __aenter__(self):
            self.group = anyio.create_task_group()
            await self.group.__aenter__()
            return self
        async def __aexit__(self, *exc):
            return await self.group.__aexit__(*exc)
    class MCP(Context):
        async def list_tools(self):
            return SimpleNamespace(tools=[SimpleNamespace(name='submit_fixture',
                input_schema={'properties': {'parameters': {'type': 'object'}}},
                model_dump=lambda **kwargs: {'name': 'submit_fixture'})])
    async def discovery(connection, name, args):
        calls.append(name)
        assert name == 'get_model_schema'
        return {'contracts': [{'protocol': 'scientific-batch-v1'}], **contract(allowed)}
    async def forbidden(*args, **kwargs):
        calls.append('upload')
        pytest.fail('This preflight fixture must never reach an upload/admission')
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://fixture.invalid/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'fixture-only')
    monkeypatch.setattr(batch.httpx2, 'AsyncClient', lambda **kwargs: Context())
    monkeypatch.setattr(batch, 'Client', lambda *args, **kwargs: MCP())
    monkeypatch.setattr(batch, 'streamable_http_client', lambda *args, **kwargs: None)
    monkeypatch.setattr(batch, 'call', discovery)
    monkeypatch.setattr(batch, 'upload', forbidden)
    if stop_at_parameters:
        def parameter_boundary(schema, parameters, source, args):
            assert args.compression == 'gzip'
            assert parameters == {'seed': 17}
            raise batch.ParameterPreflightError('Intentional test boundary after source preflight')
        monkeypatch.setattr(batch, 'preflight_parameters', parameter_boundary)
    source, parameters = tmp_path / 'original.input', tmp_path / 'parameters.json'
    source.write_bytes(gzip.compress(b'original scientific input'))
    parameters.write_text('{"seed":17}')
    args = argparse.Namespace(**{**vars(arguments(explicit)), 'source': source, 'parameters': parameters,
        'model': 'fixture', 'output': tmp_path / 'output', 'idempotency_key': 'same-original-key',
        'tool': 'submit_fixture'})
    return args, calls


@pytest.mark.parametrize('explicit,allowed', [('none', ['gzip']), (None, ['gzip', 'none'])])
def test_actual_async_taskgroup_rejection_is_typed_before_upload(tmp_path, monkeypatch, explicit, allowed):
    args, calls = install_mock_context(tmp_path, monkeypatch, explicit, allowed)
    original = args.source.read_bytes()
    with pytest.raises(batch.SourcePreflightError) as caught:
        asyncio.run(batch.run(args))
    assert isinstance(caught.value.__cause__, ExceptionGroup)
    assert calls == ['get_model_schema']
    saved = json.loads((args.output / 'source-preflight-error.json').read_bytes())
    assert saved['code'] == 'invalid_source_metadata'
    assert saved['uploads_submitted_this_invocation'] is False
    assert saved['inference_submitted_this_invocation'] is False
    receipt = batch.load_receipt(args.output / 'receipt.json')
    assert receipt['state'] == 'prepared' and 'request_descriptor' not in receipt
    assert args.source.read_bytes() == original


def test_derived_encoding_provenance_saved_before_parameters_upload_or_admission(tmp_path, monkeypatch):
    args, calls = install_mock_context(tmp_path, monkeypatch, None, stop_at_parameters=True)
    original = args.source.read_bytes()
    with pytest.raises(batch.ParameterPreflightError, match='Intentional test boundary'):
        asyncio.run(batch.run(args))
    assert calls == ['get_model_schema'] and args.compression is None
    saved = json.loads((args.output / 'source-preflight.json').read_bytes())
    assert saved['compression'] == 'gzip' and saved['source_bytes_unchanged']
    assert saved['source_sha256'] == batch.digest(original)
    assert saved['selection'] == 'published-single-encoding-and-source-signature'
    assert args.source.read_bytes() == original


@pytest.mark.parametrize('leaves', [[ValueError('unrelated')], [ConnectionError('transport')],
    [batch.SourcePreflightError('metadata'), ConnectionError('transport')]])
def test_mixed_and_unrelated_groups_are_not_unwrapped_or_retried(monkeypatch, leaves):
    original = ExceptionGroup('unchanged group', leaves)
    calls = []
    async def fail(args):
        calls.append(args)
        raise original
    monkeypatch.setattr(batch, '_run', fail)
    with pytest.raises(ExceptionGroup) as caught:
        asyncio.run(batch.run(None))
    assert caught.value is original and calls == [None]


def test_workflow_preserves_compression_omission_instead_of_inventing_none(tmp_path):
    from test_scientific_workflow import plan
    value = plan(tmp_path)
    original = copy.deepcopy(value)
    seen = []
    async def local_boundary(args):
        seen.append(args.compression)
        return {'state': 'verified'}
    result = asyncio.run(workflow.run(value, tmp_path / 'flow', run_step=local_boundary))
    assert result['state'] == 'completed' and seen == [None, None]
    assert value == original


def test_exact_retained_v60_03_bytes_plan_and_contract_resolve_without_rewriting():
    snapshot = os.environ.get('SCIENTIFIC_RETAINED_V60_03_SNAPSHOT')
    source_path = os.environ.get('SCIENTIFIC_RETAINED_V60_03_SOURCE')
    if not snapshot or not source_path:
        pytest.skip('Exact retained03 files supplied by the installed qualification gate')
    base = Path(snapshot) / 'workspace/scientist-03/unattended-20260919-r12/pdl1'
    paths = [base / 'steps/bg-batch/workflow/plan.json', base / 'steps/bg-batch/operation/model-contract.json',
             base / 'params/boltzgen-pdl1-face.json', Path(source_path)]
    before = [path.read_bytes() for path in paths]
    value, discovery, parameters = [json.loads(raw) for raw in before[:3]]
    source = before[3]
    assert batch.digest(source) == '39f4eac886f1e311f12a8a0b5ad275bafc3840d4ee945a4d8be0661d9f0c809b'
    step = value['steps'][0]
    assert 'compression' not in step
    args = argparse.Namespace(**step)
    selected = batch.scientific_contract(discovery)
    resolved, provenance = batch.resolve_source_compression(selected, parameters, args, source)
    assert resolved.compression == 'gzip'
    batch.preflight_source(selected, parameters, resolved, len(source))
    assert provenance['selection'] == 'published-single-encoding-and-source-signature'
    with pytest.raises(batch.SourcePreflightError, match="received 'none'"):
        batch.preflight_source(selected, parameters, argparse.Namespace(**{**step, 'compression': 'none'}), len(source))
    assert [path.read_bytes() for path in paths] == before
