"""Reproducible, file-based protein C-alpha and interface comparison.

No inference, downloads, or biological chain selection are performed. Explicit
chain mappings are mandatory when either structure contains multiple proteins.
Metrics describe agreement with this reference, not experimental validation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import Bio
import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB import MMCIFParser, NeighborSearch, PDBParser, Superimposer
from Bio.SeqUtils import seq1


def load_structure(text):
    parser = MMCIFParser(QUIET=True) if text.lstrip().startswith('data_') else PDBParser(QUIET=True)
    model = next(parser.get_structure('comparison', io.StringIO(text)).get_models())
    chains = {}
    for chain in model:
        residues = [r for r in chain if 'CA' in r and r.id[0] in {' ', 'H_MSE'}]
        if residues:
            chains[chain.id] = residues
    if not chains:
        raise ValueError('No protein C-alpha atoms were found.')
    return chains


def sequence(residues):
    return ''.join(seq1(r.resname, custom_map={'MSE': 'M'}) for r in residues)


def structures(value):
    """Recognize explicit coordinate fields without guessing an absent output."""
    if isinstance(value, str):
        return [value] if value.lstrip().startswith('data_') or 'ATOM  ' in value else []
    if isinstance(value, list):
        return [text for item in value for text in structures(item)]
    if isinstance(value, dict):
        names = ('structure', 'pdb', 'mmcif', 'cif', 'pdb_string', 'pdb_text', 'cif_text',
                 'structures_in_ranked_order', 'structures', 'predictions', 'outputs', 'data', 'result', 'response')
        return list(dict.fromkeys(text for key in names if key in value for text in structures(value[key])))
    return []


def confidence_fields(value, prefix=''):
    output = {}
    if isinstance(value, dict):
        for name, child in value.items():
            field = f'{prefix}.{name}'.lstrip('.')
            if name in {'confidence', 'plddt', 'ptm_score', 'ptm', 'iptm', 'iptm_score', 'ranking_score'}:
                if isinstance(child, (int, float)) and not isinstance(child, bool) and np.isfinite(child):
                    output[field] = child
                elif isinstance(child, list) and child and all(isinstance(x, (float, int)) for x in child):
                    data = np.asarray(child, dtype=float)
                    if np.isfinite(data).all():
                        output[field] = {'count': len(child), 'mean': float(data.mean()),
                                         'min': float(data.min()), 'max': float(data.max())}
            if isinstance(child, (dict, list)):
                output.update(confidence_fields(child, field))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if isinstance(item, (dict, list)):
                output.update(confidence_fields(item, f'{prefix}[{index}]'))
    return output


def matched(reference, prediction):
    a, b = sequence(reference), sequence(prediction)
    aligner = PairwiseAligner(mode='global', match_score=2, mismatch_score=-1,
                             open_gap_score=-3, extend_gap_score=-0.2)
    alignment = aligner.align(a, b)[0]
    pairs = [(int(i), int(j)) for ra, rb in zip(*alignment.aligned)
             for i, j in zip(range(*ra), range(*rb)) if a[i] == b[j] and a[i] != 'X']
    if len(pairs) < 3:
        raise ValueError('Fewer than three identical aligned residues; comparison is undefined.')
    return pairs


def rmsd(reference, prediction):
    if not np.isfinite([atom.coord for atom in reference + prediction]).all():
        raise ValueError('Coordinates contain non-finite values.')
    fit = Superimposer()
    fit.set_atoms(reference, prediction)
    return float(fit.rms)


def contacts(residue_groups, cutoff):
    """Heavy-atom contacts among mapped residues of distinct selected chains."""
    atoms, labels = [], {}
    for group, residues in enumerate(residue_groups):
        for index, residue in enumerate(residues):
            for atom in residue:
                if atom.element.upper() not in {'H', 'D'}:
                    atoms.append(atom)
                    labels[id(atom)] = (group, index)
    found = set()
    for a, b in NeighborSearch(atoms).search_all(cutoff):
        first, second = labels[id(a)], labels[id(b)]
        if first[0] != second[0]:
            found.add(tuple(sorted((first, second))))
    return found


def explicit_pairs(document, reference_text, prediction_text, reference, prediction, chain_map):
    """Use supplied design provenance, never silently equate residue positions."""
    if (document.get('schema') != 'scientific-residue-correspondence/v1'
            or not isinstance(document.get('description'), str) or not document['description'].strip()
            or not isinstance(document.get('pairs'), list)):
        raise ValueError('Explicit correspondence needs its versioned schema, description and residue pairs.')
    for field, text in [('reference_sha256', reference_text), ('prediction_sha256', prediction_text)]:
        if document.get(field) != hashlib.sha256(text.encode()).hexdigest():
            raise ValueError('Explicit correspondence ' + field + ' does not match this structure.')
    grouped = {tuple(pair): [] for pair in chain_map}
    seen_ref, seen_pred = set(), set()
    for pair in document['pairs']:
        ref_id, pred_id = pair['reference_chain'], pair['prediction_chain']
        key = (ref_id, pred_id)
        if key not in grouped:
            raise ValueError('Explicit correspondence references an unselected chain pair.')
        ref_residue, pred_residue = tuple(pair['reference_residue']), tuple(pair['prediction_residue'])
        ref_key, pred_key = (ref_id, ref_residue), (pred_id, pred_residue)
        if ref_key in seen_ref or pred_key in seen_pred:
            raise ValueError('Explicit residue correspondence must be one-to-one.')
        ref_index = {r.id: i for i, r in enumerate(reference[ref_id])}
        pred_index = {r.id: i for i, r in enumerate(prediction[pred_id])}
        if ref_residue not in ref_index or pred_residue not in pred_index:
            raise ValueError('Explicit correspondence contains an absent C-alpha residue.')
        seen_ref.add(ref_key)
        seen_pred.add(pred_key)
        grouped[key].append((ref_index[ref_residue], pred_index[pred_residue]))
    if any(len(pairs) < 3 for pairs in grouped.values()):
        raise ValueError('Every mapped chain needs at least three explicit residue pairs.')
    return grouped


def compare(reference_text, prediction_text, chain_map=None, cutoff=5.0, residue_correspondence=None):
    reference, prediction = load_structure(reference_text), load_structure(prediction_text)
    if not chain_map:
        if len(reference) != 1 or len(prediction) != 1:
            raise ValueError('Multiple protein chains require explicit --chain-map REF:PRED pairs.')
        chain_map = [(next(iter(reference)), next(iter(prediction)))]
    if len({a for a, _ in chain_map}) != len(chain_map) or len({b for _, b in chain_map}) != len(chain_map):
        raise ValueError('Chain mapping must be one-to-one.')
    if any(a not in reference or b not in prediction for a, b in chain_map):
        requested = ', '.join(f'{a}:{b}' for a, b in chain_map)
        raise ValueError(f'Absent chain mapping. Direction is reference:prediction (REF:PRED). '
                         f'Requested: {requested}. Available reference protein chains: {list(reference)}; '
                         f'available prediction protein chains: {list(prediction)}. '
                         'Choose the scientifically corresponding pairs explicitly; mappings are not automatically swapped.')
    explicit = explicit_pairs(residue_correspondence, reference_text, prediction_text,
                              reference, prediction, chain_map) if residue_correspondence is not None else None
    mapped_ref, mapped_pred, reports, residue_mapping = [], [], [], []
    for ref_id, pred_id in chain_map:
        ref, pred = reference[ref_id], prediction[pred_id]
        pairs = explicit[(ref_id, pred_id)] if explicit is not None else matched(ref, pred)
        identical = sum(sequence([ref[i]]) == sequence([pred[j]]) and sequence([ref[i]]) != 'X'
                        for i, j in pairs)
        ref_selected, pred_selected = [ref[i] for i, _ in pairs], [pred[j] for _, j in pairs]
        mapped_ref.append(ref_selected)
        mapped_pred.append(pred_selected)
        reports.append({'reference_chain': ref_id, 'prediction_chain': pred_id,
                        'reference_observed_residues': len(ref), 'prediction_observed_residues': len(pred),
                        'mapped_residues': len(pairs), 'matched_identical_residues': identical,
                        'reference_coverage': len(pairs) / len(ref),
                        'prediction_coverage': len(pairs) / len(pred),
                        'independently_fitted_ca_rmsd_angstrom': rmsd([r['CA'] for r in ref_selected], [r['CA'] for r in pred_selected])})
        residue_mapping.extend({'reference_chain': ref_id, 'prediction_chain': pred_id,
                                'reference_residue': list(ref[i].id), 'prediction_residue': list(pred[j].id)}
                               for i, j in pairs)
    ref_atoms = [r['CA'] for group in mapped_ref for r in group]
    pred_atoms = [r['CA'] for group in mapped_pred for r in group]
    metrics = {'chains': reports, 'global_ca_rmsd_angstrom': rmsd(ref_atoms, pred_atoms),
               'mapped_residues': len(ref_atoms),
               'matched_identical_residues': sum(r['matched_identical_residues'] for r in reports),
               'correspondence_method': 'explicit-provenance' if explicit is not None else 'identical-sequence-alignment',
               'correspondence_description': residue_correspondence['description'] if explicit is not None else None,
               'reference_protein_chains': list(reference),
               'prediction_protein_chains': list(prediction), 'chain_mapping': chain_map,
               'excluded_reference_chains': [c for c in reference if c not in dict(chain_map)],
               'excluded_prediction_chains': [c for c in prediction if c not in dict((b, a) for a, b in chain_map)]}
    if len(chain_map) > 1:
        native, predicted = contacts(mapped_ref, cutoff), contacts(mapped_pred, cutoff)
        interface = sorted({item for pair in native for item in pair})
        metrics['interface'] = {
            'heavy_atom_cutoff_angstrom': cutoff, 'native_contacts_mapped_residues': len(native),
            'predicted_contacts_mapped_residues': len(predicted), 'recovered_native_contacts': len(native & predicted),
            'fraction_native_contacts_mapped_residues': len(native & predicted) / len(native) if native else None,
            'interface_ca_rmsd_angstrom': rmsd([mapped_ref[g][i]['CA'] for g, i in interface],
                                             [mapped_pred[g][i]['CA'] for g, i in interface]) if len(interface) >= 3 else None,
            'interface_residues_mapped': len(interface),
            'limitation': 'C-alpha interface fit and mapped-residue contacts; not CAPRI all-backbone iRMSD, DockQ, affinity, or functional validation.'}
    return metrics, residue_mapping


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--prediction', type=Path)
    parser.add_argument('--result', type=Path, help='Raw platform JSON result containing coordinates.')
    parser.add_argument('--structure-index', type=int, default=0)
    parser.add_argument('--chain-map', nargs='+', help='Explicit reference:prediction chain IDs, e.g. A:A D:B.')
    parser.add_argument('--residue-map', type=Path,
                        help='Versioned explicit correspondence JSON with description, structure hashes and residue pairs; needed for sequence-redesigned backbone comparisons.')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--inspect', action='store_true', help='Print observed reference chains/sequences without inference.')
    args = parser.parse_args()
    reference_text = args.reference.read_text()
    if args.inspect:
        print(json.dumps({'chains': [{'id': name, 'observed_residues': len(residues), 'sequence': sequence(residues)}
                                    for name, residues in load_structure(reference_text).items()]}))
        return
    if not args.output_dir or bool(args.prediction) == bool(args.result):
        parser.error('Supply --output-dir and exactly one of --prediction or --result.')
    result = json.loads(args.result.read_text()) if args.result else {}
    if args.result:
        candidates = structures(result)
        if args.structure_index < 0 or args.structure_index >= len(candidates):
            raise ValueError(f'No coordinate structure at index {args.structure_index}; found {len(candidates)}.')
        prediction_text = candidates[args.structure_index]
    else:
        prediction_text = args.prediction.read_text()
    chain_map = [tuple(item.split(':')) for item in args.chain_map] if args.chain_map else None
    if chain_map and any(len(pair) != 2 for pair in chain_map):
        parser.error('Use REF:PRED chain mappings.')
    correspondence = json.loads(args.residue_map.read_text()) if args.residue_map else None
    metrics, mapping = compare(reference_text, prediction_text, chain_map, residue_correspondence=correspondence)
    metrics['model_confidence_not_reference_agreement'] = confidence_fields(result)
    metrics['provenance'] = {'reference_file': str(args.reference),
                             'reference_sha256': hashlib.sha256(reference_text.encode()).hexdigest(),
                             'prediction_sha256': hashlib.sha256(prediction_text.encode()).hexdigest(),
                             'result_file': str(args.result) if args.result else None,
                             'residue_map_file': str(args.residue_map) if args.residue_map else None,
                             'residue_map_sha256': hashlib.sha256(args.residue_map.read_bytes()).hexdigest() if args.residue_map else None,
                             'biopython_version': Bio.__version__, 'numpy_version': np.__version__}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in [('metrics.json', metrics), ('residue-mapping.json', mapping)]:
        (args.output_dir / filename).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    suffix = 'cif' if prediction_text.lstrip().startswith('data_') else 'pdb'
    (args.output_dir / ('prediction.' + suffix)).write_text(prediction_text)
    correspondence_method = (
        'Explicit provenance-backed residue correspondence from the supplied versioned JSON; both structure hashes '
        'are verified and all one-to-one residue identifiers must exist. Sequence identity is counted separately '
        'from mapped positions. This does not prove the supplied scientific correspondence is correct. '
        if correspondence is not None else
        'Global pairwise sequence alignment: match 2, mismatch -1, gap-open -3, gap-extend -0.2; '
        'first optimal alignment, identical non-X residues only. ')
    (args.output_dir / 'methods.md').write_text(
        '# Structural comparison method\n\n'
        'First coordinate model; explicit chain mapping (not an automatic biological assembly decision). '
        'Observed standard amino acids and MSE with C-alpha atoms only. ' + correspondence_method +
        'Coverage and full residue mapping are saved. Biopython Superimposer least-squares proper-rotation '
        'C-alpha RMSD is reported in angstroms. Per-chain fits are independent; the global fit uses all mapped chains. '
        'Interface contacts use any non-hydrogen atoms within 5 angstroms among mapped residues of distinct selected '
        'chains; interface RMSD fits C-alpha atoms of native-contact residues separately. Missing residues are excluded, '
        'so contact fractions concern mapped residues only. These are not DockQ or CAPRI all-backbone metrics. '
        'Confidence fields are separate model outputs, not experimental agreement or biological validation.\n\n'
        'API reference: https://biopython.org/docs/1.85/api/Bio.PDB.Superimposer.html\n')
    print(json.dumps({'metrics': metrics, 'output_dir': str(args.output_dir)}, allow_nan=False))


if __name__ == '__main__':
    main()
