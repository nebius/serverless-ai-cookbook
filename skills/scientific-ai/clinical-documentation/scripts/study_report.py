#!/usr/bin/env python3
"""Offline, versioned speech metrics and source-selection accounting; no model calls.

These are lexical/structural measurements, not clinical correctness or completeness.
Existing transcripts, clinical drafts, and historical scoring regimes are unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

SCHEMA = 'clinical-study-report/v1'
NORMALIZATION = 'casefold-annotation-edge-punctuation/v1'
EDGE_PUNCTUATION = '.,;:!?()[]{}\'"’‘“”-'
METHOD = {
    'id': NORMALIZATION,
    'reference_annotations': 'Replace <UNSURE>, </UNSURE>, <UNIN/> with spaces; retain uncertain inner words.',
    'both_texts': 'Unicode casefold; split on whitespace; strip the exact edge_punctuation characters; discard empty tokens.',
    'edge_punctuation': EDGE_PUNCTUATION,
    'not_performed': 'No Unicode normalization, internal punctuation splitting, contraction expansion, number mapping, translation, or stemming.',
    'alignment': 'Unit-cost word Levenshtein; tied paths prefer diagonal (match/substitution), then deletion, then insertion.',
    'denominator': 'Number of normalized reference tokens, not hypothesis length or raw whitespace count.',
}
LIMIT = 'Lexical/source selection only: neither exact matches nor all checklist items found establish clinical correctness, speaker attribution, or completeness.'
PLAN_SCHEMA = 'clinical-study-plan/v1'
BUNDLE_SCHEMA = 'clinical-study-bundle/v1'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def words(text, *, reference=False):
    if reference:
        text = re.sub(r'</?UNSURE>|<UNIN/>', ' ', text)
    return [token for raw in text.casefold().split()
            if (token := raw.strip(EDGE_PUNCTUATION))]


def word_error(reference, hypothesis):
    """Exact deterministic edit counts using two rows, without a scoring package."""
    ref, hyp = words(reference, reference=True), words(hypothesis)
    if not ref:
        raise ValueError('WER is undefined for an empty normalized reference')
    # distance, substitutions, deletions, insertions, correct
    previous = [(j, 0, 0, j, 0) for j in range(len(hyp) + 1)]
    for i, left in enumerate(ref, 1):
        current = [(i, 0, i, 0, 0)]
        for j, right in enumerate(hyp, 1):
            cost, sub, delete, insert, correct = previous[j - 1]
            equal = left == right
            diagonal = (cost + (not equal), sub + (not equal), delete, insert, correct + equal)
            cost, sub, delete, insert, correct = previous[j]
            deletion = (cost + 1, sub, delete + 1, insert, correct)
            cost, sub, delete, insert, correct = current[-1]
            insertion = (cost + 1, sub, delete, insert + 1, correct)
            current.append(min((diagonal, deletion, insertion), key=lambda row: row[0]))
        previous = current
    errors, sub, delete, insert, correct = previous[-1]
    return {'reference_tokens': len(ref), 'hypothesis_tokens': len(hyp),
            'substitutions': sub, 'deletions': delete, 'insertions': insert,
            'correct': correct, 'edit_distance': errors, 'wer': errors / len(ref)}


def checked_span(item, transcript):
    start, end = item['start'], item['end']
    if (type(start) is not int or type(end) is not int
            or not 0 <= start < end <= len(transcript)):
        raise ValueError('Invalid source character range')
    return start, end


def quoted_spans(items, transcript):
    result = []
    for item in items:
        quote, spans = item['quote'], item['spans']
        if not isinstance(quote, str) or not quote or not spans:
            raise ValueError('Missing literal source evidence')
        for span in spans:
            start, end = checked_span(span, transcript)
            if transcript[start:end] != quote:
                raise ValueError('Evidence does not match the unchanged source bytes')
            result.append((start, end))
    return result


def contains(outer, inner):
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def selection_report(document, transcript, probes=()):
    """Count actual accepted spans, never a model's supported/covered booleans."""
    if document.get('schema') != 'clinical-documentation/v11':
        raise ValueError('This reader supports clinical-documentation/v11 only')
    if document.get('transcript_sha256') != digest(transcript.encode()):
        raise ValueError('Document/transcript identity mismatch')
    selected, contexts, fact_rows = [], [], []
    for fact in document['facts']:
        phrases = fact['source_phrases']
        if not phrases or fact['statement'] != ' … '.join(p['quote'] for p in phrases):
            raise ValueError('Fact is not the recorded source-phrase selection')
        spans = quoted_spans(phrases, transcript)
        evidence = quoted_spans(fact['evidence'], transcript)
        if any(not any(contains(context, span) for context in evidence) for span in spans):
            raise ValueError('Selected phrase falls outside its cited context')
        selected.extend(spans)
        contexts.extend(evidence)
        fact_rows.append({'fact_id': fact.get('id'), 'section': fact.get('section'),
                          'selected_span_ranges': [{'start': a, 'end': b} for a, b in spans],
                          'cited_context_ranges': [{'start': a, 'end': b} for a, b in evidence]})
    # Only already-retained literal excerpts count; rejected model proposals do not.
    review = quoted_spans(document['source_excerpts'], transcript)
    segments = sorted({checked_span(row, transcript)
                       for chunk in document['source_coverage'] for row in chunk['final']})
    if not segments:
        raise ValueError('No declared source segments to assess')
    rows = []
    for segment in segments:
        rows.append({'start': segment[0], 'end': segment[1],
                     'has_selected_phrase': any(contains(segment, span) for span in selected),
                     'has_cited_context': any(contains(context, segment) for context in contexts),
                     'has_review_excerpt': any(contains(excerpt, segment) for excerpt in review)})
    gaps, cursor = [], 0
    for start, end in segments:
        if start > cursor:
            gaps.append({'start': cursor, 'end': start})
        cursor = max(cursor, end)
    if cursor < len(transcript):
        gaps.append({'start': cursor, 'end': len(transcript)})
    probes_out = []
    for probe in probes:
        target = checked_span(probe, transcript)
        if transcript[target[0]:target[1]] != probe['quote']:
            raise ValueError('Probe is not an exact span of this transcript')
        location = ('selected_phrase' if any(contains(s, target) for s in selected) else
                    'cited_context_only' if any(contains(s, target) for s in contexts) else
                    'review_excerpt_only' if any(contains(s, target) for s in review) else
                    'source_only')
        matching = [fact for fact in fact_rows if any(
            contains((span['start'], span['end']), target) for span in fact['selected_span_ranges'])]
        probes_out.append({**probe, 'location': location,
                           'accepted_fact_ids': [fact['fact_id'] for fact in matching if fact['fact_id'] is not None],
                           'meaning_preserved': 'not_assessed'})
    return {'accepted_facts': len(document['facts']),
            'selected_phrases': sum(len(fact['source_phrases']) for fact in document['facts']),
            'selected_span_occurrences': len(selected),
            'declared_segments': len(segments),
            'segments_with_selected_phrase': sum(row['has_selected_phrase'] for row in rows),
            'declared_segment_character_gaps': gaps, 'segments': rows,
            'withheld_candidates': len(document['rejected']),
            'accepted_fact_index': fact_rows,
            'review_excerpts': len(document['source_excerpts']), 'source_span_probes': probes_out,
            'clinical_completeness': 'not_established',
            'interpretation': 'A selected phrase does not cover every fact in its segment. Context/review presence is not selection as a report fact. Probe absence means literal absence, not proof of semantic omission. Rendered visibility and clinical meaning require separate review.'}


