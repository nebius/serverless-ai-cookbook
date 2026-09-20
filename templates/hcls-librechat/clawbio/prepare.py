"""Prepare pinned ClawBio source and namespaced LibreChat skills for the image.

Reads committed Git blobs, not the supplied checkout's writable working tree.
Generated files live in the existing ignored vendor build directory. No upstream
bot, credentials, unrelated skill, or proprietary component enters the image.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def git(source: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(source), *args])


def prepare(source: Path, destination: Path) -> dict:
    source, destination = source.resolve(), destination.resolve()
    selection = json.loads((HERE / "selection.json").read_text())
    revision = selection["revision"]
    if git(source, "rev-parse", "HEAD").decode().strip() != revision:
        raise ValueError("ClawBio source is not the pinned revision")
    catalog = json.loads(git(source, "show", f"{revision}:skills/catalog.json"))
    records = {row["name"]: row for row in catalog["skills"]}
    local, hosted, excluded = set(selection["local"]), set(selection["platform"]), set(selection["excluded"])
    support = set(selection.get("support_source", []))
    for name in local | hosted | support:
        if records[name]["license"] not in {"MIT", "Apache-2.0"}:
            raise ValueError(f"Unreviewed redistribution license: {name}")
    if local & hosted or local & excluded or hosted & excluded or local | hosted | excluded != set(records):
        raise ValueError("Every upstream skill needs exactly one explicit disposition")
    if destination.exists():
        raise FileExistsError("Use a fresh generated bundle directory; no source is overwritten")
    destination.mkdir(parents=True)
    root = destination / "source"
    manifest = {"schema": "scientific-ai/clawbio-bundle/v1", "repository": selection["repository"],
                "revision": revision, "skills": {}, "excluded": selection["excluded"], "files": {}}
    paths = git(source, "ls-tree", "-r", "--name-only", revision).decode().splitlines()
    for name in paths:
        path = Path(name)
        keep = (name in {"LICENSE", "CITATION.cff", "clawbio.py", "skills/catalog.json", "docs/data-handling.md"}
                or path.parts[0] in {"clawbio", "examples"}
                or (path.parts[0] == "skills" and len(path.parts) > 2 and path.parts[1] in local | hosted | support))
        if not keep or any(part.startswith(".") or part == "__pycache__" for part in path.parts):
            continue
        data = git(source, "show", f"{revision}:{name}")
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["files"][name] = hashlib.sha256(data).hexdigest()

    # Read registry paths from the pinned copied source, not the current host.
    sys.path.insert(0, str(root))
    from clawbio.cli import SKILLS

    for name in sorted(local | hosted):
        record = records[name]
        if record["license"] not in {"MIT", "Apache-2.0"}:
            raise ValueError(f"Unreviewed redistribution license: {name}")
        mode = "platform" if name in hosted else "local"
        alias = record.get("cli_alias")
        if mode == "platform":
            entrypoint = None
        elif alias:
            entrypoint = str(SKILLS[alias]["script"].relative_to(root))
        else:
            import shlex
            words = shlex.split(record["demo_command"])
            if words[0] not in {"python", "python3"} or not words[1].startswith(f"skills/{name}/"):
                raise ValueError(f"Unsupported standalone entry point: {name}")
            entrypoint = words[1]
        if entrypoint and not (root / entrypoint).is_file():
            raise ValueError(f"Missing executable source: {name}")
        skill_dir = destination / "skills" / ("clawbio-" + name)
        refs = skill_dir / "references"
        refs.mkdir(parents=True)
        upstream = (root / "skills" / name / "SKILL.md").read_text()
        (refs / "upstream.md").write_text(upstream)
        adaptation = selection.get("adaptations", {}).get(name, {})
        guidance = selection["platform"][name]["guidance"] if mode == "platform" else (
            "Use `execute_command` to run the installed CPU workflow. "
            f"Inspect `/opt/clawbio-venv/bin/python /opt/clawbio/runner.py help {name}` first; "
            "arguments differ between skills. Then run "
            f"`/opt/clawbio-venv/bin/python /opt/clawbio/runner.py run {name} -- "
            "<skill arguments> --output /data/clawbio-runs/<unique-run>`. "
            "Pass absolute paths to actual user files, not invented paths. "
            "Use --demo only when the user requests an example, never as a substitute for their data. "
            "Missing optional tools/data are explicit limitations; do not replace a real analysis with a synthetic demo."
        )
        description = record["description"].replace("\n", " ")
        text = f'''---
name: clawbio-{name}
description: {json.dumps(description)}
license: {record["license"]}
---

# ClawBio: {name}

Read [the upstream scientific method and input/output contract](references/upstream.md)
when using this skill. Deployment instructions below override upstream installation,
paths and model-serving examples, not the scientific method.

{guidance}

{adaptation.get("limitations", "")}

The skill is bundled, but that is not a claim of validation for every dataset or
clinical use. Check the exact installed coverage using
`/opt/clawbio-venv/bin/python /opt/clawbio/runner.py describe {name}`.
The original source is `/opt/clawbio/source/skills/{name}`; interpret its relative
paths from `/opt/clawbio/source`, not from `/workspace`.

For long work, keep the execute_command job ID and observe it with read_execution;
do not launch another copy after a chat timeout. Stage seekable scientific files
on local `/data` storage, then publish closed outputs to the caller's `/workspace`
bucket with the existing workspace/export tools, verifying file sizes and hashes.
Local `/data` is not durable across instance replacement.

Before a networked analysis, consult `/opt/clawbio/source/docs/data-handling.md`:
some annotation tools send variants or gene lists to external services. Explain
the destination/data to the user; do not describe those runs as local-only.
Never copy sample keys from upstream documentation. Use public-source retrieval
for literature; use the existing Token Factory agent for summaries, not an
unconfigured OpenAI/Ollama backend.

Use source-linked evidence and retain limitations, warnings and failed cases.
Clinical/genetic interpretations are research outputs, not medical decisions.
Do not treat demo success, confidence scores, ancestry estimates, associations,
or in-silico rankings as proof of diagnosis, causality or efficacy.

Upstream: {selection["repository"]}/tree/{revision}/skills/{name}
Attribution and original license are retained with the source and bundle manifest.
'''
        (skill_dir / "SKILL.md").write_text(text)
        manifest["skills"][name] = {"mode": mode, "alias": alias, "entrypoint": entrypoint,
                                     "description": description, "license": record["license"],
                                     "upstream_maturity": record["maturity_tier"],
                                     "dependencies": record["dependencies"],
                                     "models": selection["platform"].get(name, {}).get("models", []),
                                     "adapter": adaptation.get("adapter"),
                                     "limitations": adaptation.get("limitations", ""),
                                     "qualification": "not-yet-tested"}
    (destination / "qualification.json").write_text(json.dumps({
        "revision": revision, "scope": "Prepared source only; no runtime probes recorded", "results": []
    }, indent=2) + "\n")
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({"revision": result["revision"], "installed_skills": len(result["skills"]),
                      "excluded_skills": len(result["excluded"]), "source_files": len(result["files"])}))
