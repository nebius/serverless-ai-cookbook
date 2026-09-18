#!/usr/bin/env python3
"""Prepare a personal-photo dataset for FLUX.2 subject-LoRA fine-tuning.

Takes a folder of your own photos and produces the layout the training job
expects:

    <output>/dataset/   img_001.jpg + img_001.txt  (training pairs)
    <output>/refs/      held-out reference photos  (identity scoring, never trained)

What it does per image:
  - applies EXIF rotation, converts to RGB, re-encodes as JPEG
  - optionally verifies the photo contains EXACTLY ONE detectable face
    (insightface; use --no-face-check to skip if you curated by hand)
  - downsizes so the longest side is <= --max-side, warns if the short
    side is below --min-side (low-res faces hurt identity)
  - writes a caption file that starts with the trigger token, e.g.
    "TOK4ME person, photo". If a .txt sidecar with the same stem exists
    next to the input image, its text is used instead (the trigger prefix
    is added if missing). Hand-written, varied captions train better.
  - reserves --holdout images (seeded random pick) as identity references;
    they are NOT trained on, so scoring against them is honest.

Output stems are neutral (img_###) on purpose: never rely on filename-based
trigger inference in any trainer - the trigger token is set explicitly in the
training config.

Example:
    python3 prepare_dataset.py --input ~/my-photos --output ./prepared \\
        --trigger TOK4ME --class-word person --holdout 6
"""
import argparse
import random
import shutil
import sys
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--input", required=True, help="folder with your source photos")
    p.add_argument("--output", required=True, help="output folder (created)")
    p.add_argument("--trigger", default="TOK4ME",
                   help="trigger token; a rare string the model has never seen "
                        "(default: TOK4ME). Keep the case consistent everywhere.")
    p.add_argument("--class-word", default="person",
                   help="class noun after the trigger, e.g. man / woman / person")
    p.add_argument("--caption-suffix", default="photo",
                   help="default caption tail when no .txt sidecar exists")
    p.add_argument("--holdout", type=int, default=6,
                   help="number of images reserved as identity references (default 6)")
    p.add_argument("--max-side", type=int, default=1536,
                   help="downsize so the longest side is at most this (default 1536)")
    p.add_argument("--min-side", type=int, default=768,
                   help="warn when the short side is below this (default 768)")
    p.add_argument("--jpeg-quality", type=int, default=95)
    p.add_argument("--seed", type=int, default=42, help="holdout selection seed")
    p.add_argument("--no-face-check", action="store_true",
                   help="skip the insightface single-face verification")
    return p.parse_args()


def load_face_detector():
    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        sys.exit(
            "insightface is not installed. Either:\n"
            "  pip install insightface onnxruntime opencv-python-headless\n"
            "or rerun with --no-face-check if you curated the photos by hand."
        )
    det = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    det.prepare(ctx_id=-1, det_size=(640, 640))
    return det


def count_faces(detector, image):
    import numpy as np
    bgr = np.asarray(image)[:, :, ::-1]  # PIL RGB -> OpenCV BGR
    faces = [f for f in detector.get(bgr) if getattr(f, "det_score", 1.0) >= 0.5]
    return len(faces)


def build_caption(src: Path, trigger: str, class_word: str, suffix: str) -> str:
    sidecar = src.with_suffix(".txt")
    if sidecar.exists():
        text = sidecar.read_text(encoding="utf-8").strip()
        if trigger not in text:
            text = f"{trigger} {class_word}, {text}"
        return text
    return f"{trigger} {class_word}, {suffix}"


def main():
    args = parse_args()
    try:
        from PIL import Image, ImageOps
    except ImportError:
        sys.exit("Pillow is required: pip install pillow")

    src_dir = Path(args.input)
    out_dir = Path(args.output)
    dataset_dir = out_dir / "dataset"
    refs_dir = out_dir / "refs"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    refs_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(
        p for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMG_EXTS
    )
    if not sources:
        sys.exit(f"no images found in {src_dir}")

    detector = None if args.no_face_check else load_face_detector()

    rng = random.Random(args.seed)
    holdout_set = set(rng.sample(range(len(sources)), min(args.holdout, len(sources))))

    kept, skipped, low_res, ref_count = 0, 0, 0, 0
    for idx, src in enumerate(sources):
        with Image.open(src) as im:
            img = ImageOps.exif_transpose(im).convert("RGB")

        if detector is not None:
            n = count_faces(detector, img)
            if n != 1:
                print(f"SKIP {src.name}: {n} faces detected (need exactly 1)")
                skipped += 1
                continue

        w, h = img.size
        if max(w, h) > args.max_side:
            scale = args.max_side / max(w, h)
            img = img.resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        if min(img.size) < args.min_side:
            print(f"WARN {src.name}: short side {min(img.size)}px < {args.min_side}px")
            low_res += 1

        if idx in holdout_set:
            ref_count += 1
            img.save(refs_dir / f"ref_{ref_count:03d}.jpg",
                     quality=args.jpeg_quality)
            continue

        kept += 1
        stem = f"img_{kept:03d}"
        img.save(dataset_dir / f"{stem}.jpg", quality=args.jpeg_quality)
        caption = build_caption(src, args.trigger, args.class_word,
                                args.caption_suffix)
        (dataset_dir / f"{stem}.txt").write_text(caption + "\n", encoding="utf-8")

    print(f"\ntraining pairs: {kept}  holdout refs: {ref_count}  "
          f"skipped: {skipped}  low-res warnings: {low_res}")
    if kept < 30:
        print("NOTE: 30-60 varied solo shots is the sweet spot; "
              "fewer images usually means weaker identity.")
    print(f"""
Next step - upload to Object Storage (adjust bucket/region):

  aws --endpoint-url "https://storage.<REGION>.nebius.cloud" \\
    s3 cp --recursive {dataset_dir} s3://<YOUR_BUCKET>/flux-avatar/dataset/
  aws --endpoint-url "https://storage.<REGION>.nebius.cloud" \\
    s3 cp --recursive {refs_dir} s3://<YOUR_BUCKET>/flux-avatar/refs/
""")


if __name__ == "__main__":
    main()