def markdown(value):
    """Render only calculated fields; do not ask a model to recount the table."""
    lines = ['# Offline study measurements', '', LIMIT, '',
             f"Helper SHA-256: `{value['helper_sha256']}`", '']
    data = value['measurement']
    if value['kind'] == 'wer':
        lines += [f"Normalization: `{NORMALIZATION}`", '',
                  '| N reference | Hypothesis tokens | S | D | I | Edit distance | WER |',
                  '| --- | --- | --- | --- | --- | --- | --- |',
                  f"| {data['reference_tokens']} | {data['hypothesis_tokens']} | {data['substitutions']} | {data['deletions']} | {data['insertions']} | {data['edit_distance']} | {data['wer']:.12g} |", '',
                  'WER = (S + D + I) / N. The full-precision value and exact normalization are in measurement.json.',
                  'Different annotation/punctuation regimes are different measurements; do not silently replace earlier denominators.', '']
    else:
        lines += [f"Accepted source selections: {data['accepted_facts']} facts; {data['selected_phrases']} phrases; {data['selected_span_occurrences']} literal span occurrences.",
                  f"Declared segments with at least one selected phrase: {data['segments_with_selected_phrase']}/{data['declared_segments']}.",
                  f"Withheld candidates: {data['withheld_candidates']}; review excerpts: {data['review_excerpts']}.", '',
                  data['interpretation'], '', 'Clinical completeness: **not established**.', '']
        for probe in data['source_span_probes']:
            # Labels and text stay in JSON; avoid turning source text into prose claims.
            lines.append(f"- Source span {probe['start']}–{probe['end']}: `{probe['location']}`; meaning not assessed.")
        if data['declared_segment_character_gaps']:
            lines += ['', 'Declared segments do not cover every source character; see the recorded gaps.']
    lines += ['', 'Inputs are unchanged copies. Re-run the retained helper.py with these inputs into a new output directory.', '']
    return '\n'.join(lines)


