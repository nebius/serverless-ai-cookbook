#!/usr/bin/env python3
"""Render or apply a reviewed campaign control-plane release over live values."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess

import yaml

from manage_campaign import KUBECONFIG, CONTEXT, save

HELM = ["helm", "--kubeconfig", KUBECONFIG, "--kube-context", CONTEXT, "-n", "fs2-system"]
RELEASE = "fs2-serve-control-plane"


def run(command):
    return subprocess.check_output(command, text=True)


def textfile(path, text):
    path.write_text(text)
    path.chmod(0o600)


def resources(text):
    return {(r["kind"], r["metadata"]["name"]): r for r in yaml.safe_load_all(text) if r}


def differences(old, new, path=""):
    if isinstance(old, dict) and isinstance(new, dict):
        return [change for key in sorted(old.keys() | new.keys())
                for change in differences(old.get(key), new.get(key), path + "/" + key)]
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [change for index, (a, b) in enumerate(zip(old, new))
                for change in differences(a, b, path + "/" + str(index))]
    return [] if old == new else [path]


def merged_values(original, delta):
    result = copy.deepcopy(original)
    for key, value in delta.items():
        result[key] = merged_values(result.get(key, {}), value) if isinstance(value, dict) else copy.deepcopy(value)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "apply"))
    parser.add_argument("--chart", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--values-delta", type=Path, help="Reviewed optional retained-configuration reference changes")
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    old_values = json.loads(run(HELM + ["get", "values", RELEASE, "-o", "json"]))
    before = run(HELM + ["get", "manifest", RELEASE]) + "\n---\n" + run(HELM + ["get", "hooks", RELEASE])
    status = json.loads(run(HELM + ["status", RELEASE, "-o", "json"]))
    if status["info"]["status"] != "deployed":
        raise ValueError("Wait for the active Helm transaction or recovery before preparing/applying another release")
    if args.action == "prepare":
        save(args.output / "before-values.json", old_values)
        save(args.output / "before-status.json", status)
        textfile(args.output / "before-manifest.yaml", before)
        after_values = {**old_values, "image": {**old_values["image"], "digest": args.digest}}
        if args.values_delta:
            after_values = merged_values(after_values, json.loads(args.values_delta.read_text()))
        if after_values["image"]["digest"] != args.digest:
            raise ValueError("Values delta must not change the requested immutable image")
        save(args.output / "after-values.json", after_values)
        after = run(HELM + ["template", RELEASE, str(args.chart), "--is-upgrade", "-f", str(args.output / "after-values.json")])
        textfile(args.output / "rendered-manifest.yaml", after)
        old, new = resources(before), resources(after)
        if old.keys() != new.keys():
            raise ValueError("Unexpected resource addition/removal in image-only release")
        changes = {kind + "/" + name: differences(old[kind, name], new[kind, name]) for kind, name in old}
        changes = {k: v for k, v in changes.items() if v}
        save(args.output / "changed-paths.json", changes)
        print(json.dumps({"previous_revision": status["version"], "changes": changes}, indent=2))
    else:
        receipt = json.loads((args.output / "before-status.json").read_text())
        if status["version"] != receipt["version"]:
            raise ValueError("Helm release changed after the prepared plan")
        values = json.loads((args.output / "after-values.json").read_text())
        if values["image"]["digest"] != args.digest:
            raise ValueError("Image digest differs from prepared plan")
        print(run(HELM + ["upgrade", RELEASE, str(args.chart), "-f", str(args.output / "after-values.json"),
                         "--atomic", "--wait", "--timeout", "10m"]), flush=True)
        save(args.output / "after-status.json", json.loads(run(HELM + ["status", RELEASE, "-o", "json"])))


if __name__ == "__main__":
    main()
