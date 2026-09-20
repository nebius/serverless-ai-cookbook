"""Durable whole-study state for the existing scientific workflow runner.

One dedicated user instance owns its queue, even when its tenant bucket is
shared. No agent/provider loop runs here. Model execution uses the existing
receipt clients; deterministic local phases publish closed, verified files.
"""
import argparse
import asyncio
import copy
import ctypes
from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode
import uuid

from scientific_receipts import file_measurement, load, persist_local_file, receipt_lock, save, verify_file
from scientific_preparation import canonical, export_parquet

HERE = Path(__file__).parent
SCHEMA = 'scientific-workflow/v2'
FINAL = {'completed', 'failed', 'cancelled', 'needs_attention'}
MODEL_KINDS = {'native', 'batch'}
PROTEIN_METHODS = {'proteinmpnn-input', 'esmfold2-fast-input', 'design-refold-correspondence'}
LOCAL_METHODS = {'write-json', 'python-script', 'parquet-export', 'structure', 'protein-design-analysis', 'robotics-analysis', 'evo2-continuation', 'docking', 'docking-batch', 'genmol', 'aging', 'report', 'mindeval', 'clinical-study'} | PROTEIN_METHODS
HELPERS = {name: HERE / filename for name, filename in {
    'structure': 'structure-analysis.py', 'docking': 'molecule-analysis.py',
    'docking-batch': 'molecule-analysis.py', 'genmol': 'molecule-analysis.py', 'aging': 'aging-analysis.py', 'report': 'report-assembly.py',
    'mindeval': 'report-assembly.py'}.items()}
HELPERS['clinical-study'] = Path(os.environ.get('SCIENTIFIC_CLINICAL_REPORT_HELPER',
    '/app/skill/clinical-documentation/scripts/study_report.py'))
HELPERS.update({name: HERE / 'scientific_protein_preparation.py' for name in PROTEIN_METHODS})
HELPERS['python-script'] = HERE / 'scientific_study.py'
HELPERS['protein-design-analysis'] = HERE / 'design-artifact-analysis.py'
HELPERS['robotics-analysis'] = HERE / 'robotics-analysis.py'
HELPERS['evo2-continuation'] = HERE / 'sequence-analysis.py'


def workspace():
    return Path(os.environ.get('SCIENTIFIC_WORKSPACE', '/workspace')).resolve()


def stop_with_parent():
    """Do not leave an old phase calling providers after its worker is killed.

    This image is Linux. prctl also checks the small fork/death race; it does
    not alter the provider budget or pretend an ambiguous request was undone.
    """
    expected_parent = os.getppid()
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Could not bind phase process lifetime to its study worker.')
    if os.getppid() != expected_parent or expected_parent == 1:
        os.kill(os.getpid(), signal.SIGKILL)


