from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import nibabel as nib
import numpy as np
import torch
from monai import __version__ as monai_version
from monai.inferers import sliding_window_inference
from monai.transforms import Compose, ScaleIntensityRange


class RunLogger:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def info(self, message: str) -> None:
        timestamp = datetime.now(UTC).isoformat()
        line = f"{timestamp} {message}"
        print(line, flush=True)
        self.lines.append(line)

    def write(self, path: Path) -> None:
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


class ThresholdSegmenter(torch.nn.Module):
    """Small deterministic predictor for the synthetic bright target."""

    def __init__(self, threshold: float, sharpness: float) -> None:
        super().__init__()
        self.threshold = threshold
        self.sharpness = sharpness

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        foreground_logit = (image - self.threshold) * self.sharpness
        background_logit = -foreground_logit
        return torch.cat([background_logit, foreground_logit], dim=1)


def parse_shape(value: str) -> tuple[int, int, int]:
    try:
        parts = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("shape must be integers like 96,96,64") from exc
    if len(parts) != 3 or any(part < 16 for part in parts):
        raise argparse.ArgumentTypeError("shape must have three dimensions, each >= 16")
    return parts


def ellipsoid_mask(
    shape: tuple[int, int, int],
    center: tuple[float, float, float],
    radius: tuple[float, float, float],
) -> np.ndarray:
    z, y, x = np.ogrid[: shape[0], : shape[1], : shape[2]]
    distance = (
        ((z - center[0]) / radius[0]) ** 2
        + ((y - center[1]) / radius[1]) ** 2
        + ((x - center[2]) / radius[2]) ** 2
    )
    return distance <= 1.0


def make_synthetic_phantom(
    shape: tuple[int, int, int],
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    volume = rng.normal(-900.0, 25.0, size=shape).astype(np.float32)

    center = (shape[0] * 0.52, shape[1] * 0.50, shape[2] * 0.50)
    body = ellipsoid_mask(
        shape,
        center=center,
        radius=(shape[0] * 0.42, shape[1] * 0.36, shape[2] * 0.36),
    )
    organ = ellipsoid_mask(
        shape,
        center=(shape[0] * 0.50, shape[1] * 0.48, shape[2] * 0.50),
        radius=(shape[0] * 0.22, shape[1] * 0.18, shape[2] * 0.16),
    )
    target = ellipsoid_mask(
        shape,
        center=(shape[0] * 0.48, shape[1] * 0.56, shape[2] * 0.54),
        radius=(max(shape[0] * 0.06, 4.0), max(shape[1] * 0.055, 4.0), max(shape[2] * 0.05, 3.0)),
    )

    volume[body] = rng.normal(-120.0, 18.0, size=int(body.sum()))
    volume[organ] = rng.normal(30.0, 12.0, size=int(organ.sum()))
    volume[target] = rng.normal(180.0, 8.0, size=int(target.sum()))

    return volume, target.astype(np.uint8)


def choose_device(requested: str) -> tuple[torch.device, bool]:
    if requested == "cpu":
        return torch.device("cpu"), False

    cuda_available = torch.cuda.is_available()
    if requested == "auto":
        return torch.device("cuda" if cuda_available else "cpu"), cuda_available
    if requested == "cuda" and not cuda_available:
        raise RuntimeError("CUDA was requested, but torch.cuda.is_available() is false")
    return torch.device(requested), cuda_available


def dice_score(prediction: np.ndarray, target: np.ndarray) -> float:
    prediction_bool = prediction.astype(bool)
    target_bool = target.astype(bool)
    denominator = prediction_bool.sum() + target_bool.sum()
    if denominator == 0:
        return 1.0
    intersection = np.logical_and(prediction_bool, target_bool).sum()
    return float((2.0 * intersection) / denominator)


def save_nifti(array: np.ndarray, path: Path) -> None:
    affine = np.diag([1.5, 1.5, 1.5, 1.0])
    nib.save(nib.Nifti1Image(array, affine), str(path))


def save_preview(
    image: np.ndarray,
    label: np.ndarray,
    prediction: np.ndarray,
    path: Path,
) -> None:
    z_index = image.shape[0] // 2
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.5), constrained_layout=True)
    panels = [
        ("Synthetic image", image[z_index], "gray"),
        ("Reference mask", label[z_index], "magma"),
        ("Predicted mask", prediction[z_index], "magma"),
    ]
    for axis, (title, data, cmap) in zip(axes, panels, strict=True):
        axis.imshow(np.rot90(data), cmap=cmap)
        axis.set_title(title)
        axis.axis("off")
    fig.savefig(path, dpi=140)
    plt.close(fig)


def iter_files(path: Path) -> Iterable[Path]:
    for item in sorted(path.rglob("*")):
        if item.is_file():
            yield item


def build_s3_prefix(base_prefix: str, run_id: str) -> str:
    parts = [part.strip("/") for part in (base_prefix, run_id) if part.strip("/")]
    return "/".join(parts)


