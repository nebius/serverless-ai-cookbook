"""QA: compare customer's VCF to GIAB v4.2.1 truth using hap.py."""

import csv
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import boto3

GIAB_BASE = "https://ftp-trace.ncbi.nlm.nih.gov/ReferenceSamples/giab/release/AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38"
TRUTH_VCF_URL = f"{GIAB_BASE}/HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz"
TRUTH_TBI_URL = f"{TRUTH_VCF_URL}.tbi"
TRUTH_BED_URL = f"{GIAB_BASE}/HG002_GRCh38_1_22_v4.2.1_benchmark_noinconsistent.bed"


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        sys.exit(f"Missing required environment variable: {name}")
    return value


def fetch_giab_truth(scratch: Path) -> tuple[Path, Path]:
    truth_dir = scratch / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    vcf = truth_dir / "HG002_GRCh38_v4.2.1.vcf.gz"
    tbi = truth_dir / "HG002_GRCh38_v4.2.1.vcf.gz.tbi"
    bed = truth_dir / "HG002_GRCh38_v4.2.1.bed"
    for url, dest in [(TRUTH_VCF_URL, vcf), (TRUTH_TBI_URL, tbi), (TRUTH_BED_URL, bed)]:
        if not dest.exists():
            urllib.request.urlretrieve(url, dest)  # noqa: S310 (URL is constant, not user input)
    return vcf, bed


def parse_happy_summary(summary_csv: Path) -> dict:
    metrics: dict[str, float] = {}
    with summary_csv.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("Filter") != "PASS":
                continue
            type_ = row.get("Type", "").upper()
            f1 = float(row.get("METRIC.F1_Score", "nan"))
            if type_ == "SNP":
                metrics["snp_f1"] = f1
            elif type_ == "INDEL":
                metrics["indel_f1"] = f1
    return metrics


def check_threshold(metrics: dict, min_snp_f1: float) -> None:
    snp = metrics.get("snp_f1")
    if snp is None or snp < min_snp_f1:
        sys.exit(f"FAIL: SNP F1 {snp} below threshold {min_snp_f1}")


def run_validation(scratch: Path, min_snp_f1: float = 0.999) -> None:
    scratch = Path(scratch)
    bucket = _required_env("S3_BUCKET")
    sample_id = _required_env("SAMPLE_ID")
    out_prefix = _required_env("S3_OUTPUT_PREFIX")
    endpoint = _required_env("S3_ENDPOINT_URL")
    region = _required_env("AWS_DEFAULT_REGION")

    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_required_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("AWS_SECRET_ACCESS_KEY"),
        region_name=region,
    )
    query_vcf = scratch / f"{sample_id}.vcf"
    s3.download_file(bucket, f"{out_prefix}/{sample_id}/{sample_id}.vcf", str(query_vcf))

    truth_vcf, truth_bed = fetch_giab_truth(scratch)

    out_dir = scratch / "happy"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_prefix_local = str(out_dir / "happy")

    cmd = [
        "hap.py", str(truth_vcf), str(query_vcf),
        "-f", str(truth_bed),
        "-o", out_prefix_local,
        "--engine=vcfeval",
    ]
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        sys.exit(f"hap.py exited {completed.returncode}")

    metrics = parse_happy_summary(Path(f"{out_prefix_local}.summary.csv"))
    print(f"Metrics: {metrics}")
    check_threshold(metrics, min_snp_f1=min_snp_f1)
    print("PASS")


def main() -> None:
    run_validation(scratch=Path(os.environ.get("SCRATCH_DIR", "/scratch")))


if __name__ == "__main__":
    main()
