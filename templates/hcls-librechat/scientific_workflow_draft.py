"""Small typed edits to the existing v2 plan; never execute or admit a study.

Immutable revisions and the existing verified receipt journal make an edit
recoverable after a lost reply/process restart. The lock is instance-local,
matching the dedicated single-supervisor deployment contract.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from jsonschema import Draft202012Validator

import scientific_study as study
from scientific_preparation import canonical
from scientific_receipts import load, persist_local_file, receipt_lock, save, verify_file
from scientific_study_schema import DRAFT_SCHEMA


def _shape(arguments):
    problem = next(Draft202012Validator(DRAFT_SCHEMA).iter_errors(arguments), None)
    if problem:
        location = '.'.join(str(item) for item in problem.absolute_path) or 'draft'
        detail = problem.message if problem.validator in {'required', 'additionalProperties'} else f'does not satisfy {problem.validator}; use the typed fields for this kind/method'
        raise ValueError(f'Draft shape at {location}: {detail[:600]}')
    canonical(arguments)  # Reject NaN/non-JSON parameters before touching files.


def _upsert(existing, additions, removals, key):
    names = [item[key] for item in additions]
    if len(names) != len(set(names)):
        raise ValueError(f'Draft edit has duplicate {key} values.')
    if set(names) & set(removals):
        raise ValueError(f'Do not remove and upsert the same {key} in one edit.')
    unknown = set(removals) - {item[key] for item in existing}
    if unknown:
        raise ValueError(f'Cannot remove unknown {key}: ' + ', '.join(sorted(unknown)))
    replacements = {item[key]: item for item in additions}
    result = [replacements.pop(item[key], item) for item in existing if item[key] not in removals]
    return result + list(replacements.values())


def _read_revision(reference):
    path = study.path_in_workspace(reference['path'])
    verify_file(path, reference)
    return json.loads(path.read_bytes())


def _response(reference, head, *, replayed=False, validate=False):
    plan = _read_revision(reference)
    error = None
    if validate:
        try:
            study.validate(plan)
        except ValueError as problem:
            error = str(problem)
    finalized = reference['finalized'] and error is None
    return {'schema': 'scientific-workflow-draft/v1', 'plan_file': reference['path'],
            'sha256': reference['sha256'], 'size_bytes': reference['size_bytes'],
            'current_sha256': head['sha256'], 'step_count': len(plan['steps']),
            'deliverable_count': len(plan['deliverables']), 'finalized': finalized,
            'replayed': replayed, 'validation_error': error or reference.get('validation_error'),
            'inference_submitted': False,
            'next_action': ('Submit this plan_file once with run_scientific_workflow_mcp_environment-execution and output_directory; admission revalidates and freezes inputs.'
                            if finalized else 'Edit compact related groups using current_sha256, then finalize the complete plan. No study has been admitted.')}


def compose(arguments):
    """Create/upsert/finalize in small groups, or recover the current receipt."""
    _shape(arguments)
    folder = study.path_in_workspace(arguments['draft_directory'])
    receipt_path = folder / 'receipt.json'
    request_hash = hashlib.sha256(canonical(arguments)).hexdigest()
    read_only = set(arguments) == {'draft_directory'}
    with receipt_lock(folder):
        state = load(receipt_path)
        if state is not None:
            if state.get('schema') != 'scientific-workflow-draft-receipt/v1':
                raise ValueError('This directory contains a different receipt; use a dedicated draft directory.')
            plan = _read_revision(state['head'])
            if read_only:
                return _response(state['head'], state['head'], validate=state['head']['finalized'])
            previous = state['requests'].get(request_hash)
            if previous:
                return _response(previous, state['head'], replayed=True, validate=previous['finalized'])
            if arguments.get('expected_sha256') != state['head']['sha256']:
                raise ValueError('Draft changed or expected_sha256 is missing. Read draft_directory alone and use current_sha256; no edit was applied.')
        else:
            if read_only:
                raise ValueError('Draft does not exist; create it with a title and a compact group of steps.')
            if arguments.get('expected_sha256'):
                raise ValueError('Draft does not exist; an expected revision cannot be matched.')
            if not arguments.get('title', '').strip():
                raise ValueError('Creating a draft requires a meaningful title.')
            plan = {'schema': study.SCHEMA, 'title': arguments['title'], 'steps': [], 'deliverables': []}
            state = {'schema': 'scientific-workflow-draft-receipt/v1', 'requests': {}}
        plan = copy.deepcopy(plan)
        if 'title' in arguments:
            if not arguments['title'].strip():
                raise ValueError('Give this study a meaningful title.')
            plan['title'] = arguments['title']
        plan['steps'] = _upsert(plan['steps'], arguments.get('steps', []), arguments.get('remove_steps', []), 'id')
        plan['deliverables'] = _upsert(plan['deliverables'], arguments.get('deliverables', []),
                                       arguments.get('remove_deliverables', []), 'name')
        validation_error = None
        if arguments.get('finalize'):
            try:
                study.validate(plan)
            except ValueError as problem:
                validation_error = str(problem)
        data = canonical(plan)
        checksum = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory(prefix='scientific-draft-') as local:
            staged = Path(local) / 'plan.json'
            staged.write_bytes(data)
            reference = persist_local_file(staged, folder / 'revisions' / (checksum + '.json'))
        reference.update(finalized=bool(arguments.get('finalize')) and validation_error is None,
                         validation_error=validation_error)
        state['head'] = reference
        state['requests'][request_hash] = reference
        save(receipt_path, state)
        return _response(reference, reference)
