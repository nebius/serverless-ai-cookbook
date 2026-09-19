"""Manifest-aware protein-design measurements; no inference or efficacy verdict.

The manifest and sibling output-NN.artifact files are the existing batch-client
ABI. Content type comes from declared metadata, never file size or .artifact.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

try:
    import qualification_evaluators as evaluator
except ModuleNotFoundError:
    spec = importlib.util.spec_from_file_location(
        "qualification_evaluators",
        Path(__file__).parent / "scripts/qualification/evaluators.py",
    )
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_artifact(raw, artifact, name):
    compression = artifact.get("compression", "none")
    if compression == "gzip":
        raw = gzip.decompress(raw)
    elif compression == "zstd":
        raw = subprocess.run(
            ["zstd", "--decompress", "--stdout"],
            input=raw,
            capture_output=True,
            check=True,
        ).stdout
    elif compression != "none":
        raise ValueError("Unsupported declared artifact compression: " + compression)
    media = artifact["media_type"].split(";", 1)[0].lower()
    if "pdb" in media or "cif" in media:
        return {"structure": raw.decode("utf-8")}
    if "json" in media:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"value": value}
    if media == "text/csv":
        return {"csv_rows": list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))}
    if "tar" in media:
        members, structures = [], []
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as bundle:
            for member in bundle:
                if not member.isfile():
                    continue
                content = bundle.extractfile(member).read()
                members.append(
                    {
                        "name": member.name,
                        "size_bytes": len(content),
                        "sha256": digest(content),
                    }
                )
                if member.name.lower().endswith((".pdb", ".cif", ".mmcif")):
                    structures.append(
                        {"structure": content.decode("utf-8"), "member": member.name}
                    )
        return {"structures": structures, "archive_members": members}
    return {
        "uninterpreted": True,
        "declared_media_type": media,
        "name": name,
        "decoded_size_bytes": len(raw),
    }


def analyze(
    manifest_path,
    *,
    binder_chain=None,
    binder_length_min=None,
    binder_length_max=None,
    target_reference=None,
    target_chain=None,
):
    raw_manifest = manifest_path.read_bytes()
    manifest = json.loads(raw_manifest)
    if manifest.get("schema") != "fs2-serve.nebius.ai/scientific-artifact-manifest/v1":
        raise ValueError(
            "Expected the published scientific-artifact-manifest/v1 output manifest."
        )
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Output manifest must contain entries.")
    expected = {}
    for key, value in [
        ("binder_chain", binder_chain),
        ("binder_length_min", binder_length_min),
        ("binder_length_max", binder_length_max),
    ]:
        if value is not None:
            expected[key] = value
    if (
        binder_length_min is not None
        and binder_length_max is not None
        and binder_length_min > binder_length_max
    ):
        raise ValueError("Binder minimum exceeds maximum.")
    if bool(target_reference) != bool(target_chain):
        raise ValueError(
            "Target reference and explicit reference chain must be supplied together."
        )
    target = (
        evaluator.parse_chain(target_reference.read_text(), target_chain)
        if target_reference
        else None
    )
    outputs, inventory, structures, metadata, seen = [], [], [], [], set()
    for index, entry in enumerate(entries):
        name, artifact = entry["name"], entry["artifact"]
        if name in seen:
            raise ValueError("Duplicate manifest artifact name: " + name)
        seen.add(name)
        path = manifest_path.parent / f"output-{index:02d}.artifact"
        raw = path.read_bytes()
        if len(raw) != artifact["size_bytes"] or digest(raw) != artifact["sha256"]:
            raise ValueError("Artifact hash/size differs from manifest entry: " + name)
        parsed = decode_artifact(raw, artifact, name)
        outputs.append(
            {**parsed, "artifact_name": name, "semantic_type": entry["semantic_type"]}
        )
        inventory.append(
            {
                "artifact_name": name,
                "semantic_type": entry["semantic_type"],
                "local_filename": path.name,
                **artifact,
            }
        )
        pieces = (
            [{"structure": parsed["structure"]}]
            if "structure" in parsed
            else parsed.get("structures", [])
        )
        for piece in pieces:
            text = piece["structure"]
            geometry = evaluator.design_metrics(text, expected)
            sequences = {
                chain: evaluator.parse_chain(text, chain)["sequence"]
                for chain in evaluator.protein_chain_ids(text)
            }
            target_matches = (
                [
                    chain
                    for chain, sequence in sequences.items()
                    if sequence == target["sequence"]
                ]
                if target
                else None
            )
            structures.append(
                {
                    "artifact_name": name,
                    "member": piece.get("member"),
                    "coordinate_sha256": digest(text.encode()),
                    "semantic_type": entry["semantic_type"],
                    "role": "unassigned_without_explicit_provenance",
                    "geometry": geometry,
                    "target_sequence_matching_chains": target_matches,
                    "target_sequence_exact_unique": len(target_matches) == 1
                    if target
                    else None,
                    "sequence_scope": "observed C-alpha residues; missing coordinates are not invented",
                    "sequence_hashes": {
                        chain: digest(sequence.encode())
                        for chain, sequence in sequences.items()
                    },
                }
            )
        metadata.append(
            {
                "artifact_name": name,
                "content": {
                    key: value
                    for key, value in parsed.items()
                    if key not in {"structure", "structures"}
                },
            }
        )
    linked = None
    if any(
        item.get("schema_version")
        == "fs2-serve.nebius.ai/proteina-complexa-design-provenance/v1"
        for item in outputs
    ):
        linked = evaluator.proteina_design_metrics({"outputs": outputs}, expected)
        roles = {
            row[field]: role
            for row in linked["predictions"]
            for field, role in [
                ("generated_artifact", "generated"),
                ("self_refolded_artifact", "self_refolded"),
            ]
        }
        for structure in structures:
            structure["role"] = roles.get(structure["artifact_name"], structure["role"])
    return {
        "schema": "scientific-ai/protein-design-artifact-analysis/v1",
        "manifest_sha256": digest(raw_manifest),
        "artifact_inventory": inventory,
        "verified_artifacts": len(inventory),
        "coordinate_outputs": len(structures),
        "structures": structures,
        "metadata_unmodified_values": metadata,
        "linked_designs": linked,
        "requested_constraints": expected,
        "explicit_binder_unique_sequences": len(
            {
                row["sequence_hashes"][binder_chain]
                for row in structures
                if binder_chain in row["sequence_hashes"]
            }
        )
        if binder_chain
        else None,
        "target_reference_sha256": digest(target_reference.read_bytes())
        if target_reference
        else None,
        "target_reference_chain": target_chain,
        "limitations": [
            "No inference, filtering, ranking, affinity or biological efficacy validation.",
            "Coordinate output count is not sample count; raw/refold pairs are linked only by verified provenance.",
            "Model-native CSV/JSON values are retained, not treated as comparable cross-model scores.",
            "Geometry uses the existing qualification evaluator coarse C-alpha screen; not all-atom validation.",
            "No target or binder-chain identity is guessed when the caller did not specify it.",
        ],
    }


def constraint_observation(result, row):
    """Explain recorded constraints without changing selections or evaluator results."""
    geometry = row['geometry']
    observed = [chain['chain'] for chain in geometry['chains']]
    selected = result['requested_constraints'].get('binder_chain')
    reasons = []
    if selected and selected not in observed:
        reasons.append(f'Requested binder chain {selected} absent; no remapping was performed')
    for chain in geometry['chains']:
        if chain['chain'] == selected and chain.get('within_requested_length') is False:
            reasons.append(f"Selected chain {selected} fails the requested length bounds")
    if row.get('target_sequence_exact_unique') is False:
        reasons.append('Reference target sequence does not have exactly one observed chain match')
    if geometry.get('constraint_pass') is False and not reasons:
        reasons.append('Recorded evaluator constraint verdict is false; no unrecorded rejection cause inferred')
    if geometry.get('constraint_pass') is None and not reasons:
        reasons.append('Constraint verdict unavailable; no success inferred')
    return {'requested_binder_chain': selected, 'observed_chains': observed,
            'constraint_pass': geometry.get('constraint_pass'),
            'constraint_reason': '; '.join(reasons) or 'No recorded constraint failure; not biological validation',
            'target_sequence_exact_unique': row.get('target_sequence_exact_unique')}


def render_observations(result):
    def cell(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False).replace('|', '&#124;').replace('\n', ' ')
    lines = ['## Recorded constraint verdicts', '',
             'These are the unchanged requested selections and recorded evaluator verdicts. '
             'A missing requested chain is an analysis-selection mismatch, not a platform admission failure. '
             'No chain is remapped and no biological success follows from a pass.', '',
             '| Artifact / member | Observed chains | Requested binder | Constraint pass | Target exact unique | Reason |',
             '| --- | --- | --- | --- | --- | --- |']
    for row in result['structures']:
        observation = constraint_observation(result, row)
        lines.append('| ' + ' | '.join(cell(value) for value in [
            [row['artifact_name'], row['member']], observation['observed_chains'],
            observation['requested_binder_chain'], observation['constraint_pass'],
            observation['target_sequence_exact_unique'], observation['constraint_reason']]) + ' |')
    if not result['structures']:
        lines.append('| No coordinate outputs | [] | null | unknown | unknown | No coordinate verdict available |')
    selected = result['requested_constraints'].get('binder_chain')
    lines += ['', '## Observed sequence diversity', '',
              f"Requested binder chain: {cell(selected)}. Recorded unique sequences for that exact chain: "
              f"{cell(result['explicit_binder_unique_sequences'])}. "
              'Null means no explicit chain was selected; zero with an absent selected chain does not measure model-wide diversity.']
    if result['linked_designs']:
        predictions = result['linked_designs']['predictions']
        unique = len({row['sequence_sha256'] for row in predictions})
        lines.append(f'Provenance-linked design sequence hashes: {unique} unique / {len(predictions)} design rows. '
                     'Raw/refolded pairs are not counted twice; no sequence-distance or experimental claim.')
    lines += ['', '## Retained model-native scores and filter metadata', '',
              'Exact published values and row order only; no normalization, invented confidence, '
              'cross-model leaderboard or inference of hidden rejected candidates. '
              'A source filter flag is not the analysis constraint verdict above.', '',
              '| Source artifact | Field | Values in published row order |', '| --- | --- | --- |']
    shown = 0
    for item in result['metadata_unmodified_values']:
        rows = item['content'].get('csv_rows')
        if not isinstance(rows, list):
            continue
        lines.append(f"| {cell(item['artifact_name'])} | published row count | {len(rows)} |")
        fields = sorted({key for row in rows for key in row
                         if re.search(r'score|confidence|plddt|ptm|pae|rmsd|filter|reject', key, re.I)})
        for field in fields:
            lines.append(f"| {cell(item['artifact_name'])} | {cell(field)} | {cell([row.get(field) for row in rows])} |")
            shown += 1
    if not shown:
        lines.append('| No recognized published score/filter columns | unavailable | No confidence inferred |')
    lines += ['', 'All original CSV/JSON metadata remains in measurements.json. '
              'Missing rejection rows/reasons are unavailable, not zero; a filtered final artifact count '
              'cannot establish the number of accepted/rejected search candidates.', '']
    return '\n'.join(lines)


def publish(result, output):
    output.mkdir(parents=True, exist_ok=True)
    (output / "measurements.json").write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n"
    )
    with (output / "inventory.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "artifact_name",
                "member",
                "role",
                "chain",
                "observed_residues",
                "sequence_sha256",
                "adjacent_ca_median_angstrom",
                "ca_step_outside_2_5_to_4_5_fraction",
                "requested_binder_chain", "constraint_pass", "constraint_reason",
                "target_sequence_exact_unique", "within_requested_length",
            ],
        )
        writer.writeheader()
        for row in result["structures"]:
            observation = constraint_observation(result, row)
            for chain in row["geometry"]["chains"]:
                writer.writerow(
                    {
                        "artifact_name": row["artifact_name"],
                        "member": row["member"],
                        "role": row["role"],
                        "chain": chain["chain"],
                        "observed_residues": chain["residues"],
                        "sequence_sha256": chain["sequence_sha256"],
                        "adjacent_ca_median_angstrom": chain[
                            "adjacent_ca_median_angstrom"
                        ],
                        "ca_step_outside_2_5_to_4_5_fraction": chain[
                            "ca_step_outside_2_5_to_4_5_fraction"
                        ],
                        **{key: observation[key] for key in ('requested_binder_chain', 'constraint_pass',
                           'constraint_reason', 'target_sequence_exact_unique')},
                        'within_requested_length': chain.get('within_requested_length'),
                    }
                )
    linked = result["linked_designs"]
    text = "# Protein-design artifact measurements\n\n"
    text += f"Verified artifacts: {result['verified_artifacts']}. Coordinate outputs: {result['coordinate_outputs']}.\n\n"
    if linked:
        text += (
            f"Verified generated/refolded design pairs: {linked['design_count']}. "
            f"Coarse raw-geometry screen: {linked['generated_geometry_pass_count']}/{linked['design_count']}; "
            f"refold screen: {linked['self_refolded_geometry_pass_count']}/{linked['design_count']}.\n\n"
        )
    text += "See inventory.csv for every coordinate chain and measurements.json for exact hashes, provenance joins, source scores and constraints.\n\n"
    text += render_observations(result) + '\n'
    text += "\n".join("- " + item for item in result["limitations"]) + "\n"
    (output / "report.md").write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--binder-chain")
    parser.add_argument("--binder-length-min", type=int)
    parser.add_argument("--binder-length-max", type=int)
    parser.add_argument("--target-reference", type=Path)
    parser.add_argument("--target-chain")
    args = parser.parse_args()
    result = analyze(
        args.manifest,
        binder_chain=args.binder_chain,
        binder_length_min=args.binder_length_min,
        binder_length_max=args.binder_length_max,
        target_reference=args.target_reference,
        target_chain=args.target_chain,
    )
    publish(result, args.output_dir)
    print(
        json.dumps(
            {
                "verified_artifacts": result["verified_artifacts"],
                "coordinate_outputs": result["coordinate_outputs"],
                "biological_validation": False,
            }
        )
    )


if __name__ == "__main__":
    main()
