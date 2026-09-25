#!/usr/bin/env python3
"""Download pinned public inputs only; resume partial files and verify hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ARCHIVES = {
    "clinical": {"url": "https://ndownloader.figshare.com/files/30598530", "path": "raw/simulated-medical-exams-16550013-v1.zip",
                 "sha256": "20ef65540768d49ab6368672994aaef6acb21117d139e5d91e76a32432da951e", "license": "CC0-1.0"},
    "replay-train": {"url": "https://www.openslr.org/resources/12/train-clean-100.tar.gz", "path": "replay/raw/train-clean-100.tar.gz",
                     "sha256": "d4ddd1d5a6ab303066f14971d768ee43278a5f2a0aa43dc716b0e64ecbbbf6e2", "license": "CC-BY-4.0"},
    "general-test": {"url": "https://www.openslr.org/resources/12/test-clean.tar.gz", "path": "replay/raw/test-clean.tar.gz",
                     "sha256": "39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23", "license": "CC-BY-4.0"},
}
PRIMOCK_REVISION = "cd2ac707ad03cb4d2531f4ec6b90c659bf4357c5"
PRIMOCK_AUDIO = {
    "day1_consultation01_doctor": "a93ca69f49da821b2d10b03f3189fd0d82200a697805c18f316719ba328ff96b",
    "day1_consultation01_patient": "12b0c5c12018cff8399cf95b713eba4b7d2bb9d6581281844057ecab2ea3a414",
    "day1_consultation02_doctor": "39800525bbb34834aa19a6bb24dea514b093ae3417c6f22d49e585e9743a2ae6",
    "day1_consultation02_patient": "594383d70f8724740f39dc46258a01cd5762c42c46db4c6631ea205ddf66a7c2",
}
PRIMOCK_BLOBS = {
    "LICENSE.md": "0b1c29ed40e85d5fec8219e05d73b6bfef4943b3",
    "transcripts/day1_consultation01_doctor.TextGrid": "70c91e1424e43f95538d3993868c4b78c65609e7",
    "transcripts/day1_consultation01_patient.TextGrid": "f1fb8134b55a266169444990c22a0defd360c47f",
    "transcripts/day1_consultation02_doctor.TextGrid": "157dc6dc048f4116ae711899a39d98568737f271",
    "transcripts/day1_consultation02_patient.TextGrid": "7d6d524e17059c6b3e41333ecf5cfac78966bff3",
}


def file_hash(path, algorithm="sha256", git_blob=False):
    hasher = hashlib.new(algorithm)
    if git_blob:
        hasher.update(f"blob {path.stat().st_size}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def download(url, target, expected, *, git_blob=False):
    target = Path(target)
    algorithm = "sha1" if git_blob else "sha256"
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise ValueError("Refusing symlink output")
    if target.exists():
        if file_hash(target, algorithm, git_blob) != expected:
            raise ValueError("Existing output differs; no overwrite")
        return {"path": str(target), "sha256": file_hash(target), "bytes": target.stat().st_size, "state": "verified_existing"}
    partial = target.with_name(target.name + ".partial")
    if partial.is_symlink():
        raise ValueError("Refusing symlink partial")
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        if offset and (response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
            raise ValueError("Server did not honor resume offset; partial preserved")
        with partial.open("ab" if partial.exists() else "xb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)
    if file_hash(partial, algorithm, git_blob) != expected:
        raise ValueError("Downloaded content hash mismatch; partial preserved, not promoted")
    # A hard link is create-only: concurrent work cannot overwrite the final file.
    try:
        target.hardlink_to(partial)
    except FileExistsError:
        if file_hash(target, algorithm, git_blob) != expected:
            raise ValueError("Concurrent output differs; no overwrite")
    partial.unlink()
    return {"path": str(target), "sha256": file_hash(target), "bytes": target.stat().st_size, "state": "downloaded_verified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--dataset", choices=[*ARCHIVES, "primock-sample"], required=True)
    args = parser.parse_args()
    results = []
    if args.dataset in ARCHIVES:
        source = ARCHIVES[args.dataset]
        results.append(download(source["url"], args.data_root / source["path"], source["sha256"]))
    else:
        root = args.data_root / "external/primock57/source"
        for identity, expected in PRIMOCK_AUDIO.items():
            path = f"audio/{identity}.wav"
            results.append(download(f"https://media.githubusercontent.com/media/babylonhealth/primock57/{PRIMOCK_REVISION}/{path}", root / path, expected))
        for path, expected in PRIMOCK_BLOBS.items():
            results.append(download(f"https://raw.githubusercontent.com/babylonhealth/primock57/{PRIMOCK_REVISION}/{path}", root / path, expected, git_blob=True))
    print(json.dumps({"dataset": args.dataset, "verified_files": results}, indent=2))


if __name__ == "__main__":
    main()
