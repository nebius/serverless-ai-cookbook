import gzip
import io
import tarfile

import pytest

from proteina_variant_cases import target_bundle


def test_target_bundle_preserves_exact_path_bytes_and_reproducible_metadata():
    path = "assets/target_data/ligand_targets/example.pdb"
    payload = target_bundle(path, b"HETATM example\n")
    assert payload == target_bundle(path, b"HETATM example\n")
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(payload))) as archive:
        assert archive.getnames() == [path]
        assert archive.extractfile(path).read() == b"HETATM example\n"
        assert archive.getmember(path).mtime == 0


@pytest.mark.parametrize("path", ["/absolute", "assets/../other"])
def test_invalid_source_paths_rejected(path):
    with pytest.raises(ValueError):
        target_bundle(path, b"data")
