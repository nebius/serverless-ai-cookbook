"""Assemble existing research Markdown/CSV sections without changing calculations.

This checks document construction, not scientific truth or narrative accuracy.
No inference occurs. Original sources remain unchanged and are hash-linked.
"""
import argparse
import csv
from datetime import datetime
from decimal import Decimal
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re

from scientific_receipts import staged_output


def digest(data):
    return hashlib.sha256(data).hexdigest()


def cell(value):
    return html.escape(value, quote=False).replace('\\', '\\\\').replace('|', '\\|').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')


def numeric(value, name, *, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name}: expected a finite measured number, not a guessed replacement.')
    if minimum is not None and value < minimum:
        raise ValueError(f'{name}: value is below its valid minimum.')
    return value


def measurement_section(kind, data):
    """Schema-specific numerical rendering; never let an LLM relabel a unit."""
    document = json.loads(data)
    if not isinstance(document, dict):
        raise ValueError(f'{kind}: expected an object from the retained producer.')
    rows, limits = [], []
    def add(name, value, unit, source):
        rows.append({'measurement': name, 'value': value, 'unit': unit, 'source': source})
    if kind == 'operation-timing':
        body = document.get('structuredContent', document)
        if not isinstance(body, dict):
            raise ValueError('Operation timing envelope must contain an object.')
        for field, unit in [('elapsed_ms', 'ms'), ('elapsed_seconds', 's'),
                            ('duration_seconds', 's'), ('cold_start_seconds', 's'),
                            ('estimated_gpu_seconds', 'GPU·s (estimate)'),
                            ('reserved_gpu_seconds', 'GPU·s (reservation)')]:
            value = body.get(field)
            if value is not None:
                numeric(value, field, minimum=0)
            add(field, value, unit, field)
            if field == 'elapsed_ms':
                # Preserve the decimal telemetry value; conversion is explicit.
                add('model_reported_elapsed_seconds',
                    str(Decimal(str(value)) / 1000) if value is not None else None,
                    's', 'elapsed_ms / 1000; not service wall time')
        for name, start, end in [
            ('accepted_to_started', 'created_at', 'started_at'),
            ('started_to_completed', 'started_at', 'completed_at'),
            ('accepted_to_completed', 'created_at', 'completed_at')]:
            duration = None
            if body.get(start) is not None and body.get(end) is not None:
                first, last = [datetime.fromisoformat(body[key].replace('Z', '+00:00')) for key in (start, end)]
                if first.tzinfo is None or last.tzinfo is None:
                    raise ValueError('Timing timestamps require explicit timezone offsets.')
                duration = (last - first).total_seconds()
                numeric(duration, name, minimum=0)
            add(name, duration, 's', f'{end} minus {start}')
        limits = ['Reported model elapsed time, admission/activation wait, service interval and GPU reservations are separate measurements.',
                  'Accepted-to-started is not pure cold start. Missing phases remain unavailable; no GPU utilization or billing is inferred.']
    elif kind == 'recorded-export':
        if document.get('schema') != 'scientific-recorded-export/v1':
            raise ValueError('Expected scientific-recorded-export/v1, not an ad hoc scalar-count summary.')
        fields = document.get('fields')
        if not isinstance(fields, list) or not fields:
            raise ValueError('Recorded export needs its actual field metadata.')
        counts = {'f': 0, 'i': 0, 'u': 0, 'b': 0}
        names = set()
        rows_count = document.get('row_count')
        if type(rows_count) is not int or rows_count < 0:
            raise ValueError('Recorded row_count must be a nonnegative integer.')
        for field in fields:
            name, shape, dtype = field.get('name'), field.get('shape'), field.get('dtype')
            match = re.fullmatch(r'[<>=|]([fiub])[1-9][0-9]*', dtype or '')
            if not isinstance(name, str) or not name or name in names or not match:
                raise ValueError('Recorded export needs unique field names and explicit numeric dtypes.')
            names.add(name)
            if not isinstance(shape, list) or not shape or shape[0] != rows_count or any(type(x) is not int or x < 0 for x in shape):
                raise ValueError('Recorded field shape disagrees with row_count.')
            count = math.prod(shape)
            if type(field.get('scalar_values')) is not int or field['scalar_values'] != count:
                raise ValueError('Recorded field scalar count disagrees with its shape.')
            counts[match[1]] += count
            add(f'field:{name}', count, f'scalar values ({dtype})', f'fields/{len(names) - 1}/shape')
        total = sum(counts.values())
        if (type(document.get('scalar_values')) is not int or type(document.get('field_count')) is not int
                or document['scalar_values'] != total or document['field_count'] != len(fields)):
            raise ValueError('Recorded total/field count disagrees with actual field shapes.')
        add('rows', rows_count, 'rows', 'row_count')
        add('all_scalar_values', total, 'scalar values (all numeric and boolean fields)', 'sum of every field shape')
        add('floating_scalar_values', counts['f'], 'floating-point scalar values only', 'fields dtype f')
        add('integer_scalar_values', counts['i'] + counts['u'], 'integer scalar values', 'fields dtype i/u')
        add('boolean_scalar_values', counts['b'], 'boolean scalar values', 'fields dtype b')
        limits = ['Floating-point values are only a subset of the total; integer indexes/timestamps and booleans must not silently disappear.',
                  'This verifies metadata arithmetic and lineage, not raw export readback or physical action-label validity. The exporter supplies its separate byte-level readback evidence.']
    elif kind == 'rgb-statistics':
        results = document.get('results')
        if not isinstance(results, list) or not results:
            raise ValueError('RGB statistics need retained results with mean_rgb_float64.')
        roles = set()
        for result in results:
            role, means = result.get('role'), result.get('mean_rgb_float64')
            if not isinstance(role, str) or not role or role in roles or not isinstance(means, list) or len(means) != 3:
                raise ValueError('RGB statistics require unique roles and three explicit RGB channel means.')
            roles.add(role)
            for channel, value in zip('RGB', means):
                numeric(value, channel, minimum=0)
                if value > 255:
                    raise ValueError('RGB24 channel means must be in the 0–255 code-value range.')
                add(f'{role}.{channel}_mean', value, 'decoded RGB24 code value (0–255)', 'mean_rgb_float64')
            add(f'{role}.unweighted_RGB_mean', math.fsum(means) / 3,
                'decoded RGB24 code value; NOT luminance', 'arithmetic mean of the three retained channel means')
            proxy = result.get('weighted_rgb_601_proxy_float64')
            if proxy is not None:
                numeric(proxy, 'weighted RGB proxy', minimum=0)
            add(f'{role}.weighted_RGB_proxy', proxy, 'weighted RGB proxy; NOT physical luminance', 'weighted_rgb_601_proxy_float64')
        limits = ['These are retained decoded RGB code-value statistics, not a recomputation of the source video.',
                  'Unweighted RGB mean is not luminance. Even weighted gamma-encoded RGB is only a proxy; no photometric or physical-action validation is inferred.']
    elif kind == 'mindeval-runs':
        runs = document.get('data')
        if not isinstance(runs, list) or not runs:
            raise ValueError('MindEval source must contain nonempty saved data run records.')
        ids, axes, profiles, clinicians, profile_axes = set(), set(), set(), set(), set()
        scored = 0
        for run in runs:
            identity = run.get('id')
            if not isinstance(identity, str) or not identity or identity in ids:
                raise ValueError('MindEval run IDs must be present and unique; duplicate records are not independent consultations.')
            ids.add(identity)
            state = run.get('state', {})
            config = state.get('config', {})
            profile, clinician = config.get('profile_id'), config.get('clinician_model')
            if isinstance(profile, str) and profile:
                profiles.add(profile)
            if isinstance(clinician, str) and clinician:
                clinicians.add(clinician)
            judgment = (state.get('judgment') or {}).get('judgment')
            if judgment is None:
                add(f'{identity}.judgment', None, 'retained judgment', 'state/judgment/judgment')
                continue
            if not isinstance(judgment, dict) or not judgment:
                raise ValueError('MindEval judgment must be a nonempty named score mapping.')
            scored += 1
            for axis, value in judgment.items():
                if not isinstance(axis, str) or not axis.strip():
                    raise ValueError('MindEval criteria require nonempty names.')
                numeric(value, axis, minimum=1)
                if value > 6:
                    raise ValueError('MindEval score is outside the declared 1–6 scale.')
                axes.add(axis)
                if isinstance(profile, str) and profile:
                    profile_axes.add((profile, axis))
                add(f'{identity}.{axis}', value, 'judge score (1–6; uncalibrated)', 'state/judgment/judgment')
        for name, value, unit in [('consultations', len(ids), 'distinct retained run IDs'),
                                  ('scored_consultations', scored, 'runs with supplied judgment'),
                                  ('distinct_criteria', len(axes) if scored else None, 'observed criterion names'),
                                  ('distinct_profiles', len(profiles) or None, 'observed profile IDs'),
                                  ('distinct_clinicians', len(clinicians) or None, 'observed clinician model IDs'),
                                  ('profile_criterion_cells', len(profile_axes) if profile_axes else None, 'distinct observed (profile, criterion) pairs, NOT criteria')]:
            add(name, value, unit, 'actual retained runs and judgment keys')
        limits = ['Profile×criterion cells, distinct criteria, clinicians and consultations are different denominators.',
                  'No missing rows are fabricated. Uncalibrated stochastic judge scores do not establish a clinical winner, significance or independent replicates.']
    else:
        raise ValueError(f'Unsupported measurement section: {kind}.')
    lines = ['| Measurement | Value | Unit | Source / definition |\n', '| --- | ---: | --- | --- |\n']
    for row in rows:
        lines.append('| ' + ' | '.join(cell(str(row[key]) if row[key] is not None else 'unavailable')
            for key in ('measurement', 'value', 'unit', 'source')) + ' |\n')
    lines += ['\n', *('- ' + limit + '\n' for limit in limits)]
    return ''.join(lines), {'schema': 'scientific-ai/rendered-measurements/v1', 'kind': kind,
                           'measurements': rows, 'limitations': limits}


