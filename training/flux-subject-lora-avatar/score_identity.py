#!/usr/bin/env python3
"""Identity gate: score generated images against held-out reference photos.

Do not eyeball checkpoint sample grids - faces that "look right" at grid size
routinely fail a face-embedding check, and the best checkpoint is often not
the last one. This script embeds faces with ArcFace (insightface buffalo_l,
CPU is fine) and reports the cosine similarity of each candidate image's
largest face against your held-out reference set (the photos that
prepare_dataset.py reserved and that were NEVER trained on).

Per candidate the similarity is max(best-vs-any-ref, mean-vs-mean-embedding).

Usage:
  python3 score_identity.py --refs prepared/refs \
      --candidates "output/<run>/<run>/samples/*.jpg" --out scores.json

Point --candidates at each checkpoint's sample images (or at images you
generated from the endpoint) and compare mean/min/pass-rate across
checkpoints; serve the winner.

The default threshold 0.42 is a starting point from a calibrated run
(genuine-vs-impostor midpoint). Calibrate for your own face if you can:
score a few genuine photos (should land well above) and a few photos of
other people (should land well below), then pick the midpoint.

Requires: pip install insightface onnxruntime opencv-python-headless numpy
(first run downloads the buffalo_l model pack, ~300 MB).
"""
import argparse
import glob
import json
import os
import sys

IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--refs", required=True,
                   help="folder of held-out reference photos (one face each)")
    p.add_argument("--candidates", required=True,
                   help="folder or glob of generated images to score")
    p.add_argument("--threshold", type=float, default=0.42,
                   help="pass threshold on cosine similarity (default 0.42)")
    p.add_argument("--out", default="",
                   help="optional path to write full JSON results")
    return p.parse_args()


def collect(spec):
    if os.path.isdir(spec):
        return [os.path.join(spec, f) for f in sorted(os.listdir(spec))
                if f.lower().endswith(IMG_EXTS)]
    return sorted(p for p in glob.glob(spec) if p.lower().endswith(IMG_EXTS))


def main():
    args = parse_args()
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis
    except ImportError:
        sys.exit("missing deps: pip install insightface onnxruntime "
                 "opencv-python-headless numpy")

    det = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    det.prepare(ctx_id=-1, det_size=(640, 640))

    def largest_face_embedding(path):
        img = cv2.imread(path)
        if img is None:
            return None
        faces = det.get(img)
        if not faces:
            return None
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) *
                                        (f.bbox[3] - f.bbox[1]))
        emb = face.normed_embedding.astype(np.float32)
        return emb / np.linalg.norm(emb)

    # ---- reference embeddings ----
    ref_paths = collect(args.refs)
    if not ref_paths:
        sys.exit(f"no reference images in {args.refs}")
    refs = []
    for p in ref_paths:
        emb = largest_face_embedding(p)
        if emb is None:
            print(f"WARN ref {os.path.basename(p)}: no face detected, skipped")
            continue
        refs.append(emb)
    if not refs:
        sys.exit("no usable reference faces")
    refs = np.stack(refs)
    ref_mean = refs.mean(axis=0)
    ref_mean /= np.linalg.norm(ref_mean)
    print(f"references: {len(refs)} usable faces from {len(ref_paths)} images")

    # ---- candidates ----
    cand_paths = collect(args.candidates)
    if not cand_paths:
        sys.exit(f"no candidate images match {args.candidates}")

    results, sims = [], []
    for p in cand_paths:
        emb = largest_face_embedding(p)
        if emb is None:
            results.append({"image": p, "similarity": None, "passed": False,
                            "note": "no face detected"})
            print(f"{os.path.basename(p):50s}  NO FACE            FAIL")
            continue
        sim = float(max(float((refs @ emb).max()), float(ref_mean @ emb)))
        passed = sim >= args.threshold
        sims.append(sim)
        results.append({"image": p, "similarity": round(sim, 4),
                        "passed": passed})
        print(f"{os.path.basename(p):50s}  sim={sim:6.4f}  "
              f"{'PASS' if passed else 'FAIL'}")

    n = len(results)
    n_pass = sum(1 for r in results if r["passed"])
    summary = {
        "candidates": n,
        "passed": n_pass,
        "pass_rate": round(n_pass / n, 4) if n else 0.0,
        "mean_similarity": round(sum(sims) / len(sims), 4) if sims else None,
        "min_similarity": round(min(sims), 4) if sims else None,
        "threshold": args.threshold,
    }
    print("\nsummary:", json.dumps(summary))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"summary": summary, "results": results}, fh, indent=2)
        print(f"full results -> {args.out}")
    # nonzero exit if fewer than half pass, so CI-style gating works
    sys.exit(0 if n and n_pass / n >= 0.5 else 1)


if __name__ == "__main__":
    main()
