import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import scientific_study as study


@pytest.fixture
def mounted(tmp_path, monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL', 'https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'not-a-real-key')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL', 'script-study@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE', 'first-instance')
    return tmp_path


COMMON = '''import argparse,json
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--inputs',required=True)
p.add_argument('--output-dir',required=True)
a=p.parse_args()
bindings=json.loads(Path(a.inputs).read_bytes())
output=Path(a.output_dir)
'''


def plan(root, source, *, outputs=None):
    script = root / 'analysis.py'
    script.write_text(COMMON + source)
    input_file = root / 'model-result.json'
    input_file.write_text(json.dumps({'sequence': 'ACGTGGCCAT', 'molecules': ['CC(=O)Oc1ccccc1C(=O)O', 'CCO']}))
    return {'schema': study.SCHEMA, 'title': 'General reproducible scientific analysis', 'steps': [
        {'id': 'compute', 'kind': 'analysis', 'method': 'python-script', 'arguments': {
            'script': str(script), 'inputs': [{'name': 'result', 'file': str(input_file)}],
            'parameters': {'prefix': 'ACGT'}, 'outputs': outputs or ['metrics.json', 'report.md']}}
    ], 'deliverables': [{'name': 'Report', 'role': 'report', 'source': {'step': 'compute', 'file': 'report.md'}},
                       {'name': 'Measures', 'role': 'metrics', 'source': {'step': 'compute', 'file': 'metrics.json'}},
                       {'name': 'Source', 'role': 'provenance', 'source': {'step': 'compute', 'file': 'script.py'}}]}


SCRIPT = '''from rdkit import Chem
from rdkit.Chem import QED
data=json.loads(Path(bindings['inputs']['result']).read_bytes())
prefix=bindings['parameters']['prefix']
assert data['sequence'].startswith(prefix)
suffix=data['sequence'][len(prefix):]
metrics={'suffix':suffix,'suffix_bases':len(suffix),'suffix_gc_bases':sum(x in 'GC' for x in suffix),
         'suffix_gc_fraction':sum(x in 'GC' for x in suffix)/len(suffix),
         'qed':[QED.qed(Chem.MolFromSmiles(s)) for s in data['molecules']]}
(output/'metrics.json').write_text(json.dumps(metrics))
(output/'report.md').write_text('# Actual computed measurements\\n\\n'+json.dumps(metrics))
'''


def test_saved_code_computes_suffix_gc_and_actual_rdkit_qed_without_model_calls(mounted):
    from rdkit import Chem
    from rdkit.Chem import QED
    value = plan(mounted, SCRIPT)
    started = study.submit(value, mounted / 'output')
    asyncio.run(study.advance(started['id']))
    done = asyncio.run(study.advance(started['id']))
    assert done['state'] == 'completed'
    measured = json.loads(Path(done['steps']['compute']['files']['metrics.json']['path']).read_bytes())
    assert measured['suffix'] == 'GGCCAT' and measured['suffix_bases'] == 6 and measured['suffix_gc_bases'] == 4
    assert measured['suffix_gc_fraction'] == 4 / 6
    assert measured['qed'] == [QED.qed(Chem.MolFromSmiles(s)) for s in ['CC(=O)Oc1ccccc1C(=O)O', 'CCO']]
    provenance = json.loads(Path(done['steps']['compute']['files']['script-provenance.json']['path']).read_bytes())
    assert provenance['script']['sha256'] == study.measure(mounted / 'analysis.py')['sha256']
    assert provenance['inputs']['result']['sha256'] == study.measure(mounted / 'model-result.json')['sha256']
    assert json.loads(Path(done['manifest']['path']).read_bytes())['operations'] == []


