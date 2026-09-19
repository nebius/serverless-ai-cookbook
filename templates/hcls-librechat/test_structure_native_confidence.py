"""Exact native confidence arrays, including the retained v56 Boltz result shape."""
import hashlib
import json
import subprocess
import sys

import pytest

from test_structure_analysis import analysis, COORDS, pdb, spec


@pytest.mark.parametrize('arrays', [
    {'confidence_scores': [0.8958471417427063], 'ptm_scores': [0.9148377180099487]},
    {'confidence_scores': [0.8, 0.3, 0.8], 'ptm_scores': [1, 0, 0.5]},
    {'confidence_scores': [], 'ptm_scores': []},
])
def test_native_arrays_preserve_all_values_order_types_without_averaging(arrays):
    measured = analysis.confidence_fields({'result': arrays})
    assert set(measured) == {'result.confidence_scores', 'result.ptm_scores'}
    for name, values in arrays.items():
        field = measured['result.' + name]
        assert field['values'] == values and field['count'] == len(values)
        assert [type(x) for x in field['values']] == [type(x) for x in values]
        assert 'mean' not in field and 'not inferred seeds or ranks' in field['ordering']


@pytest.mark.parametrize('invalid', [True, 0.8, '0.8', [True], [float('nan')], [float('inf')], [[0.8]], {'value':0.8}])
def test_invalid_native_array_is_not_a_confidence_measurement(invalid):
    assert analysis.confidence_fields({'confidence_scores': invalid, 'ptm_scores': invalid}) == {}


def test_cli_links_full_arrays_to_exact_result_and_request_hashes(tmp_path):
    reference = tmp_path / 'reference.pdb'
    reference.write_text(pdb({'A': COORDS}))
    result = tmp_path / 'result.json'
    arrays = {'confidence_scores':[0.8958471417427063], 'ptm_scores':[0.9148377180099487]}
    result.write_text(json.dumps({'structures':[reference.read_text()], **arrays}))
    request = tmp_path / 'original.json'
    request.write_bytes(b'{"diffusion_samples":1,"recycling_steps":3,"sampling_steps":200}\n')
    output = tmp_path / 'analysis'
    subprocess.run([sys.executable, spec.origin, '--reference',str(reference),'--result',str(result),
        '--request-file',str(request),'--output-dir',str(output)], check=True,capture_output=True)
    metrics = json.loads((output/'metrics.json').read_bytes())
    assert metrics['global_ca_rmsd_angstrom'] < 1e-5
    for name, values in arrays.items():
        assert metrics['model_confidence_not_reference_agreement'][name]['values'] == values
        assert json.dumps(values) in (output/'report.md').read_text()
    assert metrics['provenance']['result_sha256'] == hashlib.sha256(result.read_bytes()).hexdigest()
    assert metrics['provenance']['request_sha256'] == hashlib.sha256(request.read_bytes()).hexdigest()
    assert metrics['sampling_provenance']['structure_index_is_seed'] is False
    assert 'not inferred seeds/ranks' in (output/'report.md').read_text()
