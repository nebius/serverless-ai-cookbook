"""Offline public recipe wiring/provenance, not model inference or cloud qualification."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'shared-runtime'


def test_canonical_runtime_bytes_and_license_preserved():
    manifest = json.loads((SHARED / 'source-manifest.json').read_text())
    assert manifest['source_commit'] == 'b193b5c65ed1ae0a11cb9c32b8be88c0c6c02ced'
    assert manifest['runtime_modules'] == 17 and manifest['unit_test_files'] == 13
    assert manifest['source_modified'] is False and manifest['weights_included'] is False
    assert len(manifest['files']) == 31
    for row in manifest['files']:
        data = (SHARED / row['path']).read_bytes()
        assert len(data) == row['bytes']
        assert hashlib.sha256(data).hexdigest() == row['sha256']


def test_no_private_dependency_or_packaged_demo_weights():
    dockerfile = (SHARED / 'Dockerfile').read_text()
    assert 'ARG TRAINING_IMAGE\nFROM ${TRAINING_IMAGE}' in dockerfile
    assert 'cr.eu-north' not in dockerfile
    assert '--from=model_bundle /model.nemo' in dockerfile
    assert '--from=model_bundle /MODEL_CARD.md' in dockerfile
    assert '--from=model_bundle /MODEL_LICENSE' in dockerfile
    assert 'sha256sum -c -' in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert 'FS2_STT_REQUIRE_GATEWAY_AUTH=1' in dockerfile
    assert 'fs2_speech.serverless_entrypoint' in dockerfile
    assert 'CMD []' in dockerfile  # clear training-image CMD serve
    assert not list(SHARED.rglob('*.nemo'))


def test_default_deny_context_has_explicit_ancestor_reexclusions():
    lines = (SHARED / 'Dockerfile.dockerignore').read_text().splitlines()
    assert lines[0] == '**'
    assert lines.index('!src/') < lines.index('src/*') < lines.index('!src/fs2_speech/')
    assert lines.index('!src/fs2_speech/') < lines.index('src/fs2_speech/*') < lines.index('!src/fs2_speech/*.py')
    for suffix in ['**/__pycache__', '**/*.pyc', '**/.env*', '**/*secret*', '**/*credential*']:
        assert suffix in lines


def test_english_profile_retains_native_math():
    text = (SHARED / 'Dockerfile').read_text()
    profile = json.loads(re.search(r"FS2_SPEECH_PROFILE_JSON='([^']+)'", text).group(1))
    assert profile == {'model': 'nemotron-speech-en-0.6b', 'chunk_size_ms': 560,
        'strip_language_tags': True, 'decoding': 'greedy_batch', 'beam_size': 4,
        'precision': 'float32', 'confidence': False, 'cuda_graphs': False}


def test_shared_primary_path_and_unchanged_clinical_limits():
    readme = (ROOT / 'README.md').read_text()
    shared = (ROOT / 'SHARED_SERVING.md').read_text()
    results = (ROOT / 'SELECTED_ENGLISH_RESULTS.md').read_text()
    assert 'Historical single-active diagnostic Endpoint' in readme
    assert 'shared Serverless serving' in readme
    assert 'no unrestricted-customer promotion mode' in shared
    assert 'not a production capacity certificate' in shared
    assert '**REJECTED**' in results and 'No clinician adjudication or human listening' in results
    assert '7.0067%' in results and '12.0952%' in results
    for forbidden in ['project-e00rene', 'aiendpoint-e00', 'storagebucket-e00', 'mbsec-e00', '/home/tux', '.tunnel.applications.']:
        assert forbidden not in readme + shared + results
