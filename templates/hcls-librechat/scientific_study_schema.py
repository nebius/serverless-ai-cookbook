"""Typed launch contract shared by the existing execution MCP and its validator."""
TEXT = {'type': 'string', 'minLength': 1}
FILE = {'oneOf': [TEXT, {'type': 'object', 'additionalProperties': False,
    'required': ['step', 'file'], 'properties': {'step': TEXT, 'file': TEXT}}],
    'description': 'Existing workspace path or exact earlier-step published file reference {step,file}; paths do not transform data.'}


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
    'source': FILE, 'parameters': FILE}
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
    local('write-json', object_schema({'filename': TEXT, 'value': {}})),
    local('python-script', object_schema({'script': {**TEXT, 'description': 'Existing workspace Python source, hash-frozen before admission; not a generated later-step file.'},
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
    local('report', object_schema({'title': TEXT, 'sections': {'type': 'array', 'minItems': 1,
        'items': object_schema({'title': TEXT, 'file': FILE, 'format': {'enum': ['markdown', 'csv', 'operation-timing', 'recorded-export', 'rgb-statistics', 'mindeval-runs']}})}})),
    local('clinical-study', object_schema({'plan_file': FILE})),
    local('mindeval', object_schema({'title': TEXT, 'records': {'type': 'array', 'minItems': 1,
        'items': FILE, 'description': 'Full saved MindEval run files with state.config, state.transcript and retained judgment. No catalog/model calls. Publishes report.md, scores.csv, runs.csv, measurements.json, provenance.json, exact records/ and full transcripts/.'}})),
]
STUDY_SCHEMA = object_schema({'schema': {'const': 'scientific-workflow/v2'}, 'title': TEXT,
    'steps': {'type': 'array', 'minItems': 1, 'items': {'oneOf': STEPS}},
    'deliverables': {'type': 'array', 'minItems': 1, 'items': object_schema({
        'name': TEXT, 'role': {'enum': ['report', 'data', 'metrics', 'provenance', 'support']}, 'source': FILE})}})

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
    'report': (['report.md', 'provenance.json', 'assembly-plan.json', 'helper.py', 'completion-manifest.json'], ['sources/NNN.ext retains every exact supplied section.']),
    'mindeval': (['report.md', 'methods.md', 'runs.csv', 'scores.csv', 'measurements.json', 'provenance.json', 'records.json', 'completion-manifest.json'],
                 ['records/NNN.json and transcripts/NNN.txt retain every full supplied record and transcript.']),
    'clinical-study': (['report.md', 'measurement.json', 'completion-manifest.json'], ['Per-case measurements and preserved input files follow the helper completion-manifest.']),
}


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
                         'always_on_success': PHASE_OUTPUTS[name][0], 'conditional': PHASE_OUTPUTS[name][1]} for name in methods},
        'submission': {'tool': 'run_scientific_workflow_mcp_environment-execution',
                       'arguments': {'plan_file': '/workspace/research/plan.json', 'output_directory': '/workspace/research/final'}},
        'plan_file_example': {'schema': 'scientific-workflow/v2', 'title': 'Retained measurements',
            'steps': [{'id': 'report', 'kind': 'analysis', 'method': 'report', 'arguments': {
                'title': 'Retained measurements', 'sections': [{'title': 'Measured rows', 'format': 'csv', 'file': '/workspace/research/measurements.csv'}]}}],
            'deliverables': [{'name': name, 'role': role, 'source': {'step': 'report', 'file': name}}
                             for name, role in [('report.md', 'report'), ('provenance.json', 'provenance')]]},
        'guidance': 'Example paths are placeholders: use actual existing files and user-authorized phases. Write longer plan/script files in bounded logical pieces, validate complete JSON, then submit once. File references are paths, not automatic content conversion. Declare only guaranteed outputs. Read-only reuse needs no provider catalog. Current model input/settings still come from its exact live published schema.'}
