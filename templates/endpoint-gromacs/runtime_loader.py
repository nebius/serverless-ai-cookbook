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


class IncompatibleRuntimeError(RuntimeError):
    pass


def validate_requested_version(value: str) -> str:
    value = value.strip()
    if not SAFE_TAG.fullmatch(value):
        raise ValueError("GROMACS_VERSION must be 'latest' or a safe NVIDIA tag")
    return value


def stable_version_tags(tags: Sequence[str]) -> list[str]:
    candidates: list[tuple[tuple[int, int, int], str]] = []
    for tag in tags:
        match = STABLE_VERSION.fullmatch(tag.strip())
        if match:
            version = tuple(int(item or 0) for item in match.groups())
            candidates.append((version, tag.strip()))
    if not candidates:
        raise RuntimeError("NVIDIA GROMACS repository has no stable version tags")
    return [
        item[1]
        for item in sorted(
            candidates,
            key=lambda item: (item[0], item[1].startswith("v")),
            reverse=True,
        )
    ]


def resolve_latest_tag(tags: Sequence[str]) -> str:
    return stable_version_tags(tags)[0]


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
                f"{cuda_root}/compat",
                f"{cuda_root}/lib64",
                f"{cuda_root}/targets/x86_64-linux/lib",
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
DRIVER_LIBS="/usr/local/nvidia/lib:/usr/local/nvidia/lib64"
TARGET_LIBS="{relative_libraries}"
export GMXLIB="$ROOTFS/{share}"
export LD_LIBRARY_PATH="$TARGET_LIBS:$DRIVER_LIBS${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
{command}
"""


def parse_engine_version(output: str) -> str:
    for line in output.splitlines():
        if "GROMACS version" in line and ":" in line:
            return line.split(":", 1)[1].strip()
    return "unknown"


def gpu_startup_smoke(
    wrapper: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    workspace = Path(tempfile.mkdtemp(prefix="gromacs-gpu-probe-", dir="/tmp"))
    try:
        (workspace / "input.mdp").write_text(
            """integrator = md
nsteps = 1
dt = 0.001
cutoff-scheme = Verlet
nstlist = 10
rcoulomb = 0.8
rvdw = 0.8
coulombtype = Cut-off
vdwtype = Cut-off
pbc = xyz
constraints = none
tcoupl = no
pcoupl = no
gen_vel = yes
gen_temp = 300
gen_seed = 17
nstxout = 0
nstvout = 0
nstenergy = 1
nstlog = 1
""",
            encoding="utf-8",
        )
        (workspace / "input.gro").write_text(
            """Argon GPU startup probe
    4
    1ARG     AR    1   0.000   0.000   0.000
    1ARG     AR    2   0.500   0.000   0.000
    1ARG     AR    3   0.000   0.500   0.000
    1ARG     AR    4   0.000   0.000   0.500
   2.00000   2.00000   2.00000
""",
            encoding="utf-8",
        )
        (workspace / "topol.top").write_text(
            """[ defaults ]
