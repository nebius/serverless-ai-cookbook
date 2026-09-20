"""Integration checks on the prepared bundle, with actual caller-shaped inputs.

Run using clawbio-venv plus pytest. No hosted model, tenant or API key is used.
"""

import csv
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys

import pytest
import yaml

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SCIENTIFIC_CLAWBIO_ROOT", HERE.parent / "vendor/clawbio"))
RUNNER = Path(os.environ.get("SCIENTIFIC_CLAWBIO_RUNNER", HERE / "runner.py"))
SKILLS = Path(os.environ.get("SCIENTIFIC_CLAWBIO_SKILLS", ROOT / "skills"))
MANIFEST = json.loads((ROOT / "manifest.json").read_text())
ENV = {**os.environ, "SCIENTIFIC_CLAWBIO_ROOT": str(ROOT.resolve()),
       "MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}


def call(*args):
    return subprocess.run([sys.executable, str(RUNNER), *map(str, args)],
                          env=ENV, text=True, capture_output=True, timeout=120)


def require_success(result):
    assert result.returncode == 0, result.stdout + result.stderr


def test_selection_covers_pinned_catalog_without_overlap():
    selection = json.loads((HERE / "selection.json").read_text())
    records = json.loads((ROOT / "source/skills/catalog.json").read_text())["skills"]
    groups = [set(selection[key]) for key in ("local", "platform", "excluded")]
    assert sum(map(len, groups)) == len(set.union(*groups)) == len(records)
    assert set.union(*groups) == {record["name"] for record in records}
    assert set(MANIFEST["skills"]) == groups[0] | groups[1]


def test_source_hashes_and_no_bot_or_environment_files():
    for relative, expected in MANIFEST["files"].items():
        path = ROOT / "source" / relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative
        assert not any(part.startswith(".") or part in {"bot", "bots"} for part in Path(relative).parts)


def test_recorded_integration_hashes_match_current_code():
    for name, expected in MANIFEST.get("integration_sha256", {}).items():
        assert hashlib.sha256((RUNNER.parent / name).read_bytes()).hexdigest() == expected
    if "qualification_sha256" in MANIFEST:
        assert hashlib.sha256((ROOT / "qualification.json").read_bytes()).hexdigest() == MANIFEST["qualification_sha256"]


@pytest.mark.parametrize("name", sorted(MANIFEST["skills"]))
def test_skill_discoverable_and_reference_preserved(name):
    path = SKILLS / f"clawbio-{name}"
    text = (path / "SKILL.md").read_text()
    metadata = yaml.safe_load(text.split("---", 2)[1])
    assert metadata["name"] == f"clawbio-{name}"
    assert 0 < len(metadata["description"]) <= 1024
    assert metadata["license"] in {"MIT", "Apache-2.0"}
    assert (path / "references/upstream.md").read_bytes() == (ROOT / f"source/skills/{name}/SKILL.md").read_bytes()
    result = call("describe", name)
    require_success(result)
    assert json.loads(result.stdout)["revision"] == MANIFEST["revision"]


@pytest.mark.parametrize("name", [name for name, spec in MANIFEST["skills"].items() if spec["mode"] == "platform"])
def test_hosted_workflow_cannot_silently_run_locally(name, tmp_path):
    result = call("run", name, "--", "--demo", "--output", tmp_path / name)
    assert result.returncode != 0 and "hosted App" in result.stderr
    assert not (tmp_path / name).exists()


def test_output_is_not_overwritten_and_unknown_skill_is_rejected(tmp_path):
    saved = tmp_path / "saved.txt"
    saved.write_text("retained")
    for output in (tmp_path, saved, Path("relative-path")):
        result = call("run", "analyze-fasta", "--", "--demo", "--output", output)
        assert result.returncode != 0
    assert saved.read_text() == "retained"
    assert call("help", "not-installed").returncode != 0
    assert call("run", "analyze-fasta", "--", "--output", tmp_path / "a", "--output", tmp_path).returncode != 0


def test_fasta_real_input_and_invalid_input(tmp_path):
    source = tmp_path / "sequences.fa"
    source.write_text(">balanced\nACGTACGTACGT\n>gc_only\nGGCCGGCCGGCC\n")
    output = tmp_path / "fasta"
    require_success(call("run", "analyze-fasta", "--", "--input", source, "--output", output))
    result = json.loads((output / "result.json").read_text())
    assert result["total_sequences"] == 2
    assert result["summary"]["total_residues"] == 24
    sequences = {row["id"]: row for row in result["sequences"]}
    assert sequences["balanced"]["gc_content"] == 50
    assert sequences["gc_only"]["gc_content"] == 100
    assert sequences["gc_only"]["length_bp"] == 12
    assert (output / "reproducibility/checksums.sha256").stat().st_size > 0
    assert call("run", "analyze-fasta", "--", "--input", tmp_path / "missing.fa", "--output", tmp_path / "bad").returncode != 0


def test_abf_matches_independent_wakefield_calculation(tmp_path):
    source = tmp_path / "summary.tsv"
    source.write_text("rsid\tz\tse\tchr\tpos\nrsA\t1\t0.1\t1\t100\nrsB\t5\t0.1\t1\t200\nrsC\t2\t0.1\t1\t300\n")
    output = tmp_path / "abf"
    require_success(call("run", "fine-mapping", "--", "--sumstats", source, "--no-figures", "--output", output))
    result = json.loads((output / "fine_mapping.json").read_text())
    assert result["method"] == "ABF" and result["lead_rsid"] == "rsB"
    values = [math.sqrt(.01 / .05) * math.exp(.5 * z * z * .04 / .05) for z in (1, 5, 2)]
    with (output / "tables/pips.tsv").open() as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    expected = dict(zip(("rsA", "rsB", "rsC"), (v / sum(values) for v in values)))
    assert sum(float(row["pip"]) for row in rows) == pytest.approx(1, abs=1e-6)
    for row in rows:
        assert float(row["pip"]) == pytest.approx(expected[row["rsid"]], rel=1e-5)
    result = call("run", "fine-mapping", "--", "--sumstats", source, "--ld=missing.npy", "--output", tmp_path / "susie")
    assert result.returncode != 0 and "SuSiE is not installed" in result.stderr


def test_rnaseq_known_up_and_down_regulation(tmp_path):
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(420)
    samples = [f"sample-{i}" for i in range(12)]
    means = np.full((100, 12), 100.)
    means[:10, 6:] = 800
    means[10:20, 6:] = 12
    counts = rng.poisson(means)
    counts_path, metadata_path = tmp_path / "counts.csv", tmp_path / "metadata.csv"
    pd.DataFrame(counts, index=[f"gene-{i}" for i in range(100)], columns=samples).to_csv(counts_path)
    pd.DataFrame({"sample_id": samples, "condition": ["control"] * 6 + ["treated"] * 6}).to_csv(metadata_path, index=False)
    output = tmp_path / "rnaseq"
    require_success(call("run", "rnaseq-de", "--", "--counts", counts_path, "--metadata", metadata_path,
                         "--formula", "~condition", "--contrast", "condition,treated,control", "--output", output))
    results = pd.read_csv(output / "tables/de_results.csv", index_col=0)
    assert len(results) == 100
    for i in range(20):
        row = results.loc[f"gene-{i}"]
        assert row["padj"] < .01
        assert row["log2FoldChange"] > 1 if i < 10 else row["log2FoldChange"] < -1


def test_command_mcp_uses_real_runner_and_retained_job(tmp_path):
    script = Path(os.environ.get("SCIENTIFIC_EXECUTION_SCRIPT", HERE.parent / "execution-mcp.py"))
    source = tmp_path / "input.fa"
    source.write_text(">input\nACGTACGTACGT\n")
    output = tmp_path / "output"
    command = shlex.join([sys.executable, str(RUNNER), "run", "analyze-fasta", "--",
                          "--input", str(source), "--output", str(output)])
    environment = {**ENV, "SCIENTIFIC_EXECUTION_DIR": str(tmp_path / "jobs"),
                   "SCIENTIFIC_WORKSPACE": str(tmp_path)}

    def mcp(name, arguments):
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                   "params": {"name": name, "arguments": arguments}}
        response = subprocess.run([sys.executable, str(script)], input=json.dumps(request) + "\n",
                                  env=environment, text=True, capture_output=True, timeout=35, check=True)
        return json.loads(json.loads(response.stdout)["result"]["content"][0]["text"])

    job = mcp("execute_command", {"command": command, "wait_seconds": 0})
    for _ in range(4):
        state = mcp("read_execution", {"job_id": job["job_id"], "wait_seconds": 30})
        if state["status"] not in {"running", "starting"}:
            break
    assert state["status"] == "completed", state
    assert len(list((tmp_path / "jobs").glob("*/request.json"))) == 1
    assert json.loads((output / "result.json").read_text())["sequences"][0]["length_bp"] == 12


