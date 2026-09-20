"""Cross-component check belongs to the workbench, not the portable skill."""
from pathlib import Path
import re
import runpy


def test_worker_static_public_copy_matches_recognized_python_outcome(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / 'skills/scientific-ai/clinical-documentation/scripts'))
    clinical = runpy.run_path(str(root / 'skills/scientific-ai/clinical-documentation/scripts/clinical_report.py'))
    source = (Path(__file__).parent / 'demos/worker.cjs').read_text()
    error = clinical['NoSupportedClinicalFacts']
    assert re.search(r"const NO_FACTS_CODE = '([^']+)';", source)[1] == error.code
    assert re.search(r"const NO_FACTS_DETAIL = '([^']+)';", source)[1] == error.detail
