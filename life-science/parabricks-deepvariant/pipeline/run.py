import os
import subprocess
import sys
from pathlib import Path

from pipeline import stage


def build_pbrun_command(
    ref_fasta: Path,
    in_fq_pair: tuple[Path, Path],
    out_vcf: Path,
    out_bam: Path,
) -> list[str]:
    return [
        "pbrun",
        "germline",
        "--ref", str(ref_fasta),
        "--in-fq", str(in_fq_pair[0]), str(in_fq_pair[1]),
        "--out-variants", str(out_vcf),
        "--out-bam", str(out_bam),
    ]


def _first_match(directory: Path, glob: str) -> Path:
    matches = sorted(directory.rglob(glob))
    if not matches:
        raise FileNotFoundError(f"No file matching {glob} under {directory}")
    return matches[0]


def run_germline(scratch: Path) -> None:
    scratch = Path(scratch)
    ref_dir = scratch / "ref"
    in_dir = scratch / "in"
    out_dir = scratch / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    bucket = os.environ["S3_BUCKET"]
    sample_id = os.environ["SAMPLE_ID"]

    client = stage.make_client()
    stage.download_prefix(client, bucket, os.environ["S3_REF_PREFIX"], ref_dir)
    stage.download_prefix(client, bucket, os.environ["S3_INPUT_PREFIX"], in_dir)

    ref_fasta = _first_match(ref_dir, "*.fasta")
    fq_files = sorted(in_dir.rglob("*_R[12].fq.gz")) or sorted(in_dir.rglob("*_[12].fq.gz"))
    if len(fq_files) < 2:
        raise FileNotFoundError(f"Expected paired FASTQ under {in_dir}, found {fq_files}")
    fq_pair = (fq_files[0], fq_files[1])

    out_vcf = out_dir / f"{sample_id}.vcf"
    out_bam = out_dir / f"{sample_id}.bam"

    cmd = build_pbrun_command(ref_fasta, fq_pair, out_vcf, out_bam)
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        sys.exit(completed.returncode)

    stage.upload_prefix(client, out_dir, bucket, f"{os.environ['S3_OUTPUT_PREFIX']}/{sample_id}")