def path_in_workspace(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Expected a nonempty workspace path.')
    path = (workspace() / value).resolve()
    if not path.is_relative_to(workspace()):
        raise ValueError('Study paths must remain inside the mounted workspace.')
    return path


def owner_identity():
    user = os.environ.get('SCIENTIFIC_STUDY_OWNER') or os.environ.get('SEED_DEFAULT_USER_EMAIL')
    origin = os.environ.get('SCIENTIFIC_MODELS_MCP_URL', '').rstrip('/')
    if not user or not origin:
        raise ValueError('Durable studies require the configured dedicated-user identity and platform endpoint.')
    return hashlib.sha256(canonical({'user': user, 'platform': origin})).hexdigest()


def caller_fingerprint():
    key = os.environ.get('SCIENTIFIC_MODELS_API_KEY')
    if not key:
        raise ValueError('The dedicated user platform key is not configured.')
    return hashlib.sha256(key.encode()).hexdigest()


def registry():
    return workspace() / '.scientific-studies' / owner_identity()


def directory(identifier):
    return registry() / str(uuid.UUID(identifier))


def measure(path):
    size, checksum = file_measurement(path)
    return {'path': str(path), 'size_bytes': size, 'sha256': checksum}


def file_reference(value, earlier):
    if isinstance(value, dict):
        if set(value) != {'step', 'file'} or value['step'] not in earlier:
            raise ValueError('File references need exactly step (an earlier step ID) and file (its published filename).')
        if not isinstance(value['file'], str) or not value['file'] or Path(value['file']).is_absolute() or '..' in Path(value['file']).parts:
            raise ValueError('Referenced output filename must be relative and cannot escape its step.')
        return
    if not path_in_workspace(value).is_file():
        raise ValueError(
            f'Input file does not exist before admission: {value}. '
            'Future outputs require an exact earlier-step reference {"step":"predict-a","file":"result.json"}, '
            'not a predicted worker path or a steps directory. For Python analysis, declare one named input '
            'per required file using inputs:[{"name":"result_a","file":{"step":"predict-a","file":"result.json"}}]; '
            'use your actual step IDs and published filenames. Correct the saved draft through the composer; '
            'do not edit immutable admitted plans.')


def known_output_reference(value, steps):
    """Reject known impossible names before any model admission; never rename."""
    if not isinstance(value, dict):
        return
    from scientific_study_schema import (known_output_files, output_contract_name,
        PHASE_OUTPUT_PATTERNS, PHASE_STABLE_OUTPUT_REFERENCES)
    source = steps[value['step']]
    contract = output_contract_name(source)
    stable = PHASE_STABLE_OUTPUT_REFERENCES.get(contract, {}).get(value['file'])
    if stable:
        raise ValueError(
            f"Step {value['step']} ({contract}) publishes {value['file']!r} only for its actual coordinate format. "
            f"For a required future input or deliverable use file:{stable!r}; it resolves to the verified "
            'original coordinate path and format without converting or renaming bytes. '
            'Already materialized files remain valid literal inputs; no study has been admitted.')
    possible = known_output_files(source)
    patterns = PHASE_OUTPUT_PATTERNS.get(contract, [])
    if (possible is not None and value['file'] not in possible
            and not any(re.fullmatch(pattern, value['file']) for pattern in patterns)):
        raise ValueError(
            f"Step {value['step']} ({contract}) cannot publish {value['file']!r}. "
            f"Use an exact published filename: {', '.join(sorted(possible))}. "
            + ('Batch artifact names follow output-NN.artifact in output-manifest.json; their count, bytes and media types are not known before execution. ' if contract == 'batch' else '')
            + ('Native input provenance must reference the original input file or its exact preparation-step reference; native does not copy it to input.json. ' if contract == 'native' else '')
            + 'Conditional files are not guaranteed before their result exists; '
            'no output has been renamed and no study has been admitted.')


def coordinate_output_references(step, steps):
    """A future batch artifact index declares no coordinate semantic type.

    Existing materialized coordinates keep their exact bytes. Only these typed
    coordinate arguments require manifest-backed selection before admission;
    raw artifacts remain valid references in other inputs and deliverables.
    """
    from scientific_study_schema import COORDINATE_INPUT_GUIDANCE, PHASE_OUTPUT_PATTERNS
    args = step.get('arguments', {})
    for name, guidance in COORDINATE_INPUT_GUIDANCE.get(step.get('method'), {}).items():
        value = args.get(name)
        if (isinstance(value, dict) and steps[value['step']].get('kind') == 'batch'
                and any(re.fullmatch(pattern, value['file'])
                        for pattern in PHASE_OUTPUT_PATTERNS['batch'])):
            raise ValueError(
                f"Step {step['id']} argument {name} cannot select future batch coordinates by "
                f"{value['file']!r}: output-NN.artifact indices do not establish semantic type. "
                + guidance + ' No file was substituted and no study has been admitted.')


def structure_manifest_reference(step):
    """Require explicit future selection; validate materialized manifests now."""
    if step.get('method') != 'structure':
        return
    args = step['arguments']
    prediction = args.get('prediction')
    if isinstance(prediction, dict):
        if prediction['file'] == 'output-manifest.json' and 'structure_index' not in args:
            raise ValueError('A future structure prediction manifest requires explicit structure_index among coordinate entries; no study has been admitted.')
        return
    if not isinstance(prediction, str):
        return
    path = path_in_workspace(prediction)
    try:
        value = json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(value, dict) or value.get('schema') != 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1':
        return
    if 'structure_index' not in args:
        raise ValueError('A structure prediction manifest requires explicit structure_index; no study has been admitted.')
    spec = importlib.util.spec_from_file_location('study_manifest_prediction', HELPERS['structure'])
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.manifest_prediction(path, args['structure_index'])


def input_references(step):
    """Named file inputs, not arbitrary strings guessed to be file paths."""
    kind = step['kind']
    if kind == 'clinical':
        return [step['source']]
    if kind in MODEL_KINDS:
        return [step[key] for key in ('input', 'source', 'parameters', 'source_artifact') if key in step]
    args, method = step.get('arguments', {}), step['method']
    if method == 'python-script':
        return [args['script'], *[item['file'] for item in args['inputs']]]
    if method == 'write-json':
        def embedded(value):
            if isinstance(value, dict):
                return [value] if set(value) == {'step', 'file'} else [ref for item in value.values() for ref in embedded(item)]
            return [ref for item in value for ref in embedded(item)] if isinstance(value, list) else []
        return embedded(args['value'])
    if method == 'parquet-export':
        return [args['source']]
    if method == 'proteinmpnn-input':
        return [args['backbone']]
    if method == 'esmfold2-fast-input':
        return [args['design_input'], args['design_result']]
    if method == 'design-refold-correspondence':
        return [args[key] for key in ('design_input', 'design_result', 'refold_input', 'refold_parameters', 'prediction', 'confidence_result') if key in args]
    if method in {'structure', 'docking'}:
        return [args[key] for key in ('reference', 'prediction', 'result', 'residue_map', 'request_file', 'confidence_result') if key in args]
    if method == 'genmol':
        return [args['input_file'], args['result_file']]
    if method == 'protein-design-analysis':
        return [args[key] for key in ('manifest_file', 'target_reference') if key in args]
    if method == 'robotics-analysis':
        return [args[key] for key in ('source_video', 'source_archive', 'native_result', 'manifest_file')]
    if method == 'evo2-continuation':
        return [args['reference_file'], *[case[key] for case in args['cases']
                for key in ('input_file', 'result_file', 'operation_file')]]
    if method == 'docking-batch':
        return [run[key] for run in args['runs'] for key in ('reference_file', 'prediction_file', 'result_file') if key in run]
    if method == 'aging':
        return [cohort[key] for cohort in args['cohorts'] for key in ('input_file', 'result_file')] + ([args['reference_ages']] if args.get('reference_ages') else [])
    if method == 'report':
        return [section['file'] for section in args['sections']]
    if method == 'mindeval':
        return args['records']
    values = [args['plan_file']]
    if isinstance(args['plan_file'], str):
        plan_path = path_in_workspace(args['plan_file'])
        if plan_path.is_file():
            report_plan = json.loads(plan_path.read_bytes())
            for case in report_plan.get('cases', []):
                for name in ('transcript', 'document', 'reference', 'source_spans'):
                    if case.get(name):
                        values.append(str((plan_path.parent / case[name]).resolve()))
    return values


def validate(plan):
    from jsonschema import Draft202012Validator
    from scientific_study_schema import STUDY_SCHEMA, PHASE_OUTPUT_DIRECTORIES
    problem = next(Draft202012Validator(STUDY_SCHEMA).iter_errors(plan), None)
    if problem:
        location = '.'.join(str(item) for item in problem.absolute_path) or 'study'
        detail = problem.message if problem.validator in {'required', 'additionalProperties'} else f'does not satisfy {problem.validator}; use the typed fields for this kind/method'
        raise ValueError(f'Study shape at {location}: {detail[:600]}')
    if not isinstance(plan, dict) or plan.get('schema') != SCHEMA:
        raise ValueError('Whole studies require schema scientific-workflow/v2.')
    if set(plan) - {'schema', 'title', 'steps', 'deliverables'}:
        raise ValueError('Study fields are schema, title, steps and deliverables.')
    if not isinstance(plan.get('title'), str) or not plan['title'].strip():
        raise ValueError('Give this study a meaningful title.')
    if not isinstance(plan.get('steps'), list) or not plan['steps']:
        raise ValueError('A study needs ordered preparation/model/analysis steps.')
    earlier, inputs, by_id = set(), {}, {}
    workflow = workflow_module() if any(step.get('kind') in MODEL_KINDS for step in plan['steps']) else None
    for step in plan['steps']:
        identifier = step.get('id') if isinstance(step, dict) else None
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier) or identifier in earlier:
            raise ValueError('Each step needs a unique ID using letters, digits, underscore or dash.')
        kind = step.get('kind')
        if kind in MODEL_KINDS:
            required = workflow.NATIVE_REQUIRED if kind == 'native' else workflow.REQUIRED
            required = required - {'output'}
            optional = workflow.NATIVE_OPTIONAL if kind == 'native' else workflow.OPTIONAL
            if required - step.keys() or step.keys() - required - optional - {'id', 'kind'}:
                raise ValueError(f'Step {identifier}: {kind} fields must match the existing client contract; output is managed by the study.')
            for name in (required | optional) - {'input', 'source', 'parameters', 'source_artifact'}:
                if name in step and (not isinstance(step[name], str) or not step[name]):
                    raise ValueError(f'Step {identifier}: {name} must be a nonempty string, preserving the chosen model contract.')
            for name in ('input', 'parameters', 'source_artifact'):
                if isinstance(step.get(name), str):
                    source = path_in_workspace(step[name])
                    try:
                        payload = json.loads(source.read_bytes())
                    except (OSError, ValueError) as error:
                        raise ValueError(f'Step {identifier}: {name} must be an existing valid JSON file before admission.') from error
                    if not isinstance(payload, dict):
                        raise ValueError(f'Step {identifier}: {name} file must contain a JSON object, not an inline path or array.')
        elif kind == 'clinical':
            if not (os.environ.get('CLINICAL_REPORT_API_KEY') or os.environ.get('NEBIUS_API_KEY') or os.environ.get('CLINICAL_REPORT_API_KEY_FILE')):
                raise ValueError('The operator must configure the existing clinical provider credential; it is never included in the study plan.')
        elif kind in {'preparation', 'analysis'}:
            if set(step) != {'id', 'kind', 'method', 'arguments'} or step['method'] not in LOCAL_METHODS or not isinstance(step['arguments'], dict):
                raise ValueError(f'Step {identifier}: use a published deterministic method and its named arguments.')
            validate_local_arguments(step['method'], step['arguments'])
        else:
            raise ValueError(f'Step {identifier}: kind must be preparation, native, batch, clinical or analysis.')
        for value in input_references(step):
            file_reference(value, earlier)
            known_output_reference(value, by_id)
            if isinstance(value, str):
                path = path_in_workspace(value)
                inputs[str(path)] = measure(path)
        coordinate_output_references(step, by_id)
        structure_manifest_reference(step)
        if step.get('method') in {'report', 'mindeval'}:
            spec = importlib.util.spec_from_file_location('study_report', HELPERS[step['method']])
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            try:
                if step['method'] == 'report':
                    from scientific_study_schema import DEFAULT_REPORT_TITLE
                    helper.validate_report_metadata(step['arguments'].get('title', DEFAULT_REPORT_TITLE), step['arguments']['sections'])
                else:
                    helper.validate_report_metadata(step['arguments']['title'])
            except ValueError as error:
                raise ValueError(f'Step {identifier}: {error}') from error
        if step.get('method') == 'mindeval':
            # Existing files can be checked now; exact earlier-step outputs are
            # checked by this same helper when they exist. Never guess bytes.
            paths = [str(path_in_workspace(value)) for value in step['arguments']['records'] if isinstance(value, str)]
            if paths:
                try:
                    checked, _, _ = helper.load_mindeval_records(paths, workspace())
                except ValueError as error:
                    raise ValueError(f'Step {identifier}: {error}') from error
                for item in checked:
                    expected = inputs[str(item['path'])]
                    if len(item['raw']) != expected['size_bytes'] or helper.digest(item['raw']) != expected['sha256']:
                        raise ValueError(f'Step {identifier}: MindEval input changed during preflight; no study admitted.')
        earlier.add(identifier)
        by_id[identifier] = step
    deliverables = plan.get('deliverables')
    if not isinstance(deliverables, list) or not deliverables:
        raise ValueError('Declare the final files and report; inference completion alone is not whole-study completion.')
    labels = set()
    for item in deliverables:
        if not isinstance(item, dict) or set(item) != {'name', 'role', 'source'} or not isinstance(item['name'], str) or not item['name'] or item['name'] in labels:
            raise ValueError('Deliverables need unique name, role and source file reference.')
        if isinstance(item['source'], str) and path_in_workspace(item['source']).is_dir():
            raise ValueError(f'Deliverable {item["name"]!r} is a directory, not a file; declare its concrete files separately.')
        file_reference(item['source'], earlier)
        known_output_reference(item['source'], by_id)
        if isinstance(item['source'], dict):
            source_step = next(step for step in plan['steps'] if step['id'] == item['source']['step'])
            source_name = Path(item['source']['file']).as_posix()
            known_directories = PHASE_OUTPUT_DIRECTORIES.get(source_step.get('method'), [])
            if source_name == '.' or source_name in known_directories or item['source']['file'].endswith('/'):
                raise ValueError(f'Deliverable {item["name"]!r} refers to output directory {item["source"]["file"]!r}, not a file. Declare concrete published files (for example records/000.json), not whole helper directories.')
        else:
            path = path_in_workspace(item['source'])
            inputs[str(path)] = measure(path)
        labels.add(item['name'])
    if not any(item['role'] == 'report' for item in deliverables):
        raise ValueError('Declare at least one report deliverable, produced by a deterministic analysis/report helper.')
    return inputs


