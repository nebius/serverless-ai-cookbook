"""Prepare a reproducible subset of the upstream VBench prompt suite."""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import re
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["id", "prompt", "seed", "category", "source_path", "source_line", "source_revision"]
CATEGORIES = ["animal", "architecture", "food", "human", "lifestyle", "plant", "scenery", "vehicles"]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def definition() -> dict:
    value = json.loads((ROOT / "data/source.json").read_text(encoding="utf-8"))
    if value.get("repository") != "Vchitect/VBench" or not re.fullmatch(r"[0-9a-f]{40}", value.get("revision", "")):
        raise ValueError("Invalid pinned VBench source definition.")
    return value


def fetch_source(relative: str, spec: dict, cache_dir: Path, source: dict) -> bytes:
    cached = cache_dir / Path(relative).name
    if cached.is_file():
        data = cached.read_bytes()
        if len(data) == spec["bytes"] and sha256(data) == spec["sha256"]:
            return data
    # The public contents API returns immutable file bytes as base64. No token is needed.
    url = f"https://api.github.com/repos/{source['repository']}/contents/{relative}?ref={source['revision']}"
    request = urllib.request.Request(url, headers={"User-Agent": "nebius-serverless-video-cookbook"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
        if len(payload) > 2 * 1024 * 1024:
            raise ValueError("Source response exceeds the size limit.")
        document = json.loads(payload)
        if document.get("encoding") != "base64":
            raise ValueError("Source API did not return file bytes.")
        data = base64.b64decode(document["content"].replace("\n", ""), validate=True)
    except (OSError, urllib.error.URLError, KeyError, ValueError) as exc:
        raise ValueError("Cannot retrieve the pinned VBench source. Check internet access or GitHub's anonymous API rate limit.") from exc
    if len(data) != spec["bytes"] or sha256(data) != spec["sha256"]:
        raise ValueError(f"Pinned source checksum differs: {relative}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data


def select_rows(source: dict, contents: dict[str, bytes], per_category: int, seed: int) -> list[dict]:
    if not 1 <= per_category <= 100:
        raise ValueError("--per-category must be 1–100.")
    chooser, seeds = random.Random(seed), random.Random(seed ^ 0x5EED)
    rows = []
    for category in CATEGORIES:
        relative = f"prompts/prompts_per_category/{category}.txt"
        candidates = [(line, text.strip()) for line, text in enumerate(contents[relative].decode("utf-8").splitlines(), 1) if text.strip()]
        if len(candidates) != source["files"][relative]["rows"]:
            raise ValueError(f"Unexpected prompt count for {category}.")
        for line, prompt in chooser.sample(candidates, per_category):
            rows.append({"id": f"vbench-{category}-{line:04d}", "prompt": prompt,
                         "seed": seeds.randrange(2**31), "category": category,
                         "source_path": relative, "source_line": line,
                         "source_revision": source["revision"]})
    return rows


def encode_csv(rows: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def prepare(output: Path, cache_dir: Path, *, per_category: int = 25, seed: int = 42) -> dict:
    source = definition()
    contents = {relative: fetch_source(relative, spec, cache_dir, source)
                for relative, spec in source["files"].items()}
    rows = select_rows(source, contents, per_category, seed)
    data = encode_csv(rows)
    provenance = {"schema": 1, "dataset": "VBench", "repository": source["repository"],
                  "revision": source["revision"], "license": source["license"],
                  "source_manifest": source, "selection_seed": seed,
                  "per_category": per_category, "rows": len(rows),
                  "selection": rows, "input_sha256": sha256(data),
                  "note": "A stratified prompt subset for generation and manual inspection; not a complete VBench evaluation."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    output.with_suffix(".source.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance


def verify(path: Path) -> dict:
    data = path.read_bytes()
    provenance = json.loads(path.with_suffix(".source.json").read_text(encoding="utf-8"))
    if provenance.get("source_manifest") != definition() or provenance.get("dataset") != "VBench":
        raise ValueError("Prompt provenance differs from the pinned source definition.")
    if sha256(data) != provenance.get("input_sha256"):
        raise ValueError("Prompt CSV differs from its recorded checksum. Prepare a new batch for changed inputs.")
    raw = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    for row in raw:
        row["seed"], row["source_line"] = int(row["seed"]), int(row["source_line"])
    if raw != provenance.get("selection") or len(raw) != provenance.get("rows"):
        raise ValueError("Prompt CSV differs from its recorded source selection.")
    if len({row["id"] for row in raw}) != len(raw):
        raise ValueError("Prompt IDs must be unique.")
    license_spec = definition()["files"]["LICENSE"]
    if sha256((ROOT / "data/LICENSE").read_bytes()) != license_spec["sha256"]:
        raise ValueError("Bundled VBench license differs from the pinned original.")
    return provenance
