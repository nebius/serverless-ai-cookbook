"""Compare paired FLUX base/adapter LeIsaac rollouts and published ACT context."""

import argparse
import json
import random
from pathlib import Path

RECIPE = json.loads((Path(__file__).parent / "recipe.json").read_text())


def summarize(base: dict, adapter: dict) -> dict:
    if base["model"] != "base" or adapter["model"] != "adapter":
        raise ValueError("expected base and adapter evaluation reports")
    for key in ("task", "dataset_revision", "calibration_id", "leisaac_revision", "seed_start",
                "episode_length_s", "control_hz", "physics_hz", "physics_steps_per_action"):
        if base[key] != adapter[key]:
            raise ValueError(f"evaluation protocol differs: {key}")
    before, after = base["episodes"], adapter["episodes"]
    if len(before) != 25 or len(after) != 25:
        raise ValueError("quality report requires 25 paired episodes per policy")
    seeds = [row["seed"] for row in before]
    if seeds != [row["seed"] for row in after] or len(set(seeds)) != 25:
        raise ValueError("evaluation seeds are not paired and unique")
    for row in before + after:
        if not 0 <= row["oranges_placed"] <= 3 or row["oranges_placed"] != sum(row["placed"]):
            raise ValueError("invalid per-episode orange count")
    base_placed = sum(row["oranges_placed"] for row in before)
    adapter_placed = sum(row["oranges_placed"] for row in after)
    differences = [new["oranges_placed"] - old["oranges_placed"]
                   for old, new in zip(before, after, strict=True)]
    rng = random.Random(42)
    bootstrap = sorted(sum(rng.choices(differences, k=25)) for _ in range(10_000))
    ci = [bootstrap[249], bootstrap[9749]]
    quality_pass = adapter_placed >= 25 and adapter_placed - base_placed >= 10 and ci[0] > 0
    return {
        "task": base["task"],
        "calibration_id": base["calibration_id"],
        "episodes_per_policy": 25,
        "base_oranges_placed": base_placed,
        "adapter_oranges_placed": adapter_placed,
        "oranges_possible": 75,
        "paired_improvement": adapter_placed - base_placed,
        "paired_episode_bootstrap_95pct_difference": ci,
        "base_full_task_successes": sum(row["full_task_success"] for row in before),
        "adapter_full_task_successes": sum(row["full_task_success"] for row in after),
        "published_act_reference": RECIPE["published_act_reference"],
        "quality_pass": quality_pass,
        "note": "ACT's published 33/75 used its own runs and policy; it is context, not a FLUX reproduction target on identical seeds.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = summarize(json.loads(args.base.read_text()), json.loads(args.adapter.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
