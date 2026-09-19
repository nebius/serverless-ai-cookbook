import pytest

from verify_diffdock_public import normalize


def test_public_poses_keep_order_and_confidences():
    result = normalize({"ligand_positions": ["first", "second"], "position_confidence": [-1.0, -2.0]})
    assert result == {"poses": [{"sdf": "first", "confidence": -1.0}, {"sdf": "second", "confidence": -2.0}]}


def test_public_count_mismatch_is_not_silently_truncated():
    with pytest.raises(ValueError, match="count mismatch"):
        normalize({"ligand_positions": ["first", "second"], "position_confidence": [-1.0]})


def test_isolated_representation_remains_unchanged():
    result = {"poses": [{"sdf": "first", "confidence": -1.0}]}
    assert normalize(result) is result
