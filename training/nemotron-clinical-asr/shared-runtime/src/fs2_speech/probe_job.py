"""Render, but never apply, a bounded task-owned GPU diagnostic Job."""

import argparse
import json
import re

from .contracts import MODELS, RuntimeProfile


def render_job(*, name: str, namespace: str, image: str, profile: RuntimeProfile,
               gpu_class: str, preemptible: bool = True) -> dict:
    for value in (name, namespace):
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value):
            raise ValueError("Job and namespace must be DNS labels")
    if not name.startswith("fs2-speech-probe-"):
        raise ValueError("diagnostic job name must start with fs2-speech-probe-")
    if not re.fullmatch(r"[^\s@]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("image must be pinned by sha256 digest")
    if not gpu_class:
        raise ValueError("select an explicitly inventoried GPU class")
    baseline = RuntimeProfile(model=profile.model, chunk_size_ms=profile.chunk_size_ms, precision=profile.precision)
    if profile != baseline:
        raise ValueError("diagnostic CLI currently supports baseline decoding/tag/confidence settings only")
    labels = {
        "app.kubernetes.io/name": "fs2-speech-probe",
        "app.kubernetes.io/part-of": "fs2-serve",
        "workload.fs2.nebius/owner": "nemotron-speech-20260916",
    }
    selector = {"accelerator.fs2.nebius/class": gpu_class}
    if preemptible:
        selector["nebius.com/preemptible"] = "true"
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {"name": name, "namespace": namespace, "labels": labels},
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 1800,
            "ttlSecondsAfterFinished": 86400,
            "template": {
                "metadata": {"labels": labels},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "nodeSelector": selector,
                    "tolerations": [{"key": "dedicated", "operator": "Equal",
                                     "value": "fs2-inference", "effect": "NoSchedule"}],
                    "securityContext": {"runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001},
                    "containers": [{
                        "name": "probe",
                        "image": image,
                        "args": ["--model", profile.model, "--chunk-ms", str(profile.chunk_size_ms),
                                 "--precision", profile.precision, "--repetitions", "3"],
                        "env": [{"name": "OMP_NUM_THREADS", "value": "2"}],
                        "resources": {
                            "requests": {"cpu": "2", "memory": "16Gi", "ephemeral-storage": "16Gi",
                                         "nvidia.com/gpu": "1"},
                            "limits": {"cpu": "4", "memory": "32Gi", "ephemeral-storage": "24Gi",
                                       "nvidia.com/gpu": "1"},
                        },
                        "volumeMounts": [{"name": "cache", "mountPath": "/cache"}],
                    }],
                    "volumes": [{"name": "cache", "emptyDir": {"sizeLimit": "20Gi"}}],
                },
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--gpu-class", required=True)
    parser.add_argument("--chunk-ms", type=int, default=560)
    parser.add_argument("--allow-regular", action="store_true")
    args = parser.parse_args()
    print(json.dumps(render_job(
        name=args.name, namespace=args.namespace, image=args.image,
        profile=RuntimeProfile(model=args.model, chunk_size_ms=args.chunk_ms),
        gpu_class=args.gpu_class, preemptible=not args.allow_regular,
    ), indent=2))


if __name__ == "__main__":
    main()
