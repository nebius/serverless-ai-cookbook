#!/usr/bin/env python3
"""Read-only, secret-minimized environment evidence for clinical ASR jobs.

Adapted from the GPU performance skill environment collector. No hardware writes.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COMMANDS: dict[str, list[str]] = {
    "nvidia_smi": ["nvidia-smi"],
    "nvidia_topology": ["nvidia-smi", "topo", "-m"],
    "nvidia_gpu_query": [
        "nvidia-smi",
        "--query-gpu=index,name,uuid,pci.bus_id,compute_cap,driver_version,memory.total,power.limit",
        "--format=csv,noheader,nounits",
    ],
    "nvcc": ["nvcc", "--version"],
    "nsys": ["nsys", "--version"],
    "ncu": ["ncu", "--version"],
    "dcgmi": ["dcgmi", "--version"],
    "numa": ["numactl", "--hardware"],
    "cpu": ["lscpu", "--json"],
    "infiniband_devices": ["ibv_devinfo", "--list"],
    "infiniband_netdevs": ["ibdev2netdev"],
    "docker_client": ["docker", "version", "--format", "{{json .Client}}"],
}

PACKAGE_NAMES = (
    "nemo_toolkit",
    "lightning",
    "mcp",
    "fastapi",
    "torch",
    "triton",
    "vllm",
    "sglang",
    "tensorrt",
    "tensorrt-llm",
    "transformer-engine",
    "flash-attn",
    "flashinfer-python",
    "llmcompressor",
    "lm-eval",
)

BINARY_NAMES = (
    "aiperf",
    "genai-perf",
    "vllm",
    "trtllm-bench",
    "lm-eval",
    "nsys",
    "ncu",
    "dcgmi",
    "nvbandwidth",
    "all_reduce_perf",
    "ibdev2netdev",
    "docker",
)

SAFE_ENV_NAMES = (
    "CUDA_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "CUDA_MODULE_LOADING",
    "CUDA_CACHE_PATH",
    "TORCH_CUDA_ARCH_LIST",
    "NCCL_DEBUG",
    "NCCL_DEBUG_SUBSYS",
    "NCCL_SOCKET_IFNAME",
    "NCCL_IB_HCA",
    "NCCL_IB_DISABLE",
    "NCCL_NET_GDR_LEVEL",
    "NCCL_P2P_LEVEL",
    "OMP_NUM_THREADS",
)


def trim_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode(errors="replace")
    return value.strip()[-20000:]


def run(command: list[str], timeout: int = 15) -> dict[str, Any]:
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "command": command}
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "available": True,
            "command": command,
            "timed_out": True,
            "stdout": trim_output(exc.stdout),
            "stderr": trim_output(exc.stderr),
        }
    return {
        "available": True,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": trim_output(completed.stdout),
        "stderr": trim_output(completed.stderr),
    }


def python_stack() -> dict[str, Any]:
    snippet = """
import json
from importlib import metadata

names = %r
versions = {}
for name in names:
    try:
        versions[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        pass

result = {"packages": versions}
try:
    import torch
    result["torch_cuda"] = {
        "build_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "cuda_available": torch.cuda.is_available(),
    }
    if torch.cuda.is_available():
        result["torch_cuda"]["devices"] = [
            {
                "index": index,
                "name": torch.cuda.get_device_name(index),
                "capability": list(torch.cuda.get_device_capability(index)),
            }
            for index in range(torch.cuda.device_count())
        ]
except Exception as exc:
    result["torch_probe_error"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(result))
""" % (PACKAGE_NAMES,)
    result = run([sys.executable, "-c", snippet], timeout=30)
    if result.get("exit_code") == 0:
        try:
            return json.loads(result.get("stdout", "{}"))
        except json.JSONDecodeError:
            pass
    return {"probe": result}


def collect() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "kernel": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "safe_environment": {
            name: os.environ[name] for name in SAFE_ENV_NAMES if name in os.environ
        },
        "binaries": {name: shutil.which(name) for name in BINARY_NAMES},
        "python_stack": python_stack(),
        "commands": {name: run(command) for name, command in COMMANDS.items()},
        "notes": [
            "Run this collector inside the workload container as well as on the host.",
            "Add container digest, model/tokenizer revisions, launch command, input checksum and benchmark artifacts to the experiment record.",
            "No arbitrary environment variables are collected to avoid exposing credentials.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit compact JSON.",
    )
    args = parser.parse_args()

    text = json.dumps(
        collect(),
        indent=None if args.compact else 2,
        sort_keys=True,
    ) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(args.output)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
