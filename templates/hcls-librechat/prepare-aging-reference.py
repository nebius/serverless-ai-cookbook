"""Build-only conversion of checksum-pinned publication preprocessing assets.

Runtime analysis uses original Keras H5 plus plain JSON, never user pickles or
the serving PyTorch conversion. The qualification corpus uses these same pins.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

REVISION = '696c477dac9b7641bf283c48af1cc9bb0a0803a3'
SOURCE = f'https://raw.githubusercontent.com/rsinghlab/AltumAge/{REVISION}'
HASHES = {
    'multi_platform_cpgs.pkl': '068ed91ba02ec575262c7e9d0857eb9589224e478b8f2a9181c0fbcb0e26359d',
    'scaler.pkl': '68331c0b8974c192460e2ebf31e4a974da3292775f82c52d54a11dea629ff53d',
    'AltumAge.h5': '2db4011115c3f877746d6dd722045da74055d25e8803368a1679d0dbaafe1846',
}


def prepare(output, source_dir=None):
    import io
    import numpy as np
    import pandas as pd
    assets = {}
    for name, expected in HASHES.items():
        if source_dir:
            data = (source_dir / name).read_bytes()
        else:
            with urlopen(f'{SOURCE}/example_dependencies/{name}', timeout=90) as response:
                data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f'Pinned AltumAge reference hash mismatch: {name}')
        assets[name] = data
    # Only the fixed, verified upstream objects above are unpickled, at build time.
    cpgs = list(map(str, pd.read_pickle(io.BytesIO(assets['multi_platform_cpgs.pkl']))))
    scaler = pd.read_pickle(io.BytesIO(assets['scaler.pkl']))
    center, scale = np.asarray(scaler.center_), np.asarray(scaler.scale_)
    if len(cpgs) != 20318 or len(set(cpgs)) != 20318 or center.shape != (20318,) or scale.shape != (20318,):
        raise ValueError('Pinned preprocessing has an unexpected feature shape')
    if not np.isfinite(center).all() or not np.isfinite(scale).all() or not (scale > 0).all():
        raise ValueError('Pinned preprocessing is not finite with positive scales')
    output.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({'cpgs': cpgs, 'center': center.tolist(), 'scale': scale.tolist()}, separators=(',', ':')).encode()
    (output / 'preprocessing.json').write_bytes(payload)
    (output / 'AltumAge.h5').write_bytes(assets['AltumAge.h5'])
    manifest = {'source_revision': REVISION, 'source_url': SOURCE, 'source_hashes': HASHES,
        'runtime_artifacts': {'preprocessing.json': hashlib.sha256(payload).hexdigest(), 'AltumAge.h5': HASHES['AltumAge.h5']}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    with urlopen(f'{SOURCE}/LICENSE', timeout=90) as response:
        (output / 'LICENSE-AltumAge').write_bytes(response.read())
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-dir', type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.source_dir)))
