"""Run paired, closed-loop Pick Orange episodes on an Isaac Sim RTX machine."""

import argparse
import base64
import json
import os
import random
import ssl
import subprocess
import sys
import time
import urllib.request
import zlib
from pathlib import Path

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--model", choices=("base", "adapter"), required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--endpoint", default="http://127.0.0.1:8765")
parser.add_argument("--episodes", type=int, default=25)
parser.add_argument("--seed", type=int, default=42000)
parser.add_argument("--episode_length_s", type=float, default=120)
parser.add_argument("--record_episodes", type=int, default=3)
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
certificate = os.environ.get("SERVICE_TLS_CERT_FILE")
TLS_CONTEXT = ssl.create_default_context(cafile=certificate) if certificate else None
if TLS_CONTEXT:
    if not args.endpoint.startswith("https://"):
        raise ValueError("SERVICE_TLS_CERT_FILE requires an HTTPS policy endpoint")
    # The temporary Job has an IP address rather than a stable DNS name.
    TLS_CONTEXT.check_hostname = False

# Isaac Sim exits the process on a second reset of this task. Run each episode
# in its own simulator process, then keep one cumulative report for the recipe.
if args.episodes > 1:
    report = None
    for index in range(args.episodes):
        child_output = args.output.parent / f"{args.model}-episode-{index:02d}" / args.output.name
        child_output.parent.mkdir(parents=True, exist_ok=True)
        child_args = sys.argv[1:].copy()
        for flag, value in (
            ("--episodes", "1"),
            ("--seed", str(args.seed + index)),
            ("--output", str(child_output)),
            ("--record_episodes", "1" if index < args.record_episodes else "0"),
        ):
            if flag in child_args:
                child_args[child_args.index(flag) + 1] = value
            else:
                child_args.extend((flag, value))
        subprocess.run([sys.executable, __file__, *child_args], check=True)
        episode_report = json.loads(child_output.read_text())
        if len(episode_report["episodes"]) != 1:
            raise RuntimeError(f"simulator did not finish episode {index}: {child_output}")
        if report is None:
            report = {**episode_report, "episodes": []}
        row = episode_report["episodes"][0]
        row["episode"] = index
        report["episodes"].append(row)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n")
        temporary.replace(args.output)
    raise SystemExit(0)

app_launcher = AppLauncher(vars(args))
simulation_app = app_launcher.app

import gymnasium as gym
import numpy as np
import torch
from isaaclab.managers import SceneEntityCfg
from isaaclab_tasks.utils import parse_env_cfg
from leisaac.tasks.pick_orange import mdp
from leisaac.utils.env_utils import dynamic_reset_gripper_effort_limit_sim, get_task_type
from leisaac.utils.robot_utils import (
    convert_leisaac_action_to_lerobot,
    convert_lerobot_action_to_leisaac,
)
import leisaac  # noqa: F401

from calibration import ID as CALIBRATION_ID

RECIPE = json.loads((Path(__file__).parent / "recipe.json").read_text())
ORANGES = [SceneEntityCfg(f"Orange{index:03d}") for index in range(1, 4)]
PLATE = SceneEntityCfg("Plate")


def request_headers() -> dict:
    headers = {"Content-Type": "application/json"}
    token_file = os.environ.get("SERVICE_TOKEN_FILE")
    if token_file:
        headers["Authorization"] = f"Bearer {Path(token_file).read_text().strip()}"
    return headers


def post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        args.endpoint.rstrip("/") + path,
        data=json.dumps(payload).encode(),
        headers=request_headers(),
    )
    with urllib.request.urlopen(request, timeout=300, context=TLS_CONTEXT) as response:
        return json.load(response)


def encode_image(image: torch.Tensor) -> dict:
    pixels = image[0].cpu().numpy()
    if pixels.ndim != 3 or pixels.shape[2] not in (3, 4):
        raise ValueError(f"unexpected LeIsaac camera shape: {pixels.shape}")
    pixels = np.ascontiguousarray(pixels[..., :3].astype(np.uint8))
    return {
        "shape": list(pixels.shape),
        "data": base64.b64encode(zlib.compress(pixels.tobytes(), level=1)).decode(),
    }


def start_video(image: torch.Tensor, path: Path):
    pixels = image[0].cpu().numpy()
    height, width = pixels.shape[:2]
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", f"{width}x{height}", "-framerate", "30", "-i", "-",
         "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "23", str(path)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return process


def action_from_observation(observation: dict) -> torch.Tensor:
    policy_obs = observation["policy"]
    if not {"front", "wrist", "joint_pos"} <= set(policy_obs):
        raise ValueError(f"LeIsaac policy observation keys changed: {set(policy_obs)}")
    state = convert_leisaac_action_to_lerobot(policy_obs["joint_pos"])
    if state.shape != (1, 6):
        raise ValueError(f"unexpected SO-101 state shape: {state.shape}")
    reply = post("/act", {
        "front": encode_image(policy_obs["front"]),
        "wrist": encode_image(policy_obs["wrist"]),
        "state": state[0].tolist(),
    })
    command = np.asarray(reply["action"], dtype=np.float32).reshape(1, 6)
    if not np.isfinite(command).all():
        raise ValueError("policy returned non-finite command")
    sim_command = convert_lerobot_action_to_leisaac(command)
    return torch.as_tensor(sim_command, dtype=torch.float32, device=args.device)


