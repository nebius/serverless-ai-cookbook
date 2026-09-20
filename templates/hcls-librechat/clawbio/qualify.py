"""Bounded installed-bundle probes; demo execution is not scientific validation."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import signal
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--record", action="store_true", help="Save probe evidence/status in the generated bundle")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((args.root / "manifest.json").read_text())
    env = {**os.environ, "SCIENTIFIC_CLAWBIO_ROOT": str(args.root.resolve()),
           "MPLCONFIGDIR": str(args.output / "matplotlib-cache"), "OPENBLAS_NUM_THREADS": "1"}

    def probe(pair):
        name, spec = pair
        if spec["mode"] == "platform":
            return {"name": name, "status": "hosted-guidance-only", "hosted_model_calls": 0}
        entry = {"name": name}
        for action in ("help", "demo"):
            command = [sys.executable, str(args.runner), "help" if action == "help" else "run", name]
            if action == "demo":
                command += ["--", "--demo", "--output", str((args.output / name).resolve())]
                if name == "article-data-fetcher":
                    entry[action] = {"exit_code": None, "error": "No headless upstream demo; adapter unit-tested separately"}
                    continue
                if name == "claw-methylation-cycle":
                    command += ["--input", str((args.root / "source/skills/claw-methylation-cycle/demo_input.txt").resolve())]
                if name == "equity-scorer":
                    command.remove("--demo")
                    command += ["--input", str((args.root / "source/examples/demo_populations.vcf").resolve()),
                                "--pop-map", str((args.root / "source/examples/demo_population_map.csv").resolve())]
                if name == "fine-mapping":
                    fixture = args.output / "abf-fixture.tsv"
                    fixture.write_text("rsid\tz\tse\tchr\tpos\nrsA\t1\t0.1\t1\t100\nrsB\t5\t0.1\t1\t200\nrsC\t2\t0.1\t1\t300\n")
                    command.remove("--demo")
                    command += ["--sumstats", str(fixture.resolve()), "--no-figures"]
            started = time.monotonic()
            try:
                process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                raw, _ = process.communicate(timeout=args.timeout)
                (args.output / f"{name}-{action}.log").write_bytes(raw)
                entry[action] = {"exit_code": process.returncode, "seconds": round(time.monotonic() - started, 3),
                                 "log_sha256": hashlib.sha256(raw).hexdigest(),
                                 "warnings": [line[-500:] for line in raw.decode(errors="replace").splitlines()
                                              if "warning" in line.lower()][:12]}
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                raw, _ = process.communicate()
                (args.output / f"{name}-{action}.log").write_bytes(raw)
                entry[action] = {"exit_code": None, "seconds": args.timeout, "error": "timeout"}
        folder = args.output / name
        files = [{"path": str(path.relative_to(folder)), "bytes": path.stat().st_size,
                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                 for path in sorted(folder.rglob("*")) if path.is_file()] if folder.exists() else []
        entry["outputs"] = files
        entry["status"] = "example-executed" if entry["help"]["exit_code"] == entry["demo"]["exit_code"] == 0 and files else "not-runtime-qualified"
        if name == "fine-mapping":
            entry["example"] = "Custom ABF-only fixture; not the upstream SuSiE demo"
        print(json.dumps({"name": name, "status": entry["status"], "files": len(files)}), flush=True)
        return entry

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(probe, manifest["skills"].items()))
    report = {"schema": "scientific-ai/clawbio-probes/v1", "revision": manifest["revision"],
              "scope": "Installed CLI and upstream demo probes; not all user-data paths or scientific validity",
              "results": results}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if args.record:
        # Generated bundle only, not upstream source or tracked selection.
        for result in results:
            manifest["skills"][result["name"]]["qualification"] = result["status"]
        evidence = json.dumps(report, indent=2) + "\n"
        (args.root / "qualification.json").write_text(evidence)
        manifest["qualification_sha256"] = hashlib.sha256(evidence.encode()).hexdigest()
        manifest["integration_sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                          for path in (args.runner, args.runner.with_name("adapters.py"),
                                                       args.runner.with_name("requirements.lock"))}
        (args.root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"total": len(results), "example_executed": sum(r["status"] == "example-executed" for r in results),
                      "not_runtime_qualified": [r["name"] for r in results if r["status"] == "not-runtime-qualified"]}))


if __name__ == "__main__":
    main()
