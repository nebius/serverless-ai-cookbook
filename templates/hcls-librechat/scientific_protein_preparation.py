"""Explicit dependent inputs for the existing ProteinMPNN and ESMFold2-Fast contracts.

No inference or sequence selection is implicit. The scientist chooses the
backbone/chain/design index and sampling settings in the immutable study plan.
"""
import hashlib
import importlib.util
import io
import json
from pathlib import Path

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


def prepare(method, args, output):
    output = Path(output)
    inputs = {name: Path(args[name]) for name in
              (('backbone',) if method == 'proteinmpnn-input' else ('design_input', 'design_result'))}
    measurements = {name: {'path': str(path), 'size_bytes': file_measurement(path)[0],
                            'sha256': file_measurement(path)[1]} for name, path in inputs.items()}
    selection = {}
    if method == 'proteinmpnn-input':
        raw = inputs['backbone'].read_text()
        try:
            value = unwrap(json.loads(raw))
        except json.JSONDecodeError:
            value = raw
        index = args['structure_index']
        if isinstance(value, dict) and value.get('schema') == 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1':
            # Exact flat storage layout of the existing batch client's verified
            # collect_outputs(), not another download/extraction implementation.
            candidates = [(i, entry) for i, entry in enumerate(value['entries'])
                          if entry.get('semantic_type') == 'protein-structure-pdb/v1']
            if index >= len(candidates):
                raise ValueError(f'Explicit structure_index {index} unavailable; found {len(candidates)} published PDB artifacts.')
            position, entry = candidates[index]
            reference = entry['artifact']
            if reference.get('compression') != 'none' or reference.get('media_type') != 'chemical/x-pdb':
                raise ValueError('This coordinate preparation requires the published uncompressed PDB artifact contract.')
            path = inputs['backbone'].parent / f'output-{position:02d}.artifact'
            verify_file(path, reference)
            inputs['selected_artifact'] = path
            measurements['selected_artifact'] = {'path': str(path), 'size_bytes': reference['size_bytes'], 'sha256': reference['sha256']}
            pdb = path.read_text()
            available = len(candidates)
        else:
            structures = structure_helper().structures(value)
            if index >= len(structures):
                raise ValueError(f'Explicit structure_index {index} unavailable; found {len(structures)} coordinate structures.')
            pdb = structures[index]
            available = len(structures)
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