def upload_to_s3(output_dir: Path, run_id: str, logger: RunLogger) -> str:
    bucket = os.environ.get("S3_BUCKET", "").strip()
    endpoint_url = os.environ.get("S3_ENDPOINT_URL", "").strip()
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "").strip()
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "").strip()
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-north1").strip()
    prefix = build_s3_prefix(os.environ.get("S3_PREFIX", "monai-medical-imaging"), run_id)

    missing = [
        name
        for name, value in (
            ("S3_BUCKET", bucket),
            ("S3_ENDPOINT_URL", endpoint_url),
            ("AWS_ACCESS_KEY_ID", access_key),
            ("AWS_SECRET_ACCESS_KEY", secret_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"S3 upload requested, but missing: {', '.join(missing)}")

    import boto3

    client = boto3.session.Session(region_name=region).client("s3", endpoint_url=endpoint_url)
    for file_path in iter_files(output_dir):
        key = f"{prefix}/{file_path.relative_to(output_dir).as_posix()}"
        logger.info(f"Uploading {file_path.name} to s3://{bucket}/{key}")
        client.upload_file(str(file_path), bucket, key)
    return f"s3://{bucket}/{prefix}/"


def run(args: argparse.Namespace) -> dict[str, object]:
    logger = RunLogger()
    started = time.perf_counter()
    run_id = args.run_id or f"{args.case_id}-{uuid.uuid4().hex[:8]}"
    output_dir = Path(args.output_dir).expanduser().resolve() / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting synthetic MONAI medical-imaging job")
    logger.info("Safety: synthetic data only; not for diagnosis or clinical validation")
    logger.info(f"Output directory: {output_dir}")

    image_hu, reference_mask = make_synthetic_phantom(args.shape, args.seed)
    preprocess = Compose(
        [
            ScaleIntensityRange(
                a_min=-1000.0,
                a_max=250.0,
                b_min=0.0,
                b_max=1.0,
                clip=True,
            )
        ]
    )
    image = np.asarray(preprocess(image_hu), dtype=np.float32)

    device, cuda_available = choose_device(args.device)
    logger.info(f"Using device: {device}")
    if device.type == "cuda":
        logger.info(f"CUDA device name: {torch.cuda.get_device_name(0)}")

    tensor = torch.from_numpy(image[None, None]).to(device)
    model = ThresholdSegmenter(args.threshold, args.sharpness).to(device).eval()
    roi_size = tuple(min(dim, roi) for dim, roi in zip(args.shape, args.roi_size, strict=True))

    with torch.inference_mode():
        logits = sliding_window_inference(
            inputs=tensor,
            roi_size=roi_size,
            sw_batch_size=args.sw_batch_size,
            predictor=model,
            overlap=args.overlap,
        )
        prediction = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy().astype(np.uint8)

    dice = dice_score(prediction, reference_mask)
    elapsed_seconds = time.perf_counter() - started
    logger.info(f"Finished inference in {elapsed_seconds:.3f} seconds")
    logger.info(f"Synthetic-reference Dice score: {dice:.4f}")

    image_path = output_dir / "synthetic_ct_phantom.nii.gz"
    reference_path = output_dir / "synthetic_target_mask.nii.gz"
    prediction_path = output_dir / "predicted_segmentation_mask.nii.gz"
    preview_path = output_dir / "preview.png"
    metadata_path = output_dir / "metadata.json"
    log_path = output_dir / "run.log"

    save_nifti(image_hu.astype(np.float32), image_path)
    save_nifti(reference_mask.astype(np.uint8), reference_path)
    save_nifti(prediction.astype(np.uint8), prediction_path)
    save_preview(image, reference_mask, prediction, preview_path)

    should_upload = args.upload_s3
    s3_uri = None
    if should_upload:
        s3_prefix = build_s3_prefix(
            os.environ.get("S3_PREFIX", "monai-medical-imaging"),
            run_id,
        )
        s3_uri = f"s3://{os.environ.get('S3_BUCKET', '<bucket>')}/{s3_prefix}/"

    metadata: dict[str, object] = {
        "run_id": run_id,
        "case_id": args.case_id,
        "created_at": datetime.now(UTC).isoformat(),
        "workflow": "synthetic-monai-sliding-window-threshold-segmentation",
        "data_source": "synthetic phantom generated at runtime",
        "contains_phi": False,
        "clinical_use": "not for diagnosis, treatment, triage, or clinical validation",
        "shape_dhw": list(args.shape),
        "roi_size_dhw": list(roi_size),
        "seed": args.seed,
        "threshold": args.threshold,
        "device": str(device),
        "torch_version": torch.__version__,
        "monai_version": monai_version,
        "cuda_available": cuda_available,
        "elapsed_seconds": elapsed_seconds,
        "dice_vs_synthetic_reference": dice,
        "artifacts": [
            image_path.name,
            reference_path.name,
            prediction_path.name,
            preview_path.name,
            metadata_path.name,
            log_path.name,
        ],
        "s3_output_uri": s3_uri,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    logger.write(log_path)

    if should_upload:
        uploaded_uri = upload_to_s3(output_dir, run_id, logger)
        logger.info(f"Uploaded artifacts to {uploaded_uri}")
        logger.write(log_path)
    else:
        logger.info("S3 upload disabled; artifacts remain on local or job ephemeral disk")
        logger.write(log_path)

    return metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a small synthetic MONAI medical-imaging segmentation job."
    )
    parser.add_argument("--case-id", default="synthetic-phantom-001")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--shape", type=parse_shape, default=parse_shape("96,96,64"))
    parser.add_argument("--roi-size", type=parse_shape, default=parse_shape("64,64,32"))
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--threshold", type=float, default=0.86)
    parser.add_argument("--sharpness", type=float, default=24.0)
    parser.add_argument("--sw-batch-size", type=int, default=2)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument(
        "--upload-s3",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Upload outputs to S3-compatible Object Storage. "
            "Defaults to true when S3_BUCKET is set."
        ),
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.upload_s3 is None:
        args.upload_s3 = bool(os.environ.get("S3_BUCKET"))
    run(args)


if __name__ == "__main__":
    main()
