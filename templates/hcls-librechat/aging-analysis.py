"""Independent, provenance-linked numerical checks of saved aging App results.

Reuses the qualification evaluator, not the hosted model implementation.
No model requests, new model architecture, or clinical validity claim.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import numpy as np

PHENO_VERSION = 'levine-2018-supplement-rounded-v1'
ALTUM_VERSION = '696c477dac9b7641bf283c48af1cc9bb0a0803a3'
ALTUM_H5_SHA256 = '2db4011115c3f877746d6dd722045da74055d25e8803368a1679d0dbaafe1846'
SUPPLEMENT = 'https://cdn.aging-us.com/article/101414/supplementary/SD1/0/aging-v10i4-101414-supplementary-material-SD1.pdf'
PHENO_FIELDS = ('age_years', 'albumin_g_l', 'creatinine_umol_l', 'glucose_mmol_l',
    'c_reactive_protein_mg_dl', 'lymphocyte_percent', 'mean_cell_volume_fl',
    'red_cell_distribution_width_percent', 'alkaline_phosphatase_u_l', 'white_blood_cell_count_10e3_per_ul')


def reference_module():
    here = Path(__file__).parent
    source = here / 'qualification_evaluators.py'
    if not source.exists():
        source = here / 'scripts/qualification/evaluators.py'
    spec = importlib.util.spec_from_file_location('aging_independent_reference', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, hashlib.sha256(source.read_bytes()).hexdigest()


def read_json(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), {'path': str(path), 'size_bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def unwrap(result):
    # Accommodate saved MCP envelopes as well as the native client's raw result.
    if isinstance(result, dict) and 'structuredContent' in result:
        result = result['structuredContent']
    if not isinstance(result, dict) or not isinstance(result.get('predictions'), list):
        raise ValueError('Expected the actual completed aging result with predictions; not a request schema or text summary')
    return result


def keyed(rows, name):
    if not isinstance(rows, list) or not rows:
        raise ValueError(f'{name} must contain a nonempty sample list')
    result = {}
    for row in rows:
        identifier = row.get('sample_id') if isinstance(row, dict) else None
        if not isinstance(identifier, str) or not identifier or identifier in result:
            raise ValueError(f'{name} requires unique nonempty sample_id values')
        result[identifier] = row
    return result


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def altum_assets(root):
    manifest, _ = read_json(root / 'manifest.json')
    if manifest.get('source_revision') != ALTUM_VERSION:
        raise ValueError('AltumAge reference revision is not the declared pinned original model')
    if manifest.get('runtime_artifacts', {}).get('AltumAge.h5') != ALTUM_H5_SHA256:
        raise ValueError('AltumAge H5 must be the checksum-pinned original artifact, not a converted network')
    for name in ('preprocessing.json', 'AltumAge.h5'):
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != manifest['runtime_artifacts'][name]:
            raise ValueError(f'AltumAge reference checksum mismatch: {name}')
    prep, _ = read_json(root / 'preprocessing.json')
    if len(prep['cpgs']) != 20318 or len(set(prep['cpgs'])) != 20318:
        raise ValueError('Reference must contain the original 20,318 distinct CpGs')
    return manifest, prep


def analyze(model, cohorts, *, assets=None, coefficient_version=None, reference_ages=None):
    if model not in {'phenoage', 'altumage'} or not 1 <= len(cohorts) <= 8:
        raise ValueError('Choose phenoage or altumage and one to eight explicitly labelled cohorts')
    evaluator, evaluator_hash = reference_module()
    version = PHENO_VERSION if model == 'phenoage' else ALTUM_VERSION
    if model == 'phenoage' and coefficient_version != PHENO_VERSION:
        raise ValueError('Explicit coefficient_version=levine-2018-supplement-rounded-v1 is required; other implementations are not interchangeable')
    assets_manifest = prep = None
    if model == 'altumage':
        assets_manifest, prep = altum_assets(Path(assets))
    rows, cohort_reports, seen_labels, comparable = [], [], set(), {}
    for cohort in cohorts:
        label = cohort.get('label')
        if not isinstance(label, str) or not label or label in seen_labels:
            raise ValueError('Cohort labels must be unique nonempty strings')
        seen_labels.add(label)
        request, input_provenance = read_json(cohort['input_file'])
        result, output_provenance = read_json(cohort['result_file'])
        result = unwrap(result)
        if result.get('model_id') != model or result.get('model_version') != version:
            raise ValueError(f'{label}: saved result model_id/model_version differs from the explicit independent method')
        samples, predictions = keyed(request.get('samples'), 'input'), keyed(result['predictions'], 'result')
        if samples.keys() != predictions.keys() or result.get('sample_count', len(predictions)) != len(predictions):
            raise ValueError(f'{label}: result sample IDs/count differ from the submitted input')
        ids = list(samples)
        normalized, imputed = {}, {}
        if model == 'phenoage':
            reference = []
            for identifier, sample in samples.items():
                values = {field: finite_number(sample.get(field), f'{identifier}.{field}') for field in PHENO_FIELDS}
                if values['c_reactive_protein_mg_dl'] <= 0:
                    raise ValueError('Raw CRP must be positive mg/dL; no implicit floor, log or unit conversion')
                normalized[identifier] = values
                reference.append(evaluator.phenoage_reference(values))
        else:
            cpgs = request.get('cpg_sites')
            if not isinstance(cpgs, list) or len(cpgs) != 20318 or len(set(cpgs)) != 20318 or set(cpgs) != set(prep['cpgs']):
                raise ValueError(f'{label}: input must name exactly the 20,318 original CpGs')
            positions = {name: index for index, name in enumerate(cpgs)}
            order = [positions[name] for name in prep['cpgs']]
            values = []
            for identifier, sample in samples.items():
                beta = sample.get('beta_values')
                if not isinstance(beta, list) or len(beta) != 20318:
                    raise ValueError(f'{identifier}: beta_values must be a 20,318-element list')
                for value in beta:
                    if value is not None and not 0 <= finite_number(value, 'beta value') <= 1:
                        raise ValueError('Beta values must lie in [0,1]')
                values.append([beta[index] for index in order])
                normalized[identifier] = {'missing_values': request.get('missing_values', 'error'), 'ordered_beta_values': values[-1]}
            value = np.asarray(values, dtype=np.float64)
            missing = np.isnan(value)
            if missing.any() and request.get('missing_values', 'error') != 'reference_median':
                raise ValueError('Null beta values require explicitly declared reference_median imputation')
            if request.get('missing_values', 'error') not in {'error', 'reference_median'}:
                raise ValueError('Unknown missing-value policy')
            center, scale = np.asarray(prep['center']), np.asarray(prep['scale'])
            imputed = dict(zip(ids, missing.sum(axis=1).tolist()))
            scaled = (np.where(missing, center, value) - center) / scale
            reference = evaluator.altumage_reference(Path(assets) / 'AltumAge.h5', scaled)
        cohort_rows = []
        field = 'phenotypic_age_years' if model == 'phenoage' else 'predicted_chronological_age_years'
        tolerance = 1e-7 if model == 'phenoage' else 0.002
        for identifier, expected in zip(ids, reference, strict=True):
            actual = finite_number(predictions[identifier].get(field), field)
            expected = finite_number(float(expected), 'independent reference')
            measured = {'cohort': label, 'sample_id': identifier, 'hosted_age_years': actual,
                'independent_age_years': expected, 'absolute_error_years': abs(actual - expected),
                'within_numerical_tolerance': abs(actual - expected) <= tolerance,
                'normalized_input_sha256': hashlib.sha256(json.dumps(normalized[identifier], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()}
            if model == 'altumage':
                measured['expected_imputed_cpg_count'] = imputed[identifier]
                measured['reported_imputed_cpg_count'] = predictions[identifier].get('imputed_cpg_count')
                measured['imputation_count_matches'] = measured['reported_imputed_cpg_count'] == imputed[identifier]
            if reference_ages and identifier in reference_ages:
                age = finite_number(reference_ages[identifier], 'provided reference age')
                measured.update(provided_reference_age_years=age, absolute_label_error_years=abs(actual - age))
            cohort_rows.append(measured)
        rows.extend(cohort_rows)
        comparable[label] = {row['sample_id']: row for row in cohort_rows}
        cohort_reports.append({'label': label, 'sample_count': len(ids), 'input': input_provenance,
            'result': output_provenance, 'absolute_tolerance_years': tolerance,
            'maximum_absolute_numerical_error_years': max(row['absolute_error_years'] for row in cohort_rows),
            'all_numerical_checks_pass': all(row['within_numerical_tolerance'] and row.get('imputation_count_matches', True) for row in cohort_rows)})
    overlaps = []
    labels = list(comparable)
    for i, left in enumerate(labels):
        for right in labels[i + 1:]:
            common = sorted(comparable[left].keys() & comparable[right].keys())
            paired = []
            for identifier in common:
                a, b = comparable[left][identifier], comparable[right][identifier]
                same = a['normalized_input_sha256'] == b['normalized_input_sha256']
                paired.append({'sample_id': identifier, 'same_normalized_input_and_policy': same,
                    'hosted_age_difference_years': b['hosted_age_years'] - a['hosted_age_years'],
                    'feature_order_invariance_eligible': model == 'altumage' and same})
            overlaps.append({'left': left, 'right': right, 'left_count': len(comparable[left]),
                'right_count': len(comparable[right]), 'common_sample_count': len(common), 'pairs': paired})
    return {'schema': 'scientific-aging-analysis/v1', 'model_id': model, 'model_version': version,
        'method': 'Independent 60-digit Decimal published supplement equations' if model == 'phenoage'
            else 'Independent float64 NumPy inference in original Keras model_config layer order, including SELU and BatchNormalization; original robust scaler and named-CpG alignment',
        'evaluator_sha256': evaluator_hash, 'reference_assets': assets_manifest,
        'primary_source': SUPPLEMENT if model == 'phenoage' else f'https://github.com/rsinghlab/AltumAge/tree/{ALTUM_VERSION}',
        'inference_submitted': False, 'cohorts': cohort_reports, 'rows': rows, 'overlaps': overlaps,
        'all_numerical_checks_pass': all(c['all_numerical_checks_pass'] for c in cohort_reports),
        'limitations': ['Numerical agreement and feature-order invariance are not biological or clinical validation.',
            'Known example training/test membership is not established; supplied ages are descriptive labels, not a held-out accuracy benchmark.',
            'PhenoAge rounded-v1 is distinct from DNAm PhenoAge, higher-precision BioAge coefficients and pyaging0.5.2 alternate mortality conversion; none is silently substituted.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True, choices=['phenoage', 'altumage'])
    parser.add_argument('--cohorts', type=Path, required=True)
    parser.add_argument('--coefficient-version')
    parser.add_argument('--reference-assets', type=Path, default=Path(__file__).with_name('aging-reference'))
    parser.add_argument('--reference-ages', type=Path)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    cohorts, _ = read_json(args.cohorts)
    ages, ages_source = read_json(args.reference_ages) if args.reference_ages else (None, None)
    if ages is not None and not isinstance(ages, dict):
        raise ValueError('reference_ages must map exact sample_id strings to numeric years')
    result = analyze(args.model, cohorts, assets=args.reference_assets, coefficient_version=args.coefficient_version, reference_ages=ages)
    result['reference_ages_source'] = ages_source
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    fields = list(dict.fromkeys(field for row in result['rows'] for field in row))
    with (args.output_dir / 'rows.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(result['rows'])
    lines = [f'# {args.model} independent numerical check', '', result['method'], '',
        f"Declared version: {result['model_version']}", f"All numerical checks pass: {result['all_numerical_checks_pass']}", '',
        '| Cohort | Samples | Maximum numerical error (years) | Checks pass |', '|---|---:|---:|---|']
    lines.extend(f"| {c['label']} | {c['sample_count']} | {c['maximum_absolute_numerical_error_years']:.12g} | {c['all_numerical_checks_pass']} |" for c in result['cohorts'])
    for overlap in result['overlaps']:
        lines.extend(['', f"{overlap['left']} vs {overlap['right']}: {overlap['common_sample_count']} overlapping sample IDs, from {overlap['left_count']} and {overlap['right_count']} rows. Only exact matching normalized inputs/policies qualify as feature-order comparisons."])
    lines += ['', 'Full sample-level values and input/result hashes are in metrics.json and rows.csv.', '', *result['limitations']]
    (args.output_dir / 'report.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'analysis_completed': True, 'all_numerical_checks_pass': result['all_numerical_checks_pass'], 'rows': len(result['rows']), 'inference_submitted': False}))


if __name__ == '__main__':
    main()
