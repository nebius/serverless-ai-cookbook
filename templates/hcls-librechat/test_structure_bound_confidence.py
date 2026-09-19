"""The retained v57/04 confidence contract, without customer coordinate payloads."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from test_structure_analysis import analysis, COORDS, pdb, spec


METRICS = {'iptm': 0.0, 'plddt_mean': 0.720092236995697, 'ptm': 0.4071556031703949}


def fixture(tmp_path, prediction=None):
    prediction = prediction or pdb({'A': COORDS}).encode()
    row = {'metrics': METRICS.copy(), 'sample_index': 0, 'seed': 1,
           'structure': {'bytes': len(prediction), 'filename': 'unused-name.cif',
                         'sha256': hashlib.sha256(prediction).hexdigest()}, 'upstream_summary': None}
    document = {'schema': 'fs2.nebius.ai/structure-confidence/v1',
                'input_identity': {'artifact_id': 'retained-test-input', 'sha256': 'a' * 64},
                'model_revision': 'c6c7958d63f5f2f1f0fed0bb9462316f8ccceea6',
                'runtime_id': 'esmfold2-fast', 'samples_per_seed': 1, 'seeds': [1], 'results': [row]}
    return write_fixture(tmp_path, prediction, document)


def write_fixture(tmp_path, prediction, document):
    raw = json.dumps(document, indent=1).encode() + b'\n'
    entries = []
    for index, (data, semantic, media) in enumerate([
            (prediction, 'protein-structure-pdb/v1', 'chemical/x-pdb'),
            (raw, 'structure-confidence-json/v1', 'application/json')]):
        (tmp_path / f'output-{index:02d}.artifact').write_bytes(data)
        entries.append({'semantic_type': semantic, 'artifact': {'compression': 'none',
            'media_type': media, 'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data)}})
    manifest = {'schema': 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1',
                'manifest_id': 'one-retained-operation', 'entries': entries}
    path = tmp_path / 'output-manifest.json'
    path.write_text(json.dumps(manifest))
    envelope = {'structure': prediction.decode(), 'retained_source_result': {'manifest': manifest,
        'confidence_artifacts': [document],
        'confidence_artifact_sources': [{'manifest_entry_index': 1, 'raw_json': raw.decode()}]}}
    return prediction, document, manifest, envelope, path


@pytest.mark.parametrize('kind', ['manifest', 'envelope'])
def test_exact_native_values_scale_zero_and_sample_source_are_preserved(tmp_path, kind):
    prediction, document, manifest, envelope, path = fixture(tmp_path)
    fields, provenance = analysis.bound_confidence(manifest if kind == 'manifest' else envelope,
                                                   prediction, source_path=path)
    assert fields == {f'confidence_artifacts[1].results[0].metrics.{k}': v for k, v in METRICS.items()}
    assert provenance['seed'] == 1 and provenance['sample_index'] == 0
    assert provenance['structure_sha256'] == hashlib.sha256(prediction).hexdigest()
    assert provenance['confidence_artifact_sha256'] == hashlib.sha256((tmp_path / 'output-01.artifact').read_bytes()).hexdigest()
    assert provenance['model_revision'] == document['model_revision']
    assert 'not determinism' in provenance['scope']
    assert analysis.confidence_fields(document) == {}  # no unbound all-sample recursion


def test_other_sample_is_not_aggregated_and_order_is_not_selection(tmp_path):
    prediction, document, *_ = fixture(tmp_path)
    other = copy.deepcopy(document['results'][0])
    other['structure']['sha256'] = 'f' * 64
    other['metrics']['plddt_mean'] = 99.0
    document['results'].insert(0, other)
    prediction, _, manifest, _, path = write_fixture(tmp_path, prediction, document)
    fields, _ = analysis.bound_confidence(manifest, prediction, source_path=path)
    assert fields['confidence_artifacts[1].results[1].metrics.plddt_mean'] == METRICS['plddt_mean']
    assert 99.0 not in fields.values()


@pytest.mark.parametrize('defect', ['absent-row', 'duplicate-row', 'wrong-size', 'seed', 'sample', 'nonfinite', 'boolean'])
def test_unproven_or_invalid_samples_fail_closed(tmp_path, defect):
    prediction, document, *_ = fixture(tmp_path)
    row = document['results'][0]
    if defect == 'absent-row':
        row['structure']['sha256'] = '0' * 64
    elif defect == 'duplicate-row':
        document['results'].append(copy.deepcopy(row))
    elif defect == 'wrong-size':
        row['structure']['bytes'] += 1
    elif defect == 'seed':
        row['seed'] = 8
    elif defect == 'sample':
        row['sample_index'] = 1
    else:
        row['metrics']['ptm'] = float('nan') if defect == 'nonfinite' else True
    prediction, _, manifest, _, path = write_fixture(tmp_path, prediction, document)
    with pytest.raises(ValueError):
        analysis.bound_confidence(manifest, prediction, source_path=path)


@pytest.mark.parametrize('defect', ['different-coordinate', 'duplicate-coordinate', 'tampered-confidence', 'missing-raw-envelope', 'different-envelope-coordinate'])
def test_exact_manifest_and_envelope_byte_identity_is_required(tmp_path, defect):
    prediction, _, manifest, envelope, path = fixture(tmp_path)
    evidence = manifest
    if defect == 'different-coordinate':
        prediction += b'REMARK changed\n'
    elif defect == 'duplicate-coordinate':
        manifest['entries'].append(copy.deepcopy(manifest['entries'][0]))
    elif defect == 'tampered-confidence':
        (tmp_path / 'output-01.artifact').write_bytes(b'{}')
    else:
        evidence = envelope
        if defect == 'missing-raw-envelope':
            del envelope['retained_source_result']['confidence_artifact_sources']
        else:
            envelope['structure'] += 'REMARK changed\n'
    with pytest.raises(ValueError):
        analysis.bound_confidence(evidence, prediction, source_path=path)


def test_absent_confidence_remains_unavailable_not_zero(tmp_path):
    prediction, _, manifest, _, path = fixture(tmp_path)
    manifest['entries'].pop()
    fields, provenance = analysis.bound_confidence(manifest, prediction, source_path=path)
    assert fields == {} and provenance['status'] == 'unavailable_no_confidence_artifact'


def test_cli_explicit_manifest_renders_exact_values_and_keeps_geometry(tmp_path):
    prediction, _, _, _, path = fixture(tmp_path)
    reference = tmp_path / 'reference.pdb'
    reference.write_bytes(prediction)
    for name, extra in [('plain', []), ('bound', ['--confidence-result', str(path)])]:
        subprocess.run([sys.executable, spec.origin, '--reference', str(reference),
            '--prediction', str(tmp_path / 'output-00.artifact'), '--output-dir', str(tmp_path / name), *extra],
            check=True, capture_output=True)
    plain, bound = [json.loads((tmp_path / name / 'metrics.json').read_bytes()) for name in ('plain', 'bound')]
    for key in ('global_ca_rmsd_angstrom', 'chains', 'mapped_residues', 'correspondence_method'):
        assert plain[key] == bound[key]
    assert (tmp_path / 'plain/residue-mapping.json').read_bytes() == (tmp_path / 'bound/residue-mapping.json').read_bytes()
    report = (tmp_path / 'bound/report.md').read_text()
    assert all(str(value) in report for value in METRICS.values())
    assert 'seed `1`, sample `0`' in report and 'unchanged native scale' in report
    assert bound['provenance']['confidence_result_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_exact_retained_v57_04_artifacts_when_explicitly_supplied(tmp_path):
    root = os.environ.get('SCIENTIFIC_RETAINED_V57_04')
    if not root:
        pytest.skip('Private original payload remains outside Git; supply its exact archived final directory.')
    root = Path(root)
    manifest = root / 'steps/esm-refold/operation/output-manifest.json'
    prediction = (manifest.parent / 'output-00.artifact').read_bytes()
    fields, proof = analysis.bound_confidence(json.loads(manifest.read_bytes()), prediction, source_path=manifest)
    assert proof['structure_sha256'] == '717539fd871d3e540aa73138215400624ae78e111af1a9c06a221b0a786d2f9f'
    assert proof['confidence_artifact_sha256'] == 'a8411c543d30c24f103f4e772f973284442b22acbf11f9ce442691a08eb79dc7'
    assert fields == {f'confidence_artifacts[1].results[0].metrics.{k}': v for k, v in METRICS.items()}
    original = root / 'steps/structure-compare/generation-e4ce79c710394ae3abf6a80b2eac4d25'
    correspondence = root / 'steps/correspondence/generation-d81b7573f20a46619e612b733bd491ba'
    subprocess.run([sys.executable, spec.origin, '--reference', str(correspondence / 'reference.pdb'),
        '--prediction', str(correspondence / 'prediction.structure'), '--residue-map', str(correspondence / 'residue-map.json'),
        '--confidence-result', str(manifest), '--output-dir', str(tmp_path / 'reassessment')], check=True, capture_output=True)
    reassessed = json.loads((tmp_path / 'reassessment/metrics.json').read_bytes())
    saved = json.loads((original / 'metrics.json').read_bytes())
    assert reassessed['global_ca_rmsd_angstrom'] == saved['global_ca_rmsd_angstrom']
    assert reassessed['chains'] == saved['chains']
    assert (tmp_path / 'reassessment/residue-mapping.json').read_bytes() == (original / 'residue-mapping.json').read_bytes()

