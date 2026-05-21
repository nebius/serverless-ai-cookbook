import json
import os
import re
import subprocess
import sys
import time
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


def _normalize_bwa_index(ref_fasta: Path) -> None:
    # Broad publishes the BWA index with a `.64.` infix
    # (`<fasta>.64.{amb,ann,bwt,pac,sa}`), but pbrun fq2bam looks for the
    # canonical `<fasta>.{amb,ann,bwt,pac,sa}`. Symlink the canonical names
    # to the `.64.` files when only the `.64.` variant is present.
    for ext in ("amb", "ann", "bwt", "pac", "sa"):
        canonical = ref_fasta.with_name(f"{ref_fasta.name}.{ext}")
        broad = ref_fasta.with_name(f"{ref_fasta.name}.64.{ext}")
        if not canonical.exists() and broad.exists():
            canonical.symlink_to(broad.name)


def _capture_stdout(cmd: list[str]) -> str:
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return completed.stdout or ""


def _parse_pbrun_version(stdout: str) -> str:
    match = re.search(
        r"(?:Parabricks Version|pbrun)[:\s]+([0-9][^\s]+)",
        stdout,
        flags=re.IGNORECASE,
    )
    return match.group(1) if match else "unknown"


def emit_metadata(dest: Path, wall_clock_seconds: float, sample_id: str) -> None:
    gpu_stdout = _capture_stdout(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    pbrun_stdout = _capture_stdout(["pbrun", "--version"])
    payload = {
        "sample_id": sample_id,
        "wall_clock_seconds": wall_clock_seconds,
        "gpu_name": gpu_stdout.strip().splitlines()[0] if gpu_stdout.strip() else "unknown",
        "parabricks_version": _parse_pbrun_version(pbrun_stdout),
    }
    Path(dest).write_text(json.dumps(payload, indent=2))


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
    _normalize_bwa_index(ref_fasta)
    # Match common paired-FASTQ naming conventions:
    #   *.R1.fq.gz / *_R1.fq.gz / *.R1.fastq.gz   (Illumina-style, dot or underscore)
    #   *_1.fq.gz / *_1.fastq.gz                   (NVIDIA tutorial sample_1.fq.gz)
    fq_files = (
        sorted(in_dir.rglob("*[._]R[12].f*q.gz"))
        or sorted(in_dir.rglob("*_[12].f*q.gz"))
    )
    if len(fq_files) < 2:
        listing = sorted(p.name for p in in_dir.rglob("*") if p.is_file())
        raise FileNotFoundError(
            f"Expected paired FASTQ under {in_dir}; found {fq_files}. "
            f"Directory contents: {listing}"
        )
    fq_pair = (fq_files[0], fq_files[1])

    out_vcf = out_dir / f"{sample_id}.vcf"
    out_bam = out_dir / f"{sample_id}.bam"

    cmd = build_pbrun_command(ref_fasta, fq_pair, out_vcf, out_bam)
    started = time.monotonic()
    completed = subprocess.run(cmd, check=False)
    elapsed = time.monotonic() - started
    if completed.returncode != 0:
        sys.exit(completed.returncode)

    emit_metadata(out_dir / "run_metadata.json", wall_clock_seconds=elapsed, sample_id=sample_id)

    stage.upload_prefix(
        client,
        out_dir,
        bucket,
        f"{os.environ['S3_OUTPUT_PREFIX'].rstrip('/')}/{sample_id}",
    )