@pytest.mark.parametrize('which', ['analysis.py', 'model-result.json'])
def test_changed_script_or_declared_input_stops_before_execution(mounted, which):
    value = plan(mounted, SCRIPT)
    started = study.submit(value, mounted / 'output')
    (mounted / which).write_text('changed bytes')
    outcome = asyncio.run(study.advance(started['id']))
    assert outcome['state'] == 'failed' and not outcome['completed_steps']
    assert not (mounted / 'output/steps').exists()


@pytest.mark.parametrize('body', ["(output/'metrics.json').write_text('{}')", "(output/'metrics.json').write_text('{}'); (output/'report.md').write_text('')"])
def test_missing_or_empty_declared_output_never_publishes_completed_phase(mounted, body):
    started = study.submit(plan(mounted, body), mounted / 'output')
    failed = asyncio.run(study.advance(started['id']))
    assert failed['state'] == 'failed' and failed['completed_steps'] == []
    assert 'missing, empty' in failed['failure']['message']
    assert not any((mounted / 'output').glob('publication-*'))


def test_script_error_and_external_output_are_explicit_failures(mounted):
    source = "raise RuntimeError('deliberate scientific-analysis failure')"
    started = study.submit(plan(mounted, source), mounted / 'error')
    failed = asyncio.run(study.advance(started['id']))
    assert failed['state'] == 'failed'
    diagnostic = next((mounted / 'error/steps/compute').glob('generation-*/diagnostic.txt')).read_text()
    assert 'exited 1' in diagnostic and 'deliberate scientific-analysis failure' in diagnostic
    with pytest.raises(ValueError, match='relative scratch'):
        study.submit(plan(mounted, SCRIPT, outputs=['../report.md']), mounted / 'escape')


def test_earlier_file_bindings_resolve_before_code_and_no_output_path_is_guessed(mounted):
    value = plan(mounted, "data=json.loads(Path(bindings['inputs']['result']).read_bytes()); (output/'metrics.json').write_text(json.dumps(data)); (output/'report.md').write_text('Saved '+str(data['answer']))")
    value['steps'].insert(0, {'id': 'prepare', 'kind': 'preparation', 'method': 'write-json', 'arguments': {'filename': 'input.json', 'value': {'answer': 42}}})
    value['steps'][1]['arguments']['inputs'][0]['file'] = {'step': 'prepare', 'file': 'input.json'}
    started = study.submit(value, mounted / 'output')
    for _ in range(3):
        done = asyncio.run(study.advance(started['id']))
    assert done['state'] == 'completed'
    assert json.loads(Path(done['steps']['compute']['files']['metrics.json']['path']).read_bytes()) == {'answer': 42}


def test_completed_script_phase_survives_worker_death_without_reexecution(mounted):
    value = plan(mounted, "(output/'metrics.json').write_text('{}'); (output/'report.md').write_text('actual report')")
    value['steps'].append({'id': 'publish-report', 'kind': 'analysis', 'method': 'report', 'arguments': {
        'title': 'Saved analysis', 'sections': [{'title': 'Findings', 'file': {'step': 'compute', 'file': 'report.md'}, 'format': 'markdown'}]}})
    value['deliverables'][0]['source'] = {'step': 'publish-report', 'file': 'report.md'}
    started = study.submit(value, mounted / 'output')
    command = [sys.executable, str(Path(__file__).with_name('scientific-study-worker.py')), '--worker']
    environment = {**os.environ, 'SCIENTIFIC_EXECUTION_DIR': str(mounted / 'execution-health')}
    first = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not study.get(started['id'])['completed_steps']:
            time.sleep(0.02)
        before = study.get(started['id'])
        assert before['completed_steps'] == ['compute']
    finally:
        first.kill()
        first.wait(timeout=3)
    second = subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and study.get(started['id'])['state'] != 'completed':
            time.sleep(0.02)
        after = study.get(started['id'])
        assert after['state'] == 'completed'
        assert after['steps']['compute'] == before['steps']['compute']
        assert len(list((mounted / 'output/steps/compute').glob('generation-*'))) == 1
    finally:
        second.terminate()
        second.wait(timeout=3)
