"""Dedicated-user bindings must cross the *filtered* MCP stdio boundary."""
import json
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).parent
BINDINGS = ('SCIENTIFIC_STUDY_OWNER_MODE', 'SCIENTIFIC_STUDY_OWNER',
            'SEED_DEFAULT_USER_EMAIL', 'CLINICAL_REPORT_API_KEY',
            'NEBIUS_API_KEY', 'CLINICAL_REPORT_API_KEY_FILE')


def render(tmp_path, configured):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('SCIENTIFIC_', 'SEED_', 'CLINICAL_', 'NEBIUS_'))}
    instructions = tmp_path / 'instructions.md'
    instructions.write_text('Test instructions.\n')
    env.update(SCIENTIFIC_DISCOVER_CHAT_MODELS='false',
               SCIENTIFIC_AGENT_INSTRUCTIONS_PATH=str(instructions), **configured)
    output = tmp_path / 'librechat.yaml'
    subprocess.run(['node', str(ROOT / 'render-config.mjs'), str(output)],
                   env=env, check=True, capture_output=True, text=True)
    return json.loads(output.read_text())['mcpServers']['environment-execution']


@pytest.mark.parametrize('name', BINDINGS)
def test_only_explicit_binding_is_forwarded_as_reference(tmp_path, name):
    configuration = render(tmp_path, {name: 'synthetic-value-not-for-config'})
    assert configuration['env'][name] == '${' + name + '}'
    assert set(BINDINGS) & configuration['env'].keys() == {name}
    assert 'synthetic-value-not-for-config' not in json.dumps(configuration)
    assert configuration['command'] == '/opt/scientific-client/bin/python'
    assert configuration['args'] == ['/opt/bionemo/execution-mcp.py']
    assert configuration['timeout'] == 30000


def test_absent_owner_mode_and_provider_are_not_invented(tmp_path):
    configuration = render(tmp_path, {})
    assert not set(BINDINGS) & configuration['env'].keys()
    assert 'LIBRECHAT_USER_ID' not in configuration['env']


@pytest.mark.parametrize('mode', ['first-instance', 'stopped-predecessor', 'invalid-mode'])
def test_mode_and_both_owner_forms_preserve_parent_precedence(tmp_path, mode):
    configured = {'SCIENTIFIC_STUDY_OWNER_MODE': mode,
                  'SCIENTIFIC_STUDY_OWNER': 'stable-owner',
                  'SEED_DEFAULT_USER_EMAIL': 'dedicated@example.test'}
    configuration = render(tmp_path, configured)
    for key in configured:
        assert configuration['env'][key] == '${' + key + '}'
    # Renderer does not authorize an invalid mode: the exact value reaches
    # the existing submit gate. Runtime behavior is exercised by the SDK gate.
    assert mode not in json.dumps(configuration)