def validate_local_arguments(method, args):
    fields = {
        'write-json': ({'filename', 'value'}, set()),
        'python-script': ({'script', 'inputs', 'parameters', 'outputs'}, set()),
        'parquet-export': ({'source', 'formats'}, set()),
        'proteinmpnn-input': ({'backbone', 'structure_index', 'chain', 'num_sequences', 'seed', 'sampling_temp', 'omit_aas'}, set()),
        'esmfold2-fast-input': ({'design_input', 'design_result', 'design_index', 'seed'}, set()),
        'design-refold-correspondence': ({'design_input', 'design_result', 'refold_input', 'refold_parameters', 'prediction', 'design_index', 'structure_index', 'prediction_chain'}, {'confidence_result'}),
        'structure': ({'reference'}, {'chain_map', 'prediction', 'result', 'structure_index', 'residue_map', 'request_file', 'confidence_result'}),
        'docking': ({'reference', 'same_coordinate_frame'}, {'prediction', 'result', 'threshold_queries'}),
        'docking-batch': ({'runs', 'same_coordinate_frame'}, {'threshold_queries'}),
        'genmol': ({'input_file', 'result_file'}, set()),
        'protein-design-analysis': ({'manifest_file'}, {'binder_chain', 'binder_length_min', 'binder_length_max', 'target_reference', 'target_chain'}),
        'robotics-analysis': ({'source_video', 'source_archive', 'native_result', 'manifest_file', 'selected_cameras'}, {'variant_index'}),
        'evo2-continuation': ({'reference_file', 'cases'}, {'title', 'reference_id'}),
        'aging': ({'model', 'cohorts'}, {'coefficient_version', 'reference_ages'}),
        'report': ({'sections'}, {'title'}), 'mindeval': ({'title', 'records'}, set()),
        'clinical-study': ({'plan_file'}, set()),
    }
    required, optional = fields[method]
    if required - args.keys() or args.keys() - required - optional:
        raise ValueError(f'{method} requires {sorted(required)}; optional fields are {sorted(optional)}.')
    if method in {'structure', 'docking'} and ('result' in args) == ('prediction' in args):
        raise ValueError(f'{method} needs exactly one result or prediction file.')
    if method.startswith('docking') and args['same_coordinate_frame'] is not True:
        raise ValueError('Docking analysis requires an explicit unchanged receptor coordinate frame.')
    if method == 'protein-design-analysis':
        if ('target_reference' in args) != ('target_chain' in args):
            raise ValueError('Protein-design target comparison requires both target_reference and its exact target_chain.')
        if args.get('binder_length_min', 0) > args.get('binder_length_max', float('inf')):
            raise ValueError('Protein-design binder minimum length exceeds maximum.')
    if method == 'write-json' and (not isinstance(args['filename'], str) or Path(args['filename']).name != args['filename'] or not args['filename'].endswith('.json')):
        raise ValueError('write-json filename must be a JSON basename.')
    if method == 'python-script':
        names = [item['name'] for item in args['inputs']]
        if len(names) != len(set(names)):
            raise ValueError('python-script input binding names must be unique.')
        reserved = {'script.py', 'script-provenance.json', 'input-bindings.json'}
        for name in args['outputs']:
            if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name or name in reserved:
                raise ValueError('python-script output names must be relative scratch files and cannot replace script/provenance/bindings evidence.')
        script = path_in_workspace(args['script'])
        if not script.is_file():
            raise ValueError('python-script source must already exist before study admission.')
        compile(script.read_text(), str(script), 'exec')
    if method == 'parquet-export' and (not isinstance(args['formats'], list) or not args['formats'] or
            any(item not in {'npz', 'hdf5', 'zip', 'sqlite'} for item in args['formats']) or len(set(args['formats'])) != len(args['formats'])):
        raise ValueError('parquet-export formats must be a unique nonempty list of npz, hdf5, zip, sqlite.')
    if method == 'structure':
        if 'chain_map' not in args and 'residue_map' not in args:
            raise ValueError('structure needs explicit chain_map or a hash-bound residue_map from which to derive exactly those pairs.')
        if 'chain_map' in args and (not isinstance(args['chain_map'], list) or not args['chain_map'] or any(not isinstance(item, str) or ':' not in item for item in args['chain_map'])):
            raise ValueError('structure chain_map must explicitly list reference:prediction pairs.')
    for name in ('sections', 'cohorts', 'runs'):
        if name in args and (not isinstance(args[name], list) or not args[name] or any(not isinstance(item, dict) for item in args[name])):
            raise ValueError(f'{method} {name} must be a nonempty list of named objects.')
    if method == 'report' and any(set(item) != {'title', 'file', 'format'} or item['format'] not in {'markdown', 'csv', 'operation-timing', 'recorded-export', 'rgb-statistics', 'mindeval-runs'} for item in args['sections']):
        raise ValueError('report sections require title, file and a published deterministic format.')
    if method == 'aging' and (args['model'] not in {'phenoage', 'altumage'} or any(not {'label', 'input_file', 'result_file'} <= item.keys() for item in args['cohorts'])):
        raise ValueError('aging requires model=phenoage|altumage and cohorts with label, input_file and result_file.')


