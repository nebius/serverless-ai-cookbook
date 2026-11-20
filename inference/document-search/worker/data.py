"""Prepare and verify 1,000 distinct, licensed Dolly reference passages.

Only source ``context`` fields are indexed. Instructions supply display titles;
responses are never included in the documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import urllib.request

DATA = Path(__file__).resolve().parent / "data"
SOURCE_PATH = DATA / "source.json"
FILES = {"documents.jsonl", "manifest.json", "LICENSE", "SOURCE.md"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _chunk_count(text: str, words: int = 160) -> int:
    """Count the existing recipe's paragraph-aware, non-overlapping chunks."""
    count, current = 0, 0
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        size = len(paragraph.split())
        if not size:
            continue
        if current and current + size > words:
            count, current = count + 1, 0
        while size > words:
            count, size = count + 1, size - words
        current += size
    return count + bool(current)


def _select(raw: bytes, source: dict) -> tuple[list[dict], list[dict]]:
    selection = source["selection"]
    count, minimum = selection["count"], selection["minimum_words"]
    seen, documents, metadata = set(), [], []
    lines = raw.decode("utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        row = json.loads(line)
        text = row.get("context", "")
        if not isinstance(text, str) or len(text.split()) < minimum:
            continue
        normalized_sha = sha256(" ".join(text.split()).encode("utf-8"))
        if normalized_sha in seen:
            continue
        seen.add(normalized_sha)
        instruction = row.get("instruction", "")
        identifier = f"dolly-context-L{line_number:05d}"
        title = " ".join(instruction.split())[:160]
        url = source["source"]["view_url"] + f"#L{line_number}"
        documents.append({"id": identifier, "title": title, "source_url": url, "text": text})
        metadata.append({"id": identifier, "title": title, "source_url": url,
                         "source_line": line_number, "record_sha256": sha256(line.encode("utf-8")),
                         "text_sha256": sha256(text.encode("utf-8")),
                         "normalized_text_sha256": normalized_sha,
                         "category": row.get("category", ""),
                         "words": len(text.split()), "bytes": len(text.encode("utf-8"))})
        if len(documents) == count:
            break
    if len(documents) != count:
        raise ValueError(f"Dataset contains fewer than {count} eligible distinct passages.")
    return documents, metadata


def _fetch_source(source: dict, cache: Path, fetch=None) -> bytes:
    expected = source["source"]
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (expected["sha256"] + ".jsonl")
    raw = target.read_bytes() if target.is_file() else b""
    if sha256(raw) != expected["sha256"]:
        if fetch is None:
            request = urllib.request.Request(expected["url"], headers={"User-Agent": "nebius-cookbooks"})
            with urllib.request.urlopen(request, timeout=90) as response:
                raw = response.read()
        else:
            raw = fetch(expected["url"])
        if len(raw) != expected["bytes"] or sha256(raw) != expected["sha256"]:
            raise ValueError("Dataset size/checksum differs from the pinned source.")
        _write(target, raw)
    return raw


def prepare(output_dir: Path, cache_dir: Path, *, source_path: Path = SOURCE_PATH, fetch=None) -> dict:
    """Download once, verify the pinned selection, and write four portable files.

    Preparation timing belongs in the caller's run log, not this immutable
    manifest. Existing unrelated files are never overwritten or deleted.
    """
    output, cache, source_path = Path(output_dir), Path(cache_dir), Path(source_path)
    source = _read_json(source_path)
    if output.exists() and (not output.is_dir() or any(p.name not in FILES or not p.is_file() for p in output.iterdir())):
        raise ValueError("Output directory contains unrelated files; choose a new directory.")
    license_bytes = (source_path.parent / "LICENSE").read_bytes()
    card = (source_path.parent / "DATASET_CARD.md").read_bytes()
    attribution = (source_path.parent / "SOURCE.md").read_bytes()
    if sha256(license_bytes) != source["license"]["sha256"]:
        raise ValueError("Bundled license checksum differs from the manifest.")
    if sha256(card) != source["source"]["card_sha256"] or b"license: cc-by-sa-3.0" not in card:
        raise ValueError("Bundled dataset card checksum/license differs from the pinned source.")
    if sha256(attribution) != source["attribution_sha256"]:
        raise ValueError("Bundled attribution checksum differs from the manifest.")
    raw = _fetch_source(source, cache, fetch)
    documents, metadata = _select(raw, source)
    if metadata != source["documents"]:
        raise ValueError("Selected passage IDs or checksums differ from the pinned manifest.")
    payload = b"".join(_json_bytes(document) for document in documents)
    manifest = {"schema": 1, "dataset": source["dataset"], "revision": source["revision"],
                "document_kind": "context passage", "selection": source["selection"],
                "source": source["source"], "license": source["license"],
                "attribution_sha256": source["attribution_sha256"],
                "documents_file": "documents.jsonl", "documents_sha256": sha256(payload),
                "documents": metadata,
                "totals": {"documents": len(documents), "words": sum(d["words"] for d in metadata),
                           "text_bytes": sum(d["bytes"] for d in metadata),
                           "chunks_160_words": sum(_chunk_count(d["text"]) for d in documents)}}
    # Write the completion manifest last, only after source selection is verified.
    _write(output / "documents.jsonl", payload)
    _write(output / "LICENSE", license_bytes)
    _write(output / "SOURCE.md", attribution)
    _write(output / "manifest.json", _json_bytes(manifest))
    return manifest


def manifest_digest(path: Path) -> str:
    """Return the immutable manifest's SHA256 (accepts directory or manifest)."""
    path = Path(path)
    return sha256((path / "manifest.json" if path.is_dir() else path).read_bytes())


def load_documents(path: Path) -> list[dict]:
    """Load the prepared input, refusing a changed or incomplete document file."""
    path = Path(path)
    directory = path if path.is_dir() else path.parent
    manifest = _read_json(directory / "manifest.json")
    raw = (directory / "documents.jsonl").read_bytes()
    if sha256(raw) != manifest["documents_sha256"]:
        raise ValueError("Prepared document checksum changed. Prepare the input again.")
    documents = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    if len(documents) != manifest["selection"]["count"]:
        raise ValueError("Prepared document count differs from the manifest.")
    return documents
