"""Offline acceptance of the typed-result bridge and safe rendering inputs."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent
ASSETS = ROOT.parents[1] / 'life-science/bionemo-librechat'
OPERATION = '11111111-1111-4111-8111-111111111111'
PDB = 'ATOM      1  CA  ALA A   1       1.000   2.000   3.000  1.00 10.00           C\nEND\n'
SDF = 'water\n  fixture\n\n  1  0  0  0  0  0  0  0  0  0999 V2000\n    0.0000    0.0000    0.0000 O   0  0  0  0  0  0  0  0  0  0  0  0\nM  END\n$$$$\n'


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.setenv('BIONEMO_ASSET_ROOT', str(ASSETS))
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE', str(tmp_path))
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


def test_multiple_operations_render_one_synchronized_overlay(bridge, monkeypatch):
    other = '22222222-2222-4222-8222-222222222222'
    seen = []
    monkeypatch.setattr(bridge, 'get_result', lambda operation: seen.append(operation) or {'protein': PDB + f'REMARK {operation}\n'})
    result = bridge.call_viewer({'operations': [
        {'operation_id': OPERATION, 'label': 'OpenFold3 Preview2'},
        {'operation_id': other, 'label': 'Boltz2'},
    ], 'title': 'Ubiquitin comparison'})
    assert seen == [OPERATION, other]
    assert '2 completed operations' in result['content'][0]['text']
    html = result['content'][1]['resource']['text']
    assert 'Overlay all (synchronized)' in html
    assert 'OpenFold3 Preview2' in html and 'Boltz2' in html
    assert "loadStructure(entries.length>1?'overlay':'0')" in html
    assert PDB not in result['content'][0]['text']


def test_completed_docking_operation_overlays_verified_workspace_receptor(bridge, monkeypatch):
    receptor = bridge.WORKSPACE / 'inputs' / 'receptor.pdb'
    receptor.parent.mkdir()
    receptor.write_text(PDB)
    monkeypatch.setattr(bridge, 'get_result', lambda _: {'ligand_positions': [SDF]})
    result = bridge.call_viewer({
        'operation_id': OPERATION,
        'workspace_files': [{'path': 'inputs/receptor.pdb', 'label': '1UBQ receptor'}],
        'title': 'DiffDock · 1UBQ + aspirin',
    })
    html = result['content'][1]['resource']['text']
    assert '1UBQ receptor' in html and 'Docking pose 1' in html
    assert 'Overlay all (synchronized)' in html
    assert PDB not in result['content'][0]['text']


def test_workspace_structure_paths_cannot_escape_root(bridge, tmp_path):
    outside = tmp_path.parent / 'outside.pdb'
    outside.write_text(PDB)
    with pytest.raises(ValueError, match='remain under'):
        bridge.call_viewer({'workspace_files': [{'path': str(outside), 'label': 'outside'}]})


def test_explicit_plddt_result_enables_real_confidence_coloring(bridge, monkeypatch):
    monkeypatch.setattr(bridge, 'get_result', lambda _: {
        'structure': PDB.replace('10.00', '82.50'), 'complex_plddt_score': 82.5,
    })
    result = bridge.call_viewer({'operation_id': OPERATION, 'title': 'Confidence-colored prediction'})
    html = result['content'][1]['resource']['text']
    assert 'Confidence (pLDDT)' in html
    assert 'Very high ≥90' in html
    assert 'plddt-b-factor' in html
    assert 'function confidenceColor(atom)' in html


def test_generic_confidence_does_not_claim_plddt_coloring(bridge, monkeypatch):
    monkeypatch.setattr(bridge, 'get_result', lambda _: {'structure': PDB, 'confidence': 0.91})
    entries = bridge.collect_structures(bridge.get_result(OPERATION))
    assert 'color_by' not in entries[0]


@pytest.mark.parametrize('operations', [
    [{'operation_id': OPERATION, 'label': 'one'}],
    [{'operation_id': OPERATION, 'label': 'one'}, {'operation_id': OPERATION, 'label': 'two'}],
    [{'operation_id': OPERATION, 'label': ''}, {'operation_id': '22222222-2222-4222-8222-222222222222', 'label': 'two'}],
])
def test_invalid_multi_operation_requests_do_not_partially_fetch(bridge, monkeypatch, operations):
    fetched = []
    monkeypatch.setattr(bridge, 'get_result', lambda operation: fetched.append(operation) or {'protein': PDB})
    with pytest.raises(ValueError):
        bridge.call_viewer({'operations': operations})
    assert len(fetched) <= 1


def test_inline_structure_and_title_are_script_safe(bridge):
    title = '</title><img src=x onerror=alert(1)>'
    pdb = PDB + '</script><script>alert(1)</script>'
    result = bridge.call_viewer({'structure_text': pdb, 'title': title})
    html = result['content'][1]['resource']['text']
    assert title not in html
    assert '</script><script>alert(1)' not in html
    assert '<\\/script>' in html


def test_workspace_media_is_signature_checked_and_bytes_stay_out_of_text(bridge):
    image = bridge.WORKSPACE / 'outputs' / 'overlay.png'
    image.parent.mkdir()
    image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'synthetic-image-bytes')
    result = bridge.call_media_viewer({'files': [
        {'path': 'outputs/overlay.png', 'label': 'CT overlay'},
    ], 'title': 'Research result'})
    assert 'synthetic-image-bytes' not in result['content'][0]['text']
    html = result['content'][1]['resource']['text']
    assert 'data:image/png;base64,' in html
    assert 'CT overlay' in html and 'Research result' in html
    assert bridge.MEDIA_TOOL['annotations']['readOnlyHint'] is True


@pytest.mark.parametrize('filename,data', [
    ('wrong.png', b'not a png'),
    ('unsupported.nii.gz', b'\x89PNG\r\n\x1a\n'),
])
def test_workspace_media_rejects_spoofed_or_unsupported_files(bridge, filename, data):
    path = bridge.WORKSPACE / filename
    path.write_bytes(data)
    with pytest.raises(ValueError):
        bridge.call_media_viewer({'files': [{'path': str(path), 'label': 'bad'}]})


def test_workspace_media_labels_are_html_safe(bridge):
    image = bridge.WORKSPACE / 'safe.png'
    image.write_bytes(b'\x89PNG\r\n\x1a\n' + b'data')
    label = '"><script>alert(1)</script>'
    result = bridge.call_media_viewer({'files': [{'path': str(image), 'label': label}],
                                       'title': label})
    html = result['content'][1]['resource']['text']
    assert label not in html
    assert '&lt;script&gt;' in html


def test_workspace_media_accepts_recording_length_pcm_audio(bridge):
    # RIFF/WAVE signature plus a payload just above the retired 8 MiB cap.
    audio = bridge.WORKSPACE / 'recording-soundtrack.wav'
    audio.write_bytes(b'RIFF' + b'\x00\x00\x00\x00' + b'WAVE' + (9 * 1024 * 1024 - 12) * b'X')
    result = bridge.call_media_viewer({
        'files': [{'path': str(audio), 'label': '45-second soundtrack'}],
        'title': 'Recording soundtrack',
    })
    assert 'Inline media viewer prepared' in result['content'][0]['text']
    assert 'data:audio/wav;base64,' in result['content'][1]['resource']['text']


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


def mock_artifact_transport(bridge, monkeypatch, artifact_updates=None, raw=None):
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY', 'fixture-key')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_BASE_URL', 'https://gateway.example.invalid/v1')
    content = json.dumps({'protein': PDB}).encode()
    artifact = {'artifact_id': OPERATION, 'size_bytes': len(content),
                'sha256': hashlib.sha256(content).hexdigest(), 'compression': 'none'}
    artifact.update(artifact_updates or {})
    envelope = {'schema': 'fs2-serve.nebius.ai/operation-artifact-result/v1',
                'content_type': 'application/json', 'artifact': artifact}
    requests = []
    class Opener:
        def open(self, request, timeout):
            assert timeout == 30
            assert request.get_header('Authorization') == 'Bearer fixture-key'
            requests.append(request.full_url)
            if request.full_url.endswith('/result'):
                return io.BytesIO(json.dumps(envelope).encode())
            assert request.full_url == f'https://gateway.example.invalid/v1/artifacts/{OPERATION}/content'
            return io.BytesIO(content if raw is None else raw)
    monkeypatch.setattr(bridge.urllib.request, 'build_opener', lambda *args: Opener())
    return requests


def test_native_artifact_result_is_verified_before_viewing(bridge, monkeypatch):
    requests = mock_artifact_transport(bridge, monkeypatch)
    result = bridge.call_viewer({'operation_id': OPERATION})
    assert '1 structure(s)' in result['content'][0]['text']
    assert PDB not in result['content'][0]['text']
    assert len(requests) == 2


@pytest.mark.parametrize('metadata', [
    {'size_bytes': 4 * 1024 * 1024 + 1}, {'size_bytes': True}, {'compression': 'gzip'},
    {'sha256': 'not-a-hash'}, {'artifact_id': 'https://outside.example.invalid/private'},
])
def test_unsupported_artifact_is_not_downloaded(bridge, monkeypatch, metadata):
    requests = mock_artifact_transport(bridge, monkeypatch, metadata)
    with pytest.raises(ValueError):
        bridge.get_result(OPERATION)
    assert len(requests) == 1


def test_native_artifact_hash_mismatch_is_not_rendered(bridge, monkeypatch):
    mock_artifact_transport(bridge, monkeypatch, {'sha256': '0' * 64})
    with pytest.raises(ValueError, match='verification'):
        bridge.call_viewer({'operation_id': OPERATION})


def test_native_artifact_response_cannot_exceed_byte_limit(bridge, monkeypatch):
    mock_artifact_transport(bridge, monkeypatch, raw=b'X' * (bridge.MAX_BYTES + 1))
    with pytest.raises(ValueError, match='4 MiB'):
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
    assert 'https://luma.com/5b82vwsa' not in landing  # General workbench, not the retired event.
    assert 'Reproduce a published result' in landing
    assert 'run Python, install packages' in landing
    assert 'Cloud account access is configured separately' in landing
    assert 'useAuth' not in landing  # No special admin-only/event-account branch.
