"""Typed launch contract shared by the existing execution MCP and its validator."""
TEXT = {'type': 'string', 'minLength': 1}
REPORT_HEADING = {**TEXT, 'pattern': r'\S', 'not': {'pattern': r'[\r\n]'},
    'description': 'Meaningful nonblank one-line heading without CR/LF. No arbitrary character-length cap; preserved verbatim.'}
JSON_BASENAME = {**TEXT, 'pattern': r'^[^/]*\.json$', 'not': {'pattern': r'\n$'},
    'description': 'Exact JSON basename ending .json, without directory components. This helper writes JSON, not Markdown; use a declared saved Python-script output or report helper for Markdown.'}
PYTHON_SCRIPT_CLI_EXAMPLE = '''import argparse, json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--inputs', required=True)
parser.add_argument('--output-dir', required=True)
args = parser.parse_args()
bindings = json.loads(Path(args.inputs).read_text())
result_file = Path(bindings['inputs']['result_a'])
result = json.loads(result_file.read_text())
parameters = bindings['parameters']
output_directory = Path(args.output_dir)
# Write exactly your declared output filenames here; close them before exit.
'''
FILE = {'oneOf': [TEXT, {'type': 'object', 'additionalProperties': False,
    'required': ['step', 'file'], 'properties': {'step': TEXT, 'file': TEXT}}],
    'description': 'Existing workspace file or exact earlier-step published file reference {step,file}; paths do not transform data. Future outputs are not existing files: never predict worker paths or pass a steps directory. For Python analysis bind each required output as its own named inputs item with file:{step,file}.'}


def object_schema(properties, required=None):
    return {'type': 'object', 'additionalProperties': False,
            'required': list(properties) if required is None else required, 'properties': properties}


def local(method, args):
    return object_schema({'id': TEXT, 'kind': {'enum': ['preparation', 'analysis']},
                          'method': {'const': method}, 'arguments': args})


CHAIN = {'oneOf': [TEXT, object_schema({'selection': {'const': 'sole-protein-chain'}})],
         'description': 'Exact chain ID, or explicitly request the sole observed protein chain; zero/multiple chains fail, never guess A.'}
NATIVE = object_schema({'id': TEXT, 'kind': {'const': 'native'}, 'model': TEXT,
                       'input': FILE, 'idempotency_key': TEXT})
BATCH_FIELDS = {'id': TEXT, 'kind': {'const': 'batch'}, **{key: TEXT for key in (
    'model', 'tool', 'operation', 'media_type', 'entry_name', 'semantic_type', 'idempotency_key', 'display_name')},
    'source': FILE, 'parameters': {**FILE,
        'description': FILE['description'] + ' The parameters JSON file contains only the model parameters object from submit-tool input_schema.properties.parameters, never a full scientific-run envelope; the batch client validates before uploads and does not unwrap it.'}}
BATCH = object_schema({**BATCH_FIELDS, 'compression': TEXT, 'service_class': TEXT,
                       'source_artifact': FILE}, list(BATCH_FIELDS))
PREDICTION = {'oneOf': [{'required': ['result'], 'not': {'required': ['prediction']}},
                      {'required': ['prediction'], 'not': {'required': ['result']}}]}
THRESHOLDS = {'type': 'array', 'items': object_schema({'confidence_above': {'type': 'number'},
                                                     'rmsd_below_angstrom': {'type': 'number'}})}
CLINICAL = object_schema({'id': TEXT, 'kind': {'const': 'clinical'}, 'source': FILE,
    'source_type': {'enum': ['audio', 'transcript', 'artifact']}, 'language': {'enum': ['en', 'de']},
    'report_model': {**TEXT, 'description': 'Explicit clinical model on the existing Token Factory provider; no automatic model swap. The tested draft profile is Qwen/Qwen3-235B-A22B-Instruct-2507.'},
    'asr_model': {'enum': ['nemotron-speech-en-0-6b', 'nemotron-speech-multilingual-0-6b']}},
    ['id', 'kind', 'source', 'source_type', 'language', 'report_model'])
