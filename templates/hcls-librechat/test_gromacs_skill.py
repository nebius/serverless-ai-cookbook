import importlib.util
from pathlib import Path
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'skills/scientific-ai/gromacs'
spec = importlib.util.spec_from_file_location('gromacs_bundle', ROOT / 'scripts/make-input-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


def test_bundle_preserves_native_inputs_and_is_reproducible(tmp_path):
    source = tmp_path / 'inputs'
    (source / 'includes').mkdir(parents=True)
    (source / 'includes/ligand.itp').write_text('actual topology bytes\n')
    (source / 'simulation.tpr').write_bytes(b'native fixture')
    first = bundle.build(source, tmp_path / 'first.tar.gz')
    second = bundle.build(source, tmp_path / 'second.tar.gz')
    assert first['sha256'] == second['sha256']
    with tarfile.open(first['path']) as archive:
        assert archive.extractfile('simulation.tpr').read() == b'native fixture'
        assert archive.getnames() == ['includes/ligand.itp', 'simulation.tpr']
    with pytest.raises(FileExistsError):
        bundle.build(source, tmp_path / 'first.tar.gz')


def test_bundle_rejects_output_within_source_and_links(tmp_path):
    source = tmp_path / 'inputs'
    source.mkdir()
    (source / 'input').write_bytes(b'a')
    with pytest.raises(ValueError, match='outside'):
        bundle.build(source, source / 'output.tar.gz')
    (source / 'alias').symlink_to(source / 'input')
    with pytest.raises(ValueError, match='symlinks'):
        bundle.build(source, tmp_path / 'output.tar.gz')