def placed_oranges(env) -> list[bool]:
    return [
        bool(mdp.put_orange_to_plate(env, object_cfg=orange, plate_cfg=PLATE)[0])
        for orange in ORANGES
    ]


def write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(path)


def main() -> None:
    if args.episodes <= 0:
        raise ValueError("episodes must be positive")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if not revision.startswith(RECIPE["leisaac_revision"]):
        raise ValueError(f"LeIsaac revision {revision} does not match recipe pin")
    health_request = urllib.request.Request(args.endpoint.rstrip("/") + "/health", headers=request_headers())
    with urllib.request.urlopen(health_request, timeout=300, context=TLS_CONTEXT) as response:
        health = json.load(response)
    if health.get("model") != args.model:
        raise ValueError(f"policy service variant mismatch: {health}")
    if health.get("calibration_id") != CALIBRATION_ID:
        raise ValueError(f"policy service calibration mismatch: {health}")

    env_cfg = parse_env_cfg(RECIPE["task"], device=args.device, num_envs=1)
    task_type = get_task_type(RECIPE["task"])
    env_cfg.use_teleop_device(task_type)
    # LeIsaac randomizes objects during environment construction as well as reset.
    # Each child process evaluates one seed, so seed before gym.make too.
    env_cfg.seed = args.seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    # Keep LeIsaac's one 60 Hz physics step per action. Its 30 Hz policy loop
    # paces wall time separately; the demonstrations and published eval use this setup.
    if env_cfg.decimation != 1 or abs(env_cfg.sim.dt - 1 / 60) > 1e-6:
        raise ValueError("LeIsaac physics settings differ from the pinned task")
    env_cfg.episode_length_s = args.episode_length_s
    env_cfg.recorders = None
    env = gym.make(RECIPE["task"], cfg=env_cfg).unwrapped
    if int(env.max_episode_length) != round(args.episode_length_s * 60):
        raise ValueError("LeIsaac episode does not have one action per 60 Hz physics step")
    report = {
        "model": args.model,
        "policy": health,
        "dataset": RECIPE["dataset"]["repo_id"],
        "dataset_revision": RECIPE["dataset"]["revision"],
        "calibration_id": CALIBRATION_ID,
        "leisaac_revision": revision,
        "task": RECIPE["task"],
        "seed_start": args.seed,
        "episode_length_s": args.episode_length_s,
        "control_hz": 30,
        "physics_hz": 60,
        "physics_steps_per_action": env_cfg.decimation,
        "episodes": [],
    }
    write_report(args.output, report)
    try:
        for index in range(args.episodes):
            seed = args.seed + index
            print(f"episode {index} seed {seed}: resetting scene", flush=True)
            random.seed(seed)
            torch.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
            np.random.seed(seed)
            # Isaac Sim's global seed hook exits cleanly on a second invocation.
            # Seed the scene RNGs directly for each paired episode.
            observation, _ = env.reset()
            # Let the cameras and kitchen scene settle before the first policy plan.
            hold = observation["policy"]["joint_pos"].clone()
            for _ in range(30):
                observation, _, _, _, _ = env.step(hold)
            env.episode_length_buf[:] = 0
            print(f"episode {index}: scene ready", flush=True)
            post("/reset", {"episode": index, "seed": seed})
            video_path = args.output.parent / f"{args.model}-rollouts" / f"episode-{index:02d}.mp4"
            video = start_video(observation["policy"]["front"], video_path) if index < args.record_episodes else None
            placed = [False, False, False]
            full_success = False
            timed_out = False
            steps = 0
            started = time.monotonic()
            next_tick = time.monotonic()
            try:
                for step in range(int(env.max_episode_length)):
                    if not simulation_app.is_running():
                        raise RuntimeError("Isaac Sim stopped during evaluation")
                    with torch.inference_mode():
                        # env.step returns observations from a new scene on termination.
                        current = placed_oranges(env)
                        placed = [old or new for old, new in zip(placed, current, strict=True)]
                        if video is not None:
                            pixels = observation["policy"]["front"][0].cpu().numpy()[..., :3]
                            video.stdin.write(np.ascontiguousarray(pixels.astype(np.uint8)).tobytes())
                        command = action_from_observation(observation)
                        if env.cfg.dynamic_reset_gripper_effort_limit:
                            dynamic_reset_gripper_effort_limit_sim(env, task_type)
                        observation, _, terminated, timeout, _ = env.step(command)
                        steps = step + 1
                        if steps % 100 == 0:
                            print(f"episode {index}: {steps} steps", flush=True)
                        if bool(terminated[0]):
                            full_success = True
                            placed = [True, True, True]
                            break
                        if bool(timeout[0]):
                            timed_out = True
                            break
                    next_tick += 1 / 30
                    while time.monotonic() < next_tick:
                        env.sim.render()
                        time.sleep(min(0.016, next_tick - time.monotonic()))
            finally:
                if video is not None:
                    video.stdin.close()
                    if video.wait() != 0:
                        raise RuntimeError(f"ffmpeg failed writing {video_path}")
            row = {
                "episode": index,
                "seed": seed,
                "oranges_placed": sum(placed),
                "placed": placed,
                "full_task_success": full_success,
                "timed_out": timed_out,
                "steps": steps,
                "wall_seconds": round(time.monotonic() - started, 2),
                "video": str(video_path) if video is not None else None,
            }
            report["episodes"].append(row)
            write_report(args.output, report)
            print(row, flush=True)
    finally:
        env.close()
        simulation_app.close()


if __name__ == "__main__":
    main()
