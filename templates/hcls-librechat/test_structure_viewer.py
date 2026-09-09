"""Offline acceptance of the typed-result bridge and safe rendering inputs."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
ASSETS = ROOT.parents[1] / 'life-science/bionemo-librechat'
OPERATION = '11111111-1111-4111-8111-111111111111'
PDB = 'ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 10.00           C\nEND\n'
SDF = 'water\n  fixture\n\n  1  0  0  0  0  0  0  0  0  0999 V2000\n    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0\nM  END\n$$$$\n'


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.setenv('BIONEMO_ASSET_ROOT', str(ASSETS))
    spec = importlib.util.spec_from_file_location('structure_bridge', ROOT / 'structure-mcp.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_folding_and_docking_coordinates_reach_ui_not_text(bridge, monkeypatch):
    seen = []
    def result(operation):
        seen.append(operation)
        return {'protein': PDB, 'ligand_positions': [SDF], 'confidence': -2.9}
    monkeypatch.setattr(bridge, 'get_result', result)
    result = bridge.call_viewer({'operation_id': OPERATION, 'title': 'Actual result'})
    assert seen == [OPERATION]
    assert PDB not in result['content'][0]['text']
    assert '2 structure(s)' in result['content'][0]['text']
    html = result['content'][1]['resource']['text']
    assert 'result.protein' in html and 'result.ligand_positions[0]' in html
    for control in ['Start rotation', 'Full screen', 'Reset view', 'Molecular representation', 'Structure']:
        assert control in html
    assert bridge.TOOL['annotations']['readOnlyHint'] is True


def test_inline_structure_and_title_are_script_safe(bridge):
    title = '</title><img src=x onerror=alert(1)>'
    pdb = PDB + '</script><script>alert(1)</script>'
    result = bridge.call_viewer({'structure_text': pdb, 'title': title})
    html = result['content'][1]['resource']['text']
    assert title not in html
    assert '</script><script>alert(1)' not in html
    assert '<\\/script>' in html


@pytest.mark.parametrize('args', [
    {}, {'operation_id': '../../secret'}, {'operation_id': OPERATION, 'structure_text': PDB},
    {'structure_path': '/etc/passwd'}, {'url': 'https://example.com'},
    {'structure_text': 'C' * 65537}, {'structure_text': 'CCO'}, {'structure_text': PDB, 'title': 5},
])
def test_invalid_inputs_never_fetch(bridge, monkeypatch, args):
    def fail(_):
        pytest.fail('Invalid arguments performed a network request')
    monkeypatch.setattr(bridge, 'get_result', fail)
    with pytest.raises(ValueError):
        bridge.call_viewer(args)


def test_artifact_only_results_fail_honestly(bridge, monkeypatch):
    monkeypatch.setattr(bridge, 'get_result', lambda _: {'artifacts': [{'artifact_id': OPERATION}]})
    with pytest.raises(ValueError, match='No inline'):
        bridge.call_viewer({'operation_id': OPERATION})


def test_missing_key_is_explicit(bridge, monkeypatch):
    monkeypatch.delenv('SCIENTIFIC_MODELS_API_KEY', raising=False)
    with pytest.raises(ValueError, match='not connected'):
        bridge.get_result(OPERATION)


def test_duplicate_coordinates_and_bound(bridge):
    assert len(bridge.collect_structures({'a': PDB, 'b': PDB})) == 1
    assert len(bridge.collect_structures([PDB + str(i) for i in range(100)])) == bridge.MAX_STRUCTURES


def test_token_factory_has_official_color_icon_and_all_participants_get_starters():
    config = (ROOT / 'render-config.mjs').read_text()
    asset = (ROOT / 'assets/token-factory.svg').read_text()
    landing = (ROOT / 'ScientificLanding.tsx').read_text()
    assert "groupIcon:" in config and "iconURL: '/assets/token-factory.svg'" in config
    assert '#E0FF4F' in asset and '#052B42' in asset
    assert 'https://luma.com/5b82vwsa' in landing
    assert 'execute commands as root' in landing
    assert 'Cloud account access is configured separately' in landing
    assert 'useAuth' not in landing  # No special admin-only/event-account branch.
