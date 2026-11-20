"""Bootstrap the document-indexing recipe inside a PyTorch Serverless Job."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import quote
from urllib.request import urlopen
import uuid

WORKSPACE = Path("/workspace/document-search")
FILES = (
    "worker/__init__.py", "worker/cli.py", "worker/data.py", "worker/durable.py", "worker/model.py",
    "worker/requirements.txt", "worker/runtime.json", "worker/data/source.json", "worker/data/LICENSE",
    "worker/data/DATASET_CARD.md", "worker/data/SOURCE.md", "scripts/prepare_job_data.py",
    "worker/search.py", "docs/brand/nebius-logo.svg",
)
DEFAULT_QUERY = "What is stalemate in chess?"


def fetch_recipe(folder):
    ref = quote(os.environ.get("RECIPE_REF", "main"), safe="")
    base = f"https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/{ref}/inference/document-search/"
    for name in FILES:
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(base + name, timeout=60) as response:
            target.write_bytes(response.read())


def load_worker(folder):
    sys.path.insert(0, str(folder))
    from worker.data import prepare
    from worker.cli import main
    from worker.durable import open_store
    return prepare, main, open_store


def main():
    started = time.perf_counter()
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    fetch_recipe(WORKSPACE)
    # The trusted PyTorch image already supplies the pinned Torch/CUDA runtime.
    packages = [line for line in (WORKSPACE / "worker/requirements.txt").read_text().splitlines()
                if line.strip() and not line.startswith(("torch", "#"))]
    subprocess.run([sys.executable, "-m", "pip", "install", *packages], check=True)
    prepare, cli, open_store = load_worker(WORKSPACE)
    setup_seconds = time.perf_counter() - started
    preparing = time.perf_counter()
    prepare(WORKSPACE / "data/job-documents", WORKSPACE / ".state/job-data-cache")
    preparation_seconds = time.perf_counter() - preparing
    print(json.dumps({"setup_seconds": setup_seconds, "preparation_seconds": preparation_seconds}), flush=True)
    run_root = os.environ["RUN_ROOT"].rstrip("/")
    report_file = WORKSPACE / ".state/index.json"
    args = ["index", "--store", run_root + "/index", "--report", str(report_file)]
    limit = int(os.environ.get("MAX_NEW_DOCUMENTS", "0"))
    if limit:
        args += ["--max-new-documents", str(limit)]
    if os.environ.get("CRASH_AFTER_CHUNKS"):
        args += ["--crash-after-chunks", os.environ["CRASH_AFTER_CHUNKS"]]
    code = cli(args)
    if code:
        return code
    report = json.loads(report_file.read_text())
    report.update(setup_seconds=setup_seconds, preparation_seconds=preparation_seconds)
    outputs = open_store(run_root + "/outputs")
    report_name = uuid.uuid4().hex + ".json"
    outputs.put_json(report_name, report)
    print("Run report:", run_root + "/outputs/" + report_name, flush=True)
    if report["complete"]:
        result_dir = WORKSPACE / "results-job-search"
        code = cli(["query", "--store", run_root + "/index", "--text",
                    os.environ.get("SEARCH_QUERY", DEFAULT_QUERY), "--output-dir", str(result_dir)])
        if code:
            return code
        for name in ("search.json", "search.html"):
            outputs.put(name, (result_dir / name).read_bytes())
            print("Search result:", run_root + "/outputs/" + name, flush=True)
    print(json.dumps({key: report[key] for key in (
        "documents_total", "documents_completed", "documents_reused", "documents_new", "documents_remaining",
        "chunks_saved", "setup_seconds", "preparation_seconds")} | {
        "job_elapsed_seconds": time.perf_counter() - started}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
