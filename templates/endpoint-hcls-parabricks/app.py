from __future__ import annotations

import gzip
import hashlib
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from hcls_api import create_app
from hcls_api.oci_runtime import run_in_runtime


GPU_COUNT = max(1, min(int(os.environ.get("PARABRICKS_GPU_COUNT", "2")), 8))
INPUT_ROOT = Path(os.environ.get("HCLS_PARABRICKS_INPUT_ROOT", "/data/hcls/parabricks/fixtures")).resolve()
MAX_INPUT_BYTES = max(1, min(int(os.environ.get("HCLS_MAX_INPUT_GIB", "100")), 1000)) * 1024**3
MAX_INTERVALS = 32
GOOGLE_CHR20_BAM_SHA256 = "0b82858821bd8817df03b35f90cdfcb2bae53af5ab46e61b8bcff1ad9ba49643"
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SAFE_SAMPLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SAFE_INTERVAL = re.compile(r"^[A-Za-z0-9_.:+-]{1,160}$")


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validate_https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


HTTPS_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), SafeRedirectHandler())


def validate_https_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("remote input URLs must use HTTPS")
    if parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError("remote input URLs cannot contain credentials or non-HTTPS ports")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("remote input hostname could not be resolved") from exc
    if not addresses:
        raise ValueError("remote input hostname did not resolve")
    for address in addresses:
        resolved = ipaddress.ip_address(address[4][0])
        if not resolved.is_global:
            raise ValueError("remote input URL resolved to a non-public address")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, expected_sha256: str | None) -> str:
    validate_https_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "nebius-hcls-parabricks/1.0"})
    digest = hashlib.sha256()
    total = 0
    try:
        with HTTPS_OPENER.open(request, timeout=60) as response, destination.open("xb") as output:
            validate_https_url(response.geturl())
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_INPUT_BYTES:
                raise ValueError("remote input exceeds the configured size limit")
            while chunk := response.read(8 * 1024 * 1024):
                total += len(chunk)
                if total > MAX_INPUT_BYTES:
                    raise ValueError("remote input exceeds the configured size limit")
                digest.update(chunk)
                output.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError):
        destination.unlink(missing_ok=True)
        raise ValueError("remote input could not be downloaded") from None
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    actual = digest.hexdigest()
    if expected_sha256 and not secrets_compare(actual, expected_sha256.lower()):
        destination.unlink(missing_ok=True)
        raise ValueError("remote input checksum mismatch")
    return actual


def secrets_compare(left: str, right: str) -> bool:
    import hmac

    return hmac.compare_digest(left, right)


