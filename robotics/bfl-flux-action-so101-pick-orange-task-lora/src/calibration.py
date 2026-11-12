"""LeIsaac range-normalized values to the e2584b2 SO-101 degree frame.

Invert LeIsaac's USD-angle-to-motor-range conversion. The pinned HF demo
uses the e2584b2 statistics and feeds physical degrees directly to the policy;
the legacy model's sign flip and offsets must not be applied.

https://github.com/LightwheelAI/leisaac/blob/24d3bcd/source/leisaac/leisaac/utils/robot_utils.py
https://github.com/LightwheelAI/leisaac/blob/24d3bcd/source/leisaac/leisaac/assets/robots/lerobot.py
https://huggingface.co/spaces/multimodalart/flux-3-action-so101-sim/blob/d7da38e032da0e136d6de21c218dc616982a8cc9/app.py
https://huggingface.co/spaces/multimodalart/flux-3-action-so101-sim/blob/d7da38e032da0e136d6de21c218dc616982a8cc9/sim.py
"""

import math
import json
import hashlib
from pathlib import Path

POLICY_REVISION = "e2584b2698e3b88368854976e354af87ec9893c6"
STATE_NORMALIZER_SHA256 = "86b5d152c9df39a640248215469c97a3facf240d481ee0e3e29fd185b423e458"
ID = "leisaac-24d3bcd-to-flux-so101-e2584b2-sim-d7da38e"
JOINTS = (
    "shoulder_pan", "shoulder_lift", "elbow_flex",
    "wrist_flex", "wrist_roll", "gripper",
)
# Pinned LeIsaac assets/robots/lerobot.py: USD degrees and motor degrees.
USD_LIMITS = ((-110, 110), (-100, 100), (-100, 90), (-95, 95), (-160, 160))
MOTOR_LIMITS = ((-100, 100),) * 5


def coefficients() -> tuple[tuple[float, ...], tuple[float, ...]]:
    scales, offsets = [], []
    for (joint_lo, joint_hi), (motor_lo, motor_hi) in zip(
        USD_LIMITS, MOTOR_LIMITS, strict=True
    ):
        ratio = (joint_hi - joint_lo) / (motor_hi - motor_lo)
        scales.append(ratio)
        offsets.append(joint_lo - motor_lo * ratio)
    # Both LeIsaac and the released policy use gripper percentage points.
    return tuple(scales + [1.0]), tuple(offsets + [0.0])


SCALE, OFFSET = coefficients()


def to_policy(values) -> list[float]:
    if len(values) != 6 or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("expected six finite SO-101 motor values")
    return [float(value) * scale + offset for value, scale, offset in zip(values, SCALE, OFFSET)]


def to_motor(values) -> list[float]:
    if len(values) != 6 or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("expected six finite FLUX SO-101 values")
    return [(float(value) - offset) / scale for value, scale, offset in zip(values, SCALE, OFFSET)]


def transform_stats(stats: dict) -> dict:
    """Transform v2.1 per-episode stats before LeRobot aggregates them into v3."""
    for key in ("observation.state", "action"):
        item = stats[key]
        original_min, original_max = item["min"], item["max"]
        if len(original_min) != 6 or len(original_max) != 6 or len(item["std"]) != 6:
            raise ValueError(f"invalid {key} calibration statistics")
        item["min"] = [min(lo * scale + offset, hi * scale + offset)
                       for lo, hi, scale, offset in zip(original_min, original_max, SCALE, OFFSET, strict=True)]
        item["max"] = [max(lo * scale + offset, hi * scale + offset)
                       for lo, hi, scale, offset in zip(original_min, original_max, SCALE, OFFSET, strict=True)]
        item["mean"] = to_policy(item["mean"])
        item["std"] = [float(value) * abs(scale) for value, scale in zip(item["std"], SCALE, strict=True)]
    return stats


def check_model_overlap(dataset_root: Path, policy_root: Path, report_path: Path) -> dict:
    """Catch a wholly out-of-frame joint before spending hours on LoRA."""
    import pyarrow.parquet as pq
    from safetensors import safe_open

    normalizer = policy_root / "policy_preprocessor_step_3_flux3_observation_history_normalizer.safetensors"
    digest = hashlib.sha256(normalizer.read_bytes()).hexdigest()
    if digest != STATE_NORMALIZER_SHA256:
        raise ValueError("checkpoint statistics do not match the e2584b2 calibration")
    with safe_open(normalizer, framework="np") as weights:
        low = weights.get_tensor("state.q01").tolist()
        high = weights.get_tensor("state.q99").tolist()
    if len(low) != 6 or len(high) != 6:
        raise ValueError("checkpoint state normalizer is not six-dimensional")
    paths = sorted((dataset_root / "data").glob("**/*.parquet"))
    if not paths:
        raise ValueError("converted dataset has no parquet data")
    total = 0
    outside = [0] * 6
    for path in paths:
        for values in pq.read_table(path, columns=["observation.state"]).column(0).to_pylist():
            if len(values) != 6 or not all(math.isfinite(value) for value in values):
                raise ValueError(f"calibrated state must contain six finite values: {path}")
            total += 1
            for index, value in enumerate(values):
                if value < low[index] or value > high[index]:
                    outside[index] += 1
    if not total:
        raise ValueError("converted dataset has no state rows")
    report = {
        "calibration_id": ID,
        "policy_revision": POLICY_REVISION,
        "state_normalizer_sha256": digest,
        "frames": total,
        "joint_order": JOINTS,
        "policy_scale": SCALE,
        "policy_offset": OFFSET,
        "checkpoint_state_q01": low,
        "checkpoint_state_q99": high,
        "outside_q01_q99_fraction": [count / total for count in outside],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    missing = [JOINTS[index] for index, count in enumerate(outside) if count == total]
    if missing:
        raise ValueError(f"calibrated data has no overlap with checkpoint state range: {missing}")
    return report
