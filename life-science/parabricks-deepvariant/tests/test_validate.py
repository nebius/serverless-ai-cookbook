import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# qa/validate.py is not on the package path; import via file path.
QA_DIR = Path(__file__).resolve().parent.parent / "qa"
sys.path.insert(0, str(QA_DIR))
import validate  # noqa: E402


def _write_summary(path: Path, snp_f1: float, indel_f1: float):
    rows = [
        {"Type": "SNP", "Filter": "PASS", "METRIC.F1_Score": str(snp_f1),
         "METRIC.Recall": "0.99", "METRIC.Precision": "0.99"},
        {"Type": "INDEL", "Filter": "PASS", "METRIC.F1_Score": str(indel_f1),
         "METRIC.Recall": "0.95", "METRIC.Precision": "0.95"},
    ]
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_parse_happy_summary_extracts_pass_snp_f1(tmp_path):
    summary = tmp_path / "summary.csv"
    _write_summary(summary, snp_f1=0.9995, indel_f1=0.96)
    metrics = validate.parse_happy_summary(summary)
    assert metrics["snp_f1"] == pytest.approx(0.9995)
    assert metrics["indel_f1"] == pytest.approx(0.96)


def test_check_threshold_passes_above_min(monkeypatch):
    validate.check_threshold({"snp_f1": 0.9995}, min_snp_f1=0.999)


def test_check_threshold_raises_below_min():
    with pytest.raises(SystemExit) as exc:
        validate.check_threshold({"snp_f1": 0.99}, min_snp_f1=0.999)
    assert "0.99" in str(exc.value)


def test_run_validation_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "buck")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://endpoint")
    monkeypatch.setenv("S3_OUTPUT_PREFIX", "parabricks/out")
    monkeypatch.setenv("SAMPLE_ID", "HG002")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-north1")

    fake_client = MagicMock()
    happy_summary = tmp_path / "happy.summary.csv"
    _write_summary(happy_summary, snp_f1=0.9999, indel_f1=0.97)

    def fake_run(cmd, check=False, **_):
        # Simulate hap.py creating its summary at the prefix we passed.
        out_prefix = cmd[cmd.index("-o") + 1]
        Path(out_prefix + ".summary.csv").write_bytes(happy_summary.read_bytes())
        return MagicMock(returncode=0)

    fake_truth_dir = tmp_path / "truth"
    fake_truth_dir.mkdir()
    (fake_truth_dir / "truth.vcf.gz").write_text("")
    (fake_truth_dir / "truth.bed").write_text("")

    ref_fasta = tmp_path / "ref.fasta"
    ref_fasta.write_text("")

    with patch("validate.boto3.client", return_value=fake_client), \
         patch("validate.subprocess.run", side_effect=fake_run) as run_mock, \
         patch("validate.fetch_giab_truth", return_value=(fake_truth_dir / "truth.vcf.gz",
                                                         fake_truth_dir / "truth.bed")), \
         patch("validate.fetch_grch38_reference", return_value=ref_fasta):
        validate.run_validation(scratch=tmp_path, min_snp_f1=0.999)

    cmd = run_mock.call_args.args[0]
    assert cmd[cmd.index("-r") + 1] == str(ref_fasta)

    fake_client.download_file.assert_called_once_with(
        "buck",
        "parabricks/out/HG002/HG002.vcf",
        str(tmp_path / "HG002.vcf"),
    )


def test_run_validation_strips_trailing_output_prefix_slash(tmp_path, monkeypatch):
    monkeypatch.setenv("S3_BUCKET", "buck")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://endpoint")
    monkeypatch.setenv("S3_OUTPUT_PREFIX", "parabricks/out/")
    monkeypatch.setenv("SAMPLE_ID", "HG002")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-north1")

    fake_client = MagicMock()
    happy_summary = tmp_path / "happy.summary.csv"
    _write_summary(happy_summary, snp_f1=0.9999, indel_f1=0.97)

    def fake_run(cmd, check=False, **_):
        out_prefix = cmd[cmd.index("-o") + 1]
        Path(out_prefix + ".summary.csv").write_bytes(happy_summary.read_bytes())
        return MagicMock(returncode=0)

    truth_vcf = tmp_path / "truth.vcf.gz"
    truth_bed = tmp_path / "truth.bed"
    truth_vcf.write_text("")
    truth_bed.write_text("")

    ref_fasta = tmp_path / "ref.fasta"
    ref_fasta.write_text("")

    with patch("validate.boto3.client", return_value=fake_client), \
         patch("validate.subprocess.run", side_effect=fake_run), \
         patch("validate.fetch_giab_truth", return_value=(truth_vcf, truth_bed)), \
         patch("validate.fetch_grch38_reference", return_value=ref_fasta):
        validate.run_validation(scratch=tmp_path, min_snp_f1=0.999)

    fake_client.download_file.assert_called_once_with(
        "buck",
        "parabricks/out/HG002/HG002.vcf",
        str(tmp_path / "HG002.vcf"),
    )
