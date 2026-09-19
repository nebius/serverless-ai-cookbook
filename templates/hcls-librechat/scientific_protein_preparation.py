"""Explicit dependent inputs for the existing ProteinMPNN and ESMFold2-Fast contracts.

No inference or sequence selection is implicit. The scientist chooses the
backbone/chain/design index and sampling settings in the immutable study plan.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile

from scientific_preparation import canonical
from scientific_receipts import file_measurement, verify_file


def structure_helper():
    spec = importlib.util.spec_from_file_location('study_structure_reader', Path(__file__).with_name('structure-analysis.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unwrap(value):
    """Only the existing, explicit MCP result envelopes; no guessed outputs."""
    for _ in range(8):
        if not isinstance(value, dict):
            break
        if value.get('isError'):
            raise ValueError('Upstream result is an error, not a protein design.')
        if value.get('structuredContent') is not None:
            value = value['structuredContent']
        elif isinstance(value.get('result'), dict):
            value = value['result']
        elif isinstance(value.get('response'), dict):
            value = value['response']
        elif isinstance(value.get('content'), list) and len(value['content']) == 1 and value['content'][0].get('type') == 'text':
            value = json.loads(value['content'][0]['text'])
        else:
            break
    return value


def complete_chain(pdb, chain):
    """Reject ambiguous positional correspondence instead of filling/truncating."""
    import numpy as np
    from Bio.PDB import PDBParser
    helper = structure_helper()
    if helper.is_mmcif(pdb):
        raise ValueError('ProteinMPNN requires PDB bytes; explicit format conversion is required for mmCIF.')
    models = list(PDBParser(QUIET=True).get_structure('input', io.StringIO(pdb)).get_models())
    if len(models) != 1 or chain not in models[0]:
        raise ValueError('Choose an existing chain in exactly one PDB model.')
    residues = [r for r in models[0][chain] if r.id[0] in {' ', 'H_MSE'}]
    if not residues or any(not all(atom in r for atom in ('N', 'CA', 'C', 'O')) for r in residues):
        raise ValueError('Selected chain requires complete N/CA/C/O positions; no missing-residue policy is inferred.')
    if any(r.id[2] != ' ' for r in residues) or any(b.id[1] != a.id[1] + 1 for a, b in zip(residues, residues[1:])):
        raise ValueError('Numbering gaps or insertions require explicit correspondence; no silent sequence shortening.')
    if not np.isfinite([r[a].coord for r in residues for a in ('N', 'CA', 'C', 'O')]).all():
        raise ValueError('Backbone coordinates must be finite.')
    sequence = helper.sequence(residues)
    if set(sequence) - set('ACDEFGHIKLMNPQRSTVWY'):
        raise ValueError('Noncanonical backbone residues require an explicit conversion policy.')
    return sequence


def coordinate_input(path, index, inputs, measurements, *, allow_mmcif=False):
    """Read coordinates from the existing verified batch layout or inline result."""
    raw = path.read_text()
    try:
        value = unwrap(json.loads(raw))
    except json.JSONDecodeError:
        value = raw
    if isinstance(value, dict) and value.get('schema') == 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1':
        roles = {'protein-structure-pdb/v1': 'chemical/x-pdb'}
        if allow_mmcif:
            roles['protein-structure-mmcif/v1'] = 'chemical/x-mmcif'
        candidates = [(i, entry) for i, entry in enumerate(value['entries']) if entry.get('semantic_type') in roles]
        if index >= len(candidates):
            raise ValueError(f'Explicit structure_index {index} unavailable; found {len(candidates)} published coordinate artifacts.')
        position, entry = candidates[index]
        reference = entry['artifact']
        if reference.get('compression') != 'none' or reference.get('media_type') != roles[entry['semantic_type']]:
            raise ValueError('Coordinate preparation requires the published uncompressed PDB/mmCIF artifact contract.')
        selected = path.parent / f'output-{position:02d}.artifact'
        verify_file(selected, reference)
        inputs['selected_artifact'] = selected
        measurements['selected_artifact'] = {'path': str(selected), 'size_bytes': reference['size_bytes'], 'sha256': reference['sha256']}
        confidence = []
        if allow_mmcif:
            for position, entry in enumerate(value['entries']):
                if entry.get('semantic_type') != 'structure-confidence-json/v1':
                    continue
                reference = entry['artifact']
                if reference.get('compression') != 'none' or reference.get('media_type') != 'application/json':
                    raise ValueError('Published confidence artifact requires its explicit uncompressed JSON contract.')
                file = path.parent / f'output-{position:02d}.artifact'
                verify_file(file, reference)
                name = f'confidence_artifact_{position}'
                inputs[name] = file
                measurements[name] = {'path': str(file), 'size_bytes': reference['size_bytes'], 'sha256': reference['sha256']}
                confidence.append(json.loads(file.read_bytes()))
        return selected.read_text(), len(candidates), {'manifest': value, 'confidence_artifacts': confidence}
    candidates = structure_helper().structures(value)
    if index >= len(candidates):
        raise ValueError(f'Explicit structure_index {index} unavailable; found {len(candidates)} coordinate structures.')
    return candidates[index], len(candidates), value


def design_correspondence(args, output):
    """Prove a full query-position map; never align only unchanged amino acids."""
    inputs = {name: Path(args[name]) for name in ('design_input', 'design_result', 'refold_input', 'refold_parameters', 'prediction')}
    measurements = {name: {'path': str(path), 'size_bytes': file_measurement(path)[0], 'sha256': file_measurement(path)[1]}
                    for name, path in inputs.items()}
    parameters = json.loads(inputs['refold_parameters'].read_bytes())
    query = json.loads(inputs['refold_input'].read_bytes())
    if parameters.get('mode') != 'single-sequence' or type(parameters.get('seed')) is not int:
        raise ValueError('Correspondence requires the exact explicit single-sequence refolding parameters and seed.')
    # Reuse the existing selected-design validator, including original backbone
    # sequence, input-row exclusion, canonical residues and complete positions.
    with tempfile.TemporaryDirectory(prefix='design-correspondence-') as temporary:
        scratch = Path(temporary)
        prepared = prepare('esmfold2-fast-input', {'design_input': str(inputs['design_input']),
            'design_result': str(inputs['design_result']), 'design_index': args['design_index'], 'seed': parameters['seed']}, scratch)
        expected_query = json.loads((scratch / 'input.json').read_bytes())
        expected_parameters = json.loads((scratch / 'parameters.json').read_bytes())
        if query != expected_query or parameters != expected_parameters:
            raise ValueError('Refolding input/parameters do not exactly match the explicitly selected ProteinMPNN design; no positional correspondence is asserted.')
        reference_text = (scratch / 'backbone.pdb').read_text()
    selection = prepared['selection']
    predicted_text, available, source_result = coordinate_input(inputs['prediction'], args['structure_index'], inputs, measurements, allow_mmcif=True)
    helper = structure_helper()
    reference = helper.load_structure(reference_text)
    prediction = helper.load_structure(predicted_text)
    ref_chain, pred_chain = selection['reference_chain'], args['prediction_chain']
    if pred_chain not in prediction:
        raise ValueError(f'Explicit prediction chain {pred_chain!r} absent; available chains are {list(prediction)}.')
    ref_residues, pred_residues = reference[ref_chain], prediction[pred_chain]
    sequence = query['sequences'][0]['sequence']
    if len(ref_residues) != len(sequence) or len(pred_residues) != len(sequence) or helper.sequence(pred_residues) != sequence:
        raise ValueError('Returned chain must contain one C-alpha position for every query residue in the exact designed sequence order. No gap filling, truncation, alignment or observed-output tolerance is used.')
    import numpy as np
    if not np.isfinite([r['CA'].coord for r in pred_residues]).all():
        raise ValueError('Returned correspondence coordinates must be finite.')
    pairs = [{'reference_chain': ref_chain, 'reference_residue': list(a.id),
              'prediction_chain': pred_chain, 'prediction_residue': list(b.id)}
             for a, b in zip(ref_residues, pred_residues, strict=True)]
    correspondence = {'schema': 'scientific-residue-correspondence/v1',
        'description': 'Full ordered query-position correspondence from the exact original ProteinMPNN backbone input, explicitly selected generated design, matching refolding query and complete returned designed sequence; not sequence-identity alignment.',
        'reference_sha256': hashlib.sha256(reference_text.encode()).hexdigest(),
        'prediction_sha256': hashlib.sha256(predicted_text.encode()).hexdigest(), 'pairs': pairs}
    # Existing evaluator validates hashes, one-to-one residue IDs and complete
    # selected chains before calculating its unchanged structural metrics.
    helper.explicit_pairs(correspondence, reference_text, predicted_text, reference, prediction, [(ref_chain, pred_chain)])
    for name, path in inputs.items():
        if file_measurement(path) != (measurements[name]['size_bytes'], measurements[name]['sha256']):
            raise ValueError('Source changed during correspondence preparation.')
    metadata = {'schema': 'scientific-protein-preparation/v1', 'method': 'design-refold-correspondence',
        'inputs': measurements, 'selection': {**selection, 'prediction_chain': pred_chain,
            'structure_index': args['structure_index'], 'available_structures': available,
            'mapped_residues': len(pairs), 'mapping_method': 'explicit-query-position-provenance'},
        'arguments': args, 'inference_submitted': False, 'scientific_validity_claim': False}
    (output / 'reference.pdb').write_text(reference_text)
    (output / 'prediction.structure').write_text(predicted_text)
    (output / 'prediction-result.json').write_bytes(canonical({'structure': predicted_text, 'retained_source_result': source_result}) + b'\n')
    (output / 'residue-map.json').write_bytes(canonical(correspondence) + b'\n')
    (output / 'provenance.json').write_bytes(canonical(metadata) + b'\n')
    (output / 'report.md').write_text('# Design/refold correspondence\n\n' +
        f'{len(pairs)} explicitly mapped query positions; reference chain {ref_chain}, prediction chain {pred_chain}.\n\n' +
        correspondence['description'] + '\n\nThis is a validated input to the existing structure evaluator, not a structural-agreement or biological-quality result.\n')
    return metadata


def prepare(method, args, output):
    output = Path(output)
    if method == 'design-refold-correspondence':
        return design_correspondence(args, output)
    inputs = {name: Path(args[name]) for name in
              (('backbone',) if method == 'proteinmpnn-input' else ('design_input', 'design_result'))}
    measurements = {name: {'path': str(path), 'size_bytes': file_measurement(path)[0],
                            'sha256': file_measurement(path)[1]} for name, path in inputs.items()}
    selection = {}
    if method == 'proteinmpnn-input':
        index = args['structure_index']
        pdb, available, _ = coordinate_input(inputs['backbone'], index, inputs, measurements)
        sequence = complete_chain(pdb, args['chain'])
        request = {'input_pdb': pdb, 'input_pdb_chains': [args['chain']],
                   'num_seq_per_target': args['num_sequences'], 'random_seed': args['seed'],
                   'sampling_temp': args['sampling_temp'], 'omit_AAs': args['omit_aas']}
        (output / 'input.json').write_bytes(canonical(request) + b'\n')
        selection = {'structure_index': index, 'available_structures': available, 'chain': args['chain'],
                     'residue_count': len(sequence), 'destination_model': 'proteinmpnn'}
    elif method == 'esmfold2-fast-input':
        from Bio import SeqIO
        request = json.loads(inputs['design_input'].read_bytes())
        chains = request.get('input_pdb_chains')
        if not isinstance(chains, list) or len(chains) != 1:
            raise ValueError('This single-chain refolding adapter requires an explicitly selected single ProteinMPNN chain; multi-chain splitting is not inferred.')
        pdb = request['input_pdb']
        reference_sequence = complete_chain(pdb, chains[0])
        value = unwrap(json.loads(inputs['design_result'].read_bytes()))
        if not isinstance(value, dict) or not isinstance(value.get('mfasta'), str):
            raise ValueError('Expected the actual ProteinMPNN mfasta result, not a path or status receipt.')
        records = list(SeqIO.parse(io.StringIO(value['mfasta']), 'fasta'))
        original = [r for r in records if r.description.startswith('input ')]
        if len(original) != 1 or str(original[0].seq) != reference_sequence:
            raise ValueError('ProteinMPNN input sequence does not match the explicitly linked original backbone request.')
        designs = [r for r in records if not r.description.startswith('input ')]
        index = args['design_index']
        if index >= len(designs):
            raise ValueError(f'Explicit design_index {index} unavailable; found {len(designs)} generated designs excluding the input row.')
        selected = designs[index]
        sequence = str(selected.seq)
        if not sequence or set(sequence) - set('ACDEFGHIKLMNPQRSTVWY') or len(sequence) != len(reference_sequence):
            raise ValueError('Designed sequence must be canonical and match every original backbone position; no truncation, gaps or concatenated-chain split is inferred.')
        (output / 'input.json').write_bytes(canonical({'sequences': [{'id': 'A', 'sequence': sequence, 'type': 'protein'}]}) + b'\n')
        (output / 'parameters.json').write_bytes(canonical({'sequence': sequence, 'mode': 'single-sequence', 'seed': args['seed']}) + b'\n')
        (output / 'selected.fasta').write_text('>' + selected.description + '\n' + sequence + '\n')
        selection = {'design_index': index, 'available_designs': len(designs), 'selected_fasta_header': selected.description,
                     'reference_chain': chains[0], 'residue_count': len(sequence), 'destination_model': 'esmfold2-fast',
                     'requested_seed': args['seed'], 'sequence_sha256': hashlib.sha256(sequence.encode()).hexdigest()}
    else:
        raise ValueError('Unknown explicit protein preparation method.')
    (output / 'backbone.pdb').write_text(pdb)
    for name, path in inputs.items():
        if file_measurement(path) != (measurements[name]['size_bytes'], measurements[name]['sha256']):
            raise ValueError('Upstream bytes changed during dependent input preparation.')
    metadata = {'schema': 'scientific-protein-preparation/v1', 'method': method, 'inputs': measurements,
                'selection': selection, 'arguments': args, 'inference_submitted': False,
                'limitation': 'Explicit computational dependency only; not experimental validation, binding evidence or a refolding accuracy claim.'}
    (output / 'provenance.json').write_bytes(canonical(metadata) + b'\n')
    (output / 'report.md').write_text('# Protein input preparation\n\n' +
        f"Prepared {selection['destination_model']} input for {selection['residue_count']} residues.\n\n" +
        'Selection and exact source hashes are recorded in provenance.json; generated-design indexes are not model seeds.\n\n' + metadata['limitation'] + '\n')
    return metadata
