"""Index documents in a Serverless Job; keep results in Object Storage."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sys
import time

from worker.search import QUERY_INSTRUCTION, semantic_rank
from worker.data import load_documents, manifest_digest
from worker.durable import RunConfig, index_documents, inspect_documents, open_store


ROOT = Path(__file__).resolve().parents[1]


def settings_from(path: Path) -> dict:
    settings = json.loads(path.read_text())
    encoder = settings["encoder_settings"]
    if encoder.get("pooling") != "last-token" or encoder.get("normalize") is not True:
        raise ValueError("This encoder requires last-token pooling and normalize=true.")
    revision = settings["model_revision"]
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise ValueError("Pin model_revision to its full commit SHA.")
    return settings


def run_config(data: Path, settings: dict) -> RunConfig:
    return RunConfig(manifest_sha256=manifest_digest(data), model=settings["model"],
                     model_revision=settings["model_revision"], dimensions=settings["dimensions"],
                     chunk_words=settings["chunk_words"], encoder_settings=settings["encoder_settings"])


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def write_search(folder: Path, query: str, matches: list[dict], fingerprint: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    write_json(folder / "search.json", {"query": query, "run_fingerprint": fingerprint, "matches": matches})
    cards = []
    for match in matches:
        title = html.escape(match.get("title", match["source"]))
        url = match.get("viewer_url") or match.get("source_url", "")
        if not url.startswith("https://"):
            raise ValueError("Search source links must use HTTPS.")
        cards.append(f'<article><h2><a href="{html.escape(url, quote=True)}">{title}</a></h2>'
                     f'<p>Similarity {match["similarity"]:.4f}</p><p>{html.escape(match["text"])}</p></article>')
    logo = (ROOT / "docs/brand/nebius-logo.svg").read_text()
    (folder / "search.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Document search with a Nebius Serverless Job</title><style>body{font:17px/1.6 system-ui;max-width:920px;margin:40px auto;padding:0 24px;color:#24271f;background:#fafaf6}'
        'header svg{width:140px;height:auto}article{padding:20px 0;border-bottom:1px solid #ddd}a{color:inherit}</style>'
        f'<header>{logo}<p>Powered by Nebius Serverless AI</p></header><h1>{html.escape(query)}</h1>'
        + ''.join(cards) + '<p>Scores express similarity, not answer confidence.</p>'
        '<footer><p>Passages: <a href="https://huggingface.co/datasets/databricks/databricks-dolly-15k">Databricks Dolly 15k</a>'
        ' (Wikipedia reference text), <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>.</p></footer></html>', encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("index", "verify", "status", "query"):
        c = sub.add_parser(command)
        c.add_argument("--data", type=Path, default=ROOT / "data/job-documents")
        c.add_argument("--store", required=True, help="s3://bucket/prefix; plain local paths are for offline tests")
        c.add_argument("--config", type=Path, default=ROOT / "worker/runtime.json")
        if command != "query":
            c.add_argument("--report", type=Path)
        if command in ("index", "query"):
            c.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
        if command == "index":
            c.add_argument("--batch-size", type=int)
            c.add_argument("--max-new-documents", type=int, help="Save at most this many new documents in this invocation; rerun to continue")
            c.add_argument("--crash-after-chunks", type=int, help="Controlled test: exit 75 after N computed chunks, before the current document is saved")
        if command == "query":
            c.add_argument("--text", required=True)
            c.add_argument("--top-k", type=int, default=5)
            c.add_argument("--output-dir", type=Path, default=Path("results-job-search"))
    return p


def context(args):
    settings = settings_from(args.config)
    documents = load_documents(args.data)
    return settings, documents, run_config(args.data, settings), open_store(args.store)


def progress_message(stats: dict) -> str:
    count = stats["documents_completed"]
    noun = "document" if count == 1 else "documents"
    return (f'{count:,} {noun} already saved, '
            f'{stats["documents_remaining"]:,} to go.')


def index(args) -> None:
    if args.crash_after_chunks is not None and args.crash_after_chunks < 1:
        raise ValueError("--crash-after-chunks must be positive")
    if args.max_new_documents is not None and args.max_new_documents < 1:
        raise ValueError("--max-new-documents must be positive")
    started = time.perf_counter()
    settings, documents, config, store = context(args)
    batch_size = settings["batch_size"] if args.batch_size is None else args.batch_size
    encoder, model_startup_seconds, computed = None, 0.0, 0
    last_progress = None

    def encode(texts):
        nonlocal encoder, model_startup_seconds
        if encoder is None:
            from worker.model import LocalEncoder
            loading = time.perf_counter()
            encoder = LocalEncoder(settings, device=args.device)
            model_startup_seconds = time.perf_counter() - loading
        return encoder(texts)

    def show_progress(stats):
        nonlocal last_progress
        if last_progress is None:
            print(progress_message(stats), flush=True)
        elif (stats["documents_new"] % 50 == 0 or not stats["documents_remaining"]
              or stats["documents_new"] == args.max_new_documents):
            print(f'{stats["documents_completed"]:,} of {stats["documents_total"]:,} documents saved.', flush=True)
        last_progress = stats["documents_completed"]

    def after_chunk(_record):
        nonlocal computed
        computed += 1
        if args.crash_after_chunks is not None and computed >= args.crash_after_chunks:
            print(f"Controlled test stop after {computed:,} computed chunks. "
                  "The unfinished document will run again; saved documents are kept.", flush=True)
            os._exit(75)

    stats = index_documents(documents, store, encode, config, batch_size=batch_size,
                            stop_after_documents=args.max_new_documents,
                            after_chunk_embedded=after_chunk, progress=show_progress)
    # The lazy first embedding call includes initialization; report it separately.
    stats["embedding_seconds"] = max(0.0, stats["embedding_seconds"] - model_startup_seconds)
    record = {**stats, "model_startup_seconds": model_startup_seconds,
              "hardware": encoder.hardware if encoder is not None else {
                  "device": args.device, "model_load_seconds": 0.0, "model_not_loaded": True},
              "batch_size": batch_size, "settings": settings,
              "utc": datetime.now(timezone.utc).isoformat(),
              "application_wall_seconds": time.perf_counter() - started}
    if args.report:
        write_json(args.report, record)
    print(f'Finished: {stats["documents_new"]:,} new, '
          f'{stats["documents_reused"]:,} reused, {stats["documents_remaining"]:,} remaining.')


def status(args) -> None:
    _settings, documents, config, store = context(args)
    stats = inspect_documents(documents, store, config)["stats"]
    if args.report:
        write_json(args.report, stats)
    print(progress_message(stats))


def verify(args) -> None:
    _settings, documents, config, store = context(args)
    stats = inspect_documents(documents, store, config)["stats"]
    if not stats["complete"]:
        raise ValueError("Index is incomplete. " + progress_message(stats) + " Rerun index to continue.")
    if args.report:
        write_json(args.report, stats)
    print(f'All {stats["documents_total"]:,} documents verified.')


def query(args) -> None:
    if not args.text.strip() or not 1 <= args.top_k <= 20:
        raise ValueError("Use a nonempty query and --top-k 1–20")
    settings, documents, config, store = context(args)
    inspected = inspect_documents(documents, store, config)
    if not inspected["stats"]["complete"]:
        raise ValueError("Index is incomplete; rerun index before searching.")
    from worker.model import LocalEncoder
    encoder = LocalEncoder(settings, device=args.device)
    vector = encoder([f"Instruct: {QUERY_INSTRUCTION}\nQuery:{args.text.strip()}"])[0]
    matches = semantic_rank(inspected["records"], vector, args.top_k)
    write_search(args.output_dir, args.text, matches, inspected["stats"]["run_fingerprint"])
    for position, match in enumerate(matches, 1):
        print(f'{position}. {match.get("title", match["source"])} ({match["similarity"]:.4f})\n'
              f'   {match.get("viewer_url") or match.get("source_url", "")}\n   {match["text"][:450]}\n')
    print("Saved report:", args.output_dir / "search.html")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    commands = {"index": index, "status": status, "verify": verify, "query": query}
    try:
        commands[args.command](args)
        return 0
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        # Do not dump credential-bearing requests in a traceback.
        print("Error:", str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
