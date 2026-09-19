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


def is_mmcif(text):
    """CIF allows comments before its data block (including AlphaFold outputs)."""
    first = next((line.strip() for line in text.splitlines()
                  if line.strip() and not line.lstrip().startswith('#')), '')
    return first.startswith('data_')


def load_structure(text):
    parser = MMCIFParser(QUIET=True) if is_mmcif(text) else PDBParser(QUIET=True)
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
        return [value] if is_mmcif(value) or 'ATOM  ' in value else []
    if isinstance(value, list):
        return [text for item in value for text in structures(item)]
    if isinstance(value, dict):
        names = ('structure', 'pdb', 'mmcif', 'cif', 'pdb_string', 'pdb_text', 'cif_text',
                 'structures_in_ranked_order', 'structures_with_scores', 'structures', 'predictions', 'outputs', 'data', 'result', 'response')
        return [text for key in names if key in value for text in structures(value[key])]
    return []


def confidence_fields(value, prefix=''):
    output = {}
    if isinstance(value, dict):
        if value.get('schema') == 'fs2.nebius.ai/structure-confidence/v1':
            # These rows have explicit structure identities. Never aggregate
            # other samples through recursive confidence-name discovery.
            return output
        for name, child in value.items():
            field = f'{prefix}.{name}'.lstrip('.')
            if name == 'confidence_artifacts' and isinstance(value.get('manifest'), dict):
                # Published artifacts are handled only by the byte-bound join,
                # including legacy envelopes that lack the new raw-byte field.
                continue
            if name in {'confidence_scores', 'ptm_scores'}:
                # Exact native Boltz result fields. Preserve every value and
                # returned order; no rank/seed association or calibration.
                if (isinstance(child, list) and all(isinstance(x, (float, int))
                        and not isinstance(x, bool) and np.isfinite(x) for x in child)):
                    output[field] = {'values': list(child), 'count': len(child),
                                     'ordering': 'as returned; not inferred seeds or ranks'}
            if name in {'confidence', 'plddt', 'plddt_mean', 'ptm_score', 'ptm', 'iptm', 'iptm_score', 'ranking_score'}:
                if isinstance(child, (int, float)) and not isinstance(child, bool) and np.isfinite(child):
                    output[field] = child
                elif isinstance(child, list) and child and all(isinstance(x, (float, int)) and not isinstance(x, bool) for x in child):
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