def workflow_module():
    spec = importlib.util.spec_from_file_location('durable_workflow_client', HERE / 'scientific-workflow.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def existing_submission(record, fingerprint):
    """An accepted immutable identity is observable without the phase lock."""
    if record['identity'] != fingerprint or record['caller_fingerprint'] != caller_fingerprint():
        raise ValueError('Study identity/caller changed; original operation receipts are retained.')
    return {**view(record), 'study_admission': 'accepted',
            'reused_existing_study': True, 'new_study_admitted': False}


def submit(plan, output):
    if os.environ.get('SCIENTIFIC_STUDY_OWNER_MODE') not in {'first-instance', 'stopped-predecessor'}:
        raise ValueError('The operator must confirm one active dedicated-user supervisor before enabling durable studies; see the stop-first deployment preflight.')
    output = path_in_workspace(str(output))
    frozen = canonical(plan)
    fingerprint = hashlib.sha256(canonical({'plan': plan, 'output': str(output), 'owner': owner_identity()})).hexdigest()
    identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, fingerprint))
    root = directory(identifier)
    # advance() holds receipt_lock for a complete phase. Loading its verified
    # publication is independently synchronized and must remain a read-only
    # idempotent replay, not an EAGAIN that looks like rejected admission.
    previous = load(root / 'receipt.json')
    if previous:
        return existing_submission(previous, fingerprint)
    root.mkdir(parents=True, exist_ok=True)
    with ExitStack() as locks:
        try:
            locks.enter_context(receipt_lock(root))
        except BlockingIOError:
            # The first admission may have persisted between our read and
            # lock attempt. Never restart it or claim that nothing was saved.
            previous = load(root / 'receipt.json')
            if previous:
                return existing_submission(previous, fingerprint)
            return {'id': identifier, 'job_id': identifier, 'status': 'admission_pending',
                    'study_admission': 'unknown', 'new_study_admitted': False,
                    'output_directory': str(output),
                    'guidance': 'Another request holds this exact study admission lock. '
                        'Its saved admission is not yet observable. Do not resubmit, change the plan/output, '
                        'or claim that nothing was submitted. Observe this identity in Runs or read_execution.',
                    'next_observation': {
                        'registered_tool_name': 'read_execution_mcp_environment-execution',
                        'tool_name': 'read_execution', 'arguments': {'job_id': identifier}}}
        previous = load(root / 'receipt.json')
        if previous:
            return existing_submission(previous, fingerprint)
        inputs = validate(plan)
        implementations = {}
        for step in plan['steps']:
            if step['kind'] == 'clinical':
                script = Path(os.environ.get('SCIENTIFIC_CLINICAL_SCRIPT', '/app/skill/clinical-documentation/scripts/clinical_report.py'))
                report_helper = Path(os.environ.get('SCIENTIFIC_CLINICAL_REPORT_HELPER', str(script.with_name('study_report.py'))))
                for helper in [HERE / 'scientific_clinical.py', script, script.with_name('document.py'), report_helper]:
                    if not helper.is_file():
                        raise ValueError('The existing clinical runner is not installed.')
                    implementations['clinical/' + helper.name] = measure(helper)
            if step['kind'] in {'preparation', 'analysis'}:
                helper = HELPERS.get(step['method'], HERE / 'scientific_preparation.py')
                if not helper.is_file():
                    raise ValueError(f'Installed deterministic helper is unavailable: {step["method"]}.')
                implementations[step['method']] = measure(helper)
                if step['method'] in PROTEIN_METHODS:
                    implementations['protein-structure-reader'] = measure(HERE / 'structure-analysis.py')
                if step['method'] == 'protein-design-analysis':
                    evaluator = HERE / 'qualification_evaluators.py'
                    if not evaluator.is_file():
                        evaluator = HERE / 'scripts/qualification/evaluators.py'
                    implementations['protein-design-evaluator'] = measure(evaluator)
        output.mkdir(parents=True, exist_ok=True)
        # The output binding is durable and exclusive across plans/owner queues.
        binding = output / 'study-binding.json'
        binding_bytes = canonical({'study_id': identifier, 'identity': fingerprint, 'owner': owner_identity()})
        if binding.exists() and binding.read_bytes() != binding_bytes:
            raise ValueError('Output directory already belongs to another study; choose a new directory.')
        with tempfile.TemporaryDirectory(prefix='study-submit-') as scratch:
            local = Path(scratch) / 'binding.json'
            local.write_bytes(binding_bytes)
            persist_local_file(local, binding)
            local = Path(scratch) / 'plan.json'
            local.write_bytes(frozen)
            persist_local_file(local, root / 'plan.json')
        record = {'schema': 'scientific-study-state/v1', 'id': identifier, 'identity': fingerprint,
                  'owner': owner_identity(), 'caller_fingerprint': caller_fingerprint(),
                  'title': plan['title'], 'state': 'queued', 'created_at': time.time(),
                  'updated_at': time.time(), 'output_directory': str(output), 'inputs': inputs,
                  'implementations': implementations,
                  'completed_steps': [], 'steps': {}, 'current_step': None, 'phase': 'queued'}
        save(root / 'receipt.json', record)
        return {**view(record), 'study_admission': 'accepted',
                'reused_existing_study': False, 'new_study_admitted': True}


def resolve(value, record):
    if isinstance(value, dict) and set(value) == {'step', 'file'}:
        prior = record['steps'].get(value['step'], {})
        if prior.get('state') != 'completed' or value['file'] not in prior.get('files', {}):
            raise ValueError(f'Required output {value["step"]}/{value["file"]} is not verified and complete.')
        reference = prior['files'][value['file']]
        verify_file(Path(reference['path']), reference)
        return reference['path']
    if isinstance(value, list):
        return [resolve(item, record) for item in value]
    if isinstance(value, dict):
        return {key: resolve(item, record) for key, item in value.items()}
    return value


def verify_owner(record):
    if record['owner'] != owner_identity() or record['caller_fingerprint'] != caller_fingerprint():
        raise ValueError('Dedicated study owner/key changed; no model work is submitted under a replacement identity.')


def verify_cancellation_identity(record, plan):
    """Stopping saved work needs its identity, not unchanged analysis helpers."""
    verify_owner(record)
    expected = hashlib.sha256(canonical({'plan': plan, 'output': record['output_directory'],
                                         'owner': record['owner']})).hexdigest()
    if record['identity'] != expected or record['id'] != str(uuid.uuid5(uuid.NAMESPACE_URL, expected)):
        raise ValueError('Saved study plan identity changed; no cancellation was sent.')


def verify_inputs(record):
    verify_owner(record)
    for item in record['inputs'].values():
        verify_file(Path(item['path']), item)
    for item in record.get('implementations', {}).values():
        verify_file(Path(item['path']), item)
    for step in record['steps'].values():
        if step.get('state') == 'completed':
            for item in step.get('files', {}).values():
                verify_file(Path(item['path']), item)


def local_command(method, args, scratch):
    helper = HELPERS[method]
    command = [sys.executable, str(helper)]
    if method in {'robotics-analysis', 'evo2-continuation'}:
        plan = scratch / 'helper-input.json'
        plan.write_bytes(canonical(args))
        return command + ['--plan', str(plan), '--output-dir', str(scratch)]
    if method == 'clinical-study':
        return command + ['assemble', '--plan', args['plan_file'], '--output', str(scratch)]
    if method == 'genmol':
        return command + ['--request', args['input_file'], '--genmol-result', args['result_file'],
                          '--output', str(scratch / 'metrics.json')]
    if method == 'protein-design-analysis':
        command += ['--manifest', args['manifest_file'], '--output-dir', str(scratch)]
        for key in ('binder_chain', 'binder_length_min', 'binder_length_max', 'target_reference', 'target_chain'):
            if key in args:
                command += ['--' + key.replace('_', '-'), str(args[key])]
        return command
    if method in {'report', 'mindeval', 'aging', 'docking-batch'}:
        data = args if method in {'report', 'mindeval'} else args['cohorts'] if method == 'aging' else args['runs']
        if method == 'report':
            from scientific_study_schema import DEFAULT_REPORT_TITLE
            data = {'title': DEFAULT_REPORT_TITLE, **args}
        manifest = scratch / 'helper-input.json'
        manifest.write_bytes(canonical(data))
        command += [{'report': '--manifest', 'mindeval': '--mindeval-plan', 'aging': '--cohorts', 'docking-batch': '--runs'}[method], str(manifest)]
    if method in {'structure', 'docking'}:
        for key in ('reference', 'prediction', 'result', 'structure_index', 'residue_map', 'request_file', 'confidence_result'):
            if key in args:
                command += ['--' + key.replace('_', '-'), str(args[key])]
        if method == 'structure':
            chain_map = args.get('chain_map')
            if args.get('residue_map'):
                mapping = json.loads(path_in_workspace(args['residue_map']).read_bytes())
                if (mapping.get('schema') != 'scientific-residue-correspondence/v1'
                        or not all(re.fullmatch(r'[0-9a-f]{64}', mapping.get(key, '')) for key in ('reference_sha256', 'prediction_sha256'))
                        or not isinstance(mapping.get('pairs'), list) or not mapping['pairs']):
                    raise ValueError('Chain selection requires a nonempty hash-bound residue correspondence.')
                derived = list(dict.fromkeys(f'{item["reference_chain"]}:{item["prediction_chain"]}' for item in mapping['pairs']))
                if chain_map is not None and set(chain_map) != set(derived):
                    raise ValueError('Explicit chain_map contradicts the hash-bound residue_map pairs.')
                chain_map = derived
            # Existing evaluator verifies both structure hashes and every
            # residue identity before using these exact correspondence pairs.
            command += ['--chain-map', *chain_map]
    if method == 'aging':
        command += ['--model', args['model']]
        for key in ('coefficient_version', 'reference_ages'):
            if key in args:
                command += ['--' + key.replace('_', '-'), str(args[key])]
    if method.startswith('docking'):
        command += ['--same-coordinate-frame', '--output', str(scratch / 'metrics.json')]
        for query in args.get('threshold_queries', []):
            command += ['--threshold-query', str(query['confidence_above']), str(query['rmsd_below_angstrom'])]
    else:
        command += ['--output-dir', str(scratch)]
    return command


