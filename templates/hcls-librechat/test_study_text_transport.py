"""A serialized v2 object is a transport representation, not a v1 fallback."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
import scientific_study as study  # noqa: E402 - exercise the sibling installed module

SPEC = importlib.util.spec_from_file_location('study_text_execution', ROOT / 'execution-mcp.py')
execution = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(execution)
SCHEMA = next(tool['inputSchema'] for tool in execution.TOOLS if tool['name'] == 'run_scientific_workflow')


def plan():
    return {'schema': 'scientific-workflow/v2', 'title': 'Exact saved values', 'steps': [
        {'id': 'prepare', 'kind': 'analysis', 'method': 'write-json',
         'arguments': {'filename': 'data.json', 'value': {'seed': 7, 'values': [1, 16]}}}],
        'deliverables': [{'name': 'data.json', 'role': 'report',
                          'source': {'step': 'prepare', 'file': 'data.json'}}]}


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    for key, value in {'SCIENTIFIC_WORKSPACE': str(tmp_path),
                       'SCIENTIFIC_MODELS_MCP_URL': 'https://platform.test/mcp',
                       'SCIENTIFIC_MODELS_API_KEY': 'synthetic-private',
                       'SCIENTIFIC_STUDY_OWNER_MODE': 'first-instance',
                       'SEED_DEFAULT_USER_EMAIL': 'text@example.test'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(execution, 'WORKSPACE', str(tmp_path))
    monkeypatch.setattr(execution, 'ROOT', tmp_path / 'jobs')
    monkeypatch.setattr(study, 'workflow_module', lambda: pytest.fail('No model transport'))
    return tmp_path


def test_object_and_observed_json_text_have_identical_study_and_outputs(mounted):
    args = {'study': json.dumps(plan()), 'output_directory': str(mounted / 'final')}
    Draft202012Validator(SCHEMA).validate(args)
    first = execution.run_scientific_workflow(args)
    second = execution.run_scientific_workflow({**args, 'study': plan()})
    assert first['id'] == second['id']
    assert json.loads((study.directory(first['id']) / 'plan.json').read_bytes()) == plan()
    asyncio.run(study.advance(first['id']))
    final = asyncio.run(study.advance(first['id']))
    assert final['state'] == 'completed'
    assert json.loads(Path(final['artifacts'][0]['path']).read_bytes()) == {'seed': 7, 'values': [1, 16]}
    assert len(study.list_studies()) == 1


@pytest.mark.parametrize('bad', [
    '{', '{"schema":"scientific-workflow/v2","schema":"scientific-workflow/v2"}',
    json.dumps(plan()).replace('"seed": 7', '"seed": 7, "seed": 8'),
    json.dumps(plan()).replace('"seed": 7', '"seed": NaN'),
    json.dumps(plan()).replace('"seed": 7', '"seed": Infinity'),
    json.dumps(plan()).replace('"seed": 7', '"seed": 1e400'),
    json.dumps({**plan(), 'schema': 'scientific-workflow/v1'}),
    json.dumps({key: value for key, value in plan().items() if key != 'deliverables'}),
    json.dumps({'study': plan()}), json.dumps(json.dumps(plan())), '[]', 'null',
])
def test_invalid_text_never_reaches_admission_or_legacy_process(mounted, monkeypatch, bad):
    monkeypatch.setattr(study, 'submit', lambda *a: pytest.fail('Invalid draft must not reach admission'))
    monkeypatch.setattr(execution, 'execute', lambda *a: pytest.fail('No legacy fallback'))
    with pytest.raises(ValueError):
        execution.run_scientific_workflow({'study': bad, 'output_directory': str(mounted / 'final')})
    assert list(mounted.iterdir()) == []


def test_actual_mcp_sdk_lists_and_accepts_text_contract(mounted):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def check():
        server = StdioServerParameters(command=sys.executable, args=[str(ROOT / 'execution-mcp.py')], env=dict(os.environ))
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                schema = next(t.model_dump(by_alias=True)['inputSchema'] for t in tools.tools if t.name == 'run_scientific_workflow')
                args = {'study': json.dumps(plan()), 'output_directory': str(mounted / 'sdk-final')}
                Draft202012Validator(schema).validate(args)
                result = await session.call_tool('run_scientific_workflow', args)
                assert not result.model_dump(by_alias=True)['isError']
                record = json.loads(result.content[0].text)
                assert record['state'] == 'queued'
                invalid = await session.call_tool('run_scientific_workflow', {**args, 'study': '{'})
                assert invalid.model_dump(by_alias=True)['isError']
                assert len(study.list_studies()) == 1
    asyncio.run(check())


def test_seeded_guidance_preserves_whole_study_and_evidence_first_claims():
    seed = (ROOT / 'seed-workbench.js').read_text()
    full = (ROOT.parents[1] / 'life-science/bionemo-librechat/scientific-agent-instructions.md').read_text()
    for text in (seed, full):
        assert 'strict JSON text' in text
        assert 'same samples' in text
        assert 'sample identifiers' in ' '.join(text.split())
    assert 'downgrading to legacy v1' in seed
    assert 'Do not switch to v1' in full


def test_mismatched_report_section_delimiters_have_actionable_bounded_error(mounted, monkeypatch):
    # The retained v54 call had this exact closing-delimiter class inside its
    # JSON-text study; accepting strings must NOT silently fix that second error.
    malformed = '{"schema":"scientific-workflow/v2","steps":[{"arguments":{"sections":[{"file":"private-path.md"}}]}]}'
    monkeypatch.setattr(study, 'submit', lambda *a: pytest.fail('No admission for malformed JSON'))
    with pytest.raises(ValueError) as caught:
        execution.run_scientific_workflow({'study': malformed, 'output_directory': str(mounted / 'final')})
    assert 'line 1, column' in str(caught.value)
    assert 'composer plan_file' in str(caught.value)
    assert 'No study was admitted' in str(caught.value)
    assert 'private-path.md' not in str(caught.value)