def gpu_names() -> list[str]:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi is None:
        return []
    try:
        completed = subprocess.run(
            [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()] if completed.returncode == 0 else []


def normalize_google_chr20_bam(
    reads: Path,
    work_dir: Path,
    *,
    rootfs: Path,
    samtools: str,
    image_environment: dict[str, str],
) -> tuple[Path, Path]:
    """Remove empty non-chr20 dictionary entries from Google's bounded demo BAM.

    Parabricks requires every BAM dictionary contig to exist in the supplied
    reference, while Google's official chr20 quickstart BAM retains empty
    whole-genome dictionary entries. The input is selected by immutable SHA-256;
    arbitrary customer BAMs are never rewritten.
    """
    filtered_sam = work_dir / "google-chr20.filtered.sam"
    normalized_bam = work_dir / "google-chr20.parabricks.bam"
    normalized_bai = work_dir / "google-chr20.parabricks.bam.bai"
    view = run_in_runtime(
        rootfs=rootfs,
        guest_command=samtools,
        args=["view", "-h", str(reads)],
        cwd=work_dir,
        image_environment=image_environment,
        timeout=120,
    )
    with filtered_sam.open("x", encoding="utf-8") as output:
        for line in view.stdout.splitlines(keepends=True):
            if line.startswith("@SQ\t") and "\tSN:chr20\t" not in line:
                continue
            output.write(line)
    if view.returncode != 0:
        filtered_sam.unlink(missing_ok=True)
        raise RuntimeError(f"samtools could not read the guided BAM: {view.stderr[-500:]}")
    converted = run_in_runtime(
        rootfs=rootfs,
        guest_command=samtools,
        args=["view", "-b", "-o", str(normalized_bam), str(filtered_sam)],
        cwd=work_dir,
        image_environment=image_environment,
        timeout=120,
    )
    filtered_sam.unlink(missing_ok=True)
    if converted.returncode != 0:
        raise RuntimeError(f"samtools could not normalize the guided BAM: {converted.stderr[-500:]}")
    indexed = run_in_runtime(
        rootfs=rootfs,
        guest_command=samtools,
        args=["index", str(normalized_bam), str(normalized_bai)],
        cwd=work_dir,
        image_environment=image_environment,
        timeout=120,
    )
    if indexed.returncode != 0:
        raise RuntimeError(f"samtools could not index the guided BAM: {indexed.stderr[-500:]}")
    return normalized_bam, normalized_bai


class ParabricksAdapter:
    service_id = "parabricks-deepvariant"

    def __init__(self) -> None:
        self.rootfs = Path("/")
        self.pbrun = ""
        self.samtools = ""
        self.image_environment: dict[str, str] = {}
        self.runtime: dict[str, Any] = {}
        self.timeout_seconds = max(300, min(int(os.environ.get("HCLS_ENGINE_TIMEOUT_SECONDS", "14400")), 86400))

    def load(self) -> None:
        spec_path = os.environ.get("PARABRICKS_RUNTIME_SPEC")
        metadata_path = os.environ.get("PARABRICKS_RUNTIME_METADATA")
        if not spec_path or not metadata_path:
            raise RuntimeError("Parabricks runtime selection is unavailable")
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        self.runtime = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
        self.rootfs = Path(spec["rootfs"])
        self.pbrun = str(spec["guest_command"])
        self.samtools = str(spec["guest_samtools"])
        self.image_environment = dict(spec["image_environment"])
        if not self.pbrun.startswith("/") or not self.samtools.startswith("/"):
            raise RuntimeError("Parabricks runtime command is invalid")
        INPUT_ROOT.mkdir(parents=True, exist_ok=True)

    def health(self) -> dict[str, Any]:
        names = gpu_names()
        return {
            "ready": bool(self.pbrun) and len(names) >= GPU_COUNT and os.access(INPUT_ROOT, os.R_OK),
            "engine": "NVIDIA Parabricks DeepVariant",
            "engine_version": self.runtime.get("actual_engine_version", "unknown"),
            "gpu_count_required": GPU_COUNT,
            "gpus": names,
            "input_root_readable": os.access(INPUT_ROOT, os.R_OK),
            "runtime": self.runtime,
        }

    def capabilities(self) -> dict[str, Any]:
        fixture_base = "https://storage.googleapis.com/deepvariant/quickstart-testdata"
        fixture = lambda filename, sha256: {
            "filename": filename,
            "url": f"{fixture_base}/{filename}",
            "sha256": sha256,
        }
        return {
            "workload": "germline_variant_calling",
            "engine": {
                "name": "NVIDIA Parabricks DeepVariant",
                "version": self.runtime.get("actual_engine_version", "unknown"),
            },
            "runtime": self.runtime,
            "accelerator": {"required": True, "kind": "NVIDIA CUDA", "count": GPU_COUNT},
            "examples": [
                {
                    "id": "deepvariant-chr20-smoke",
                    "label": "DeepVariant chr20 bounded smoke",
                    "input": {
                        "sample_id": "NA12878-smoke",
                        "reference": fixture("ucsc.hg19.chr20.unittest.fasta", "b532f011328adfbc7cf92e37923d6035f251b78ff52e1d570dfa10697cca7fe5"),
                        "reference_index": fixture("ucsc.hg19.chr20.unittest.fasta.fai", "3cc62926bafa8f397679927070c40e970a414bb21fdb92c46dfb497a7a955032"),
                        "reads": fixture("NA12878_S1.chr20.10_10p1mb.bam", "0b82858821bd8817df03b35f90cdfcb2bae53af5ab46e61b8bcff1ad9ba49643"),
                        "reads_index": fixture("NA12878_S1.chr20.10_10p1mb.bam.bai", "5ce54eede47a7ae2440a877f812fc6c7f101e67d4e84d8d279778aa6165b4d67"),
                        "intervals": ["chr20:10000000-10010000"],
                        "mode": "shortread",
                    },
                }
            ],
            "accepted_inputs": ["mounted_fixture_path", "public_https_url_with_sha256"],
            "limits": {"input_gib": MAX_INPUT_BYTES // 1024**3, "intervals": MAX_INTERVALS},
            "metrics": ["variant_records", "wall_clock_seconds"],
            "disclaimer": "Research use only. Variant calls require independent validation and are not diagnostic results.",
        }

    def source(self, raw: Any, role: str, destination_dir: Path) -> tuple[Path, str]:
        if not isinstance(raw, dict):
            raise ValueError(f"{role} must be an object")
        filename = str(raw.get("filename", ""))
        if not SAFE_NAME.fullmatch(filename) or ".." in filename:
            raise ValueError(f"{role}.filename must be a safe basename")
        path_value = raw.get("path")
        url_value = raw.get("url")
        if (path_value is None) == (url_value is None):
            raise ValueError(f"{role} requires exactly one of path or url")
        expected = raw.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
            raise ValueError(f"{role}.sha256 is required")
        destination = destination_dir / filename
        if path_value is not None:
            if not isinstance(path_value, str) or not SAFE_NAME.fullmatch(path_value) or ".." in path_value:
                raise ValueError(f"{role}.path must be a fixture basename")
            source = (INPUT_ROOT / path_value).resolve()
            if source.parent != INPUT_ROOT or not source.is_file():
                raise ValueError(f"mounted fixture not found for {role}")
            shutil.copyfile(source, destination)
            actual = sha256_file(destination)
            if not secrets_compare(actual, expected.lower()):
                destination.unlink(missing_ok=True)
                raise ValueError(f"mounted fixture checksum mismatch for {role}")
            return destination, actual
        return destination, download(str(url_value), destination, expected)

    def run(self, payload: dict[str, Any], work_dir: Path) -> dict[str, Any]:
        names = gpu_names()
        if len(names) < GPU_COUNT:
            raise RuntimeError(f"Parabricks requires {GPU_COUNT} visible NVIDIA GPU(s)")
        sample_id = str(payload.get("sample_id", ""))
        if not SAFE_SAMPLE.fullmatch(sample_id):
            raise ValueError("sample_id contains unsupported characters")
        mode = str(payload.get("mode", "shortread"))
        if mode not in {"shortread", "pacbio", "ont"}:
            raise ValueError("mode must be shortread, pacbio, or ont")
        use_wes_model = bool(payload.get("use_wes_model", False))
        if use_wes_model and mode != "shortread":
            raise ValueError("use_wes_model is only valid in shortread mode")
        intervals = payload.get("intervals", [])
        if not isinstance(intervals, list) or len(intervals) > MAX_INTERVALS:
            raise ValueError(f"intervals must contain at most {MAX_INTERVALS} values")
        if any(not isinstance(value, str) or not SAFE_INTERVAL.fullmatch(value) for value in intervals):
            raise ValueError("interval contains unsupported characters")

        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        temporary_dir = work_dir / "tmp"
        for directory in (input_dir, output_dir, temporary_dir):
            directory.mkdir(parents=True, exist_ok=False)
        inputs: dict[str, Path] = {}
        input_digests: dict[str, str] = {}
        input_records: list[dict[str, Any]] = []
        for role in ("reference", "reference_index", "reads", "reads_index"):
            path, digest = self.source(payload.get(role), role, input_dir)
            inputs[role] = path
            input_digests[role] = digest
            input_records.append({"role": role, "filename": path.name, "sha256": digest, "bytes": path.stat().st_size})

        guided_bam_normalized = input_digests["reads"] == GOOGLE_CHR20_BAM_SHA256
        if guided_bam_normalized:
            inputs["reads"], inputs["reads_index"] = normalize_google_chr20_bam(
                inputs["reads"],
                input_dir,
                rootfs=self.rootfs,
                samtools=self.samtools,
                image_environment=self.image_environment,
            )

        out_variants = output_dir / f"{sample_id}.deepvariant.vcf.gz"
        command = [
            self.pbrun,
            "deepvariant",
            "--ref",
            str(inputs["reference"]),
            "--in-bam",
            str(inputs["reads"]),
            "--out-variants",
            str(out_variants),
            "--num-gpus",
            str(GPU_COUNT),
            "--tmp-dir",
            str(temporary_dir),
        ]
        if mode != "shortread":
            command.extend(["--mode", mode])
        if use_wes_model:
            command.append("--use-wes-model")
        for interval in intervals:
            command.extend(["-L", interval])
        log_path = work_dir / "parabricks.log"
        completed = run_in_runtime(
            rootfs=self.rootfs,
            guest_command=self.pbrun,
            args=command[1:],
            cwd=work_dir,
            image_environment=self.image_environment,
            timeout=self.timeout_seconds,
        )
        log_path.write_text(
            (completed.stdout + "\n" + completed.stderr)[-2_000_000:], encoding="utf-8"
        )
        if completed.returncode != 0:
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
            raise RuntimeError(f"Parabricks DeepVariant failed with exit code {completed.returncode}: {tail}")
        if not out_variants.is_file():
            raise RuntimeError("Parabricks completed without producing a VCF")

        variant_records = 0
        with gzip.open(out_variants, "rt", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if line and not line.startswith("#"):
                    variant_records += 1
        summary = {
            "engine": "NVIDIA Parabricks DeepVariant",
            "engine_version": self.runtime.get("actual_engine_version", "unknown"),
            "runtime": self.runtime,
            "sample_id": sample_id,
            "mode": mode,
            "use_wes_model": use_wes_model,
            "intervals": intervals,
            "gpu_count": GPU_COUNT,
            "gpus": names,
            "variant_records": variant_records,
            "inputs": input_records,
            "guided_bam_header_normalized": guided_bam_normalized,
            "output_vcf": f"output/{out_variants.name}",
            "research_only": True,
            "clinical_use": False,
        }
        (work_dir / "deepvariant-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        shutil.rmtree(temporary_dir, ignore_errors=True)
        return summary


app = create_app(ParabricksAdapter())