def _json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode()


def _cell(value):
    return str(value).replace('|', '\\|').replace('\r', ' ').replace('\n', ' ')


def _bundle_report(value):
    lines = ['# Speech and clinical-source study measurements', '', LIMIT, '',
             'This is a deterministic measurement report, not a consultation draft or a medical assessment.', '',
             '| Case | Accepted facts | Selected / declared source segments | WER edits / reference tokens | WER (%) |',
             '| --- | ---: | ---: | ---: | ---: |']
    for case in value['cases']:
        selection, wer = case['source_selection'], case['wer']
        facts = selection['measurement']['accepted_facts'] if selection['status'] == 'measured' else 'not measured'
        segments = (f"{selection['measurement']['segments_with_selected_phrase']} / {selection['measurement']['declared_segments']}"
                    if selection['status'] == 'measured' else 'not measured')
        edits = f"{wer['measurement']['edit_distance']} / {wer['measurement']['reference_tokens']}" if wer['status'] == 'measured' else 'no reference'
        percent = f"{wer['measurement']['wer'] * 100:.12g}" if wer['status'] == 'measured' else 'not measured'
        lines.append(f"| {_cell(case['id'])} | {facts} | {segments} | {edits} | {percent} |")
    lines += ['', '## Interpretation boundaries', '',
              '- Accepted facts are counted from the validated v11 `facts` list and literal `source_phrases`, not an invented `source.text` field.',
              '- Source selection does not require a human WER reference. Missing WER references do not prevent source coverage measurement.',
              '- Case and declared edge punctuation are already ignored by this WER method; differences in those features alone cannot explain its errors.',
              '- A literal probe absent from accepted phrases is not proof of semantic omission. Equivalent wording is not automatically classified.',
              '- Model confidence, literal citations and lexical agreement do not establish medical correctness or completeness.',
              '- Original drafts, transcripts, failed attempts and poor predictions are not changed.', '',
              f"Normalization: `{NORMALIZATION}`. WER is stored as a ratio in JSON and explicitly converted to percent in this table.",
              'No cross-case mean or model ranking is inferred from cases with different sources, languages or normalization.', '',
              '## Source identity', '', f"Plan SHA-256: `{value['plan_sha256']}`", f"Helper SHA-256: `{value['helper_sha256']}`", '']
    for case in value['cases']:
        lines.append(f"### {_cell(case['id'])}")
        lines.append('')
        for role, item in case['inputs'].items():
            lines.append(f"- {role}: `{item['sha256']}`, {item['size_bytes']} bytes.")
        if case['source_selection']['status'] == 'measured':
            measured = case['source_selection']['measurement']
            lines.append(f"- Withheld candidates: {measured['withheld_candidates']}; review excerpts: {measured['review_excerpts']}; clinical completeness not established.")
        lines.append('')
    return '\n'.join(lines)


