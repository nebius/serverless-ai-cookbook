import argparse
import importlib.util
import json
from pathlib import Path

from rdkit import Chem
from rdkit.Chem import AllChem


ROOT = Path(__file__).parent


def load_module():
    spec = importlib.util.spec_from_file_location('diffdock_campaign', ROOT / 'diffdock-campaign.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def receptor(path: Path):
    path.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C  \nEND\n')


def sdf(smiles: str) -> str:
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    assert AllChem.EmbedMolecule(molecule, randomSeed=7) == 0
    return Chem.MolToMolBlock(molecule) + '\n$$$$\n'


def arguments(tmp_path: Path, protein: Path):
    return argparse.Namespace(
        receptor=[('target', protein)], ligand=[('ethanol', 'CCO')], ligand_file=None,
        glob_ligands=None, genmol_summary=None, top_candidates=5,
        output_dir=tmp_path / 'out', idempotency_key='recording-dock-test', num_poses=1,
        time_divisions=20, steps=18, random_seed=7, wait_seconds=30,
        max_workers=2, recover_only=False,
    )


def test_campaign_uploads_once_and_materializes_verified_pose(tmp_path, monkeypatch):
    module = load_module(); protein = tmp_path / 'target.pdb'; receptor(protein)
    uploads, calls = [], []

    def upload_source(**kwargs):
        uploads.append(kwargs)
        return ({'artifact_id': '00000000-0000-4000-8000-000000000001',
                 'sha256': '1' * 64, 'size_bytes': protein.stat().st_size,
                 'media_type': 'chemical/x-pdb', 'compression': 'none'}, 0)

    def invoke(**kwargs):
        calls.append(json.loads(kwargs['input_path'].read_text()))
        directory = kwargs['directory']; directory.mkdir(parents=True, exist_ok=True)
        module.save(directory / 'receipt.json', {'state': 'succeeded', 'operation_id': 'dock-op'})
        module.save(directory / 'operation.json', {'id': 'dock-op',
                    'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:00:03Z'})
        module.save(directory / 'result.json', {
            'status': 'success', 'details': 'success: generated 1 pose(s)',
            'ligand': 'CCO', 'protein': protein.read_text(),
            'ligand_positions': [sdf('CCO')], 'position_confidence': [-1.25],
            'trajectory': [],
        })
        return {'state': 'succeeded', 'operation_id': 'dock-op'}, 0

    monkeypatch.setattr(module, 'upload_source', upload_source)
    monkeypatch.setattr(module, 'invoke', invoke)
    result, code = module.run(arguments(tmp_path, protein))
    assert code == 0 and result['state'] == 'succeeded'
    assert len(uploads) == 1 and len(calls) == 1
    assert calls[0]['protein']['artifact_id'].endswith('1')
    assert (tmp_path / 'out/cases/target-ethanol/analysis/pose-rank-1.sdf').is_file()
    assert (tmp_path / 'out/measurements.csv').is_file()
    assert (tmp_path / 'out/gallery.png').is_file()
    assert (tmp_path / 'out/score-heatmap.png').is_file()


def test_genmol_candidates_are_consumed_without_substitution(tmp_path):
    module = load_module()
    summary = tmp_path / 'summary.json'
    summary.write_text(json.dumps({'top_five_valid_unique_by_qed': [
        {'row': 4, 'canonical_smiles': 'c1ccncc1O'},
        {'row': 8, 'canonical_smiles': 'NC1=CC=CC=C1'},
    ]}))
    args = argparse.Namespace(ligand=None, ligand_file=None, glob_ligands=None,
                              genmol_summary=summary, top_candidates=1)
    assert module.collect_ligands(args) == [('genmol-row-4', 'Oc1cccnc1')]


def test_live_native_pose_and_confidence_cardinality_must_match():
    module = load_module()
    value = {'status': 'success', 'ligand': 'CCO',
             'ligand_positions': [sdf('CCO')], 'position_confidence': []}
    try:
        module.validate_result(value, 'CCO', 1)
    except ValueError as error:
        assert 'cardinality' in str(error)
    else:
        raise AssertionError('mismatched native DiffDock rows must be rejected')
