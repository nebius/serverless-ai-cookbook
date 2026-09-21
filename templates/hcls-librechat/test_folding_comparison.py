import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parent


def load_module():
    spec = importlib.util.spec_from_file_location('folding_comparison', ROOT / 'folding-comparison.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def pdb() -> str:
    lines = []
    for index in range(1, 7):
        lines.append(f'ATOM  {index:5d}  CA  ALA A{index:4d}    {index * 3.0:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 20.00           C  ')
    return '\n'.join(lines + ['TER', 'END', ''])


def result_for(model: str, structure: str):
    if model == 'openfold2':
        return {'input_id': 'protein', 'structures_in_ranked_order': [{
            'format': 'pdb', 'structure': structure, 'confidence': 75.0,
            'ptm_score': 0.8, 'inference_seconds': 1.2}]}
    if model == 'openfold3':
        return {'request_id': 'protein', 'outputs': [{'input_id': 'protein',
            'runtime_metrics': {'inference_seconds': 2.5},
            'structures_with_scores': [{'format': 'cif', 'structure': structure,
                'confidence_score': 0.9, 'complex_plddt_score': 0.8,
                'complex_pde_score': 0.1, 'ptm_score': 0.85, 'iptm_score': 0.0}]}]}
    return {'structures': [{'format': 'mmcif', 'structure': structure}],
            'confidence_scores': [0.91], 'ptm_scores': [0.86]}


def test_three_model_campaign_preserves_operations_and_metrics(tmp_path, monkeypatch):
    module = load_module(); structure = pdb()
    fasta = tmp_path / 'protein.fasta'; fasta.write_text('>protein\nAAAAAA\n')
    reference = tmp_path / 'reference.pdb'; reference.write_text(structure)
    calls = []

    def invoke(**kwargs):
        payload = json.loads(kwargs['input_path'].read_text()); calls.append((kwargs['model'], payload))
        directory = kwargs['directory']; directory.mkdir(parents=True, exist_ok=True)
        operation = f"{kwargs['model']}-op"
        module.save(directory / 'receipt.json', {'state': 'succeeded', 'operation_id': operation})
        module.save(directory / 'operation.json', {'id': operation,
                    'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:00:04Z'})
        module.save(directory / 'result.json', result_for(kwargs['model'], structure))
        return {'state': 'succeeded', 'operation_id': operation}, 0

    monkeypatch.setattr(module, 'invoke', invoke)
    args = argparse.Namespace(fasta=[('protein', fasta)], glob_fasta=None,
        reference=[('protein', reference)], reference_dir=None, output_dir=tmp_path / 'out',
        idempotency_key='recording-fold-test', wait_seconds=30, max_workers=3, recover_only=False)
    result, code = module.run(args)
    assert code == 0 and result['state'] == 'succeeded' and result['succeeded_count'] == 3
    assert {model for model, _ in calls} == {'openfold2', 'openfold3', 'boltz2'}
    assert all(case['comparison']['global_ca_rmsd_angstrom'] == 0 for case in result['cases'])
    assert all(case['comparison']['tm_score_reference_normalized_ca'] == 1 for case in result['cases'])
    assert (tmp_path / 'out/measurements.csv').is_file()
    assert (tmp_path / 'out/gallery.png').is_file()
    assert (tmp_path / 'out/report.md').is_file()