1 1 no 1.0 1.0
[ atomtypes ]
Ar 18 39.948 0.0 A 0.3405 0.996
[ moleculetype ]
ARG 1
[ atoms ]
1 Ar 1 ARG AR 1 0.0 39.948
[ system ]
Argon GPU startup probe
[ molecules ]
ARG 4
""",
            encoding="utf-8",
        )
        commands = (
            [
                str(wrapper),
                "grompp",
                "-f",
                "input.mdp",
                "-c",
                "input.gro",
                "-p",
                "topol.top",
                "-o",
                "input.tpr",
            ],
            [
                str(wrapper),
                "mdrun",
                "-s",
                "input.tpr",
                "-deffnm",
                "probe",
                "-nsteps",
                "1",
                "-ntmpi",
                "1",
                "-ntomp",
                "1",
                "-nb",
                "gpu",
            ],
        )
        for command in commands:
            completed = runner(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout or "no output")[-1200:]
                raise IncompatibleRuntimeError(
                    f"GPU startup probe failed at {command[1]} with exit={completed.returncode}: "
                    f"{detail}"
                )
    finally:
        shutil.rmtree(workspace)


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

    def _resolve(self, resolved_tag: str, env: dict[str, str]) -> tuple[str, dict[str, Any]]:
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
        return digest, selected_config

    def _cached(self, directory: Path, digest: str) -> dict[str, Any] | None:
        metadata_path = directory / "runtime.json"
        wrapper_path = directory / "gmx-runtime"
        if not metadata_path.is_file() or not wrapper_path.is_file():
            return None
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("resolved_digest") != digest:
            return None
        return metadata

    def _load_candidate(
        self, resolved_tag: str, env: dict[str, str]
    ) -> tuple[Path, Path, dict[str, Any]]:
        digest, image_config = self._resolve(resolved_tag, env)
        digest_key = digest.removeprefix("sha256:")
        final_directory = self.cache_root / digest_key
        wrapper = final_directory / "gmx-runtime"
        metadata_path = final_directory / "runtime.json"
        cached = self._cached(final_directory, digest)
        if cached is not None:
            gpu_startup_smoke(wrapper, self.runner)
            cached = {**cached, "gpu_startup_probe": "passed"}
            metadata_path.write_text(
                json.dumps(cached, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(
                f"NVIDIA GROMACS runtime compatible: resolved={resolved_tag} "
                f"digest={digest} cache=hit gpu_probe=passed",
                flush=True,
            )
            return wrapper, metadata_path, cached

        staging: Path | None = None
        try:
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
            staging_wrapper = staging / "gmx-runtime"
            probe_failures: list[str] = []
            actual_version = "unknown"
            execution_mode = "unknown"
            for candidate_mode in ("nvidia_loader", "host_loader"):
                staging_wrapper.write_text(
                    runtime_wrapper(rootfs, gmx, selected_build, candidate_mode),
                    encoding="utf-8",
                )
                staging_wrapper.chmod(0o755)
                version_probe = self.runner(
                    [str(staging_wrapper), "--version"],
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
                "requested_version": resolved_tag,
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
            staging = None
            gpu_startup_smoke(wrapper, self.runner)
            metadata["gpu_startup_probe"] = "passed"
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(
                f"NVIDIA GROMACS runtime compatible: actual={actual_version} "
                f"resolved={resolved_tag} build={selected_build} cache=miss gpu_probe=passed",
                flush=True,
            )
            return wrapper, metadata_path, metadata
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)

    def load(self) -> tuple[Path, Path, dict[str, Any]]:
        self.cache_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        auth_dir = Path(tempfile.mkdtemp(prefix="ngc-auth-", dir="/run"))
        auth_dir.chmod(0o700)
        config_path = auth_dir / "config.json"
        try:
            env = self._auth_environment(auth_dir)
            if self.requested_version == "latest":
                tags = self._run(["crane", "ls", self.repository], env, timeout=120).splitlines()
                candidates = stable_version_tags(tags)
            else:
                candidates = [self.requested_version]

            rejected: list[dict[str, str]] = []
            for resolved_tag in candidates:
                try:
                    binary, metadata_path, metadata = self._load_candidate(resolved_tag, env)
                except IncompatibleRuntimeError as exc:
                    if self.requested_version != "latest":
                        raise
                    reason = str(exc)[-1200:]
                    rejected.append({"tag": resolved_tag, "reason": reason})
                    print(
                        f"NVIDIA GROMACS tag rejected by GPU probe: resolved={resolved_tag} "
                        f"reason={reason}",
                        flush=True,
                    )
                    continue

                if self.requested_version != "latest":
                    return binary, metadata_path, metadata
                selection = {
                    **metadata,
                    "requested_version": "latest",
                    "selection_policy": "highest-stable-gpu-compatible",
                    "rejected_newer_tags": rejected,
                    "gpu_startup_probe": "passed",
                }
                selection_path = self.cache_root / "runtime-selection.json"
                selection_path.write_text(
                    json.dumps(selection, indent=2, sort_keys=True), encoding="utf-8"
                )
                return binary, selection_path, selection
            raise RuntimeError("no stable NVIDIA GROMACS tag passed the GPU startup probe")
        finally:
            if config_path.exists():
                config_path.write_text("{}", encoding="utf-8")
                config_path.unlink()
            if auth_dir.exists():
                auth_dir.rmdir()


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
