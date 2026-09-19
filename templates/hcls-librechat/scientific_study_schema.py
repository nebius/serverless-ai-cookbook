"""Typed launch contract shared by the existing execution MCP and its validator."""
TEXT = {'type': 'string', 'minLength': 1}
FILE = {'oneOf': [TEXT, {'type': 'object', 'additionalProperties': False,
    'required': ['step', 'file'], 'properties': {'step': TEXT, 'file': TEXT}}],
    'description': 'Existing workspace path or exact earlier-step published file reference {step,file}.'}


def object_schema(properties, required=None):
    return {'type': 'object', 'additionalProperties': False,
            'required': list(properties) if required is None else required, 'properties': properties}


def local(method, args):
    return object_schema({'id': TEXT, 'kind': {'enum': ['preparation', 'analysis']},
                          'method': {'const': method}, 'arguments': args})


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
    local('parquet-export', object_schema({'source': FILE, 'formats': {'type': 'array', 'minItems': 1,
        'uniqueItems': True, 'items': {'enum': ['npz', 'hdf5', 'zip', 'sqlite']}}})),
    local('proteinmpnn-input', object_schema({'backbone': FILE, 'structure_index': {'type': 'integer', 'minimum': 0},
        'chain': {'type': 'string', 'minLength': 1, 'maxLength': 1},
        'num_sequences': {'type': 'integer', 'minimum': 1, 'maximum': 8},
        'seed': {'type': 'integer', 'minimum': 1, 'maximum': 2147483647},
        'sampling_temp': {'type': 'number', 'minimum': 0.01, 'maximum': 1},
        'omit_aas': {'type': 'array', 'uniqueItems': True, 'items': {'enum': list('ACDEFGHIKLMNPQRSTVWYX')}}})),
    local('esmfold2-fast-input', object_schema({'design_input': FILE, 'design_result': FILE,
        'design_index': {'type': 'integer', 'minimum': 0}, 'seed': {'type': 'integer', 'minimum': 0, 'maximum': 2147483647}})),
    local('structure', {**object_schema({'reference': FILE, 'prediction': FILE, 'result': FILE,
        'chain_map': {'type': 'array', 'minItems': 1, 'items': TEXT}, 'structure_index': {'type': 'integer', 'minimum': 0},
        'residue_map': FILE, 'request_file': FILE}, ['reference', 'chain_map']), **PREDICTION}),
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
]
STUDY_SCHEMA = object_schema({'schema': {'const': 'scientific-workflow/v2'}, 'title': TEXT,
    'steps': {'type': 'array', 'minItems': 1, 'items': {'oneOf': STEPS}},
    'deliverables': {'type': 'array', 'minItems': 1, 'items': object_schema({
        'name': TEXT, 'role': {'enum': ['report', 'data', 'metrics', 'provenance', 'support']}, 'source': FILE})}})