@pytest.mark.parametrize("downloaded", [True, False])
def test_article_adapter_passes_explicit_headless_arguments(monkeypatch, tmp_path, downloaded):
    spec = importlib.util.spec_from_file_location("adapters", HERE / "adapters.py")
    adapters = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapters)
    captured = {}

    def load_module(module):
        def run(**kwargs):
            captured.update(kwargs)
            (tmp_path / "data.tsv").write_text("downloaded fixture")
            (tmp_path / "manifest.json").write_text(json.dumps({"files": [{
                "filename": "data.tsv.gz", "local_path": str(tmp_path / "data.tsv.gz"), "downloaded": downloaded}]}))
        module.run = run

    fake_spec = type("Spec", (), {"loader": type("Loader", (), {"exec_module": staticmethod(load_module)})()})()
    monkeypatch.setattr(adapters.importlib.util, "spec_from_file_location", lambda *args: fake_spec)
    monkeypatch.setattr(adapters.importlib.util, "module_from_spec", lambda spec: type("Module", (), {})())
    monkeypatch.setattr(sys, "argv", ["adapters.py", "article-data-fetcher", "--id", "GSE123", "--types", "tsv,csv", "--output", str(tmp_path)])
    if downloaded:
        adapters.main()
        item = json.loads((tmp_path / "manifest.json").read_text())["files"][0]
        assert item["local_path"] == str(tmp_path / "data.tsv")
        assert item["sha256"] == hashlib.sha256(b"downloaded fixture").hexdigest()
    else:
        with pytest.raises(SystemExit) as error:
            adapters.main()
        assert error.value.code == 1
    assert captured["non_interactive"] is True
    assert captured["file_types"] == {"tsv", "csv"}
    assert captured["identifier"] == "GSE123"
