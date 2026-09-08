from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Sequence


SAFE_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
STABLE_VERSION = re.compile(r"^v?(\d+)\.(\d+)(?:\.(\d+))?$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_REPOSITORY = "nvcr.io/nvidia/gromacs"


def validate_requested_version(value: str) -> str:
    value = value.strip()
    if not SAFE_TAG.fullmatch(value):
        raise ValueError("GROMACS_VERSION must be 'latest' or a safe NVIDIA tag")
    return value


def resolve_latest_tag(tags: Sequence[str]) -> str:
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for tag in tags:
        match = STABLE_VERSION.fullmatch(tag.strip())
        if match:
            version = tuple(int(item or 0) for item in match.groups())
            candidates.append((version, tag.strip()))
    if not candidates:
        raise RuntimeError("NVIDIA GROMACS repository has no stable version tags")
    return max(candidates, key=lambda item: (item[0], item[1].startswith("v")))[1]


def safe_tar_members(path: Path) -> None:
    with tarfile.open(path, mode="r:*") as archive:
        for member in archive:
            candidate = Path(member.name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise RuntimeError(f"unsafe path in NVIDIA runtime archive: {member.name!r}")


def find_gromacs_binary(rootfs: Path, requested_build: str) -> tuple[Path, str]:
    validate_requested_version(requested_build)
    base = rootfs / "usr/local/gromacs"
    preferred = base / requested_build / "bin/gmx"
    if preferred.is_file():
        return preferred, requested_build
    candidates = sorted(base.glob("*/bin/gmx"))
    if not candidates:
        direct = base / "bin/gmx"
        if direct.is_file():
            return direct, "default"
        raise RuntimeError("pulled NVIDIA image does not contain a GROMACS binary")
    selected = candidates[0]
    return selected, selected.parent.parent.name


def runtime_library_paths(
    rootfs: Path, build: str, *, include_system_libraries: bool = True
) -> list[str]:
    paths = [
        f"usr/local/gromacs/{build}/lib" if build != "default" else "usr/local/gromacs/lib"
    ]
    cuda_roots = {"usr/local/cuda"}
    cuda_parent = rootfs / "usr/local"
    if cuda_parent.is_dir():
        cuda_roots.update(
            path.relative_to(rootfs).as_posix()
            for path in cuda_parent.glob("cuda-*")
            if path.is_dir()
        )
    for cuda_root in sorted(cuda_roots):
        paths.extend(
            [
                f"{cuda_root}/lib64",
                f"{cuda_root}/targets/x86_64-linux/lib",
                f"{cuda_root}/compat",
            ]
        )
    paths.append("usr/local/fftw/lib")
    if include_system_libraries:
        paths.extend(["usr/lib/x86_64-linux-gnu", "lib/x86_64-linux-gnu"])
    return paths


def runtime_wrapper(
    rootfs: Path, gmx_binary: Path, build: str, execution_mode: str = "nvidia_loader"
) -> str:
    relative_binary = gmx_binary.relative_to(rootfs).as_posix()
    loader_candidates = (
        "lib64/ld-linux-x86-64.so.2",
        "lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    )
    loader = next((item for item in loader_candidates if (rootfs / item).exists()), None)
    if loader is None:
        raise RuntimeError("pulled NVIDIA image has no supported x86_64 dynamic loader")
    if execution_mode not in {"nvidia_loader", "host_loader"}:
        raise ValueError(f"unsupported execution mode: {execution_mode}")

    library_paths = runtime_library_paths(
        rootfs,
        build,
        include_system_libraries=execution_mode == "nvidia_loader",
    )
    relative_libraries = ":".join(f'${{ROOTFS}}/{item}' for item in library_paths)
    share = (
        f"usr/local/gromacs/{build}/share/gromacs/top"
        if build != "default"
        else "usr/local/gromacs/share/gromacs/top"
    )
    if execution_mode == "nvidia_loader":
        command = (
            f'exec "$ROOTFS/{loader}" --library-path "$LD_LIBRARY_PATH" '
            f'"$ROOTFS/{relative_binary}" "$@"'
        )
    else:
        command = f'exec "$ROOTFS/{relative_binary}" "$@"'
    return f"""#!/bin/sh
set -eu
RUNTIME_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOTFS="$RUNTIME_DIR/rootfs"
TARGET_LIBS="{relative_libraries}"
DRIVER_LIBS="/usr/local/nvidia/lib:/usr/local/nvidia/lib64"
export GMXLIB="$ROOTFS/{share}"
export LD_LIBRARY_PATH="$DRIVER_LIBS:$TARGET_LIBS${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
{command}
"""


def parse_engine_version(output: str) -> str:
    for line in output.splitlines():
        if "GROMACS version" in line and ":" in line:
            return line.split(":", 1)[1].strip()
    return "unknown"


class RuntimeLoader:
    def __init__(
        self,
        *,
        cache_root: Path,
        requested_version: str,
        requested_build: str,
        api_key: str,
        repository: str = SAFE_REPOSITORY,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        if repository != SAFE_REPOSITORY:
            raise ValueError(f"GROMACS_IMAGE_REPOSITORY must remain {SAFE_REPOSITORY}")
        if not api_key.strip():
            raise ValueError("NGC_API_KEY is required")
        self.cache_root = cache_root
        self.requested_version = validate_requested_version(requested_version)
        self.requested_build = validate_requested_version(requested_build)
        self.api_key = api_key.strip()
        self.repository = repository
        self.runner = runner

    def _run(self, args: Sequence[str], env: dict[str, str], timeout: int = 900) -> str:
        completed = self.runner(
            list(args),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown registry error")[-1200:]
            detail = detail.replace(self.api_key, "[REDACTED]")
            raise RuntimeError(f"runtime command failed ({args[0]} {args[1]}): {detail}")
        return completed.stdout.strip()

    def _auth_environment(self, auth_dir: Path) -> dict[str, str]:
        auth = base64.b64encode(f"$oauthtoken:{self.api_key}".encode()).decode()
        config_path = auth_dir / "config.json"
        config_path.write_text(json.dumps({"auths": {"nvcr.io": {"auth": auth}}}), encoding="utf-8")
        config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return {**os.environ, "DOCKER_CONFIG": str(auth_dir)}

    def _resolve(self, env: dict[str, str]) -> tuple[str, str, dict[str, Any]]:
        if self.requested_version == "latest":
            tags = self._run(["crane", "ls", self.repository], env, timeout=120).splitlines()
            resolved_tag = resolve_latest_tag(tags)
        else:
            resolved_tag = self.requested_version
        reference = f"{self.repository}:{resolved_tag}"
        digest = self._run(
            ["crane", "digest", "--platform", "linux/amd64", reference], env, timeout=120
        )
        if not DIGEST.fullmatch(digest):
            raise RuntimeError("NVIDIA registry returned an invalid image digest")
        raw_config = self._run(
            ["crane", "config", "--platform", "linux/amd64", reference], env, timeout=120
        )
        config = json.loads(raw_config)
        image_env = {
            item.split("=", 1)[0]: item.split("=", 1)[1]
            for item in config.get("config", {}).get("Env", [])
            if "=" in item
        }
        selected_config = {
            "entrypoint": config.get("config", {}).get("Entrypoint"),
            "nvidia_require_cuda": image_env.get("NVIDIA_REQUIRE_CUDA"),
        }
        return resolved_tag, digest, selected_config

    def _cached(self, directory: Path, digest: str) -> dict[str, Any] | None:
        metadata_path = directory / "runtime.json"
        wrapper_path = directory / "gmx-runtime"
        if not metadata_path.is_file() or not wrapper_path.is_file():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("resolved_digest") != digest:
            return None
        return metadata

    def load(self) -> tuple[Path, Path, dict[str, Any]]:
        self.cache_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        auth_dir = Path(tempfile.mkdtemp(prefix="ngc-auth-", dir="/run"))
        auth_dir.chmod(0o700)
        config_path = auth_dir / "config.json"
        staging: Path | None = None
        try:
            env = self._auth_environment(auth_dir)
            resolved_tag, digest, image_config = self._resolve(env)
            digest_key = digest.removeprefix("sha256:")
            final_directory = self.cache_root / digest_key
            cached = self._cached(final_directory, digest)
            if cached is not None:
                print(
                    f"NVIDIA GROMACS runtime ready: requested={self.requested_version} "
                    f"resolved={resolved_tag} digest={digest} cache=hit",
                    flush=True,
                )
                return final_directory / "gmx-runtime", final_directory / "runtime.json", cached

            staging = self.cache_root / f".staging-{uuid.uuid4().hex}"
            staging.mkdir(mode=0o755)
            archive = staging / "runtime.tar"
            reference = f"{self.repository}:{resolved_tag}"
            print(
                f"Pulling NVIDIA GROMACS runtime: requested={self.requested_version} "
                f"resolved={resolved_tag} digest={digest}",
                flush=True,
            )
            self._run(
                ["crane", "export", "--platform", "linux/amd64", reference, str(archive)],
                env,
                timeout=1800,
            )
            safe_tar_members(archive)
            rootfs = staging / "rootfs"
            rootfs.mkdir(mode=0o755)
            extracted = self.runner(
                ["tar", "-xf", str(archive), "-C", str(rootfs), "--no-same-owner"],
                capture_output=True,
                text=True,
                check=False,
                timeout=900,
            )
            if extracted.returncode != 0:
                raise RuntimeError(f"failed to unpack NVIDIA runtime: {extracted.stderr[-1200:]}")
            archive_bytes = archive.stat().st_size
            archive.unlink()
            gmx, selected_build = find_gromacs_binary(rootfs, self.requested_build)
            wrapper = staging / "gmx-runtime"
            probe_failures: list[str] = []
            actual_version = "unknown"
            execution_mode = "unknown"
            for candidate_mode in ("nvidia_loader", "host_loader"):
                wrapper.write_text(
                    runtime_wrapper(rootfs, gmx, selected_build, candidate_mode),
                    encoding="utf-8",
                )
                wrapper.chmod(0o755)
                version_probe = self.runner(
                    [str(wrapper), "--version"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=120,
                )
                candidate_version = parse_engine_version(version_probe.stdout)
                if version_probe.returncode == 0 and candidate_version != "unknown":
                    actual_version = candidate_version
                    execution_mode = candidate_mode
                    break
                detail = (version_probe.stderr or version_probe.stdout or "no output")[-800:]
                probe_failures.append(
                    f"{candidate_mode} exit={version_probe.returncode}: {detail}"
                )
            if execution_mode == "unknown":
                raise RuntimeError(
                    "pulled GROMACS runtime failed all version probes: "
                    + "; ".join(probe_failures)
                )
            metadata = {
                "requested_version": self.requested_version,
                "resolved_tag": resolved_tag,
                "resolved_reference": reference,
                "resolved_digest": digest,
                "selected_cpu_build": selected_build,
                "actual_engine_version": actual_version,
                "execution_mode": execution_mode,
                "archive_bytes": archive_bytes,
                **image_config,
            }
            (staging / "runtime.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
            )
            if final_directory.exists():
                shutil.rmtree(final_directory)
            staging.rename(final_directory)
            print(
                f"NVIDIA GROMACS runtime ready: actual={actual_version} "
                f"build={selected_build} cache=miss",
                flush=True,
            )
            return final_directory / "gmx-runtime", final_directory / "runtime.json", metadata
        finally:
            if config_path.exists():
                config_path.write_text("{}", encoding="utf-8")
                config_path.unlink()
            if auth_dir.exists():
                auth_dir.rmdir()
            if staging is not None and staging.exists():
                shutil.rmtree(staging)


def write_environment(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        f"export {key}={shlex.quote(value)}\n" for key, value in sorted(values.items())
    )
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()
    loader = RuntimeLoader(
        cache_root=Path(os.environ.get("GROMACS_RUNTIME_CACHE", "/var/cache/hcls-gromacs")),
        requested_version=os.environ.get("GROMACS_VERSION", "latest"),
        requested_build=os.environ.get("GROMACS_CPU_BUILD", "avx2_256"),
        api_key=os.environ.get("NGC_API_KEY", ""),
        repository=os.environ.get("GROMACS_IMAGE_REPOSITORY", SAFE_REPOSITORY),
    )
    binary, metadata, resolved = loader.load()
    write_environment(
        args.env_file,
        {
            "GROMACS_BINARY": str(binary),
            "GROMACS_RUNTIME_METADATA": str(metadata),
            "GROMACS_RESOLVED_TAG": str(resolved["resolved_tag"]),
            "GROMACS_RESOLVED_DIGEST": str(resolved["resolved_digest"]),
        },
    )


if __name__ == "__main__":
    main()
