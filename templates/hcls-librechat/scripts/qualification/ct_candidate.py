#!/usr/bin/env python3
"""Render a task-owned CT candidate with read-only weights and private caches.

No production Service labels are inherited. This generator does not apply the
candidate or create any storage, credentials, node group, or public endpoint.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from manage_campaign import save

MODEL = "nv-segment-ct"
NAME = "fs2-ct-point-candidate-20260918"


def render(configmaps: dict, image: str) -> dict:
    if "@sha256:" not in image or len(image.rsplit("@sha256:", 1)[1]) != 64:
        raise ValueError("Candidate image must be digest-pinned")
    bundles = next(json.loads(cm["data"]["renderer-bundles.json"])
                   for cm in configmaps["items"] if "renderer-bundles.json" in cm.get("data", {}))
    matches = [bundle for bundle in bundles if bundle["modelRef"] == MODEL]
    if len(matches) != 1:
        raise ValueError("Expected one unchanged CT baseline bundle")
    deployment = next(resource for resource in matches[0]["resources"] if resource["kind"] == "Deployment")
    spec = copy.deepcopy(deployment["spec"]["template"]["spec"])
    if len(spec["containers"]) != 1 or spec["containers"][0]["name"] != "server":
        raise ValueError("Unexpected CT runtime shape")
    spec.pop("initContainers", None)
    spec["restartPolicy"] = "Never"
    spec["activeDeadlineSeconds"] = 3600
    spec["nodeSelector"]["accelerator.fs2.nebius/pool-id"] = "h100-1x"
    server = spec["containers"][0]
    if server.get("command") != ["/opt/fs2-media-venv/bin/python", "/opt/fs2-media/nv_segment_ct_server.py"]:
        raise ValueError("Refuse to inherit a checkpoint wrapper")
    server["image"] = image
    caches = {"CUDA_CACHE_PATH": "cuda", "TORCHINDUCTOR_CACHE_DIR": "torchinductor",
              "TORCH_EXTENSIONS_DIR": "torch-extensions", "TRITON_CACHE_DIR": "triton"}
    for env in server["env"]:
        if env["name"] in caches:
            env["value"] = "/runtime-cache/" + caches[env["name"]]
    server["env"].append({"name": "HF_HUB_OFFLINE", "value": "1"})
    for volume in spec["volumes"]:
        if "persistentVolumeClaim" in volume:
            volume["persistentVolumeClaim"]["readOnly"] = True
    for mount in server["volumeMounts"]:
        if mount["name"] == "model-cache":
            mount["readOnly"] = True
    return {"apiVersion": "v1", "kind": "Pod", "metadata": {
        "name": NAME, "namespace": "fs2-models",
        "labels": {"fs2.nebius/task": "fs2-science-ct-point-repair-r20260918"},
        "annotations": {"fs2.nebius/qualification-scope": "isolated-runtime-not-public-readiness",
                        "fs2.nebius/baseline-template-digest": matches[0]["templateDigest"]}}, "spec": spec}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configmaps", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--name", default=NAME)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Refusing to overwrite a retained candidate")
    if not args.name.startswith("fs2-ct-point-candidate-") or len(args.name) > 63:
        raise ValueError("Candidate name must remain task-owned")
    pod = render(json.loads(args.configmaps.read_text()), args.image)
    pod["metadata"]["name"] = args.name
    save(args.output, pod)
    print(json.dumps({"pod": args.name, "output": str(args.output), "applied": False}))


if __name__ == "__main__":
    main()
