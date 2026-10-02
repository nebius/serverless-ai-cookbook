"""Run one headless Franka pick-and-place case and publish its result."""

import argparse
import json
import math
import os
import re
import traceback
from pathlib import Path


def evaluate(controller_done, final_position, target_position):
    if not all(math.isfinite(value) for value in (*final_position, *target_position)):
        return {"xy_error_m": None, "z_error_m": None, "success": False}
    xy_error = math.dist(final_position[:2], target_position[:2])
    z_error = abs(final_position[2] - target_position[2])
    return {"xy_error_m": xy_error, "z_error_m": z_error, "success": controller_done and xy_error <= 0.08 and z_error <= 0.08}


def simulate(pick_x, place_y, max_steps):
    from isaacsim import SimulationApp

    app = SimulationApp({"headless": True})
    try:
        import numpy as np
        from isaacsim.core.api import World
        from isaacsim.robot.manipulators.examples.franka.controllers import PickPlaceController
        from isaacsim.robot.manipulators.examples.franka.tasks import PickPlace

        target = np.array([0.7, place_y, 0.0515 / 2.0])
        world = World(stage_units_in_meters=1.0, physics_dt=1 / 60)
        task = PickPlace(
            name="pick_place",
            cube_initial_position=np.array([pick_x, 0.3, 0.05]),
            target_position=target,
        )
        world.add_task(task)
        world.reset()
        params = task.get_params()
        cube_name = params["cube_name"]["value"]
        robot_name = params["robot_name"]["value"]
        robot = world.scene.get_object(robot_name)
        cube = world.scene.get_object(cube_name)
        # NVIDIA's multiple-tasks example slows the grasp phases for cubes at varied positions.
        controller = PickPlaceController(
            name="controller", gripper=robot.gripper, robot_articulation=robot,
            events_dt=[0.008, 0.002, 0.5, 0.1, 0.05, 0.05, 0.0025, 1, 0.008, 0.08],
        )
        controller.reset()

        controller_done = False
        for step in range(1, max_steps + 1):
            world.step(render=False)
            observations = world.get_observations()
            action = controller.forward(
                picking_position=observations[cube_name]["position"],
                placing_position=observations[cube_name]["target_position"],
                current_joint_positions=observations[robot_name]["joint_positions"],
            )
            robot.apply_action(action)
            if controller.is_done():
                controller_done = True
                break
        if controller_done:
            for _ in range(30):
                world.step(render=False)
        final_position = cube.get_world_pose()[0].tolist()
        return {
            "isaac_sim_version": "5.1.0",
            "robot": "Franka Panda",
            "pick_position_m": [pick_x, 0.3, 0.05],
            "target_position_m": target.tolist(),
            "final_cube_position_m": [value if math.isfinite(value) else None for value in final_position],
            "controller_done": controller_done,
            "steps": step,
            "max_steps": max_steps,
            **evaluate(controller_done, final_position, target.tolist()),
        }, app
    except Exception:
        traceback.print_exc()
        raise


def upload(result_path, run_id, case_id):
    import boto3

    required = ("S3_BUCKET", "S3_ENDPOINT_URL", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError(f"missing S3 environment variables: {', '.join(missing)}")
    bucket = os.environ["S3_BUCKET"]
    prefix = os.environ.get("S3_PREFIX", "isaac-pick-place").strip("/")
    key = f"{prefix}/{run_id}/{case_id}/result.json"
    client = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT_URL"], region_name=os.environ["AWS_DEFAULT_REGION"])
    client.upload_file(str(result_path), bucket, key)
    client.put_object(Bucket=bucket, Key=f"{prefix}/{run_id}/{case_id}/COMPLETE", Body=b"")
    print(f"published s3://{bucket}/{key}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--pick-x", type=float, required=True)
    parser.add_argument("--place-y", type=float, required=True)
    parser.add_argument("--max-steps", type=int, default=5000)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/isaac-results"))
    parser.add_argument("--local", action="store_true", help="keep result locally without S3 upload")
    args = parser.parse_args()
    for name in ("run_id", "case_id"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", getattr(args, name)):
            parser.error(f"--{name.replace('_', '-')} must use letters, digits, _ or -")
    if not math.isfinite(args.pick_x) or not math.isfinite(args.place_y) or args.max_steps < 1:
        parser.error("positions must be finite and --max-steps must be positive")
    if not args.local:
        required = ("S3_BUCKET", "S3_ENDPOINT_URL", "AWS_DEFAULT_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            parser.error(f"missing S3 environment variables: {', '.join(missing)}")

    result, app = simulate(args.pick_x, args.place_y, args.max_steps)
    result.update({"run_id": args.run_id, "case_id": args.case_id})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    result_path = args.output_dir / "result.json"
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result, allow_nan=False), flush=True)
    if not args.local:
        upload(result_path, args.run_id, args.case_id)
    # Isaac's fast shutdown exits Python, so publish before closing the app.
    app.close()


if __name__ == "__main__":
    main()
