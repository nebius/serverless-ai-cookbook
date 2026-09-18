from __future__ import annotations

from pathlib import Path

import pytest

from app import VinaAdapter, finite_vector


def test_finite_vector_rejects_invalid_box() -> None:
    with pytest.raises(ValueError, match="three-number"):
        finite_vector({"size": [1, 2]}, "size", [20, 20, 20], 1, 60)
    with pytest.raises(ValueError, match="between"):
        finite_vector({"size": [20, 20, 100]}, "size", [20, 20, 20], 1, 60)


def test_custom_structure_requires_explicit_box(tmp_path: Path) -> None:
    adapter = VinaAdapter()
    adapter.vina_class = object
    with pytest.raises(ValueError, match="explicit center and size"):
        adapter.run({"ligand_pdbqt": "ROOT\\nATOM"}, tmp_path)


def test_capabilities_distinguish_vina_from_autodock_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.importlib.metadata.version", lambda _name: "1.2.7")
    capabilities = VinaAdapter().capabilities()
    assert capabilities["accelerator"]["kind"] == "CPU"
    assert capabilities["engine"]["scoring_semantics"] == "vina"
    assert "not interchangeable" in capabilities["disclaimer"]