def run_python_script(args, scratch, generation):
    """The existing scientific Python environment, with frozen code and files.

    This is an explicitly declared preparation/analysis phase, not an LLM loop
    or alternate model client. Model requests remain native/batch plan stages.
    """
    script = path_in_workspace(args['script'])
    inputs = {item['name']: path_in_workspace(item['file']) for item in args['inputs']}
    measured = {'script': measure(script), 'inputs': {name: measure(path) for name, path in inputs.items()}}
    output = scratch / 'script-output'
    output.mkdir()
    bindings = scratch / 'input-bindings.json'
    bindings.write_bytes(canonical({'schema': 'scientific-python-bindings/v1',
        'inputs': {name: str(path) for name, path in inputs.items()}, 'parameters': args['parameters']}) + b'\n')
    # Run the exact frozen bytes copied to local scratch, preserving the original
    # source hash and avoiding in-place source changes during interpreter reads.
    source = scratch / 'script.py'
    source.write_bytes(script.read_bytes())
    verify_file(source, measured['script'])
    environment = {name: value for name, value in os.environ.items()
                   if not any(word in name.upper() for word in ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'CREDENTIAL'))}
    completed = subprocess.run([sys.executable, str(source), '--inputs', str(bindings), '--output-dir', str(output)],
        cwd=scratch, env=environment, capture_output=True, timeout=120, preexec_fn=stop_with_parent)
    if completed.returncode:
        (generation / 'diagnostic.txt').write_bytes(f'Python analysis exited {completed.returncode}.\n'.encode() + completed.stderr[-8192:])
        raise RuntimeError(f'Saved Python analysis failed; diagnostic retained at {generation / "diagnostic.txt"}.')
    verify_file(script, measured['script'])
    for name, path in inputs.items():
        verify_file(path, measured['inputs'][name])
    files = {}
    for name in args['outputs']:
        candidate = (output / name).resolve()
        if not candidate.is_relative_to(output) or not candidate.is_file() or not candidate.stat().st_size:
            raise ValueError(f'Declared Python output {name!r} is missing, empty or outside its private output directory; study is not complete.')
        files[name] = candidate
    provenance = scratch / 'script-provenance.json'
    provenance.write_bytes(canonical({'schema': 'scientific-python-analysis/v1', **measured,
        'parameters': args['parameters'], 'outputs': {name: {key: value for key, value in measure(path).items() if key != 'path'} for name, path in files.items()},
        'interpreter': sys.executable, 'scientific_validity_claim': False}) + b'\n')
    return {**files, 'script.py': source, 'input-bindings.json': bindings, 'script-provenance.json': provenance}


def batch_coordinate_manifest(prediction, producer):
    """Find metadata in the recorded producer, not in neighboring directories.

    A direct batch coordinate reference must retain the same operation's
    published confidence evidence. The selected coordinate is never replaced.
    """
    files = producer.get('files', {})
    manifest = files.get('output-manifest.json')
    if manifest is None or prediction['file'] == 'output-manifest.json':
        return None
    if producer.get('state') != 'completed' or not producer.get('operation_id'):
        raise ValueError('Coordinate metadata requires its completed recorded model operation.')
    coordinate = files.get(prediction['file'])
    if not coordinate or Path(coordinate['path']).parent != Path(manifest['path']).parent:
        raise ValueError('Coordinate and manifest must belong to the same recorded operation directory.')
    for item in (coordinate, manifest):
        verify_file(path_in_workspace(item['path']), item)
    body = json.loads(Path(manifest['path']).read_bytes())
    if body.get('schema') != 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1':
        raise ValueError('Recorded coordinate metadata is not a scientific artifact manifest.')
    matches = [index for index, entry in enumerate(body['entries'])
               if entry.get('semantic_type') in {'protein-structure-pdb/v1', 'protein-structure-mmcif/v1'}
               and all(entry.get('artifact', {}).get(key) == coordinate[key] for key in ('sha256', 'size_bytes'))]
    if len(matches) != 1 or Path(coordinate['path']).name != f'output-{matches[0]:02d}.artifact':
        raise ValueError('Selected coordinates need one exact matching entry in their recorded operation manifest.')
    return {'step': prediction['step'], 'file': 'output-manifest.json'}


def paired_structure_arguments(step, record):
    """Carry producer-registered metadata without changing scientific selection."""
    args = step['arguments']
    prediction = args.get('prediction')
    if (step['method'] not in {'structure', 'design-refold-correspondence'} or 'confidence_result' in args
            or not isinstance(prediction, dict) or set(prediction) != {'step', 'file'}):
        return args
    producer = record['steps'].get(prediction['step'], {})
    binding = producer.get('structure_confidence_pairs', {}).get(prediction['file'])
    if binding is None:
        manifest = batch_coordinate_manifest(prediction, producer)
        return {**args, 'confidence_result': manifest} if manifest else args
    if producer.get('state') != 'completed' or producer.get('method') != 'design-refold-correspondence':
        raise ValueError('Structure confidence pair must come from its completed correspondence producer.')
    files = producer['files']
    coordinate, envelope = files.get(prediction['file']), files.get(binding.get('result_file'))
    if (not coordinate or not envelope
            or any(binding.get(key) != coordinate.get(key) for key in ('sha256', 'size_bytes'))
            or binding.get('result_sha256') != envelope.get('sha256')
            or Path(coordinate['path']).parent != Path(envelope['path']).parent):
        raise ValueError('Registered structure/confidence pair does not match the same recorded generation.')
    # resolve() verifies both exact registered file hashes; the structure helper
    # then verifies equal coordinate bytes plus the unique manifest/sample row.
    return {**args, 'confidence_result': {'step': prediction['step'], 'file': binding['result_file']}}


