"""One immutable run description and one complete JSON result per document.

Use one writer per dedicated prefix. A failed/unfinished document is recomputed;
previously saved documents are skipped. No cross-writer lock is provided.
"""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit


class DurableError(RuntimeError):
    pass


def _bytes(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()


@dataclass(frozen=True)
class RunConfig:
    manifest_sha256: str
    model: str
    model_revision: str
    dimensions: int
    chunk_words: int = 160
    encoder_settings: dict = field(default_factory=dict)


def index_documents(documents, store, embed_fn, config, *, batch_size=16,
                    stop_after_documents=None, after_chunk_embedded=None, progress=None):
    started = time.perf_counter()
    if (type(batch_size) is not int or batch_size < 1 or
            (stop_after_documents is not None and (type(stop_after_documents) is not int or stop_after_documents < 1))):
        raise DurableError("Batch size and document limit must be positive integers.")
    run, plan, results, exists = _load(documents, store, config)
    timing = {"scan_seconds": time.perf_counter() - started, "embedding_seconds": 0.0, "save_seconds": 0.0}
    reused_docs, reused_chunks = len(results), sum(len(r["chunks"]) for r in results.values())
    stats = lambda: _stats(run, plan, results, reused_docs, reused_chunks, timing, started)
    if progress:
        progress(stats())
    if not exists:
        saving = time.perf_counter()
        store.put_json("run.json", run)
        timing["save_seconds"] += time.perf_counter() - saving
    pending = [(k, identifier, chunks) for k, identifier, chunks in plan if k not in results]
    for key, identifier, chunks in pending[:stop_after_documents]:
        records = []
        for offset in range(0, len(chunks), batch_size):
            batch = chunks[offset:offset + batch_size]
            embedding = time.perf_counter()
            vectors = embed_fn([chunk["text"] for chunk in batch])
            if not isinstance(vectors, (list, tuple)) or len(vectors) != len(batch):
                raise DurableError("Encoder returned an incomplete batch.")
            vectors = [_vector(v, config.dimensions) for v in vectors]
            timing["embedding_seconds"] += time.perf_counter() - embedding
            for chunk, vector in zip(batch, vectors):
                record = {**chunk, "vector": vector}
                if after_chunk_embedded:
                    after_chunk_embedded(record)
                records.append(record)
        saving = time.perf_counter()
        # A document is done only after its complete result has been saved.
        store.put_json(key, {"document_id": identifier, "run_fingerprint": run["run_fingerprint"], "chunks": records})
        timing["save_seconds"] += time.perf_counter() - saving
        results[key] = {"chunks": records}
        if progress:
            progress(stats())
    return stats()


class JSONStore:
    def get_json(self, key):
        raw = self.get(key)
        return None if raw is None else json.loads(raw)

    def put_json(self, key, value):
        self.put(key, _bytes(value))


class LocalStore(JSONStore):
    """Atomic files for offline tests or a durable local disk."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, key):
        try:
            return (self.root / key).read_bytes()
        except FileNotFoundError:
            return None

    def put(self, key, value):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(value)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def keys(self):
        return [p.relative_to(self.root).as_posix() for p in self.root.rglob("*")
                if p.is_file() and not p.name.startswith(".pending-")]


class S3Store(JSONStore):
    def __init__(self, uri, *, endpoint_url=None, client=None):
        parsed = urlsplit(uri)
        self.bucket, self.prefix = parsed.netloc, parsed.path.strip("/")
        endpoint_url = endpoint_url or os.environ.get("S3_ENDPOINT_URL")
        endpoint = urlsplit(endpoint_url or "")
        if (parsed.scheme != "s3" or not self.bucket or not self.prefix or parsed.username
                or parsed.query or parsed.fragment or endpoint.scheme != "https"
                or not endpoint.hostname or endpoint.username or endpoint.query or endpoint.fragment):
            raise DurableError("Use s3://bucket/prefix and an explicit HTTPS S3_ENDPOINT_URL.")
        if client is None:
            import boto3
            client = boto3.client("s3", endpoint_url=endpoint_url)
        self.client = client

    def _call(self, action, **kwargs):
        try:
            return getattr(self.client, action)(Bucket=self.bucket, **kwargs)
        except Exception as exc:
            error = getattr(exc, "response", {})
            error = error.get("Error", {}) if isinstance(error, dict) else {}
            code = error.get("Code") if isinstance(error, dict) else None
            code = code if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", code) else "Unknown"
            if action == "get_object" and code in {"NoSuchKey", "NotFound", "404"}:
                return None
            raise DurableError(f"Object Storage request failed ({code}); check access and connectivity.") from None

    def get(self, key):
        result = self._call("get_object", Key=f"{self.prefix}/{key}")
        if result is None:
            return None
        try:
            return result["Body"].read()
        finally:
            result["Body"].close()

    def put(self, key, value):
        self._call("put_object", Key=f"{self.prefix}/{key}", Body=value)

    def keys(self):
        keys, token = [], None
        while True:
            args = {"Prefix": self.prefix + "/", **({"ContinuationToken": token} if token else {})}
            result = self._call("list_objects_v2", **args)
            keys.extend(item["Key"][len(self.prefix) + 1:] for item in result.get("Contents", []))
            if not result.get("IsTruncated"):
                return keys
            token = result["NextContinuationToken"]


def open_store(uri, *, endpoint_url=None, client=None):
    return S3Store(str(uri), endpoint_url=endpoint_url, client=client) if str(uri).startswith("s3://") else LocalStore(uri)



def _pack(text, words):
    packed, current = [], []
    for paragraph in [p.split() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]:
        if current and len(current) + len(paragraph) > words:
            packed.append(" ".join(current))
            current = []
        while len(paragraph) > words:
            packed.append(" ".join(paragraph[:words]))
            paragraph = paragraph[words:]
        current.extend(paragraph)
    if current:
        packed.append(" ".join(current))
    return packed


def _vector(value, dimensions):
    if (not isinstance(value, list) or len(value) != dimensions
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
        raise DurableError("Embedding has wrong dimensions or non-finite values.")
    return value


def _load(documents, store, config):
    if (not documents or len({d["id"] for d in documents}) != len(documents)
            or type(config.dimensions) is not int or config.dimensions < 1
            or type(config.chunk_words) is not int or not 10 <= config.chunk_words <= 500):
        raise DurableError("Use unique documents, positive dimensions and chunk_words between 10 and 500.")
    fingerprint = hashlib.sha256(_bytes({"documents": documents, "config": asdict(config)})).hexdigest()
    run = {"storage_version": 2, "run_fingerprint": fingerprint, "settings": asdict(config)}
    plan = []
    for doc in documents:
        chunks = [{"id": f'{doc["id"]}:{i}', "document_id": doc["id"], "source": doc["id"],
                   "title": doc["title"], "source_url": doc["source_url"], "chunk_index": i, "text": text}
                  for i, text in enumerate(_pack(doc["text"], config.chunk_words))]
        if not chunks:
            raise DurableError("Documents must contain nonempty text.")
        key = "documents/" + hashlib.sha256(doc["id"].encode()).hexdigest() + ".json"
        plan.append((key, doc["id"], chunks))
    keys, results = set(store.keys()), {}
    if "run.json" in keys and store.get_json("run.json") != run:
        raise DurableError("Data/settings changed or legacy storage format. Use a fresh store/prefix.")
    if keys - ({"run.json"} | {key for key, _, _ in plan}) or (keys and "run.json" not in keys):
        raise DurableError("Unexpected or legacy objects. Use a fresh store/prefix.")
    for key, identifier, chunks in plan:
        if key not in keys:
            continue
        saved = store.get_json(key)
        if (not isinstance(saved, dict) or saved.get("run_fingerprint") != fingerprint
                or saved.get("document_id") != identifier or not isinstance(saved.get("chunks"), list)
                or len(saved["chunks"]) != len(chunks)):
            raise DurableError("Saved document is incomplete or belongs to a different run.")
        for expected, record in zip(chunks, saved["chunks"]):
            if not isinstance(record, dict) or any(record.get(k) != v for k, v in expected.items()):
                raise DurableError("Saved document metadata differs from its input.")
            _vector(record.get("vector"), config.dimensions)
        results[key] = saved
    return run, plan, results, "run.json" in keys


def _stats(run, plan, results, reused_docs, reused_chunks, timing, started):
    total = sum(len(chunks) for _, _, chunks in plan)
    saved = sum(len(result["chunks"]) for result in results.values())
    return {"run_fingerprint": run["run_fingerprint"], "documents_total": len(plan),
            "documents_completed": len(results), "documents_reused": reused_docs,
            "documents_new": len(results) - reused_docs, "documents_remaining": len(plan) - len(results),
            "chunks_total": total, "chunks_saved": saved, "chunks_reused": reused_chunks,
            "chunks_new": saved - reused_chunks, "chunks_remaining": total - saved,
            "complete": len(results) == len(plan), **timing, "wall_seconds": time.perf_counter() - started}


def inspect_documents(documents, store, config):
    started = time.perf_counter()
    run, plan, results, _ = _load(documents, store, config)
    timing = {"scan_seconds": time.perf_counter() - started, "embedding_seconds": 0.0, "save_seconds": 0.0}
    return {"stats": _stats(run, plan, results, len(results), sum(len(r["chunks"]) for r in results.values()), timing, started),
            "records": [chunk for key, _, _ in plan if key in results for chunk in results[key]["chunks"]]}


def load_records(documents, store, config, *, require_complete=True):
    result = inspect_documents(documents, store, config)
    if require_complete and not result["stats"]["complete"]:
        raise DurableError("Collection is incomplete; finish indexing before querying.")
    return result["records"]