def prepare_bundle(plan_file):
    """Validate every input and compute every case before publishing any output."""
    plan_bytes = plan_file.read_bytes()
    plan = json.loads(plan_bytes)
    if (not isinstance(plan, dict) or set(plan) != {'schema', 'cases'}
            or plan.get('schema') != PLAN_SCHEMA or not isinstance(plan['cases'], list) or not plan['cases']):
        raise ValueError('Expected clinical-study-plan/v1 with a nonempty cases list')
    source = Path(__file__).read_bytes()
    value = {'schema': BUNDLE_SCHEMA, 'plan_sha256': digest(plan_bytes), 'helper_sha256': digest(source),
             'cases': [], 'clinical_validation': False, 'inference_submitted': False,
             'units': {'wer': 'ratio', 'wer_percent': 'percent', 'source_offsets': 'Unicode code points',
                       'file_sizes': 'bytes', 'facts_and_segments': 'counts'}}
    files, identifiers = {'plan.json': plan_bytes, 'helper.py': source}, set()
    for specification in plan['cases']:
        if (not isinstance(specification, dict)
                or set(specification) - {'id', 'transcript', 'document', 'reference', 'source_spans', 'provenance'}):
            raise ValueError('Unknown clinical-study case fields')
        identifier = specification.get('id')
        if (not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', identifier)
                or identifier in identifiers):
            raise ValueError('Case IDs must be unique filename-safe identifiers')
        identifiers.add(identifier)
        inputs = {}
        for role in ('transcript', 'document', 'reference', 'source_spans'):
            filename = specification.get(role)
            if filename is None:
                continue
            if not isinstance(filename, str) or not filename:
                raise ValueError(f'{identifier}: {role} must name an actual input file')
            path = Path(filename)
            inputs[role] = (path if path.is_absolute() else plan_file.parent / path).read_bytes()
        if 'transcript' not in inputs:
            raise ValueError(f'{identifier}: transcript is required')
        if 'source_spans' in inputs and 'document' not in inputs:
            raise ValueError(f'{identifier}: source_spans requires document')
        transcript = inputs['transcript'].decode('utf-8')
        provenance = specification.get('provenance', {})
        if (not isinstance(provenance, dict)
                or set(provenance) - {'operation_id', 'model_id', 'clinical_job_id', 'language', 'transcription_reused'}
                or any(not isinstance(item, str) or not item for key, item in provenance.items() if key != 'transcription_reused')
                or ('transcription_reused' in provenance and type(provenance['transcription_reused']) is not bool)):
            raise ValueError(f'{identifier}: unsupported or invalid declared provenance fields')
        case = {'id': identifier, 'declared_provenance': provenance,
                'provenance_scope': 'Caller-declared identifiers; exact file hashes verified locally, service identity not queried.',
                'inputs': {role: {'sha256': digest(data), 'size_bytes': len(data)} for role, data in inputs.items()},
                'source_selection': {'status': 'not_measured', 'reason': 'No clinical document supplied; accepted fact count is unknown, not zero.'},
                'wer': {'status': 'not_measured', 'reason': 'No human reference supplied; source selection remains independently measurable.'}}
        if 'document' in inputs:
            case['source_selection'] = {'status': 'measured', 'measurement': selection_report(
                json.loads(inputs['document']), transcript, json.loads(inputs.get('source_spans', b'[]')))}
        if 'reference' in inputs:
            case['wer'] = {'status': 'measured', 'normalization': METHOD,
                           'measurement': word_error(inputs['reference'].decode('utf-8'), transcript),
                           'interpretation': 'Case/declared edge punctuation are ignored; WER does not evaluate medication, negation or clinical correctness.'}
        value['cases'].append(case)
        files[f'cases/{identifier}/measurement.json'] = _json_bytes(case)
        for role, data in inputs.items():
            files[f'cases/{identifier}/{role}' + ('.json' if role in {'document', 'source_spans'} else '.txt')] = data
    files['measurement.json'] = _json_bytes(value)
    files['report.md'] = _bundle_report(value).encode()
    return value, files