def run_local(step, record):
    method, args = step['method'], resolve(paired_structure_arguments(step, record), record)
    for value in input_references({'kind': step['kind'], 'method': method, 'arguments': args}):
        # Literal paths and resolved generated files use the same mounted root.
        if isinstance(value, str):
            path_in_workspace(value)
    generation = Path(record['output_directory']) / 'steps' / step['id'] / ('generation-' + uuid.uuid4().hex)
    generation.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix='scientific-study-phase-') as temporary:
        scratch = Path(temporary)
        selected_files = None
        if method == 'write-json':
            (scratch / args['filename']).write_bytes(canonical(args['value']) + b'\n')
        elif method == 'parquet-export':
            export_parquet(path_in_workspace(args['source']), scratch, args['formats'])
        elif method in PROTEIN_METHODS:
            from scientific_protein_preparation import prepare
            prepare(method, {key: str(path_in_workspace(value)) if key in {'backbone', 'design_input', 'design_result', 'refold_input', 'refold_parameters', 'prediction', 'confidence_result'} else value
                             for key, value in args.items()}, scratch)
        elif method == 'python-script':
            selected_files = run_python_script(args, scratch, generation)
        else:
            command = local_command(method, args, scratch)
            # No secrets or API keys are needed by deterministic analysis.
            environment = {name: value for name, value in os.environ.items()
                           if not any(word in name.upper() for word in ('KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'CREDENTIAL'))}
            completed = subprocess.run(command, cwd=workspace(), env=environment,
                                       capture_output=True, timeout=120, preexec_fn=stop_with_parent)
            if completed.returncode and not (method.startswith('docking') and completed.returncode == 2):
                (generation / 'diagnostic.txt').write_bytes(completed.stderr[-8192:])
                raise RuntimeError(f'Deterministic {method} helper failed; retained diagnostic at {generation / "diagnostic.txt"}.')
        files = {}
        sources = selected_files or {str(source.relative_to(scratch)): source for source in sorted(scratch.rglob('*')) if source.is_file()}
        for name, source in sources.items():
            if source.is_file():
                files[name] = persist_local_file(source, generation / name)
        if not files:
            raise RuntimeError('Deterministic phase produced no files.')
        if method == 'structure':
            selected = [name for name in ('prediction.pdb', 'prediction.cif') if name in files]
            if len(selected) != 1:
                raise ValueError('Structural comparison must publish one actual coordinate format.')
            original = selected[0]
            coordinate_format = 'mmcif' if original.endswith('.cif') else 'pdb'
            provenance = json.loads(Path(files['metrics.json']['path']).read_bytes())['provenance']
            if (provenance.get('prediction_sha256') != files[original]['sha256']
                    or provenance.get('prediction_format') != coordinate_format):
                raise ValueError('Structural output format/hash differs from its measured provenance.')
            # A logical key, not another file: downstream resolution, downloads
            # and viewers keep the original .pdb/.cif path and exact bytes.
            files['prediction.structure'] = {**files[original], 'coordinate_format': coordinate_format,
                                             'original_file': original}
        result = {'state': 'completed', 'files': files, 'method': method,
                  'helper_sha256': file_measurement(HELPERS[method])[1] if method in HELPERS else file_measurement(HERE / 'scientific_preparation.py')[1]}
        if method == 'design-refold-correspondence':
            coordinate, envelope = files['prediction.structure'], files['prediction-result.json']
            retained = json.loads(Path(envelope['path']).read_bytes()).get('retained_source_result', {})
            if isinstance(retained, dict) and 'manifest' in retained:
                result['structure_confidence_pairs'] = {'prediction.structure': {
                    'sha256': coordinate['sha256'], 'size_bytes': coordinate['size_bytes'],
                    'result_file': 'prediction-result.json', 'result_sha256': envelope['sha256']}}
        if method == 'mindeval':
            filename = 'customer-summary.json'
            result['customer_artifacts'] = {filename: {**files[filename], 'role': 'metrics'}}
            result['customer_summary'] = filename
        if method == 'robotics-analysis':
            filename = 'visual-comparisons.json'
            visual = json.loads(Path(files[filename]['path']).read_bytes())
            if visual.get('schema') != 'scientific-robotics-visual-comparisons/v1':
                raise ValueError('Unsupported robotics visual-comparison index.')
            selected = {filename: {**files[filename], 'role': 'support'}}
            for row in visual['comparisons']:
                if row['state'] != 'available':
                    continue
                name = row['file']
                if (not re.fullmatch(r'comparison-(?:native|dataset-[0-9]{3,})\.png', name)
                        or name not in files or name in selected
                        or any(row.get(key) != files[name].get(key) for key in ('sha256', 'size_bytes'))):
                    raise ValueError('Robotics comparison image differs from its registered generation.')
                selected[name] = {**files[name], 'role': 'support'}
            result['customer_artifacts'] = selected
        return result


async def run_model(step, record):
    workflow = workflow_module()
    root = Path(record['output_directory']) / 'steps' / step['id']
    prior = record['steps'].get(step['id'], {})
    if prior.get('consecutive_observation_errors', 0) >= workflow.MAX_READ_RECONNECTS:
        raise RuntimeError('Existing read-only reconnect budget is exhausted; inspect the original operation. No duplicate admission is attempted.')
    converted = resolve(step, record)
    converted['output'] = str(root / 'operation')
    for field in ('input', 'source', 'parameters', 'source_artifact'):
        if field in converted:
            converted[field] = str(path_in_workspace(converted[field]))
    plan = {'schema': 'scientific-workflow/v1', 'steps': [converted]}
    workflow.validate_files(plan)
    result = await workflow.run(plan, root / 'workflow', wait_seconds=10)
    observed = result.get('step_states', {}).get(step['id'], {})
    state = 'completed' if result['state'] == 'completed' else result['state']
    files = {}
    if state == 'completed':
        for path in sorted((root / 'operation').iterdir()):
            if path.is_file() and path.name != 'receipt.json':
                files[path.name] = measure(path)
    count = len(result.get('observation_errors', []))
    delta = max(0, count - prior.get('observation_error_count', 0))
    consecutive = prior.get('consecutive_observation_errors', 0) + delta if observed.get('state') == 'observation_interrupted' else 0
    return {'state': state, 'files': files, 'observation_error_count': count,
            'consecutive_observation_errors': consecutive,
            **{key: observed[key] for key in ('operation_id',) if key in observed}}


def publication_artifacts(plan, record):
    """Verify promised files, then include explicitly registered customer outputs.

    A phase producer, not directory enumeration or an LLM, chooses supplementary
    customer files. No worker/checkpoint files are included implicitly. Explicit
    impossible/missing promises still fail, even when useful other files exist.
    """
    artifacts = []
    for item in plan['deliverables']:
        path = path_in_workspace(resolve(item['source'], record))
        info = measure(path)
        if item['role'] == 'report' and not info['size_bytes']:
            raise ValueError('A promised report is empty; study cannot complete.')
        artifacts.append({'name': item['name'], 'role': item['role'], **info})
    paths = {item['path'] for item in artifacts}
    names = {item['name'] for item in artifacts}
    for step in plan['steps']:
        result = record['steps'][step['id']]
        for filename, selected in result.get('customer_artifacts', {}).items():
            registered = result.get('files', {}).get(filename)
            if (result.get('state') != 'completed' or not registered
                    or any(selected.get(key) != registered.get(key) for key in ('path', 'sha256', 'size_bytes'))
                    or selected.get('role') not in {'report', 'data', 'metrics', 'provenance', 'support'}):
                raise ValueError('Customer output is not an exact verified completed-step file.')
            path = path_in_workspace(registered['path'])
            verify_file(path, registered)
            if selected['role'] == 'report' and not registered['size_bytes']:
                raise ValueError('A registered customer report is empty; study cannot complete.')
            if str(path) in paths:
                continue
            name = f"steps/{step['id']}/{filename}"
            if name in names:
                raise ValueError('Declared and registered customer artifact names conflict; no file was renamed.')
            artifacts.append({'name': name, 'role': selected['role'], **measure(path),
                              'source_step': step['id'], 'source_file': filename,
                              'publication_basis': 'registered_customer_output'})
            paths.add(str(path))
            names.add(name)
    return artifacts


def run_clinical(step, record):
    from scientific_clinical import customer_artifacts, outcome_documents
    source = path_in_workspace(resolve(step['source'], record))
    root = Path(record['output_directory']) / 'steps' / step['id'] / 'clinical-checkpoint'
    command = [sys.executable, str(HERE / 'scientific_clinical.py'), '--source', str(source),
        '--source-type', step['source_type'], '--language', step['language'], '--report-model', step['report_model'],
        '--root', str(root), '--cancel-file', str(directory(record['id']) / 'cancel-request.json')]
    if step.get('asr_model'):
        command += ['--asr-model', step['asr_model']]
    # Existing runner owns its bounded provider/platform observations. No
    # additional LLM loop, retry, context expansion or overall artificial limit.
    result = subprocess.run(command, capture_output=True, cwd=workspace(), preexec_fn=stop_with_parent)
    if result.returncode:
        raise RuntimeError('Clinical stage runner could not finish; inspect its saved checkpoint before recovery.')
    value = json.loads(result.stdout)
    state = value['state']
    operations = value.get('operations', [])
    allowed_no_report = state == 'no_supported_clinical_facts' and step.get('allow_no_report') is True
    if state == 'completed' or allowed_no_report:
        if allowed_no_report:
            required = {'transcript.txt', 'review.json', 'coverage.json', 'run.json'}
            if required - value['files'].keys():
                raise ValueError('No-report outcome is missing its required source/review/coverage/run evidence.')
            if {'report.md', 'document.json', 'follow-up.md'} & value['files'].keys():
                raise ValueError('No-report outcome unexpectedly includes report artifacts; preserve the checkpoint for inspection.')
        if value.get('active_operations'):
            raise ValueError('Clinical outcome still has active operations; it cannot be published as complete.')
        generation = root.parent / ('generation-' + uuid.uuid4().hex)
        public_files = {}
        for name, info in value['files'].items():
            if '/' not in name:
                verify_file(Path(info['path']), info)
                public_files[name] = persist_local_file(Path(info['path']), generation / name)
        outcome = {'schema': 'scientific-clinical-outcome/v1', 'outcome': state,
                   'report_produced': not allowed_no_report, 'clinical_validation': False,
                   'no_report_explicitly_allowed': step.get('allow_no_report') is True,
                   'source': measure(Path(source)), 'language': step['language'],
                   'report_model': step['report_model'],
                   'report_provider': 'https://api.tokenfactory.nebius.com/v1',
                   'files': public_files.copy()}
        with tempfile.TemporaryDirectory(prefix='clinical-outcome-') as temporary:
            for name, content in outcome_documents(outcome).items():
                local = Path(temporary) / name
                local.write_bytes(content)
                public_files[name] = persist_local_file(local, generation / name)
        return {'state': 'completed', 'files': public_files, 'clinical_validation': False,
                'customer_artifacts': customer_artifacts(public_files, not allowed_no_report),
                'outcome': state, 'report_produced': not allowed_no_report,
                'checkpoint': str(root), 'report_model': step['report_model'],
                'operations': operations,
                'report_provider': 'https://api.tokenfactory.nebius.com/v1'}
    if state == 'pending':
        return {'state': 'clinical_pending', 'checkpoint': str(root), 'operations': operations}
    if state == 'admission_unknown':
        return {'state': 'needs_attention', 'checkpoint': str(root), 'admission_unknown': True, 'operations': operations,
                'failure': {'message': 'A clinical call has no saved response; its completion/billing is unknown. No duplicate call was made.'}}
    if state == 'no_supported_clinical_facts':
        return {'state': 'failed', 'checkpoint': str(root),
                'failure': {'message': 'No supported clinical facts were extracted, so no report was produced. The unchanged source and review remain in the checkpoint.'}}
    return {'state': state, 'checkpoint': str(root), 'operations': operations,
            'queue_blocked': bool(value.get('active_operations')),
            'failure': {'message': 'Clinical stage is incomplete; inspect its unchanged checkpoint.'}}


def request_cancel(identifier):
    root = directory(identifier)
    current = load(root / 'receipt.json')
    if not current:
        raise ValueError('Unknown study for this dedicated user.')
    if current['state'] in FINAL - {'needs_attention'} and not current.get('queue_blocked'):
        return view(current)
    save(root / 'cancel-request.json', {'requested_at': time.time(), 'study_id': current['id']})
    return {**view(current), 'cancellation_requested': True}


async def cancel_active(step, record):
    operation_dir = Path(record['output_directory']) / 'steps' / step['id'] / 'operation'
    known = load(operation_dir / 'receipt.json') or {}
    if known.get('state') in {'submitting', 'admission_unknown'} and not known.get('operation_id'):
        return {'state': 'needs_attention', 'failure': 'Admission is unknown; cancellation cannot invent an operation ID.'}
    operation = known.get('operation_id')
    recorded = record.get('steps', {}).get(step['id'], {}).get('operation_id')
    if recorded and recorded != operation:
        raise ValueError('Saved study and operation receipts disagree; no cancellation was sent.')
    if not operation:
        return {'state': 'cancelled'}
    return await cancel_known_operation(operation, step['kind'] == 'batch', directory(record['id']) / 'cancel-sent.json')


async def cancel_known_operation(operation, scientific, intent):
    workflow = workflow_module()
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    async with workflow.batch.httpx2.AsyncClient(headers={'Authorization': 'Bearer ' + os.environ['SCIENTIFIC_MODELS_API_KEY']}, timeout=120, trust_env=False) as http:
        async with workflow.batch.Client(workflow.batch.streamable_http_client(endpoint, http_client=http)) as client:
            saved = load(intent)
            if saved and saved.get('operation_id') != operation:
                raise ValueError('Cancellation receipt belongs to another operation; no request was sent.')
            if not saved:
                save(intent, {'operation_id': operation, 'state': 'sending'})
                await workflow.batch.call(client, 'cancel_scientific_run' if scientific else 'cancel_operation', {'operation_id': operation})
                save(intent, {'operation_id': operation, 'state': 'sent'})
            result = await workflow.batch.call(client, 'get_scientific_status' if scientific else 'get_operation', {'operation_id': operation})
    # Native status is flat: its "operation" field is a name such as
    # "generate-media". Scientific status can wrap the operation object.
    operation_status = result['operation'] if isinstance(result.get('operation'), dict) else result
    status = operation_status.get('status')
    if not isinstance(status, str) or not status:
        raise ValueError('Cancellation status response has no operation status; cancellation is not confirmed.')
    if status not in {'succeeded', 'failed', 'cancelled', 'expired', 'preempted'} and saved and saved.get('state') == 'sending':
        return {'state': 'needs_attention', 'operation_id': operation, 'queue_blocked': True,
                'cancellation_unknown': True,
                'failure': {'message': 'The original cancellation response was lost. Read-only status is still nonterminal; cancellation is not confirmed and later study work is held. Inspect the known operation before explicit recovery; no cancellation or inference was silently repeated.'}}
    return {'state': 'cancelled' if status in {'succeeded', 'failed', 'cancelled', 'expired', 'preempted'} else 'cancelling', 'operation_id': operation}


async def advance(identifier, model_runner=None, local_runner=None, cancel_runner=None):
    root = directory(identifier)
    with receipt_lock(root):
        record = load(root / 'receipt.json')
        if not record or (record['state'] in FINAL and not (root / 'cancel-request.json').exists()):
            return view(record) if record else None
        plan = json.loads((root / 'plan.json').read_bytes())
        cancelling = (root / 'cancel-request.json').exists()
        try:
            if cancelling:
                verify_cancellation_identity(record, plan)
            else:
                verify_inputs(record)
            remaining = [step for step in plan['steps'] if step['id'] not in record['completed_steps']]
            if cancelling:
                active = remaining[0] if remaining else None
                if record.get('admission_unknown'):
                    outcome = {'state': 'needs_attention', 'queue_blocked': True,
                               'cancellation_failure': {'message': 'An earlier provider admission is unknown. No duplicate call or false cancellation confirmation is allowed.'}}
                elif active and active['kind'] == 'clinical':
                    from scientific_clinical import operation_states
                    checkpoint = Path(record['output_directory']) / 'steps' / active['id'] / 'clinical-checkpoint'
                    saved = load(checkpoint / 'receipt.json') or {}
                    pending = [item for item in operation_states(checkpoint, saved.get('files', {}))
                               if item['status'] not in {'succeeded', 'failed', 'cancelled', 'expired', 'preempted'}]
                    outcomes = [await cancel_known_operation(item['operation_id'], False,
                        root / ('cancel-' + item['operation_id'] + '.json')) for item in pending]
                    unresolved = next((item for item in outcomes if item['state'] == 'needs_attention'), None)
                    outcome = unresolved or {'state': 'cancelled' if all(item['state'] == 'cancelled' for item in outcomes) else 'cancelling'}
                else:
                    outcome = await (cancel_runner or cancel_active)(active, record) if active and active['kind'] in MODEL_KINDS else {'state': 'cancelled'}
                if 'failure' in outcome:
                    outcome = {**outcome, 'cancellation_failure': outcome['failure']}
                    del outcome['failure']
                record.update(outcome, phase='cancellation')
                if outcome['state'] == 'cancelled':
                    record['queue_blocked'] = False
                    record['finished_at'] = time.time()
            elif remaining:
                step = remaining[0]
                record.update(state='running', phase=step['kind'], current_step=step['id'])
                save(root / 'receipt.json', record)
                if step['kind'] in MODEL_KINDS:
                    outcome = await (model_runner or run_model)(step, record)
                elif step['kind'] == 'clinical':
                    outcome = run_clinical(step, record)
                else:
                    outcome = (local_runner or run_local)(step, record)
                record['steps'][step['id']] = outcome
                if outcome['state'] == 'completed':
                    record['completed_steps'].append(step['id'])
                    record['phase'] = 'step_completed'
                else:
                    record['state'] = outcome['state']
                    if outcome['state'] in FINAL:
                        record['finished_at'] = time.time()
                    if outcome.get('failure'):
                        record['failure'] = outcome['failure']
                    if outcome.get('admission_unknown'):
                        record.update(admission_unknown=True, queue_blocked=True)
                    elif outcome.get('queue_blocked'):
                        record['queue_blocked'] = True
            else:
                record.update(state='publishing', phase='publication')
                save(root / 'receipt.json', record)
                artifacts = publication_artifacts(plan, record)
                manifest = {'schema': 'scientific-study-artifacts/v1', 'study_id': record['id'],
                            'plan_identity': record['identity'], 'title': record['title'],
                            'artifacts': artifacts, 'scientific_validity_claim': False,
                            'inputs': list(record['inputs'].values()), 'implementations': record['implementations'],
                            'operations': [value['operation_id'] for value in record['steps'].values() if value.get('operation_id')],
                            'clinical_operations': [item for value in record['steps'].values() for item in value.get('operations', [])]}
                with tempfile.TemporaryDirectory(prefix='study-manifest-') as temporary:
                    source = Path(temporary) / 'manifest.json'
                    source.write_bytes(canonical(manifest) + b'\n')
                    # A killed object-store copy must not corrupt a fixed final
                    # filename. Only the completed receipt exposes this verified
                    # immutable generation; previous partial attempts remain.
                    publication = Path(record['output_directory']) / ('publication-' + uuid.uuid4().hex)
                    final = persist_local_file(source, publication / 'manifest.json')
                record.update(state='completed', phase='completed', current_step=None,
                              manifest=final, artifacts=artifacts, finished_at=time.time())
        except Exception as error:
            active = record.get('current_step')
            known = load(Path(record['output_directory']) / 'steps' / active / 'operation' / 'receipt.json') if active else None
            unknown = bool(known and known.get('state') in {'submitting', 'admission_unknown'})
            active_operation = bool(known and known.get('operation_id') and known.get('state') not in {'verified', 'succeeded', 'failed', 'cancelled', 'expired', 'preempted'})
            if cancelling:
                unknown |= bool(record.get('admission_unknown'))
                active_operation |= bool(record.get('queue_blocked'))
            active_spec = next((step for step in plan['steps'] if step['id'] == active), None)
            if active_spec and active_spec['kind'] == 'clinical':
                from scientific_clinical import operation_states
                checkpoint = Path(record['output_directory']) / 'steps' / active / 'clinical-checkpoint'
                saved = load(checkpoint / 'receipt.json') or {}
                files = saved.get('files', {})
                operations = operation_states(checkpoint, files)
                active_operation = any(item['status'] not in {'succeeded', 'failed', 'cancelled', 'expired', 'preempted'} for item in operations)
                for name in files:
                    if name.endswith('/request.json') and name.replace('/request.json', '/response.json') not in files:
                        state_info = files.get(name.replace('/request.json', '/state.json'))
                        state = json.loads(Path(state_info['path']).read_bytes()) if state_info else {}
                        unknown |= not bool(state.get('operation_id'))
            record.update(state='needs_attention' if unknown or active_operation else 'failed', phase='failure',
                          **{'cancellation_failure' if cancelling else 'failure':
                             {'type': type(error).__name__, 'message': str(error)[:2000]}},
                          admission_unknown=unknown, queue_blocked=unknown or active_operation, finished_at=time.time())
        record['updated_at'] = time.time()
        save(root / 'receipt.json', record)
        return view(record)


def completion_summaries(record, artifacts):
    """Small read-only projection of explicitly published, verified summaries.

    The full file is always retained. The preview byte ceiling is a display
    bound, never an execution/admission limit or silently truncated table.
    Legacy studies without producer registration have no projection.
    """
    if record.get('state') != 'completed':
        return []
    summaries = []
    for step_id, step in record.get('steps', {}).items():
        filename = step.get('customer_summary')
        if not filename:
            continue
        registered = step.get('files', {}).get(filename)
        selected = step.get('customer_artifacts', {}).get(filename)
        artifact = next((item for item in artifacts if registered and all(
            item.get(key) == registered.get(key) for key in ('path', 'sha256', 'size_bytes'))), None)
        entry = {'source_step': step_id, 'state': 'unavailable'}
        if not registered or not selected or not artifact or step.get('state') != 'completed' or any(
                selected.get(key) != registered.get(key) for key in ('path', 'sha256', 'size_bytes')):
            entry['notice'] = 'Summary is not a verified published customer artifact; no measurements are projected.'
        else:
            entry.update(artifact_name=artifact['name'], sha256=artifact['sha256'], download_url=artifact['download_url'])
            if artifact['size_bytes'] > 65536:
                entry['notice'] = 'Summary exceeds the inline preview size; download the complete published file. No rows are truncated.'
            else:
                try:
                    path = path_in_workspace(artifact['path'])
                    with path.open('rb') as stream:
                        raw = stream.read(65537)
                    if len(raw) != artifact['size_bytes'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
                        raise ValueError('Summary bytes differ from publication.')
                    value = json.loads(raw)
                    if not isinstance(value, dict) or value.get('schema') != 'scientific-study-summary/v1' or not isinstance(value.get('text'), str):
                        raise ValueError('Unsupported summary shape.')
                    entry.update(state='verified', text=value['text'])
                except (OSError, ValueError, TypeError):
                    entry['notice'] = 'Published summary could not be verified; no measurements are projected. Saved study state is unchanged.'
        summaries.append(entry)
    return summaries


def view(record):
    result = copy.deepcopy({key: record[key] for key in ('id', 'title', 'state', 'phase', 'current_step', 'completed_steps',
        'steps', 'created_at', 'updated_at', 'finished_at', 'failure', 'cancellation_failure', 'admission_unknown', 'cancellation_unknown', 'queue_blocked', 'manifest', 'artifacts') if key in record})
    result.update(job_id=record['id'], status='completed' if record['state'] == 'completed' else
                  'failed' if record['state'] in {'failed', 'needs_attention', 'cancelled'} else 'running',
                  durable_study=True, output_directory=record['output_directory'],
                  guidance='This saved whole study runs independently of chat. Reconnect to Runs for phases and verified final files; no continue prompt is needed for mechanical waits.')
    result['step_count'] = len(json.loads((directory(record['id']) / 'plan.json').read_bytes())['steps'])
    for artifact in result.get('artifacts', []):
        relative = Path(artifact['path']).relative_to(workspace())
        artifact['download_url'] = '/demos?' + urlencode({'tab': 'workspace', 'path': str(relative.parent), 'file': relative.name})
    summaries = completion_summaries(record, result.get('artifacts', []))
    if summaries:
        result['completion_summaries'] = summaries
        result['guidance'] += ' Quote verified completion_summaries text with its exact record identities and artifact links; do not recompute, transpose or invent summary numbers. Unavailable values stay unavailable.'
    return result


def get(identifier):
    record = load(directory(identifier) / 'receipt.json')
    if not record:
        raise ValueError('Unknown study for this dedicated user.')
    if record['caller_fingerprint'] != caller_fingerprint():
        raise ValueError('Study belongs to a different configured platform key.')
    return view(record)


def list_studies():
    results = []
    for path in registry().glob('*/receipt.json'):
        record = load(path)
        if record['caller_fingerprint'] == caller_fingerprint():
            results.append(view(record))
    return sorted(results, key=lambda item: item['created_at'])


def engine_status():
    configured = os.environ.get('SCIENTIFIC_STUDY_OWNER_MODE') in {'first-instance', 'stopped-predecessor'}
    path = Path(os.environ.get('SCIENTIFIC_EXECUTION_DIR', '/data/hcls-execution')) / 'study-worker.json'
    try:
        health = load(path) or {}
        alive = (health.get('owner_namespace') == owner_identity()
                 and Path(f'/proc/{int(health["pid"])}/stat').read_text().split()[21] == health['process_start'])
    except (ValueError, KeyError, OSError):
        health, alive = {}, False
    return {'configured': configured, 'alive': alive, 'last_observed_at': health.get('updated_at'),
            'current_study': health.get('current_study'), 'blocked_by_study': health.get('blocked_by_study')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true')
    group.add_argument('--status')
    group.add_argument('--cancel')
    group.add_argument('--advance')
    args = parser.parse_args()
    if args.list:
        result = {'data': list_studies(), 'engine': engine_status()}
    elif args.status:
        result = get(args.status)
    elif args.cancel:
        result = request_cancel(args.cancel)
    else:
        result = asyncio.run(advance(args.advance))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
