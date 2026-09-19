"""Durable adapter for the existing bounded clinical-documentation runner.

The clinical algorithm, prompts, provider, budgets and review count are unchanged.
Each saved clinical file is checkpointed through the existing verified publisher.
A lost provider response is ambiguous and never silently regenerated on restart.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import mimetypes
import os
from pathlib import Path
import sys
import tempfile
import threading

from scientific_receipts import load, save, persist_local_file, verify_file


CUSTOMER_OUTPUT_ROLES = {
    'transcript.txt': 'data', 'report.md': 'report', 'document.json': 'data',
    'review.json': 'data', 'review.md': 'report', 'follow-up.md': 'report',
    'coverage.json': 'data', 'run.json': 'provenance',
    'clinical-outcome.json': 'provenance', 'clinical-outcome.md': 'report',
}
COMMON_CUSTOMER_OUTPUTS = {'transcript.txt', 'review.json', 'coverage.json', 'run.json'}
POSITIVE_CUSTOMER_OUTPUTS = {'report.md', 'document.json', 'review.md', 'follow-up.md'}
NO_REPORT_EXCLUDED = {'report.md', 'document.json', 'follow-up.md'}


def customer_artifacts(files, report_produced):
    """Register only verified customer evidence, never provider-call internals."""
    required = COMMON_CUSTOMER_OUTPUTS | {'clinical-outcome.json', 'clinical-outcome.md'}
    if report_produced:
        required |= POSITIVE_CUSTOMER_OUTPUTS
    elif NO_REPORT_EXCLUDED & files.keys():
        raise ValueError('No-report outcome unexpectedly contains clinical draft artifacts.')
    if required - files.keys():
        raise ValueError('Clinical customer publication is missing required draft/source/review evidence: '
                         + ', '.join(sorted(required - files.keys())))
    selected = {}
    for name, role in CUSTOMER_OUTPUT_ROLES.items():
        if name in files:
            info = files[name]
            verify_file(Path(info['path']), info)
            selected[name] = {**info, 'role': role}
    return selected


def outcome_documents(outcome):
    """Measure existing literal evidence without another model or clinical judgment.

    The established report reader owns span/coverage semantics. These additions
    do not alter the generated report, source, review queue, or questions.
    """
    files = outcome['files']
    required = COMMON_CUSTOMER_OUTPUTS | (POSITIVE_CUSTOMER_OUTPUTS if outcome['report_produced'] else set())
    if required - files.keys():
        raise ValueError('Clinical outcome is missing required source or draft evidence.')
    for name in required:
        verify_file(Path(files[name]['path']), files[name])
    transcript = Path(files['transcript.txt']['path']).read_text(encoding='utf-8')
    assessment = {
        'schema': 'scientific-clinical-assessment/v1',
        'transcript_sha256': hashlib.sha256(transcript.encode()).hexdigest(),
        'transcript_characters': len(transcript),
        'clinical_correctness': 'not_established', 'clinical_completeness': 'not_established',
        'speaker_attribution': 'not_established',
    }
    lines = ['# Clinical stage outcome', '', outcome['outcome'], '']
    if outcome['report_produced']:
        script = Path(os.environ.get('SCIENTIFIC_CLINICAL_SCRIPT',
            '/app/skill/clinical-documentation/scripts/clinical_report.py'))
        helper = Path(os.environ.get('SCIENTIFIC_CLINICAL_REPORT_HELPER', str(script.with_name('study_report.py'))))
        spec = importlib.util.spec_from_file_location('clinical_outcome_measurements', helper)
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        document = json.loads(Path(files['document.json']['path']).read_bytes())
        assessment.update(reader.selection_report(document, transcript))
        assessment['helper_sha256'] = hashlib.sha256(helper.read_bytes()).hexdigest()
        lines.extend(['A clinical draft was produced. The following measurements validate literal source selection, '
                      'not clinical correctness, speaker identity, or completeness.', '',
                      '| Measurement | Value |', '| --- | --- |'])
        for label, key in [('Accepted source-linked entries', 'accepted_facts'),
                           ('Selected source phrases', 'selected_phrases'),
                           ('Exact selected span occurrences', 'selected_span_occurrences'),
                           ('Declared source segments', 'declared_segments'),
                           ('Segments with a selected phrase', 'segments_with_selected_phrase'),
                           ('Withheld candidates', 'withheld_candidates'),
                           ('Retained review excerpts', 'review_excerpts')]:
            lines.append(f'| {label} | {assessment[key]} |')
        missing = [row for row in assessment['segments'] if not row['has_selected_phrase']]
        lines.extend(['', '## Source selection limits', '', assessment['interpretation'], '',
                      f"Declared segment character gaps: {len(assessment['declared_segment_character_gaps'])}.", '',
                      'Segments without a selected report phrase (character offsets; not a finding that clinical facts are absent):', ''])
        lines.extend([f"- [{row['start']}, {row['end']}): cited-context presence={row['has_cited_context']}; "
                      f"review-excerpt presence={row['has_review_excerpt']}." for row in missing] or
                     ['- None; this still does not establish completeness.'])
        lines.extend(['', 'Review report.md and document.json against transcript.txt. Withheld candidates remain in '
                      'review.json/review.md; uncertain details and suggested questions remain separate in follow-up.md. '
                      'Teaching narration, self-report and observed findings require human review; literal citations do not establish attribution.'])
    else:
        if outcome['outcome'] != 'no_supported_clinical_facts' or not outcome['no_report_explicitly_allowed']:
            raise ValueError('Only the explicitly permitted no-supported-facts outcome may publish no-report evidence.')
        if NO_REPORT_EXCLUDED & files.keys():
            raise ValueError('No-report outcome unexpectedly contains clinical draft artifacts.')
        review = json.loads(Path(files['review.json']['path']).read_bytes())
        rejected = review.get('rejected') if isinstance(review, dict) else None
        assessment.update(status='no_report', accepted_facts=0, selected_phrases=0,
                          withheld_candidates=len(rejected) if isinstance(rejected, list) else None,
                          source_selection_coverage='not_applicable_without_a_document')
        lines.extend(['No supported clinical facts were extracted. No report, document or follow-up was produced. '
                      'This explicitly permitted no-report outcome is not a finding of absent illness or proof that the '
                      'source lacks important information. Review unchanged transcript.txt, review.json and coverage.json.', '',
                      f'Unchanged transcript: {len(transcript)} characters; SHA-256 {assessment["transcript_sha256"]}.',
                      'A no-report outcome is not a completed clinical assessment.'])
    measured = {**outcome, 'source_assessment': assessment}
    return {'clinical-outcome.json': (json.dumps(measured, ensure_ascii=False, sort_keys=True) + '\n').encode(),
            'clinical-outcome.md': ('\n'.join(lines) + '\n').encode()}


class AdmissionUnknown(RuntimeError):
    pass


def operation_states(root, files):
    result = []
    for name, info in files.items():
        if name.startswith('calls/') and name.endswith('/state.json'):
            verify_file(Path(info['path']), info)
            value = json.loads(Path(info['path']).read_bytes())
            if value.get('operation_id'):
                result.append({'operation_id': value['operation_id'], 'status': value.get('status', 'unknown'), 'kind': 'inference'})
    upload = load(Path(root) / 'audio-upload/receipt.json') or {}
    if upload.get('operation_id'):
        result.append({'operation_id': upload['operation_id'], 'status': 'succeeded' if upload.get('state') == 'finalized' else 'unknown', 'kind': 'upload'})
    return result


class Checkpoint:
    def __init__(self, root, local):
        self.root, self.local = Path(root), Path(local)
        self.lock = threading.RLock()
        self.index = load(self.root / 'receipt.json') or {'files': {}}
        for relative, info in self.index['files'].items():
            if Path(relative).is_absolute() or '..' in Path(relative).parts:
                raise ValueError('Clinical checkpoint path is invalid.')
            verify_file(Path(info['path']), info)
            target = self.local / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(info['path']).read_bytes())

    def persist(self, path, value):
        with self.lock:
            path = Path(path)
            relative = str(path.relative_to(self.local))
            path.parent.mkdir(parents=True, exist_ok=True)
            content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + '\n'
            # The POSIX publisher may hard-link this closed scratch inode.
            # Replace our private scratch inode, never modify a published one.
            path.unlink(missing_ok=True)
            path.write_text(content, encoding='utf-8')
            # Content-addressed immutable checkpoint objects are not overwritten.
            import hashlib
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            info = persist_local_file(path, self.root / 'objects' / digest)
            self.index['files'][relative] = info
            save(self.root / 'receipt.json', self.index)


def guarded_classes(module, checkpoint, cancelled):
    original_platform, original_reporter = module.Platform, module.Reporter

    class Platform(original_platform):
        def upload(self, path, model):
            # Reuse the deployed idempotent byte uploader, not the older inline
            # upload implementation which has no saved reservation receipt.
            spec = importlib.util.spec_from_file_location('study_clinical_upload', Path(__file__).with_name('upload-artifact.py'))
            uploader = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(uploader)
            media = mimetypes.guess_type(path.name)[0]
            if media in {'audio/x-wav', 'audio/vnd.wave'}:
                media = 'audio/wav'
            if not media or not media.startswith(('audio/', 'video/')):
                raise ValueError('Clinical audio file has an unsupported media type.')
            args = argparse.Namespace(model=model, file=path, media_type=media,
                output_dir=checkpoint.root / 'audio-upload', idempotency_key=self.run_id + '-upload')
            args.output_dir.mkdir(parents=True, exist_ok=True)
            result = asyncio.run(uploader.run(args))
            checkpoint.persist(self.output / 'audio-artifact.json', result['artifact'])
            return result['artifact']

        def operation(self, stage, endpoint, payload):
            folder = self.output / 'calls' / stage
            if cancelled() and not (folder / 'state.json').exists():
                raise InterruptedError('Study cancellation requested before the next clinical operation.')
            state = module.read(folder / 'state.json') if (folder / 'state.json').exists() else {}
            if (folder / 'request.json').exists() and not (folder / 'response.json').exists() and not state.get('operation_id'):
                raise AdmissionUnknown('Clinical platform admission has no confirmed operation ID; inspect the retained request, never duplicate it.')
            return super().operation(stage, endpoint, payload)

    class Reporter(original_reporter):
        def complete(self, stage, prompt, data):
            if cancelled():
                raise InterruptedError('Study cancellation requested before the next clinical provider call.')
            folder = self.platform.output / 'calls' / stage
            if self.provider and (folder / 'request.json').exists() and not (folder / 'response.json').exists():
                raise AdmissionUnknown('Clinical provider response is missing for a retained request. Its billing/completion is unknown; no automatic duplicate call.')
            return super().complete(stage, prompt, data)

    return Platform, Reporter


def run(source, source_type, language, report_model, root, cancel_file, asr_model=None):
    script = Path(os.environ.get('SCIENTIFIC_CLINICAL_SCRIPT', '/app/skill/clinical-documentation/scripts/clinical_report.py'))
    sys.path.insert(0, str(script.parent))
    spec = importlib.util.spec_from_file_location('study_clinical_runner', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = Path(root)
    with tempfile.TemporaryDirectory(prefix='clinical-study-seekable-') as directory:
        local = Path(directory)
        checkpoint = Checkpoint(root, local)
        module.save = checkpoint.persist
        module.Platform, module.Reporter = guarded_classes(module, checkpoint, lambda: Path(cancel_file).exists())
        args = module.parser().parse_args(['--' + source_type, str(source), '--language', language,
            '--report-model', report_model, '--report-provider', 'https://api.tokenfactory.nebius.com/v1',
            '--base-url', os.environ['SCIENTIFIC_MODELS_MCP_URL'].rstrip('/').removesuffix('/mcp'),
            '--output', str(local), *(['--asr-model', asr_model] if asr_model else [])])
        try:
            module.run(args, key=os.environ['SCIENTIFIC_MODELS_API_KEY'],
                       provider_key=os.environ.get('CLINICAL_REPORT_API_KEY') or os.environ.get('NEBIUS_API_KEY'))
            state = 'completed'
        except AdmissionUnknown:
            state = 'admission_unknown'
        except InterruptedError:
            state = 'cancelled'
        except TimeoutError:
            # Existing bounded platform observation expired; confirmed IDs are
            # saved. Next worker observation resumes only those same operations.
            state = 'pending'
        except module.NoSupportedClinicalFacts:
            state = 'no_supported_clinical_facts'
        except Exception as error:
            # A first failed provider request is also ambiguous if its response
            # was not durably captured. Never grow the existing retry budget.
            pending = []
            for name in checkpoint.index['files']:
                if not name.endswith('/request.json') or name.replace('/request.json', '/response.json') in checkpoint.index['files']:
                    continue
                state_info = checkpoint.index['files'].get(name.replace('/request.json', '/state.json'))
                known = json.loads(Path(state_info['path']).read_bytes()) if state_info else {}
                if not known.get('operation_id'):
                    pending.append(name)
            state = 'admission_unknown' if pending else 'failed'
            checkpoint.index['error_type'] = type(error).__name__
        checkpoint.index.update(state=state, clinical_validation=False)
        operations = operation_states(root, checkpoint.index['files'])
        active = [item for item in operations if item['status'] not in {'succeeded', 'failed', 'cancelled', 'expired', 'preempted'}]
        if state == 'failed' and active:
            state = 'needs_attention'
            checkpoint.index['state'] = state
        save(root / 'receipt.json', checkpoint.index)
        return {'state': state, 'files': checkpoint.index['files'], 'clinical_validation': False,
                'operations': operations, 'active_operations': active,
                'error_type': checkpoint.index.get('error_type')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--source-type', required=True, choices=['audio', 'transcript', 'artifact'])
    parser.add_argument('--language', required=True, choices=['en', 'de'])
    parser.add_argument('--report-model', required=True)
    parser.add_argument('--asr-model')
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--cancel-file', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(**vars(args))))


if __name__ == '__main__':
    main()
