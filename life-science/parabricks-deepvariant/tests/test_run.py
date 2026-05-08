import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from pipeline import run


def test_build_pbrun_command_uses_local_paths():
    cmd = run.build_pbrun_command(
        ref_fasta=Path("/scratch/ref/Homo_sapiens_assembly38.fasta"),
        in_fq_pair=(Path("/scratch/in/HG002_R1.fq.gz"), Path("/scratch/in/HG002_R2.fq.gz")),
        out_vcf=Path("/scratch/out/HG002.vcf"),
        out_bam=Path("/scratch/out/HG002.bam"),
    )
    # Defensive checks on command shape
    assert cmd[0] == "pbrun"
    assert "germline" in cmd
    assert "--ref" in cmd and str(Path("/scratch/ref/Homo_sapiens_assembly38.fasta")) in cmd
    assert "--in-fq" in cmd
    fq_idx = cmd.index("--in-fq")
    # in-fq takes both pair members as space-separated args (Parabricks convention)
    assert cmd[fq_idx + 1].endswith("HG002_R1.fq.gz")
    assert cmd[fq_idx + 2].endswith("HG002_R2.fq.gz")
    assert "--out-variants" in cmd and str(Path("/scratch/out/HG002.vcf")) in cmd
    assert "--out-bam" in cmd and str(Path("/scratch/out/HG002.bam")) in cmd


def test_run_germline_orders_stage_in_pbrun_and_stage_out(tmp_path, s3_env):
    calls = []

    def fake_download_prefix(client, bucket, prefix, dest):
        calls.append(("download_prefix", prefix, str(dest)))
        Path(dest).mkdir(parents=True, exist_ok=True)
        # synthesize files the runner expects to find
        if "ref" in prefix:
            (Path(dest) / "Homo_sapiens_assembly38.fasta").write_text("")
        else:
            (Path(dest) / "HG002_R1.fq.gz").write_text("")
            (Path(dest) / "HG002_R2.fq.gz").write_text("")

    def fake_upload_prefix(client, src, bucket, prefix):
        calls.append(("upload_prefix", str(src), prefix))

    def fake_subproc(cmd, capture_output=False, text=False, check=False):
        # pbrun germline (no --version) is the variant call; metadata helpers
        # also go through subprocess.run, so return string stdout for them.
        if cmd[0] == "pbrun" and "--version" not in cmd:
            return MagicMock(returncode=0, stdout="")
        if cmd[0] == "nvidia-smi":
            return MagicMock(returncode=0, stdout="NVIDIA H200\n")
        if cmd[0] == "pbrun" and "--version" in cmd:
            return MagicMock(returncode=0, stdout="Parabricks Version: 4.7.0-1\n")
        return MagicMock(returncode=0, stdout="")

    with patch("pipeline.run.stage.make_client", return_value=MagicMock()), \
         patch("pipeline.run.stage.download_prefix", side_effect=fake_download_prefix), \
         patch("pipeline.run.stage.upload_prefix", side_effect=fake_upload_prefix), \
         patch("pipeline.run.subprocess.run", side_effect=fake_subproc) as mock_run:
        run.run_germline(scratch=tmp_path)

    # Three S3 ops in order: download ref, download fq, upload outputs
    op_names = [c[0] for c in calls]
    assert op_names == ["download_prefix", "download_prefix", "upload_prefix"]
    # pbrun germline was invoked exactly once (separate from metadata helpers)
    pbrun_germline_calls = [
        c for c in mock_run.call_args_list
        if c.args[0][0] == "pbrun" and "--version" not in c.args[0]
    ]
    assert len(pbrun_germline_calls) == 1
    assert pbrun_germline_calls[0].args[0][0] == "pbrun"


def test_run_germline_raises_on_pbrun_nonzero(tmp_path, s3_env):
    def fake_download_prefix(client, bucket, prefix, dest):
        Path(dest).mkdir(parents=True, exist_ok=True)
        if "ref" in prefix:
            (Path(dest) / "Homo_sapiens_assembly38.fasta").write_text("")
        else:
            (Path(dest) / "HG002_R1.fq.gz").write_text("")
            (Path(dest) / "HG002_R2.fq.gz").write_text("")

    failed = MagicMock(returncode=1)
    with patch("pipeline.run.stage.make_client", return_value=MagicMock()), \
         patch("pipeline.run.stage.download_prefix", side_effect=fake_download_prefix), \
         patch("pipeline.run.stage.upload_prefix"), \
         patch("pipeline.run.subprocess.run", return_value=failed):
        with pytest.raises(SystemExit) as exc:
            run.run_germline(scratch=tmp_path)
    assert exc.value.code == 1


def test_emit_metadata_writes_expected_fields(tmp_path):
    nvidia_smi_stdout = "NVIDIA H200\n"
    pbrun_version_stdout = "Parabricks Version: 4.7.0-1\n"

    def fake_subproc(cmd, capture_output=False, text=False, check=False):
        if cmd[0] == "nvidia-smi":
            return MagicMock(stdout=nvidia_smi_stdout, returncode=0)
        if cmd[0] == "pbrun" and "--version" in cmd:
            return MagicMock(stdout=pbrun_version_stdout, returncode=0)
        return MagicMock(stdout="", returncode=0)

    out = tmp_path / "run_metadata.json"
    with patch("pipeline.run.subprocess.run", side_effect=fake_subproc):
        run.emit_metadata(out, wall_clock_seconds=123.4, sample_id="HG002")

    payload = json.loads(out.read_text())
    assert payload["sample_id"] == "HG002"
    assert payload["wall_clock_seconds"] == pytest.approx(123.4)
    assert payload["gpu_name"] == "NVIDIA H200"
    assert payload["parabricks_version"] == "4.7.0-1"