def assemble(plan_file, output):
    """Hash-bound re-entry resumes own partial output without replacing evidence."""
    value, files = prepare_bundle(plan_file)
    identity = {'schema': BUNDLE_SCHEMA, 'plan_sha256': value['plan_sha256'],
                'helper_sha256': value['helper_sha256'],
                'inputs': {case['id']: case['inputs'] for case in value['cases']}}
    marker = output / '.clinical-study-prepared.json'
    if output.exists() and not marker.is_file():
        raise ValueError('Output already exists without this report preparation identity; choose a new directory')
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    def write_once(name, data):
        path = output / name
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError(f'Existing report artifact differs: {name}; historical evidence was not overwritten')
            return
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o600)
        if path.read_bytes() != data:
            raise OSError(f'Report artifact readback mismatch: {name}')
    write_once(marker.name, _json_bytes(identity))
    for name, data in files.items():
        write_once(name, data)
    manifest = {**identity, 'schema': 'clinical-study-artifacts/v1', 'state': 'complete',
                'case_count': len(value['cases']), 'clinical_validation': False,
                'artifacts': [{'path': name, 'sha256': digest(data), 'size_bytes': len(data)}
                              for name, data in sorted(files.items())]}
    # The completion marker is written only after every listed byte is verified.
    manifest_bytes = _json_bytes(manifest)
    reused = (output / 'completion-manifest.json').is_file()
    write_once('completion-manifest.json', manifest_bytes)
    return {'schema': BUNDLE_SCHEMA, 'state': 'complete', 'output': str(output),
            'manifest': str(output / 'completion-manifest.json'), 'manifest_sha256': digest(manifest_bytes),
            'case_count': len(value['cases']), 'reused_completed_output': reused,
            'clinical_validation': False, 'inference_submitted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='kind', required=True)
    wer = sub.add_parser('wer', help='Measure one frozen reference/transcript pair')
    wer.add_argument('--reference', type=Path, required=True)
    wer.add_argument('--hypothesis', type=Path, required=True)
    coverage = sub.add_parser('coverage', help='Account for selected spans; never certify completeness')
    coverage.add_argument('--document', type=Path, required=True)
    coverage.add_argument('--transcript', type=Path, required=True)
    coverage.add_argument('--source-spans', type=Path, help='Optional JSON list of exact {start,end,quote} source probes')
    bundle = sub.add_parser('assemble', help='Deterministic multi-case study report; optional WER and independent source selection')
    bundle.add_argument('--plan', type=Path, required=True, help='Versioned clinical-study-plan/v1 JSON; relative inputs resolve beside this file')
    for command in (wer, coverage, bundle):
        command.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.kind == 'assemble':
        print(json.dumps(assemble(args.plan, args.output)))
        return
    names = ('reference', 'hypothesis') if args.kind == 'wer' else ('document', 'transcript', 'source_spans')
    inputs = {name: getattr(args, name).read_bytes() for name in names if getattr(args, name) is not None}
    if args.kind == 'wer':
        measured = word_error(inputs['reference'].decode(), inputs['hypothesis'].decode())
    else:
        measured = selection_report(json.loads(inputs['document']), inputs['transcript'].decode(),
                                    json.loads(inputs.get('source_spans', b'[]')))
    source = Path(__file__).read_bytes()
    value = {'schema': SCHEMA, 'kind': args.kind, 'helper_sha256': digest(source),
             'normalization': METHOD if args.kind == 'wer' else None,
             'inputs': {name: {'sha256': digest(data), 'bytes': len(data)} for name, data in inputs.items()},
             'measurement': measured, 'clinical_validation': False}
    # Never overwrite a completed measurement or a historical failed report.
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = {'helper.py': source, 'measurement.json': (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode(),
             'report.md': markdown(value).encode()}
    files.update({name + ('.json' if name in {'document', 'source_spans'} else '.txt'): data
                  for name, data in inputs.items()})
    for name, data in files.items():
        path = args.output / name
        path.write_bytes(data)
        path.chmod(0o600)
    print(json.dumps({'output': str(args.output), 'kind': args.kind, 'schema': SCHEMA,
                      'measurement_sha256': digest(files['measurement.json']), 'clinical_validation': False}))


if __name__ == '__main__':
    main()
