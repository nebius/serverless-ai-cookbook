"""Run selected upstream offline regression suites in isolated subprocesses."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET

SKILLS = ["analyze-fasta", "affinity-proteomics", "article-data-fetcher", "eqtl-catalogue-region-fetch",
          "gwas-catalog-region-fetch", "ld-1000g-region-compute", "locuscompare-region-render",
          "rnaseq-de", "scrna-orchestrator", "proteomics-de"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.root, args.output = args.root.resolve(), args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "PYTHONPATH": str(args.root / "source"), "OPENBLAS_NUM_THREADS": "1",
           "OMP_NUM_THREADS": "1", "NUMBA_NUM_THREADS": "1", "MPLBACKEND": "Agg"}

    def run(name):
        folder = args.root / "source/skills" / name
        tests = [str(p) for p in sorted((folder / "tests").glob("test_*.py")) if not p.name.startswith("test_live_")]
        xml = args.output / f"{name}.xml"
        command = [sys.executable, "-m", "pytest", "-q", "--import-mode=importlib", *tests, f"--junitxml={xml}"]
        process = subprocess.Popen(command, cwd=folder, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            raw, _ = process.communicate(timeout=180)
            result = {"name": name, "exit_code": process.returncode}
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            raw, _ = process.communicate()
            result = {"name": name, "exit_code": None, "error": "timeout"}
        (args.output / f"{name}.log").write_bytes(raw)
        if xml.exists():
            suites = ET.parse(xml).getroot().findall("testsuite")
            result.update({key: sum(int(s.get(key, "0")) for s in suites)
                           for key in ("tests", "failures", "errors", "skipped")})
        print(json.dumps(result), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, SKILLS))
    (args.output / "report.json").write_text(json.dumps({"scope": "Selected upstream offline regression suites", "results": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