def assemble(title, sections, *, source_data=None):
    if not isinstance(title, str) or not title.strip() or len(title) > 160 or '\n' in title:
        raise ValueError('Use a nonempty one-line document title of at most160 characters.')
    if not isinstance(sections, list) or not 1 <= len(sections) <= 16:
        raise ValueError('Provide one to sixteen existing Markdown or CSV sections.')
    parts = [f'# {title}\n\n']
    provenance = []
    for index, section in enumerate(sections):
        label = section.get('title')
        if not isinstance(label, str) or not label.strip() or len(label) > 160 or '\n' in label:
            raise ValueError('Every section needs a nonempty one-line title.')
        source = Path(section['file'])
        data = source.read_bytes() if source_data is None else source_data[index]
        text = data.decode('utf-8')
        if not text.strip():
            raise ValueError(f'{label}: empty source is not a completed report section.')
        record = {'title': label, 'format': section['format'], 'source_file': str(source),
                  'source_size_bytes': len(data), 'source_sha256': digest(data)}
        parts.append(f'## {label}\n\n')
        if section['format'] == 'markdown':
            parts.append(text)  # Verbatim original UTF-8 text, including line endings.
            record['rendering'] = 'verbatim UTF-8 Markdown; scientific assertions not re-evaluated'
        elif section['format'] == 'csv':
            rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
            if not rows or not rows[0] or any(not column.strip() for column in rows[0]) or len(set(rows[0])) != len(rows[0]):
                raise ValueError(f'{label}: CSV needs distinct nonempty column headers.')
            if any(len(row) != len(rows[0]) for row in rows[1:]):
                raise ValueError(f'{label}: CSV row width differs from its header; no shifted columns accepted.')
            def render(row):
                return '| ' + ' | '.join(cell(value) for value in row) + ' |\n'
            parts += [render(rows[0]), render(['---'] * len(rows[0])), *(render(row) for row in rows[1:])]
            record.update(row_count=len(rows) - 1, column_count=len(rows[0]),
                          rendering='CSV values in original order, Markdown-escaped; no numeric recomputation or rounding')
        elif section['format'] in {'operation-timing', 'recorded-export', 'rgb-statistics', 'mindeval-runs'}:
            rendered, measurements = measurement_section(section['format'], data)
            parts.append(rendered)
            record.update(rendering='Schema-specific deterministic measurements; unavailable values are explicit',
                          measurements=measurements)
        else:
            raise ValueError('Unsupported report section format.')
        parts.append('\n\n')
        provenance.append(record)
    parts += ['## Document provenance\n\n',
              'Sections were assembled from retained files. This validates file lineage and table construction, not scientific truth, clinical validity or the accuracy of an optional narrative. No new model work was submitted.\n\n']
    for source in provenance:
        parts.append(f"- {source['title']}: {source['source_size_bytes']} bytes; SHA-256 `{source['source_sha256']}`.\n")
    output = ''.join(parts).encode('utf-8')
    return output, {'schema': 'scientific-ai/report-assembly/v1', 'sections': provenance,
        'report_size_bytes': len(output), 'report_sha256': digest(output),
        'scientific_claims_validated': False, 'inference_submitted': False}


