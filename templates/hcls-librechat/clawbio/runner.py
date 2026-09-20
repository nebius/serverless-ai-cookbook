"""Run installed ClawBio workflows without a second MCP server or GPU stack."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import certifi

ROOT = Path(os.environ.get("SCIENTIFIC_CLAWBIO_ROOT", "/opt/clawbio"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["list", "describe", "help", "run"])
    parser.add_argument("skill", nargs="?")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        workers = int(os.environ.get("SCIENTIFIC_CLAWBIO_CPUS", "1"))
        if workers < 1:
            raise ValueError()
    except ValueError:
        parser.error("SCIENTIFIC_CLAWBIO_CPUS must be a positive integer")
    manifest = json.loads((ROOT / "manifest.json").read_text())
    if args.action == "list":
        print(json.dumps({"revision": manifest["revision"], "skills": [
            {"name": name, "mode": item["mode"], "qualification": item["qualification"]}
            for name, item in manifest["skills"].items()]}, indent=2))
        return 0
    if args.skill not in manifest["skills"]:
        parser.error("Skill is not included in this image; consult clawbio/selection.json")
    item = manifest["skills"][args.skill]
    if args.action == "describe":
        print(json.dumps({"name": args.skill, "revision": manifest["revision"], **item}, indent=2))
        return 0
    if item["mode"] == "platform":
        parser.error("Use the hosted App via the installed skill and live schema, not a local GPU runtime")
    source = ROOT / "source"
    script = (source / item["entrypoint"]).resolve()
    if not script.is_relative_to(source.resolve()) or not script.is_file():
        parser.error("Installed entry point is invalid")
    extra = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    adapter = [sys.executable, str(Path(__file__).with_name("adapters.py")), args.skill] if item.get("adapter") else None
    if args.action == "help":
        command = [*(adapter or [sys.executable, str(script)]), "--help"]
        workdir = source
    else:
        if "--output" not in extra or extra.index("--output") + 1 == len(extra):
            parser.error("Pass --output with a fresh absolute local staging directory")
        if extra.count("--output") != 1 or any(x == "-o" or x.startswith("--output=") for x in extra):
            parser.error("Pass exactly one --output argument")
        out = Path(extra[extra.index("--output") + 1])
        if not out.is_absolute() or (out.exists() and (not out.is_dir() or any(out.iterdir()))):
            parser.error("Output must be a fresh absolute directory; existing results are not overwritten")
        if args.skill == "fine-mapping" and ("--demo" in extra or any(x.split("=", 1)[0] == "--ld" for x in extra)):
            parser.error("Only Wakefield ABF without LD is installed; SuSiE is not installed")
        # Use the skill's actual argparse contract, the same one shown by help.
        # The generic upstream dispatcher incorrectly rejects valid native
        # inputs such as RNA-seq --counts/--metadata without an extra --input.
        command = [*(adapter or [sys.executable, str(script)]), *extra]
        # Tabix and some upstream tools save caches in cwd. Keep those with
        # this run rather than modifying packaged source or another run.
        out.mkdir(parents=True, exist_ok=True)
        workdir = out
    env = {**os.environ, "PYTHONPATH": str(source), "MPLBACKEND": "Agg",
           "SCIENTIFIC_CLAWBIO_CPUS": str(workers),
           "OPENBLAS_NUM_THREADS": str(workers), "OMP_NUM_THREADS": str(workers), "NUMBA_NUM_THREADS": str(workers),
           "PLINK_BIN": os.environ.get("PLINK_BIN", "plink1.9")}
    # The manylinux pysam wheel's libcurl can otherwise use a missing build-host
    # CA path. Keep verification enabled and use the bundled certificate roots.
    env.setdefault("CURL_CA_BUNDLE", certifi.where())
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    return subprocess.run(command, cwd=workdir, env=env, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
