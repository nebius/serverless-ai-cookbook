"""Numerical, sample-correspondence and original-reference regressions."""
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('aging_analysis', ROOT / 'aging-analysis.py')
aging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aging)


def cohort(tmp_path, label, request, result):
    inputs, outputs = tmp_path / (label + '.input.json'), tmp_path / (label + '.result.json')
    inputs.write_text(json.dumps(request)); outputs.write_text(json.dumps(result))
    return {'label': label, 'input_file': str(inputs), 'result_file': str(outputs)}


def pheno(tmp_path, *, prediction=41.90792243378, version=aging.PHENO_VERSION):
    sample = {'sample_id': 'person', 'age_years': 50, 'albumin_g_l': 45, 'creatinine_umol_l': 80,
        'glucose_mmol_l': 5, 'c_reactive_protein_mg_dl': 0.1, 'lymphocyte_percent': 30,
        'mean_cell_volume_fl': 90, 'red_cell_distribution_width_percent': 13,
        'alkaline_phosphatase_u_l': 70, 'white_blood_cell_count_10e3_per_ul': 6}
    result = {'model_id': 'phenoage', 'model_version': version,
        'predictions': [{'sample_id': 'person', 'phenotypic_age_years': prediction}], 'sample_count': 1}
    return cohort(tmp_path, 'published-synthetic', {'samples': [sample]}, result)


def test_declared_published_formula_recomputed_not_trusted(tmp_path):
    result = aging.analyze('phenoage', [pheno(tmp_path)], coefficient_version=aging.PHENO_VERSION)
    assert result['all_numerical_checks_pass'] is True
    assert result['row_count'] == len(result['rows']) == 1
    assert result['rows'][0]['independent_age_years'] == pytest.approx(41.90792243378, abs=1e-10)
    bad = aging.analyze('phenoage', [pheno(tmp_path, prediction=51.52728733548)], coefficient_version=aging.PHENO_VERSION)
    assert bad['all_numerical_checks_pass'] is False
    assert bad['rows'][0]['absolute_error_years'] > 9


def test_version_crp_and_exact_result_ids_are_explicit(tmp_path):
    c = pheno(tmp_path)
    with pytest.raises(ValueError, match='Explicit coefficient_version'):
        aging.analyze('phenoage', [c])
    with pytest.raises(ValueError, match='model_id/model_version'):
        aging.analyze('phenoage', [pheno(tmp_path, version='another-formula')], coefficient_version=aging.PHENO_VERSION)
    c = pheno(tmp_path)
    original = json.loads(Path(c['input_file']).read_text())
    original['samples'][0]['c_reactive_protein_mg_dl'] = 0
    Path(c['input_file']).write_text(json.dumps(original))
    with pytest.raises(ValueError, match='Raw CRP'):
        aging.analyze('phenoage', [c], coefficient_version=aging.PHENO_VERSION)
    c = pheno(tmp_path)
    result = json.loads(Path(c['result_file']).read_text())
    result['predictions'][0]['sample_id'] = 'not-the-submitted-person'
    Path(c['result_file']).write_text(json.dumps(result))
    with pytest.raises(ValueError, match='sample IDs'):
        aging.analyze('phenoage', [c], coefficient_version=aging.PHENO_VERSION)


def test_original_h5_order_and_selu_are_not_sorted_weight_groups(tmp_path):
    import h5py
    h5 = tmp_path / 'ordered.h5'
    layers = [
        {'class_name': 'InputLayer', 'config': {'name': 'input'}},
        {'class_name': 'Dense', 'config': {'name': 'z_first', 'activation': 'linear'}},
        {'class_name': 'Activation', 'config': {'name': 'activation', 'activation': 'selu'}},
        {'class_name': 'Dense', 'config': {'name': 'a_last', 'activation': 'linear'}},
    ]
    with h5py.File(h5, 'w') as model:
        model.attrs['model_config'] = json.dumps({'config': {'layers': layers}})
        for name, kernel, bias in [('z_first', [[2.]], [-3.]), ('a_last', [[4.]], [5.])]:
            group = model.create_group('model_weights/' + name)
            group.attrs['weight_names'] = ['kernel:0', 'bias:0']
            group.create_dataset('kernel:0', data=kernel); group.create_dataset('bias:0', data=bias)
    evaluator, _ = aging.reference_module()
    actual = evaluator.altumage_reference(h5, np.array([[1.], [2.]]))
    expected = [1.0507009873554805 * 1.6732632423543772 * np.expm1(-1) * 4 + 5,
                1.0507009873554805 * 1 * 4 + 5]
    assert actual == pytest.approx(expected)


@pytest.mark.skipif(not os.getenv('AGING_REFERENCE_DIR'), reason='Pinned publication asset integration test requires prepared assets')
def test_pinned_real_altum_cohorts_reordering_missingness_and_one_overlap(tmp_path):
    root = Path(os.environ['AGING_REFERENCE_DIR'])
    cases_path = Path(os.environ['AGING_CASES_FILE'])
    corpus = json.loads(cases_path.read_text())
    cases = corpus['cases'] if isinstance(corpus, dict) else corpus
    selected = [c for c in cases if c['model_id'] == 'altumage' and (
        c['case_id'] == 'altumage-published-0-complete' or 'reversed-columns' in c['case_id'] or 'missing-1pct' in c['case_id'])]
    assert len(selected) == 3
    cohorts = []
    for case in selected:
        expected = case['expected']
        result = {'model_id': 'altumage', 'model_version': aging.ALTUM_VERSION,
            'predictions': [{'sample_id': sample['sample_id'],
                'predicted_chronological_age_years': expected['reference_predictions'][sample['sample_id']],
                'imputed_cpg_count': expected['imputed_counts'][sample['sample_id']]} for sample in case['arguments']['samples']]}
        cohorts.append(cohort(tmp_path, case['case_id'], case['arguments'], result))
    checked = aging.analyze('altumage', cohorts, assets=root)
    assert checked['all_numerical_checks_pass'] is True
    assert len(checked['rows']) == 33
    one = next(p for p in checked['overlaps'] if '0-complete' in p['left'] and 'reversed-columns' in p['right'])
    assert one['common_sample_count'] == 1 and one['right_count'] == 16
    assert all(p['feature_order_invariance_eligible'] for p in one['pairs'])
    changed = next(p for p in checked['overlaps'] if 'reversed-columns' in p['left'] and 'missing-1pct' in p['right'])
    assert not any(p['feature_order_invariance_eligible'] for p in changed['pairs'])
    request = json.loads(Path(cohorts[0]['input_file']).read_text())
    request['cpg_sites'][0] = request['cpg_sites'][1]
    Path(cohorts[0]['input_file']).write_text(json.dumps(request))
    with pytest.raises(ValueError, match='20,318 original CpGs'):
        aging.analyze('altumage', cohorts[:1], assets=root)