def publish_bundle(manifest_file, output_dir):
    """Publish a complete source-bound document; never replace differing bytes.

    The durable worker owns output-directory selection and one stage writer.
    Completion is the last verified file, not an atomic directory rename.
    """
    manifest_file, output_dir = Path(manifest_file), Path(output_dir)
    manifest_bytes = manifest_file.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or set(manifest) != {'title', 'sections'}:
        raise ValueError('Report manifest must contain exactly title and sections.')
    sections = manifest['sections']
    if not isinstance(sections, list) or not 1 <= len(sections) <= 16:
        raise ValueError('Provide one to sixteen existing Markdown or CSV sections.')
    resolved, inputs = [], []
    for section in sections:
        if not isinstance(section, dict) or set(section) != {'title', 'format', 'file'}:
            raise ValueError('Each report section must contain exactly title, format and file.')
        source = Path(section['file'])
        source = source if source.is_absolute() else manifest_file.parent / source
        resolved.append({**section, 'file': str(source)})
        inputs.append(source.read_bytes())
    report, provenance = assemble(manifest['title'], resolved, source_data=inputs)
    helper = Path(__file__).read_bytes()
    provenance.update(manifest_sha256=digest(manifest_bytes), helper_sha256=digest(helper))
    files = {'report.md': report,
             'provenance.json': (json.dumps(provenance, indent=2, allow_nan=False) + '\n').encode(),
             'assembly-plan.json': manifest_bytes, 'helper.py': helper}
    for index, (section, data) in enumerate(zip(resolved, inputs)):
        extension = {'markdown': 'md', 'csv': 'csv'}.get(section['format'], 'json')
        files[f'sources/{index:03d}.{extension}'] = data
    completion = {'schema': 'scientific-ai/report-artifacts/v1', 'state': 'complete',
        'manifest_sha256': digest(manifest_bytes), 'helper_sha256': digest(helper),
        'section_count': len(sections), 'scientific_claims_validated': False,
        'inference_submitted': False, 'artifacts': [
            {'path': name, 'sha256': digest(data), 'size_bytes': len(data)}
            for name, data in sorted(files.items())]}
    # Serialize/validate all sections before touching output. Re-entry writes
    # only identical/missing files through the existing bucket-safe publisher.
    files['completion-manifest.json'] = (json.dumps(completion, indent=2, allow_nan=False) + '\n').encode()
    for name, data in files.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with staged_output(target) as staged:
            staged.path.write_bytes(data)
    return {'report_size_bytes': len(report), 'report_sha256': digest(report),
        'section_count': len(sections), 'inference_submitted': False,
        'completion_manifest': str(output_dir / 'completion-manifest.json'),
        'completion_manifest_sha256': digest(files['completion-manifest.json'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish_bundle(args.manifest, args.output_dir)))


if __name__ == '__main__':
    main()