STEPS = [NATIVE, BATCH, CLINICAL,
    local('write-json', object_schema({'filename': JSON_BASENAME, 'value': {}})),
    local('python-script', object_schema({'script': {**TEXT, 'description': 'Existing workspace Python source, hash-frozen before admission; not a generated later-step file. CLI receives --inputs <bindings.json path> --output-dir <private directory>; parse arguments, then json.loads(Path(args.inputs).read_text()). Read source paths from bindings["inputs"][name], not JSON from argv itself. Discovery includes the exact CLI example.'},
        'inputs': {'type': 'array', 'items': object_schema({'name': TEXT, 'file': FILE})},
        'parameters': {'type': 'object', 'description': 'Immutable scientific parameters supplied in the saved bindings JSON.'},
        'outputs': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': TEXT}},
        ['script', 'inputs', 'parameters', 'outputs'])),
    local('parquet-export', object_schema({'source': FILE, 'formats': {'type': 'array', 'minItems': 1,
        'uniqueItems': True, 'items': {'enum': ['npz', 'hdf5', 'zip', 'sqlite']}}})),
    local('proteinmpnn-input', object_schema({'backbone': FILE, 'structure_index': {'type': 'integer', 'minimum': 0},
        'chain': CHAIN,
        'num_sequences': {'type': 'integer', 'minimum': 1, 'maximum': 8},
        'seed': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647},
        'sampling_temp': {'type': 'number', 'minimum': 0.01, 'maximum': 1},
        'omit_aas': {'type': 'array', 'uniqueItems': True, 'items': {'enum': list('ACDEFGHIKLMNPQRSTVWYX')}}})),
    local('esmfold2-fast-input', object_schema({'design_input': FILE, 'design_result': FILE,
        'design_index': {'type': 'integer', 'minimum': 0}, 'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2147483647}})),
    local('design-refold-correspondence', object_schema({**{name: FILE for name in
        ('design_input', 'design_result', 'refold_input', 'refold_parameters', 'prediction')},
        'design_index': {'type': 'integer', 'minimum': 0}, 'structure_index': {'type': 'integer', 'minimum': 0},
        'prediction_chain': CHAIN})),
    local('structure', {**object_schema({'reference': FILE, 'prediction': FILE, 'result': FILE,
        'chain_map': {'type': 'array', 'minItems': 1, 'items': TEXT}, 'structure_index': {'type': 'integer', 'minimum': 0},
        'residue_map': FILE, 'request_file': FILE}, ['reference']), **PREDICTION,
        'anyOf': [{'required': ['chain_map']}, {'required': ['residue_map']}]}),
    local('docking', {**object_schema({'reference': FILE, 'prediction': FILE, 'result': FILE,
        'same_coordinate_frame': {'const': True}, 'threshold_queries': THRESHOLDS},
        ['reference', 'same_coordinate_frame']), **PREDICTION}),
    local('docking-batch', object_schema({'runs': {'type': 'array', 'minItems': 1, 'items': {
        **object_schema({'run_id': TEXT, 'group_id': TEXT, 'reference_file': FILE, 'result_file': FILE,
                          'prediction_file': FILE}, ['run_id', 'reference_file']),
        'oneOf': [{'required': ['result_file'], 'not': {'required': ['prediction_file']}},
                  {'required': ['prediction_file'], 'not': {'required': ['result_file']}}]}},
        'same_coordinate_frame': {'const': True}, 'threshold_queries': THRESHOLDS}, ['runs', 'same_coordinate_frame'])),
    local('aging', object_schema({'model': {'enum': ['phenoage', 'altumage']}, 'cohorts': {'type': 'array',
        'minItems': 1, 'items': object_schema({'label': TEXT, 'input_file': FILE, 'result_file': FILE})},
        'coefficient_version': TEXT, 'reference_ages': FILE}, ['model', 'cohorts'])),
    local('genmol', object_schema({'input_file': {**FILE,
        'description': FILE['description'] + ' Original raw GenMol request JSON, with smiles and num_molecules; preserves actual scoring/defaults.'},
        'result_file': {**FILE, 'description': FILE['description'] + ' Raw GenMol result JSON with molecules:[{smiles,score}]. Deterministically measures validity, unique/duplicate/returned counts, QED and Crippen LogP, underfill and unavailable scores; no new inference or recursive envelope guessing.'}})),
    local('protein-design-analysis', {**object_schema({
        'manifest_file': {**FILE, 'description': FILE['description'] + ' Exact batch output-manifest.json; verified output-NN.artifact siblings are read from the same directory in manifest order using declared media types, not filename extensions. Measures all artifacts; no new inference or efficacy claim.'},
        'binder_chain': TEXT, 'binder_length_min': {'type': 'integer', 'minimum': 1},
        'binder_length_max': {'type': 'integer', 'minimum': 1},
        'target_reference': FILE, 'target_chain': TEXT}, ['manifest_file']),
        'dependentRequired': {'target_reference': ['target_chain'], 'target_chain': ['target_reference']}}),
    local('report', object_schema({'title': REPORT_HEADING, 'sections': {'type': 'array', 'minItems': 1, 'maxItems': 16,
        'items': object_schema({'title': REPORT_HEADING, 'file': FILE, 'format': {'enum': ['markdown', 'csv', 'operation-timing', 'recorded-export', 'rgb-statistics', 'mindeval-runs']}})}})),
    local('clinical-study', object_schema({'plan_file': FILE})),
    local('mindeval', object_schema({'title': REPORT_HEADING, 'records': {'type': 'array', 'minItems': 1,
        'items': FILE, 'description': 'Full native saved run JSON: state.config, state.transcript[{role,content,...}], and optional state.judgment.judgment mapping criterion names to scores. This nested native judgment shape is directly supported: do NOT transform it into judgment.scores or write a custom parser. Preserves original records/transcripts, identities, supplied criterion rows, descriptive within-profile pairing, missing cells and judge-family limitations. No catalog/model calls.'}})),
]
DELIVERABLE = object_schema({'name': TEXT,
    'role': {'enum': ['report', 'data', 'metrics', 'provenance', 'support']}, 'source': FILE})
STUDY_SCHEMA = object_schema({'schema': {'const': 'scientific-workflow/v2'}, 'title': TEXT,
    'steps': {'type': 'array', 'minItems': 1, 'items': {'oneOf': STEPS}},
    'deliverables': {'type': 'array', 'minItems': 1, 'items': DELIVERABLE}})
DRAFT_SCHEMA = object_schema({
    'draft_directory': {**TEXT, 'description': 'Workspace directory for verified draft receipts and immutable plan revisions, not the final output directory.'},
    'expected_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$',
                        'description': 'Required for edits to an existing draft: copy current_sha256 from its latest receipt.'},
    'title': TEXT,
    'steps': {'type': 'array', 'minItems': 1, 'items': {'oneOf': STEPS},
              'description': 'One small related group of complete typed steps. Upsert by id; existing order is retained and new IDs append in supplied order.'},
    'deliverables': {'type': 'array', 'minItems': 1, 'items': DELIVERABLE,
                     'description': 'Upsert declared final files by name; references may target steps added in a later draft edit.'},
    'remove_steps': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': TEXT},
    'remove_deliverables': {'type': 'array', 'minItems': 1, 'uniqueItems': True, 'items': TEXT},
    'finalize': {'type': 'boolean', 'default': False,
                 'description': 'Validate the complete v2 plan and existing inputs using the unchanged admission validator. May accompany the last group. Does not submit inference.'},
}, ['draft_directory'])

# Discovery and validation use the same argument definitions, not a second
# loosely documented plan language. Lists apply only to successful phases;
# conditional filenames must never become unconditional final deliverables.
PHASE_OUTPUTS = {
    'native': (['result.json'], ['Other files depend on the native result contract.']),
    'batch': (['result.json', 'output-manifest.json'], ['output-NN.artifact: one verified sibling per manifest entry; role, MIME and compression come from output-manifest.json.']),
    'clinical': ([], ['Returned files follow the existing clinical receipt. A valid no-report outcome does not promise a normal report.']),
    'write-json': ([], ['Exactly the declared filename; JSON values are not automatically loaded from file references.']),
    'python-script': (['script.py', 'input-bindings.json', 'script-provenance.json'], ['Every declared outputs filename is required nonempty before success.']),
    'parquet-export': (['comparison.json', 'report.md'], ['Requested formats only: data.npz, data.h5, data.zip, data.sqlite.']),
    'proteinmpnn-input': (['input.json', 'backbone.pdb', 'provenance.json', 'report.md'], []),
    'esmfold2-fast-input': (['input.json', 'parameters.json', 'selected.fasta', 'backbone.pdb', 'provenance.json', 'report.md'], []),
    'design-refold-correspondence': (['reference.pdb', 'prediction.structure', 'prediction-result.json', 'residue-map.json', 'provenance.json', 'report.md'], []),
    'structure': (['metrics.json', 'residue-mapping.json', 'report.md', 'methods.md'], ['prediction.pdb OR prediction.cif according to the actual selected coordinates.']),
    'docking': (['metrics.json', 'rows.csv', 'report.md'], []),
    'docking-batch': (['metrics.json', 'rows.csv', 'report.md'], []),
    'aging': (['metrics.json', 'rows.csv', 'report.md'], []),
    'genmol': (['metrics.json', 'rows.csv', 'report.md', 'completion-manifest.json'], []),
    'protein-design-analysis': (['measurements.json', 'inventory.csv', 'report.md'], []),
    'report': (['report.md', 'provenance.json', 'assembly-plan.json', 'helper.py', 'completion-manifest.json'], ['sources/NNN.ext retains every exact supplied section.']),
    'mindeval': (['report.md', 'methods.md', 'runs.csv', 'scores.csv', 'measurements.json', 'provenance.json', 'records.json', 'completion-manifest.json'],
                 ['records/NNN.json and transcripts/NNN.txt retain every full supplied record and transcript.']),
    'clinical-study': (['report.md', 'measurement.json', 'completion-manifest.json'], ['Per-case measurements and preserved input files follow the helper completion-manifest.']),
}
# Exact directory names published by these helpers, never downloadable files.
# Unknown/dynamic outputs are not inferred from prose or forbidden here.
PHASE_OUTPUT_DIRECTORIES = {'mindeval': ['records', 'transcripts'], 'report': ['sources']}

# Only helpers with an exhaustive output contract belong here. Model,
# clinical and manifest-driven helper outputs remain dynamic, not guessed.
PHASE_OUTPUT_ALTERNATIVES = {
    'structure': ['prediction.pdb', 'prediction.cif'],
    'proteinmpnn-input': [], 'esmfold2-fast-input': [],
    'design-refold-correspondence': [],
    'genmol': [],
    'protein-design-analysis': [],
}


def known_output_files(step):
    """Possible exact files when the helper or saved plan determines them.

    Possible is not guaranteed: structure emits one coordinate format. None
    means this preflight cannot know the complete output set, not an error.
    """
    method = step.get('method')
    if method in PHASE_OUTPUT_ALTERNATIVES:
        return set(PHASE_OUTPUTS[method][0] + PHASE_OUTPUT_ALTERNATIVES[method])
    args = step.get('arguments', {})
    if method == 'write-json':
        return {args['filename']}
    if method == 'python-script':
        return set(PHASE_OUTPUTS[method][0]) | set(args['outputs'])
    if method == 'parquet-export':
        return set(PHASE_OUTPUTS[method][0]) | {
            'data.' + {'hdf5': 'h5'}.get(kind, kind) for kind in args['formats']}
    return None


def describe_workflow(methods=None):
    contracts = {item['properties'].get('method', item['properties']['kind']).get('const'): item for item in STEPS}
    if methods is None:
        return {'schema': 'scientific-workflow-discovery/v1', 'methods': list(contracts),
                'guidance': 'Select only needed methods to obtain their exact typed phase contract and published filenames. Do not inspect implementation source or all unrelated model schemas.'}
    if not isinstance(methods, list) or not methods or any(name not in contracts for name in methods):
        raise ValueError('Select nonempty known phase names: ' + ', '.join(contracts))
    if len(set(methods)) != len(methods):
        raise ValueError('Select each phase contract only once.')
    return {'schema': 'scientific-workflow-discovery/v1', 'study_schema': 'scientific-workflow/v2',
        'phases': {name: {'step_schema': contracts[name],
                         'always_on_success': PHASE_OUTPUTS[name][0], 'conditional': PHASE_OUTPUTS[name][1],
                         'directories_not_deliverable_files': PHASE_OUTPUT_DIRECTORIES.get(name, []),
                         **({'possible_exact_files': PHASE_OUTPUTS[name][0] + PHASE_OUTPUT_ALTERNATIVES[name]}
                            if name in PHASE_OUTPUT_ALTERNATIVES else {}),
                         **({'cli_example': PYTHON_SCRIPT_CLI_EXAMPLE,
                             'bindings_schema': {'schema': 'scientific-python-bindings/v1',
                                                 'inputs': {'result_a': '<resolved verified file path>'},
                                                 'parameters': '<exact saved parameters object>'}}
                            if name == 'python-script' else {})} for name in methods},
        'submission': {'tool': 'run_scientific_workflow_mcp_environment-execution',
                       'arguments': {'plan_file': '/workspace/research/plan.json', 'output_directory': '/workspace/research/final'}},
        'draft_composer': {'tool': 'compose_scientific_workflow_mcp_environment-execution',
            'guidance': 'Create with draft_directory, title and a compact group of typed steps/deliverables. Add related groups with expected_sha256=current_sha256; finalize=true can accompany the last group. Pass its finalized plan_file to the existing launcher. Draft-directory-only reads recover a lost reply. No inference is submitted by composition.'},
        'plan_file_example': {'schema': 'scientific-workflow/v2', 'title': 'Retained measurements',
            'steps': [{'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
                'title': 'Retained measurements', 'sections': [{'title': 'Measured rows', 'format': 'csv', 'file': '/workspace/research/measurements.csv'}]}}],
            'deliverables': [{'name': name, 'role': role, 'source': {'step': 'report', 'file': name}}
                             for name, role in [('report.md', 'report'), ('provenance.json', 'provenance')]]},
        'guidance': 'Example paths are placeholders: use actual existing files and user-authorized phases. Prefer the draft composer for longer plans; save unsupported-science Python source in bounded logical pieces before referencing it. Future generated files require exact {step,file} references, not predicted worker paths or directories; bind each required Python input separately. Correct saved drafts only through the composer, never alter immutable admitted plans. File references are paths, not automatic content conversion. Declare only guaranteed outputs. Read-only reuse needs no provider catalog. Current model input/settings still come from its exact live published schema.'}
