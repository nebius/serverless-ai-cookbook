import hashlib
import importlib.util
import json
from pathlib import Path
import types
import zipfile

import anndata as ad
import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location('scvi_integrate', Path(__file__).with_name('scvi-integrate.py'))
pipeline = importlib.util.module_from_spec(spec); spec.loader.exec_module(pipeline)


def test_scvi_pipeline_admits_once_and_materializes_before_after_umap(tmp_path):
    source = tmp_path / 'synthetic.h5ad'
    names = [f'cell-{index:03}' for index in range(20)]
    data = ad.AnnData(X=np.arange(200, dtype=np.float32).reshape(20, 10) % 7,
                      obs=pd.DataFrame({'batch': pd.Categorical(['a', 'b'] * 10)}, index=names),
                      var=pd.DataFrame(index=[f'gene-{index:03}' for index in range(10)]))
    ad.settings.allow_write_nullable_strings = True; data.write_h5ad(source)
    args = types.SimpleNamespace(source=source, batch_key='batch', labels_key=None,
        unlabeled_category='Unknown', method='scvi', max_epochs=20, n_latent=10, seed=42,
        output_dir=tmp_path / 'output', idempotency_key='scvi-recording-test', wait_seconds=30,
        recover_only=False, model='scvi-scanvi', tool='integrate_single_cell_native')
    commands = []

    def runner(command, **kwargs):
        commands.append(command); target = Path(command[command.index('--output-dir') + 1])
        target.mkdir(parents=True, exist_ok=True)
        if command[1].endswith('upload-artifact.py'):
            raw = source.read_bytes(); pipeline.save(target / 'artifact.json', {
                'artifact_id': '11111111-1111-4111-8111-111111111111',
                'sha256': hashlib.sha256(raw).hexdigest(), 'size_bytes': len(raw),
                'media_type': 'application/x-hdf5', 'compression': 'none'})
        else:
            stage = tmp_path / 'stage'; stage.mkdir(exist_ok=True)
            (stage / 'integrated.h5ad').write_bytes(source.read_bytes())
            pd.DataFrame(np.zeros((20, 10)), index=names).to_csv(stage / 'latent_embeddings.csv')
            pd.DataFrame({'umap_1': np.linspace(-1, 1, 20), 'umap_2': np.linspace(1, -1, 20)},
                         index=names).to_csv(stage / 'umap_embeddings.csv')
            (stage / 'preview.png').write_bytes(b'\x89PNG\r\n\x1a\nfixture')
            (stage / 'manifest.json').write_text(json.dumps({
                'method': 'scvi', 'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'cells': 20, 'genes': 10, 'latent_dimensions': 10, 'batch_key': 'batch',
                'labels_key': None, 'unlabeled_category': None, 'max_epochs': 20, 'seed': 42,
                'scvi_tools_version': '1.5.0.post1', 'torch_version': 'fixture', 'gpu': 'fixture'}))
            archive = target / 'result.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                for filename in ('manifest.json', 'integrated.h5ad', 'latent_embeddings.csv',
                                 'umap_embeddings.csv', 'preview.png'):
                    output.write(stage / filename, filename)
            identity = pipeline.file_identity(archive)
            pipeline.save(target / 'result.json', {'schema': 'scientific-native-file/v1',
                'content_type': 'application/zip', 'artifact': identity,
                'file': {'path': str(archive), **identity}})
            pipeline.save(target / 'receipt.json', {'state': 'succeeded', 'operation_id': 'scvi-operation'})
            pipeline.save(target / 'operation.json', {'structuredContent': {'id': 'scvi-operation',
                'accepted_at': '2026-09-21T00:00:00Z', 'completed_at': '2026-09-21T00:00:05Z'}})
        return types.SimpleNamespace(returncode=0, stdout='', stderr='')

    result, code = pipeline.run(args, runner)
    assert code == 0 and result['operation_id'] == 'scvi-operation'
    assert result['input']['cells'] == 20 and result['input']['genes'] == 10
    assert result['embedding']['plotted_cells'] == 20
    assert [Path(command[1]).name for command in commands] == ['upload-artifact.py', 'invoke-native.py']
    assert Path(result['before_after_path']).read_bytes().startswith(b'\x89PNG')
