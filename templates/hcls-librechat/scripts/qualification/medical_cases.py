#!/usr/bin/env python3
"""Prepare public expert-labelled CT studies without model submissions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile

import nibabel as nib
import numpy as np
from scipy.ndimage import distance_transform_edt

from datasets import digest, fetch, write_json


ARCHIVE_URL = "https://msd-for-monai.s3-us-west-2.amazonaws.com/Task09_Spleen.tar"
ARCHIVE_MD5 = "410d4a301da4e5b2f6f86ec3ddba524e"


def prepare(archive_path: Path, output: Path, count: int) -> dict:
    with archive_path.open("rb") as stream:
        archive_md5 = hashlib.file_digest(stream, "md5").hexdigest()
    if archive_md5 != ARCHIVE_MD5:
        raise ValueError("MSD archive differs from the official MONAI tutorial checksum.")
    with archive_path.open("rb") as stream:
        archive_sha = hashlib.file_digest(stream, "sha256").hexdigest()
    folder = output / "references/msd-spleen"
    folder.mkdir(parents=True, exist_ok=True)
    metadata, metadata_receipt = fetch(
        "https://raw.githubusercontent.com/Project-MONAI/model-zoo/dev/models/vista3d/configs/metadata.json",
        folder / "vista3d-metadata.json")
    if json.loads(metadata)["network_data_format"]["outputs"]["pred"]["channel_def"]["3"] != "spleen":
        raise ValueError("VISTA3D label 3 does not identify spleen in the recorded upstream metadata.")
    metadata_receipt["path"] = str(Path(metadata_receipt["path"]).relative_to(output))
    cases, preparations = [], []
    with tarfile.open(archive_path) as archive:
        dataset_bytes = archive.extractfile("Task09_Spleen/dataset.json").read()
        (folder / "dataset.json").write_bytes(dataset_bytes)
        dataset = json.loads(dataset_bytes)
        # Deterministic scan order, not selected by outcome or model quality.
        selected = dataset["training"][:count]
        for entry in selected:
            filename = Path(entry["image"]).name
            sample = filename.removesuffix(".nii.gz")
            sample_folder = folder / sample
            sample_folder.mkdir(exist_ok=True)
            image_bytes = archive.extractfile("Task09_Spleen/" + entry["image"].removeprefix("./")).read()
            label_bytes = archive.extractfile("Task09_Spleen/" + entry["label"].removeprefix("./")).read()
            image_path, label_path = sample_folder / "image.nii.gz", sample_folder / "expert-label.nii.gz"
            image_path.write_bytes(image_bytes)
            label_path.write_bytes(label_bytes)
            image, label = nib.load(image_path), nib.load(label_path)
            if len(image_bytes) > 33554432 or len(image.shape) != 3 or any(n < 8 or n > 512 for n in image.shape):
                preparations.append({"sample": sample, "status": "blocked_input_contract", "shape": image.shape,
                                     "bytes": len(image_bytes), "reason": "Unmodified public scan exceeds the hosted input envelope; not silently downsampled."})
                continue
            if image.shape != label.shape or not np.allclose(image.affine, label.affine):
                raise ValueError("Published image/mask geometry does not match.")
            # Simulate an expert clicking the deepest interior voxel, explicitly
            # using the reference mask. These assisted cases are not automatic
            # segmentation or fair zero-shot test evidence.
            foreground = np.asanyarray(label.dataobj) == 1
            spacing = nib.affines.voxel_sizes(label.affine)
            interior_distance = distance_transform_edt(foreground, sampling=spacing)
            positive = [int(value) for value in np.unravel_index(np.argmax(interior_distance), label.shape)]
            for mode in ("label", "point", "label-plus-point"):
                arguments = {}
                if mode != "point":
                    arguments["label_prompt"] = [3]
                if mode != "label":
                    arguments.update(points=[positive], point_labels=[1])
                cases.append({"case_id": f"nv-segment-ct-{sample}-{mode}", "persona": "medical-imaging-researcher",
                    "model_id": "nv-segment-ct", "tool": "segment_ct_native", "mode": "native", "arguments": arguments,
                    "preparation": {"artifact_fields": [{"field": "input_nifti_base64", "transport": "artifact", "compression": "none",
                        "local_path": str(image_path.relative_to(output)), "media_type": "application/gzip",
                        "sha256": digest(image_bytes), "size_bytes": len(image_bytes), "required": True}]},
                    "expected": {"evaluator": "ct_segmentation", "reference_path": str(label_path.relative_to(output)),
                        "reference_foreground_label": 1, "prediction_foreground_label": 1 if mode == "point" else 3,
                        "prompt_mode": mode},
                    "provenance": {"dataset_id": f"msd-task09-{sample}", "source_url": ARCHIVE_URL,
                        "paper_url": "https://www.nature.com/articles/s41467-022-30695-9", "license": dataset["licence"],
                        "archive_sha256": archive_sha, "archive_md5": archive_md5,
                        "image_sha256": digest(image_bytes), "expert_mask_sha256": digest(label_bytes),
                        "label_mapping_source": metadata_receipt,
                        "protocol_deviation": "Original unmodified public training scans with expert masks. VISTA3D training overlap expected; not held-out generalization or clinical validation. Point modes use an oracle expert-interior click from the mask, reported separately from label-only automatic segmentation."},
                    "workload": {"unique_input_id": f"msd-task09-{sample}", "repetition": 1, "seed": None, "priority": "batch"}})
            preparations.append({"sample": sample, "status": "prepared", "cases": 3, "shape": list(image.shape),
                                 "image_bytes": len(image_bytes), "positive_point": positive})
    manifest = {"schema_version": 1, "study_id": "expert-labelled-ct-spleen-v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "preparations": preparations, "cases": cases}
    write_json(output / "cases.json", manifest)
    return {"manifest": str(output / "cases.json"), "cases": len(cases), "preparations": preparations}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scans", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output, args.scans), indent=2))


if __name__ == "__main__":
    main()
