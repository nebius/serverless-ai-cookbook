#!/usr/bin/env python3
"""Run one scVI/scANVI integration and materialize verified before/after views."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess

import anndata as ad
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import PCA
import umap

from recording_pipeline import (extract_verified_zip, file_identity, immutable_input, invoke,
                                native_file, operation_metadata, publish_bytes, timing, upload_source,
                                workspace_urls)
from scientific_receipts import save


def validate_source(path: Path, batch_key: str, labels_key: str | None,
                    unlabeled_category: str | None, method: str) -> ad.AnnData:
    if not path.is_file() or path.suffix.lower() != '.h5ad' or not 1 <= path.stat().st_size <= 64 * 1024 * 1024:
        raise ValueError('scVI input must be a nonempty .h5ad file up to 64 MiB.')
    data = ad.read_h5ad(path, backed='r')
    if not 1 <= data.n_obs <= 100_000 or not 1 <= data.n_vars <= 50_000:
        data.file.close(); raise ValueError('AnnData shape is outside the interactive App limits.')
    if batch_key not in data.obs:
        data.file.close(); raise ValueError(f'AnnData has no obs batch column {batch_key!r}.')
    if method == 'scanvi':
        if not labels_key or labels_key not in data.obs:
            data.file.close(); raise ValueError('scANVI requires a real labels_key in AnnData.obs.')
        if unlabeled_category not in set(data.obs[labels_key].astype(str)):
            data.file.close(); raise ValueError('The selected unlabeled category is absent from labels_key.')
    return data


def raw_umap(data: ad.AnnData, indexes: np.ndarray, seed: int) -> np.ndarray:
    matrix = data.X[indexes]
    if sparse.issparse(matrix):
        matrix = matrix.tocsr().astype(np.float64)
        means = np.asarray(matrix.mean(axis=0)).ravel()
        variances = np.asarray(matrix.power(2).mean(axis=0)).ravel() - means ** 2
    else:
        matrix = np.asarray(matrix, dtype=np.float64)
        variances = np.var(matrix, axis=0)
    features = np.argsort(variances, kind='stable')[-min(2000, data.n_vars):]
    selected = matrix[:, features]
    selected = selected.toarray() if sparse.issparse(selected) else np.asarray(selected)
    libraries = np.maximum(selected.sum(axis=1, keepdims=True), 1)
    normalized = np.log1p(selected / libraries * 10_000)
    dimensions = min(30, len(indexes) - 1, normalized.shape[1])
    latent = PCA(n_components=max(2, dimensions), random_state=seed).fit_transform(normalized)
    if len(indexes) < 4:
        return np.pad(latent[:, :2], ((0, 0), (0, max(0, 2 - latent.shape[1]))))[:, :2]
    return umap.UMAP(n_components=2, n_neighbors=min(15, len(indexes) - 1), min_dist=0.3,
                     random_state=seed, transform_seed=seed).fit_transform(latent)


def render_comparison(data: ad.AnnData, after_csv: Path, batch_key: str, seed: int,
                      labels_key: str | None = None) -> tuple[bytes, dict]:
    rng = np.random.default_rng(seed)
    indexes = np.arange(data.n_obs)
    if len(indexes) > 10_000:
        indexes = np.sort(rng.choice(indexes, 10_000, replace=False))
    before = raw_umap(data, indexes, seed)
    after_frame = pd.read_csv(after_csv, index_col=0)
    names = np.asarray(data.obs_names)[indexes]
    missing = [name for name in names if name not in after_frame.index]
    if missing:
        raise ValueError('Returned UMAP is missing source cells.')
    after = after_frame.loc[names, ['umap_1', 'umap_2']].to_numpy()
    batches = data.obs.iloc[indexes][batch_key].astype(str)
    codes, labels = pd.factorize(batches, sort=True)
    panels = [(before, codes, 'Before · normalized counts · batch'),
              (after, codes, 'After · latent · batch')]
    label_categories = []
    label_codes = None
    if labels_key:
        label_codes, label_categories = pd.factorize(
            data.obs.iloc[indexes][labels_key].astype(str), sort=True)
        panels.append((after, label_codes, f'After · latent · {labels_key}'))
    figure, axes = plt.subplots(1, len(panels), figsize=(6.5 * len(panels), 5.5),
                                facecolor='#f4f7f3')
    axes = np.atleast_1d(axes)
    for axis, (coordinates, colors, title) in zip(axes, panels, strict=True):
        axis.scatter(coordinates[:, 0], coordinates[:, 1], c=colors, cmap='turbo', s=12,
                     alpha=0.78, linewidths=0)
        axis.set_title(title); axis.set_xlabel('UMAP 1'); axis.set_ylabel('UMAP 2')
        axis.set_xticks([]); axis.set_yticks([])
    handles = [plt.Line2D([], [], marker='o', linestyle='', color=plt.get_cmap('turbo')(
        index / max(1, len(labels) - 1)), label=str(label)) for index, label in enumerate(labels[:16])]
    if handles:
        figure.legend(handles=handles, title=batch_key, loc='lower center', ncol=min(8, len(handles)))
    if labels_key and len(label_categories) <= 16:
        label_handles = [plt.Line2D([], [], marker='o', linestyle='', color=plt.get_cmap('turbo')(
            index / max(1, len(label_categories) - 1)), label=str(label))
            for index, label in enumerate(label_categories)]
        axes[-1].legend(handles=label_handles, title=labels_key, loc='best', fontsize='small')
    figure.suptitle('scVI/scANVI integration · observed metadata colors', fontsize=16,
                    color='#19241d')
    figure.tight_layout(rect=(0, 0.08 if handles else 0, 1, 0.95))
    target = io.BytesIO(); figure.savefig(target, format='png', dpi=160, bbox_inches='tight',
                                           metadata={'Software': 'Nebius Scientific AI'})
    plt.close(figure)
    return target.getvalue(), {'plotted_cells': len(indexes), 'total_cells': int(data.n_obs),
                               'batch_categories': [str(item) for item in labels],
                               'label_key': labels_key,
                               'label_categories': [str(item) for item in label_categories]}


def run(args, runner=subprocess.run):
    source = args.source.resolve()
    data = validate_source(source, args.batch_key, args.labels_key, args.unlabeled_category, args.method)
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_dir, run_dir, analysis = output / 'upload', output / 'run', output / 'analysis'
    artifact, code = upload_source(source=source, model=args.model, media_type='application/x-hdf5',
                                   directory=upload_dir, idempotency_key=args.idempotency_key + '-source',
                                   runner=runner)
    if code == 75:
        data.file.close(); return {'state': 'upload_pending', 'output_dir': str(output)}, 75
    payload = {'anndata_base64': artifact, 'filename': source.name, 'method': args.method,
               'batch_key': args.batch_key, 'max_epochs': args.max_epochs,
               'n_latent': args.n_latent, 'seed': args.seed, 'research_only': True}
    if args.method == 'scanvi':
        payload.update(labels_key=args.labels_key, unlabeled_category=args.unlabeled_category)
    input_path = output / 'input.json'; immutable_input(input_path, payload)
    receipt, code = invoke(model=args.model, tool=args.tool, input_path=input_path,
                           directory=run_dir, idempotency_key=args.idempotency_key,
                           wait_seconds=args.wait_seconds, recover_only=args.recover_only, runner=runner)
    if code == 75:
        data.file.close(); return {**receipt, 'output_dir': str(output)}, code
    archive = native_file(run_dir / 'result.json', 'application/zip')
    artifacts = extract_verified_zip(archive, analysis, required=(
        'manifest.json', 'integrated.h5ad', 'latent_embeddings.csv', 'umap_embeddings.csv', 'preview.png'))
    manifest = json.loads((analysis / 'manifest.json').read_text())
    identity = file_identity(source)
    if (manifest.get('input_sha256') != identity['sha256'] or manifest.get('method') != args.method
            or manifest.get('batch_key') != args.batch_key or manifest.get('cells') != data.n_obs
            or manifest.get('genes') != data.n_vars or manifest.get('seed') != args.seed):
        data.file.close(); raise ValueError('scVI result manifest differs from submitted input or parameters.')
    image, plotted = render_comparison(data, analysis / 'umap_embeddings.csv', args.batch_key,
                                       args.seed, args.labels_key)
    data.file.close()
    comparison = publish_bytes(analysis / 'before-after-umap.png', image)
    operation = operation_metadata(run_dir / 'operation.json')
    summary = {
        'schema': 'nebius-scientific-ai/scvi-integration/v1', 'state': 'succeeded',
        'model': args.model, 'operation_id': operation.get('id') or receipt.get('operation_id'),
        'input': {'path': str(source), **identity, 'cells': manifest['cells'], 'genes': manifest['genes']},
        'parameters': {key: value for key, value in payload.items() if key != 'anndata_base64'},
        'runtime': {'timing': timing(operation), 'scvi_tools_version': manifest.get('scvi_tools_version'),
                    'torch_version': manifest.get('torch_version'), 'gpu': manifest.get('gpu')},
        'embedding': {'latent_dimensions': manifest.get('latent_dimensions'), **plotted},
        'artifacts': {**artifacts, 'before_after_umap': comparison},
        'limitations': ['Research use only; batch mixing is descriptive and not biological or clinical validation.',
                        'The before view uses deterministic normalized-count PCA/UMAP for visualization only.'],
    }
    save(analysis / 'summary.json', summary)
    before_after = analysis / 'before-after-umap.png'
    integrated = analysis / 'integrated.h5ad'
    summary_path = analysis / 'summary.json'
    return {**summary, 'before_after_path': str(before_after),
            'integrated_anndata_path': str(integrated), 'summary_path': str(summary_path),
            'workspace_urls': workspace_urls(before_after=before_after, integrated_anndata=integrated,
                                             summary=summary_path)}, 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--batch-key', required=True)
    parser.add_argument('--method', choices=('scvi', 'scanvi'), default='scvi')
    parser.add_argument('--labels-key')
    parser.add_argument('--unlabeled-category', default='Unknown')
    parser.add_argument('--max-epochs', type=int, default=20)
    parser.add_argument('--n-latent', type=int, default=10)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--idempotency-key', required=True)
    parser.add_argument('--operation-wait-seconds', '--wait-seconds', dest='wait_seconds', type=int, default=600)
    parser.add_argument('--recover-only', action='store_true')
    parser.add_argument('--model', default='scvi-scanvi')
    parser.add_argument('--tool', default='integrate_single_cell_native')
    args = parser.parse_args()
    if (not 8 <= len(args.idempotency_key) <= 193 or not 1 <= args.max_epochs <= 20
            or not 2 <= args.n_latent <= 64 or args.seed < 0 or not 0 <= args.wait_seconds <= 3600):
        parser.error('Invalid scVI key, epochs, latent dimensions, seed or wait.')
    try:
        value, code = run(args); print(json.dumps(value, separators=(',', ':'))); raise SystemExit(code)
    except Exception as error:
        print(json.dumps({'state': 'error', 'error_type': type(error).__name__,
                          'details': 'Inspect retained upload/run/analysis receipts; do not submit a fallback.',
                          'output_dir': str(args.output_dir)}, separators=(',', ':')))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
