import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from server import BioIRRuntime, FoldRequest


def test_query_only_msa_has_real_newlines(monkeypatch):
    runtime = BioIRRuntime()
    captured = {}

    def make_request(request_id, sequence, msa):
        captured.update(sequence=sequence, msa=msa)
        return {}

    monkeypatch.setattr(runtime, "_make_request", make_request)
    monkeypatch.setattr(runtime, "_run", lambda *_: ("data_test\n", {"ptm": 0.5}, 1.0))
    try:
        result = runtime.predict(FoldRequest(sequence="ACDE"), "test")
        assert captured["msa"].splitlines() == [">query", "ACDE"]
        assert result.cif.startswith("data_")
    finally:
        runtime.close()