def bound_confidence(value, prediction_bytes, *, source_path=None):
    """Join a published confidence row by exact bytes, never names or rank.

    Accept the existing downloaded batch manifest, or the correspondence
    envelope retaining that manifest and the exact verified confidence bytes.
    No network access, sibling search, unit conversion or cross-run lookup.
    """
    manifest_schema = 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1'
    retained = value.get('retained_source_result', {}) if isinstance(value, dict) else {}
    manifest = value if isinstance(value, dict) and value.get('schema') == manifest_schema else retained.get('manifest')
    if not isinstance(manifest, dict) or manifest.get('schema') != manifest_schema:
        raise ValueError('Confidence evidence requires a published batch manifest or its verified correspondence envelope.')
    checksum = hashlib.sha256(prediction_bytes).hexdigest()
    entries = manifest.get('entries', [])
    coordinates = [entry for entry in entries
                   if entry.get('semantic_type') in {'protein-structure-pdb/v1', 'protein-structure-mmcif/v1'}
                   and entry.get('artifact', {}).get('sha256') == checksum
                   and entry['artifact'].get('size_bytes') == len(prediction_bytes)
                   and entry['artifact'].get('compression') == 'none']
    if len(coordinates) != 1:
        raise ValueError('Confidence manifest must contain exactly one selected coordinate SHA256/size match.')
    if retained:
        if value.get('structure', '').encode('utf-8') != prediction_bytes:
            raise ValueError('Confidence correspondence envelope coordinates differ from the selected prediction.')
    matches, declared = [], 0
    for index, entry in enumerate(entries):
        if entry.get('semantic_type') != 'structure-confidence-json/v1':
            continue
        declared += 1
        artifact = entry['artifact']
        if artifact.get('compression') != 'none' or artifact.get('media_type') != 'application/json':
            raise ValueError('Confidence artifact must be uncompressed JSON.')
        if manifest is value:
            if source_path is None:
                raise ValueError('A downloaded manifest requires its exact local artifact layout.')
            raw = (Path(source_path).parent / f'output-{index:02d}.artifact').read_bytes()
        else:
            sources = [item for item in retained.get('confidence_artifact_sources', [])
                       if item.get('manifest_entry_index') == index]
            if len(sources) != 1 or not isinstance(sources[0].get('raw_json'), str):
                raise ValueError('Confidence envelope lacks exact source bytes; supply the retained output-manifest.json explicitly.')
            raw = sources[0]['raw_json'].encode('utf-8')
        if hashlib.sha256(raw).hexdigest() != artifact.get('sha256') or len(raw) != artifact.get('size_bytes'):
            raise ValueError('Confidence artifact SHA256/size does not match the same manifest.')
        document = json.loads(raw)
        if document.get('schema') != 'fs2.nebius.ai/structure-confidence/v1':
            raise ValueError('Confidence artifact lacks the supported structure-bound schema.')
        for row_index, row in enumerate(document.get('results', [])):
            identity = row.get('structure', {})
            if identity.get('sha256') != checksum:
                continue
            if identity.get('bytes') != len(prediction_bytes):
                raise ValueError('Confidence row byte count contradicts the selected structure.')
            if (type(row.get('seed')) is not int or type(row.get('sample_index')) is not int
                    or row['sample_index'] < 0 or row['seed'] not in document.get('seeds', [])
                    or type(document.get('samples_per_seed')) is not int
                    or row['sample_index'] >= document['samples_per_seed']):
                raise ValueError('Confidence row has contradictory seed/sample provenance.')
            metrics = row.get('metrics')
            if not isinstance(metrics, dict) or not metrics or any(
                    type(number) not in (int, float) or not np.isfinite(number) for number in metrics.values()):
                raise ValueError('Confidence metrics must be finite native numbers, including zero.')
            prefix = f'confidence_artifacts[{index}].results[{row_index}].metrics'
            matches.append(({f'{prefix}.{key}': number for key, number in metrics.items()}, {
                'status': 'exact_structure_sha256_and_size_match',
                'manifest_id': manifest.get('manifest_id'), 'manifest_entry_index': index,
                'confidence_artifact_sha256': artifact['sha256'], 'confidence_artifact_size_bytes': len(raw),
                'structure_sha256': checksum, 'structure_size_bytes': len(prediction_bytes),
                'seed': row['seed'], 'sample_index': row['sample_index'],
                'runtime_id': document.get('runtime_id'), 'model_revision': document.get('model_revision'),
                'input_identity': document.get('input_identity'),
                'scope': 'Exact published byte association; seed/sample are retained labels, not determinism or biological validity. Native numeric scales are unchanged.'}))
    if not declared:
        return {}, {'status': 'unavailable_no_confidence_artifact', 'structure_sha256': checksum}
    if len(matches) != 1:
        raise ValueError('Confidence evidence requires exactly one matching row; absent or ambiguous samples are not inferred.')
    return matches[0]


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
    if isinstance(cutoff, bool) or not isinstance(cutoff, (int, float)) or not np.isfinite(cutoff) or cutoff <= 0:
        raise ValueError('Contact cutoff must be a finite positive distance in angstroms.')
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
    metrics = {'schema': 'scientific-ai/protein-structure-comparison/v1',
               'units': {'rmsd': 'angstrom', 'contact_cutoff': 'angstrom', 'coverage': 'fraction',
                         'residue_and_contact_counts': 'counts', 'model_confidence': 'unchanged model-native values; not reference accuracy'},
               'chains': reports, 'global_ca_rmsd_angstrom': rmsd(ref_atoms, pred_atoms),
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


def sampling_provenance(request_bytes, structure_index):
    """Retain named request settings without inventing seed or runtime guarantees."""
    value = {'extracted_structure_index': structure_index, 'index_base': 0,
             'structure_index_is_seed': False, 'determinism_established': False,
             'request_fields': [], 'request_sha256': None,
             'scope': 'Selection within extracted coordinate fields is not a native rank, random seed, model seed or independent request. Identical returned coordinates are not deduplicated. Named settings below are declared by the retained request, not proof the runtime honored them.'}
    if request_bytes is None:
        value['request_status'] = 'not_supplied; seed and requested sample counts are unknown'
        return value
    request = json.loads(request_bytes)
    if not (isinstance(request, dict) or
            isinstance(request, list) and request and all(isinstance(item, dict) for item in request)):
        raise ValueError('Retained request must be a JSON object or a nonempty array of request objects.')
    if isinstance(request, list):
        # Protenix's uploaded input is an array of named complex records. Keep
        # array-index JSON pointers; a coordinate index is NOT a request index.
        value['request_document_shape'] = 'array-of-objects'
        value['request_record_count'] = len(request)
        value['request_record_association'] = 'not established; recorded fields describe all supplied records, not a selected structure'
    names = {'seed', 'seeds', 'random_seed', 'random_seeds', 'model_seed', 'model_seeds',
             'num_samples', 'num_diffusion_samples', 'diffusion_samples', 'selected_models'}
    def walk(item, pointer=''):
        if isinstance(item, dict):
            for key, child in item.items():
                location = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
                if key in names:
                    scalar = type(child) is int
                    array = isinstance(child, list) and all(type(part) is int for part in child)
                    value['request_fields'].append({'json_pointer': location,
                        'value': child if scalar or array else None,
                        'status': 'recorded' if scalar or array else 'unsupported_sampling_value_not_interpreted'})
                elif isinstance(child, (dict, list)):
                    walk(child, location)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                if isinstance(child, (dict, list)):
                    walk(child, f'{pointer}/{index}')
    walk(request)
    value['request_sha256'] = hashlib.sha256(request_bytes).hexdigest()
    value['request_status'] = 'provided; no service-side association was queried by this offline helper'
    return value


def report_markdown(metrics):
    """Render actual mapping, units and poor agreement without a model recount."""
    lines = ['# Protein structure comparison', '',
             'Descriptive agreement with the supplied reference; not experimental, functional or clinical validation.', '',
             f"Global jointly fitted C-alpha RMSD: **{metrics['global_ca_rmsd_angstrom']:.12g} Å**.",
             f"Mapped residues: {metrics['mapped_residues']}; identical sequence matches: {metrics['matched_identical_residues']}.",
             f"Correspondence: `{metrics['correspondence_method']}`.", '',
             '| Reference chain | Prediction chain | Mapped / observed reference | Mapped / observed prediction | Independently fitted chain RMSD (Å) |',
             '| --- | --- | ---: | ---: | ---: |']
    def escape(text):
        return str(text).replace('|', '\\|').replace('\n', ' ')
    for chain in metrics['chains']:
        lines.append(f"| {escape(chain['reference_chain'])} | {escape(chain['prediction_chain'])} | {chain['mapped_residues']} / {chain['reference_observed_residues']} | {chain['mapped_residues']} / {chain['prediction_observed_residues']} | {chain['independently_fitted_ca_rmsd_angstrom']:.12g} |")
    lines += ['', 'Per-chain fits are independent and can be small while the global complex arrangement is wrong. Global and independent-fit RMSDs are not interchangeable.',
              'Coverage concerns observed mapped C-alpha residues, not missing sequence positions or the full biological assembly.',
              f"Excluded reference chains: {metrics['excluded_reference_chains']}; excluded prediction chains: {metrics['excluded_prediction_chains']}."]
    if 'interface' in metrics:
        interface = metrics['interface']
        lines += ['', '## Mapped interface', '',
                  f"Heavy-atom contact cutoff: {interface['heavy_atom_cutoff_angstrom']} Å.",
                  f"Recovered reference contacts: {interface['recovered_native_contacts']} / {interface['native_contacts_mapped_residues']}.",
                  f"Predicted contacts: {interface['predicted_contacts_mapped_residues']}; mapped interface residues: {interface['interface_residues_mapped']}.",
                  f"Separately fitted interface C-alpha RMSD (Å): {interface['interface_ca_rmsd_angstrom'] if interface['interface_ca_rmsd_angstrom'] is not None else 'undefined: fewer than three mapped interface residues'}.",
                  interface['limitation']]
    sampling = metrics.get('sampling_provenance', sampling_provenance(None, None))
    lines += ['', '## Sampling and confidence', '',
              f"Selected extracted structure index: {sampling['extracted_structure_index']} (zero-based when supplied, **not a seed**).",
              sampling['scope'], f"Request evidence: {sampling.get('request_status', 'not supplied')}."]
    for field in sampling['request_fields']:
        lines.append(f"- Declared `{escape(field['json_pointer'])}`: `{field['value']}` ({field['status']}).")
    confidence = metrics.get('model_confidence_not_reference_agreement', {})
    lines += ['Model-confidence values remain separate, in their model-native units. No rescaling or accuracy/affinity claim is made.',
              f"Retained confidence fields: {len(confidence)}; see metrics.json for their exact source paths and values."]
    for field, value in confidence.items():
        if isinstance(value, dict) and 'values' in value:
            lines.append(f"- Native `{escape(field)}`: `{json.dumps(value['values'], allow_nan=False)}` "
                         '(exact returned order, not inferred seeds/ranks; source result SHA-256 below).')
        elif type(value) in (int, float):
            lines.append(f'- Native `{escape(field)}`: `{value}` (unchanged native scale).')
    binding = metrics.get('confidence_binding')
    if binding:
        lines += [f"Confidence association: `{binding['status']}`."]
        if 'seed' in binding:
            lines += [f"Retained seed `{binding['seed']}`, sample `{binding['sample_index']}`; runtime `{escape(binding['runtime_id'])}`, model revision `{escape(binding['model_revision'])}`.", binding['scope']]
    lines += ['', '## Provenance', '']
    for key in ('reference_sha256', 'prediction_sha256', 'result_sha256', 'residue_map_sha256', 'request_sha256', 'confidence_result_sha256'):
        lines.append(f"- {key}: `{metrics.get('provenance', {}).get(key) or 'not supplied'}`")
    if binding and binding.get('confidence_artifact_sha256'):
        lines.append(f"- confidence_artifact_sha256: `{binding['confidence_artifact_sha256']}`")
    lines += ['', 'Poor reference agreement remains a scientific finding, not a failed service request. No quality threshold or biological success is inferred.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--prediction', type=Path)
    parser.add_argument('--result', type=Path, help='Raw platform JSON result containing coordinates.')
    parser.add_argument('--confidence-result', type=Path,
                        help='Explicit same-operation output-manifest.json or paired correspondence envelope; exact structure/artifact SHA256 and unique sample must match.')
    parser.add_argument('--structure-index', type=int, default=0)
    parser.add_argument('--chain-map', nargs='+', action='extend', help='Explicit reference:prediction chain IDs, e.g. A:A D:B; repeated flags append mappings.')
    parser.add_argument('--residue-map', type=Path,
                        help='Versioned explicit correspondence JSON with description, structure hashes and residue pairs; needed for sequence-redesigned backbone comparisons.')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--request-file', type=Path, help='Optional original request JSON for hash-linked declared sampling settings; never infer a seed from a filename/index.')
    parser.add_argument('--inspect', action='store_true', help='Print observed reference chains/sequences without inference.')
    args = parser.parse_args()
    reference_bytes = args.reference.read_bytes()
    reference_text = reference_bytes.decode('utf-8')
    if args.inspect:
        print(json.dumps({'chains': [{'id': name, 'observed_residues': len(residues), 'sequence': sequence(residues)}
                                    for name, residues in load_structure(reference_text).items()]}))
        return
    if not args.output_dir or bool(args.prediction) == bool(args.result):
        parser.error('Supply --output-dir and exactly one of --prediction or --result.')
    if args.structure_index < 0 or (args.prediction and args.structure_index != 0):
        parser.error('Structure index must be nonnegative; a direct prediction file has only index 0.')
    result_bytes = args.result.read_bytes() if args.result else None
    result = json.loads(result_bytes) if result_bytes is not None else {}
    if args.result:
        candidates = structures(result)
        if args.structure_index < 0 or args.structure_index >= len(candidates):
            raise ValueError(f'No coordinate structure at index {args.structure_index}; found {len(candidates)}.')
        prediction_text = candidates[args.structure_index]
    else:
        prediction_text = args.prediction.read_bytes().decode('utf-8')
    chain_map = [tuple(item.split(':')) for item in args.chain_map] if args.chain_map else None
    if chain_map and any(len(pair) != 2 for pair in chain_map):
        parser.error('Use REF:PRED chain mappings.')
    correspondence = json.loads(args.residue_map.read_text()) if args.residue_map else None
    metrics, mapping = compare(reference_text, prediction_text, chain_map, residue_correspondence=correspondence)
    metrics['model_confidence_not_reference_agreement'] = confidence_fields(result)
    confidence_path = args.confidence_result
    confidence_bytes = confidence_path.read_bytes() if confidence_path else None
    retained = result.get('retained_source_result', {}) if isinstance(result, dict) else {}
    if confidence_bytes is not None or isinstance(retained, dict) and 'manifest' in retained:
        evidence = json.loads(confidence_bytes) if confidence_bytes is not None else result
        fields, binding = bound_confidence(evidence, prediction_text.encode('utf-8'), source_path=confidence_path)
        metrics['model_confidence_not_reference_agreement'].update(fields)
        metrics['confidence_binding'] = binding
    else:
        metrics['confidence_binding'] = {'status': 'unavailable_no_structure_bound_evidence',
            'scope': 'Any inline native result confidence is retained separately; no selected sample association is inferred.'}
    request_bytes = args.request_file.read_bytes() if args.request_file else None
    prediction_format = 'mmcif' if is_mmcif(prediction_text) else 'pdb'
    metrics['sampling_provenance'] = sampling_provenance(request_bytes, args.structure_index)
    metrics['provenance'] = {'reference_file': str(args.reference),
                             'reference_sha256': hashlib.sha256(reference_bytes).hexdigest(),
                             'prediction_sha256': hashlib.sha256(prediction_text.encode()).hexdigest(),
                             'prediction_format': prediction_format,
                             'result_file': str(args.result) if args.result else None,
                             'result_sha256': hashlib.sha256(result_bytes).hexdigest() if result_bytes is not None else None,
                             'confidence_result_file': str(confidence_path) if confidence_path else None,
                             'confidence_result_sha256': hashlib.sha256(confidence_bytes).hexdigest() if confidence_bytes is not None else None,
                             'request_file': str(args.request_file) if args.request_file else None,
                             'request_sha256': metrics['sampling_provenance']['request_sha256'],
                             'residue_map_file': str(args.residue_map) if args.residue_map else None,
                             'residue_map_sha256': hashlib.sha256(args.residue_map.read_bytes()).hexdigest() if args.residue_map else None,
                             'biopython_version': Bio.__version__, 'numpy_version': np.__version__}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for filename, data in [('metrics.json', metrics), ('residue-mapping.json', mapping)]:
        (args.output_dir / filename).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    suffix = 'cif' if prediction_format == 'mmcif' else 'pdb'
    (args.output_dir / ('prediction.' + suffix)).write_bytes(prediction_text.encode('utf-8'))
    (args.output_dir / 'report.md').write_text(report_markdown(metrics), encoding='utf-8')
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
