from __future__ import annotations

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
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SENSITIVE_ENV_NAME = re.compile(r"(?:KEY|TOKEN|PASS|SECRET|CREDENTIAL)", re.IGNORECASE)


class IncompatibleRuntimeError(RuntimeError):
    """The image is valid but cannot execute on the current Serverless worker."""


def validate_requested_version(value: str, variable_name: str) -> str:
    value = value.strip()
    if not SAFE_TAG.fullmatch(value):
        raise ValueError(f"{variable_name} must be 'latest' or a safe NVIDIA tag")
    return value


def stable_version_tags(tags: Sequence[str], stable_pattern: re.Pattern[str]) -> list[str]:
    candidates: list[tuple[tuple[int, ...], str]] = []
    for raw_tag in tags:
        tag = raw_tag.strip()
        if stable_pattern.fullmatch(tag):
            candidates.append((tuple(int(item) for item in re.findall(r"\d+", tag)), tag))
    if not candidates:
        raise RuntimeError("NVIDIA repository has no supported stable version tags")
    return [item[1] for item in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)]


def safe_tar_members(path: Path) -> None:
    with tarfile.open(path, mode="r:*") as archive:
        for member in archive:
            candidate = Path(member.name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise RuntimeError(f"unsafe path in NVIDIA runtime archive: {member.name!r}")
            if member.islnk():
                link = Path(member.linkname)
                if link.is_absolute() or ".." in link.parts:
                    raise RuntimeError(f"unsafe hard link in NVIDIA runtime archive: {member.name!r}")


def public_image_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config = raw_config.get("config", {})
    image_env = {
        item.split("=", 1)[0]: item.split("=", 1)[1]
        for item in config.get("Env", [])
        if "=" in item and SAFE_ENV_NAME.fullmatch(item.split("=", 1)[0])
    }
    return {
        "entrypoint": config.get("Entrypoint"),
        "command": config.get("Cmd"),
        "working_directory": config.get("WorkingDir"),
        "nvidia_require_cuda_configured": "NVIDIA_REQUIRE_CUDA" in image_env,
        "image_environment_names": sorted(image_env),
    }


def execution_environment(raw_config: dict[str, Any]) -> dict[str, str]:
    config = raw_config.get("config", {})
    result: dict[str, str] = {}
    for item in config.get("Env", []):
        if "=" not in item:
            continue
        name, value = item.split("=", 1)
        if SAFE_ENV_NAME.fullmatch(name) and not SENSITIVE_ENV_NAME.search(name):
            result[name] = value
    return result


class OciRuntimeLoader:
    def __init__(
        self,
        *,
        service_name: str,
        cache_root: Path,
        requested_version: str,
        version_variable: str,
        repository: str,
        required_repository: str,
        stable_pattern: re.Pattern[str],
        api_key: str,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        if repository != required_repository:
            raise ValueError(f"runtime repository must remain {required_repository}")
        if not api_key.strip():
            raise ValueError("NGC_API_KEY is required")
        self.service_name = service_name
        self.cache_root = cache_root
        self.requested_version = validate_requested_version(requested_version, version_variable)
        self.version_variable = version_variable
        self.repository = repository
        self.stable_pattern = stable_pattern
        self.api_key = api_key.strip()
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
            detail = (completed.stderr or completed.stdout or "unknown registry error")[-1600:]
            detail = detail.replace(self.api_key, "[REDACTED]")
            raise RuntimeError(f"runtime command failed ({args[0]} {args[1]}): {detail}")
        return completed.stdout.strip()

    def _auth_environment(self, auth_dir: Path) -> dict[str, str]:
        auth = base64.b64encode(f"$oauthtoken:{self.api_key}".encode()).decode()
        config_path = auth_dir / "config.json"
        config_path.write_text(json.dumps({"auths": {"nvcr.io": {"auth": auth}}}), encoding="utf-8")
        config_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return {**os.environ, "DOCKER_CONFIG": str(auth_dir)}

    def _resolve(self, tag: str, env: dict[str, str]) -> tuple[str, dict[str, Any]]:
        reference = f"{self.repository}:{tag}"
        digest = self._run(["crane", "digest", "--platform", "linux/amd64", reference], env, 120)
        if not DIGEST.fullmatch(digest):
            raise RuntimeError("NVIDIA registry returned an invalid image digest")
        raw_config = json.loads(
            self._run(["crane", "config", "--platform", "linux/amd64", reference], env, 120)
        )
        return digest, raw_config

    def _materialize(
        self, tag: str, env: dict[str, str]
    ) -> tuple[Path, dict[str, Any], dict[str, str]]:
        digest, raw_config = self._resolve(tag, env)
        final_directory = self.cache_root / digest.removeprefix("sha256:")
        rootfs = final_directory / "rootfs"
        internal_path = final_directory / "materialization.json"
        if rootfs.is_dir() and internal_path.is_file():
            internal = json.loads(internal_path.read_text(encoding="utf-8"))
            if internal.get("resolved_digest") == digest:
                return rootfs, internal, execution_environment(raw_config)

        staging: Path | None = None
        try:
            staging = self.cache_root / f".staging-{uuid.uuid4().hex}"
            staging.mkdir(mode=0o755)
            archive = staging / "runtime.tar"
            reference = f"{self.repository}:{tag}"
            print(
                f"Pulling NVIDIA {self.service_name} runtime: requested={self.requested_version} "
                f"resolved={tag} digest={digest}",
                flush=True,
            )
            self._run(
                ["crane", "export", "--platform", "linux/amd64", reference, str(archive)],
                env,
                3600,
            )
            safe_tar_members(archive)
            rootfs = staging / "rootfs"
            rootfs.mkdir(mode=0o755)
            extracted = self.runner(
                [
                    "tar",
                    "-xf",
                    str(archive),
                    "-C",
                    str(rootfs),
                    "--no-same-owner",
                    "--no-same-permissions",
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=1800,
            )
            if extracted.returncode != 0:
                raise RuntimeError(f"failed to unpack NVIDIA runtime: {extracted.stderr[-1600:]}")
            archive_bytes = archive.stat().st_size
            archive.unlink()
            internal = {
                "requested_version": tag,
                "resolved_tag": tag,
                "resolved_reference": reference,
                "resolved_digest": digest,
                "archive_bytes": archive_bytes,
                **public_image_config(raw_config),
            }
            (staging / "materialization.json").write_text(
                json.dumps(internal, indent=2, sort_keys=True), encoding="utf-8"
            )
            if final_directory.exists():
                shutil.rmtree(final_directory)
            staging.rename(final_directory)
            staging = None
            return final_directory / "rootfs", internal, execution_environment(raw_config)
        finally:
            if staging is not None and staging.exists():
                shutil.rmtree(staging)

    def load(
        self,
        probe: Callable[[Path, dict[str, str]], dict[str, Any]],
    ) -> tuple[Path, Path, dict[str, Any], dict[str, str]]:
        self.cache_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        auth_dir = Path(tempfile.mkdtemp(prefix="ngc-auth-", dir="/run"))
        auth_dir.chmod(0o700)
        config_path = auth_dir / "config.json"
        try:
            env = self._auth_environment(auth_dir)
            if self.requested_version == "latest":
                tags = self._run(["crane", "ls", self.repository], env, 120).splitlines()
                candidates = stable_version_tags(tags, self.stable_pattern)
            else:
                candidates = [self.requested_version]

            rejected: list[dict[str, str]] = []
            for tag in candidates:
                try:
                    rootfs, base_metadata, image_env = self._materialize(tag, env)
                    probe_metadata = probe(rootfs, image_env)
                except IncompatibleRuntimeError as exc:
                    if self.requested_version != "latest":
                        raise
                    reason = str(exc)[-1200:]
                    rejected.append({"tag": tag, "reason": reason})
                    print(f"NVIDIA {self.service_name} tag rejected: resolved={tag} reason={reason}", flush=True)
                    continue

                selected = {
                    **base_metadata,
                    **probe_metadata,
                    "requested_version": self.requested_version,
                    "selection_policy": (
                        "highest-stable-gpu-compatible"
                        if self.requested_version == "latest"
                        else "exact-tag"
                    ),
                    "rejected_newer_tags": rejected,
                    "gpu_startup_probe": "passed",
                }
                selection_path = self.cache_root / "runtime-selection.json"
                public_selection = {
                    key: value for key, value in selected.items() if not key.startswith("guest_")
                }
                selection_path.write_text(
                    json.dumps(public_selection, indent=2, sort_keys=True), encoding="utf-8"
                )
                return rootfs, selection_path, selected, image_env
            raise RuntimeError(f"no stable NVIDIA {self.service_name} tag passed the startup probe")
        finally:
            if config_path.exists():
                config_path.write_text("{}", encoding="utf-8")
                config_path.unlink()
            if auth_dir.exists():
                auth_dir.rmdir()


def _copy_device(source: Path, destination: Path) -> None:
    info = source.lstat()
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _copy_device(child, destination / child.name)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        destination.unlink()
    if stat.S_ISCHR(info.st_mode) or stat.S_ISBLK(info.st_mode):
        os.mknod(destination, stat.S_IFMT(info.st_mode) | stat.S_IMODE(info.st_mode), info.st_rdev)
    elif source.is_symlink():
        destination.symlink_to(os.readlink(source))
    elif source.is_file():
        shutil.copyfile(source, destination)
        destination.chmod(stat.S_IMODE(info.st_mode))


def _inject_nvidia_tools(rootfs: Path) -> None:
    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        source = Path(nvidia_smi)
        _copy_device(source.resolve(), rootfs / source.relative_to("/"))


def _inject_driver_libraries(rootfs: Path) -> None:
    library_directories = (
        Path("/usr/lib/x86_64-linux-gnu"),
        Path("/lib/x86_64-linux-gnu"),
        Path("/usr/lib64"),
        Path("/lib64"),
    )
    copied: set[Path] = set()
    for directory in library_directories:
        if not directory.is_dir():
            continue
        for pattern in ("libnvidia-*.so*", "libcuda.so*"):
            for source in sorted(directory.glob(pattern)):
                if not source.is_file():
                    continue
                destination = rootfs / source.relative_to("/")
                if destination in copied:
                    continue
                _copy_device(source.resolve(), destination)
                copied.add(destination)


def _copy_gpu_namespace(rootfs: Path) -> None:
    (rootfs / "dev").mkdir(parents=True, exist_ok=True)
    for name in ("null", "zero", "random", "urandom", "tty"):
        source = Path("/dev") / name
        if source.exists():
            _copy_device(source, rootfs / "dev" / name)
    for source in sorted(Path("/dev").glob("nvidia*")):
        _copy_device(source, rootfs / "dev" / source.name)
    (rootfs / "dev/shm").mkdir(parents=True, exist_ok=True)

    # Default container isolation commonly retains CAP_MKNOD but not
    # CAP_SYS_ADMIN. In that case a copied nvidia-smi plus the driver's proc
    # metadata reproduces the subset of NVIDIA Container Toolkit injection
    # needed by runtimes that discover GPUs via NVML.
    proc_driver = Path("/proc/driver/nvidia")
    if proc_driver.is_dir() and not _mounted_at(rootfs / "proc"):
        try:
            _copy_device(proc_driver, rootfs / "proc/driver/nvidia")
        except OSError as exc:
            print(f"NVIDIA proc metadata copy was incomplete: {exc}", flush=True)


def _mounted_at(destination: Path) -> bool:
    expected = str(destination.resolve())
    try:
        lines = Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        fields = line.split()
        if len(fields) > 4 and fields[4].replace("\\040", " ") == expected:
            return True
    return False


def _bind_mount(source: Path, destination: Path, *, recursive: bool = False) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if _mounted_at(destination):
        return
    option = "--rbind" if recursive else "--bind"
    completed = subprocess.run(
        ["/usr/bin/mount", option, str(source), str(destination)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "mount failed")[-600:]
        raise IncompatibleRuntimeError(
            f"cannot expose {source} to the NVIDIA runtime: {detail}"
        )


def prepare_chroot_runtime(rootfs: Path) -> None:
    if not Path("/dev/nvidiactl").exists():
        raise IncompatibleRuntimeError("no NVIDIA control device is visible to the wrapper")

    # NVIDIA Container Toolkit normally supplies these mounts. Because the API
    # wrapper materializes the selected NGC image at endpoint startup, recreate
    # the same kernel views before entering its filesystem with chroot. /dev is
    # recursive so the existing Serverless /dev/shm mount is retained.
    try:
        _bind_mount(Path("/proc"), rootfs / "proc")
        _bind_mount(Path("/sys"), rootfs / "sys")
        _bind_mount(Path("/dev"), rootfs / "dev", recursive=True)
    except IncompatibleRuntimeError as exc:
        print(f"NVIDIA runtime kernel bind mounts unavailable; using device-copy mode: {exc}", flush=True)
        _copy_gpu_namespace(rootfs)

    _inject_nvidia_tools(rootfs)

    for source in (Path("/usr/local/nvidia/lib"), Path("/usr/local/nvidia/lib64")):
        if source.is_dir():
            destination = rootfs / source.relative_to("/")
            shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)
    _inject_driver_libraries(rootfs)

    etc = rootfs / "etc"
    etc.mkdir(parents=True, exist_ok=True)
    for name in ("hosts", "resolv.conf"):
        source = Path("/etc") / name
        destination = etc / name
        if source.is_file():
            if destination.exists() or destination.is_symlink():
                destination.unlink()
            shutil.copyfile(source, destination)


def host_to_guest(rootfs: Path, path: Path | str) -> str:
    resolved_root = rootfs.resolve()
    resolved_path = Path(path).resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"runtime path is outside the selected NVIDIA rootfs: {resolved_path}") from exc
    return f"/{relative.as_posix()}" if relative.as_posix() != "." else "/"


def run_in_runtime(
    *,
    rootfs: Path,
    guest_command: str,
    args: Sequence[str],
    cwd: Path,
    image_environment: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    guest_cwd = host_to_guest(rootfs, cwd)
    root_prefix = f"{rootfs.resolve()}/"
    mapped_args = [
        f"/{value[len(root_prefix):]}" if value.startswith(root_prefix) else value
        for value in (str(item) for item in args)
    ]
    clean_environment = {
        name: value
        for name, value in image_environment.items()
        if SAFE_ENV_NAME.fullmatch(name) and not SENSITIVE_ENV_NAME.search(name)
    }
    clean_environment.update(
        {
            "HOME": "/root",
            "NVIDIA_VISIBLE_DEVICES": "all",
            "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
        }
    )
    driver_paths = "/usr/local/nvidia/lib:/usr/local/nvidia/lib64"
    image_libraries = clean_environment.get("LD_LIBRARY_PATH", "")
    clean_environment["LD_LIBRARY_PATH"] = (
        f"{driver_paths}:{image_libraries}" if image_libraries else driver_paths
    )
    clean_environment.setdefault(
        "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    )
    environment_args = [f"{name}={value}" for name, value in sorted(clean_environment.items())]
    command = [
        "/usr/sbin/chroot",
        str(rootfs),
        "/usr/bin/env",
        "-i",
        *environment_args,
        "/bin/sh",
        "-c",
        'cd "$1"; shift; exec "$@"',
        "hcls-runtime",
        guest_cwd,
        guest_command,
        *mapped_args,
    ]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def write_environment(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"export {key}={shlex.quote(value)}\n" for key, value in sorted(values.items())),
        encoding="utf-8",
    )
    path.chmod(0o600)
