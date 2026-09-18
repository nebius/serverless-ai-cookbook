#!/usr/bin/env python3
"""Prepare bounded, recorded ALOHA segments using pinned LeRobot 0.6.1.

No model inference. Camera frames, actions, states and efforts come from the
same recorded source rows. Downsampling/reindexing is explicit provenance, not
a claim that a short derived clip reproduces the paper's manipulation success.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import httpx
import numpy as np
import pyarrow.parquet as pq

REPOSITORY = "lerobot/aloha_static_coffee"
REVISION = "b144896feb1f37398a862927b22cd3abdf005a6b"
CAMERAS = ("observation.images.cam_high", "observation.images.cam_right_wrist")
SEGMENTS = ((0, 200), (1, 250))
FRAMES, STRIDE, SOURCE_FPS = 64, 2, 50
FILES = ("README.md", "meta/info.json", "meta/stats.json", "meta/tasks.parquet",
         "meta/episodes/chunk-000/file-000.parquet", "data/chunk-000/file-000.parquet",
         *(f"videos/{camera}/chunk-000/file-000.mp4" for camera in CAMERAS))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(destination: Path, runtime: Path, source_cache: Path | None = None) -> dict:
    if importlib.metadata.version("lerobot") != "0.6.1":
        raise ValueError("Use the pinned lerobot==0.6.1 CPU environment.")
    # This study also has a local datasets.py case generator. Do not let its
    # script directory shadow Hugging Face's unrelated `datasets` dependency.
    sys.path[:] = [entry for entry in sys.path if Path(entry).resolve() != Path(__file__).resolve().parent]
    sys.path.insert(0, str(runtime))
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    from fs2_lerobot_augmentation.contracts import Selection
    from fs2_lerobot_augmentation.dataset import (open_and_validate, package_dataset,
        encode_episode_reference, source_row, write_bundle_manifest)

    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "aloha-coffee-two-recorded-segments"
    if output.exists():
        raise ValueError("Derived output already exists; use a new version, never overwrite evidence.")
    source = source_cache or destination / "source"
    source.mkdir(exist_ok=True)
    with httpx.Client(follow_redirects=True, trust_env=False, timeout=180) as client:
        response = client.get(f"https://huggingface.co/api/datasets/{REPOSITORY}/tree/{REVISION}?recursive=true&expand=false")
        response.raise_for_status()
        tree = {entry["path"]: entry for entry in response.json() if entry["type"] == "file"}
    def fetch(name: str) -> dict:
        entry = tree[name]
        path = source / name
        expected_hash = entry.get("lfs", {}).get("oid")
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            url = f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{name}"
            with httpx.Client(follow_redirects=True, trust_env=False, timeout=180) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with path.open("xb") as target:
                        for chunk in response.iter_bytes(4 * 1024 * 1024):
                            target.write(chunk)
        sha = digest(path)
        if path.stat().st_size != entry["size"] or (expected_hash and sha != expected_hash):
            raise ValueError(f"Source hash/size differs from pinned repository: {name}")
        print(json.dumps({"downloaded": name, "bytes": path.stat().st_size}), flush=True)
        return {"path": name, "sha256": sha, "size_bytes": path.stat().st_size,
                "url": f"https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/{name}"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        identities = list(pool.map(fetch, FILES))
    info = json.loads((source / "meta/info.json").read_text())
    if info["fps"] != SOURCE_FPS or info["codebase_version"] != "v3.0":
        raise ValueError("Unexpected source timing or dataset version.")
    data = pq.read_table(source / "data/chunk-000/file-000.parquet").to_pydict()
    episodes = pq.read_table(source / "meta/episodes/chunk-000/file-000.parquet").to_pylist()
    features = {}
    nonvideo = ("observation.state", "observation.effort", "action", "next.done")
    for name in nonvideo:
        features[name] = {key: copy.deepcopy(value) for key, value in info["features"][name].items() if key != "fps"}
    for camera in CAMERAS:
        features[camera] = {"dtype": "video", "shape": (3, 480, 640), "names": ["channels", "height", "width"]}
    dataset = LeRobotDataset.create(repo_id="fs2/aloha-coffee-recorded-qualification", root=output,
        fps=SOURCE_FPS // STRIDE, features=features, robot_type="aloha", use_videos=True, video_backend="pyav")
    segments = []
    selected_originals = []
    for local_episode, (source_episode, start_frame) in enumerate(SEGMENTS):
        episode = next(row for row in episodes if row["episode_index"] == source_episode)
        offsets = list(range(start_frame, start_frame + FRAMES * STRIDE, STRIDE))
        first = int(episode["dataset_from_index"])
        indices = [first + offset for offset in offsets]
        if indices[-1] >= int(episode["dataset_to_index"]):
            raise ValueError("Selected segment exceeds its recorded episode.")
        task = episode["tasks"][0]
        frames = {}
        for camera in CAMERAS:
            start_seconds = float(episode[f"videos/{camera}/from_timestamp"])
            video_first = round(start_seconds * SOURCE_FPS) + start_frame
            if abs(video_first - (start_seconds * SOURCE_FPS + start_frame)) > 1e-5:
                raise ValueError("Video start is not exactly on the original frame grid.")
            vf = f"select=between(n\\,{video_first}\\,{video_first + (FRAMES-1)*STRIDE})*not(mod(n-{video_first}\\,{STRIDE}))"
            command = ["ffmpeg", "-v", "error", "-threads", "2", "-i", str(source / f"videos/{camera}/chunk-000/file-000.mp4"),
                "-vf", vf, "-vsync", "0", "-frames:v", str(FRAMES), "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
            pixels = subprocess.check_output(command)
            frames[camera] = np.frombuffer(pixels, dtype=np.uint8).reshape(FRAMES, 480, 640, 3)
        numeric_hashes = {}
        for offset, original_index in enumerate(indices):
            original = {name: np.asarray(data[name][original_index], dtype=features[name]["dtype"])
                        .reshape(tuple(features[name]["shape"])) for name in nonvideo}
            selected_originals.append(original)
            expected_time = np.float32(offsets[offset] / SOURCE_FPS)
            if np.float32(data["timestamp"][original_index]) != expected_time:
                raise ValueError("Recorded numeric timestamp is not aligned with selected camera frame.")
            dataset.add_frame({**original, **{camera: frames[camera][offset] for camera in CAMERAS}, "task": task})
        dataset.save_episode()
        for name in nonvideo:
            array = np.stack([row[name] for row in selected_originals[-FRAMES:]])
            numeric_hashes[name] = {"sha256": hashlib.sha256(array.tobytes()).hexdigest(),
                                    "dtype": str(array.dtype), "shape": list(array.shape)}
        segments.append({"derived_episode": local_episode, "source_episode": source_episode,
            "source_frame_indices": offsets, "source_global_indices": indices,
            "source_timestamps_seconds": [float(data["timestamp"][index]) for index in indices],
            "derived_timestamps_seconds": [index / (SOURCE_FPS // STRIDE) for index in range(FRAMES)],
            "numeric_values": numeric_hashes, "task": task})
    dataset.finalize()
    provenance = {"schema": "scientific-qualification-recorded-robotics/v1", "repository": REPOSITORY,
        "revision": REVISION, "license": "MIT", "paper": "https://arxiv.org/abs/2304.13705",
        "homepage": "https://tonyzhaozh.github.io/aloha/", "source_files": identities, "segments": segments,
        "derivation": {"source_fps": SOURCE_FPS, "derived_fps": SOURCE_FPS // STRIDE,
            "stride": STRIDE, "frames_per_segment": FRAMES, "camera_subset": list(CAMERAS),
            "video_reencoding": "LeRobot pinned writer; RGB frames decoded from recorded AV1; output codec may be lossy",
            "numeric_policy": "exact selected recorded action/state/effort/next.done; canonical indices/timestamps rebased",
            "not_claimed": ["complete original episodes", "paper success-rate reproduction", "policy training validity after generative edits", "physical action alignment of generated outputs"]}}
    (output / "qualification-source-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    write_bundle_manifest(output)
    checked = open_and_validate(output, repo_id="fs2/aloha-coffee-recorded-qualification",
                                selection=Selection(episodes="all", cameras="all"))
    compared = 0
    for index, expected in enumerate(selected_originals):
        actual = source_row(checked.dataset, index)
        for name in nonvideo:
            # Both source and rewritten Parquet store bool(shape=[1]) as a
            # scalar. Compare the exact dtype/value in its declared shape;
            # this does not coerce action/state values or replace booleans.
            observed = np.asarray(actual[name]).reshape(expected[name].shape)
            if observed.dtype != expected[name].dtype or not np.array_equal(observed, expected[name]):
                raise ValueError(f"Derived stored {name} differs from recorded source at frame {index}")
            compared += expected[name].size
    mp4s = []
    for episode in checked.episodes:
        for camera in CAMERAS:
            clip = destination / f"recorded-episode-{episode.index}-{camera.rsplit('.',1)[-1]}.mp4"
            encode_episode_reference(checked, episode, camera, clip)
            mp4s.append({"path": str(clip), "sha256": digest(clip), "size_bytes": clip.stat().st_size})
    bundle = destination / "aloha-coffee-two-recorded-segments.tar.zst"
    artifact = package_dataset(output, bundle)
    receipt = {"dataset": str(output), "bundle": str(bundle), "sha256": artifact.sha256,
        "size_bytes": artifact.size_bytes, "episodes": len(checked.episodes), "frames": checked.frames,
        "decoded_camera_frames": checked.decoded_video_frames, "fps": checked.fps,
        "cameras": list(checked.cameras), "exact_numeric_values_compared": compared,
        "source_mp4_clips": mp4s, "provenance": str(output / "qualification-source-provenance.json"),
        "model_calls": 0, "scope": "offline data integrity and real recorded-source preparation; not Cosmos qualification"}
    (destination / "preparation-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--source-cache", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.runtime, args.source_cache), indent=2))
