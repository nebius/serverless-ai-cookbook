import importlib.util
import json
from pathlib import Path
import types

from rdkit import Chem
from rdkit.Chem import QED


spec = importlib.util.spec_from_file_location(
    'genmol_generate', Path(__file__).with_name('genmol-generate.py'))
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def model_result():
    smiles = ['Nc1ccccn1', 'Nc1ccccn1', 'CCO', 'not-a-smiles']
    return {'status': 'success', 'molecules': [
        {'smiles': value, 'score': float(QED.qed(Chem.MolFromSmiles(value)))
         if Chem.MolFromSmiles(value) is not None else 0.1}
        for value in smiles],
        'metrics': {'requested_molecules': 4, 'returned_molecules': 4,
                    'accepted_molecules': 3}}


def test_one_admission_materializes_complete_candidate_review(tmp_path):
    args = types.SimpleNamespace(
        output_dir=tmp_path / 'output', idempotency_key='genmol-recording-test',
        num_molecules=4, smiles_mask='[*{10-20}]', scoring='QED',
        temperature=1.0, noise=1.0, wait_seconds=30, recover_only=False,
        model='genmol', tool='genmol_generate_native')
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        pipeline.save(target / 'receipt.json', {
            'state': 'succeeded', 'operation_id': 'genmol-operation'})
        pipeline.save(target / 'operation.json', {'structuredContent': {
            'id': 'genmol-operation', 'accepted_at': '2026-09-21T00:00:00Z',
            'completed_at': '2026-09-21T00:00:05Z'}})
        pipeline.save(target / 'result.json', model_result())
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'genmol-operation'
    assert result['counts'] == {
        'requested': 4, 'generated': 4, 'valid': 3, 'duplicates': 1, 'retained': 1}
    assert len(commands) == 1 and Path(commands[0][1]).name == 'invoke-native.py'
    assert (args.output_dir / 'analysis/candidate-grid.png').read_bytes().startswith(
        b'\x89PNG\r\n\x1a\n')
    rows = json.loads((args.output_dir / 'analysis/summary.json').read_text())['candidates']
    assert rows[0]['retained'] and rows[0]['hydrogen_bond_donors'] >= 1
    assert rows[1]['canonical_duplicate_of_row'] == 1 and not rows[1]['retained']
    assert rows[2]['retention_status'] == 'no aromatic heterocycle'
    assert not rows[3]['valid'] and rows[3]['retention_status'] == 'invalid'
    assert result['workspace_urls'] == {}


def test_aromatic_heterocycle_requires_an_aromatic_ring_with_a_heteroatom():
    assert pipeline.aromatic_heterocycle(Chem.MolFromSmiles('Nc1ccccn1'))
    assert not pipeline.aromatic_heterocycle(Chem.MolFromSmiles('Nc1ccccc1'))
    assert not pipeline.aromatic_heterocycle(Chem.MolFromSmiles('C1CCNCC1'))
