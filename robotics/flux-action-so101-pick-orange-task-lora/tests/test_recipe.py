import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_dataset = load("prepare_dataset")
calibration = load("calibration")
publish = load("publish")
summarize = load("summarize")
train_job = load("train_job")


class RecipeTests(unittest.TestCase):
    def test_long_full_run_uses_requested_steps(self):
        with patch.dict(os.environ, {"FULL_STEPS": "60000"}):
            self.assertEqual(train_job.training_steps("full"), 60000)
            self.assertEqual(train_job.training_steps("smoke"), 100)
        with patch.dict(os.environ, {"FULL_STEPS": "60001"}):
            with self.assertRaisesRegex(SystemExit, "multiple of 5000"):
                train_job.training_steps("full")

    def test_wandb_flags_enable_metrics_without_exposing_api_key(self):
        with patch.dict(os.environ, {"WANDB_API_KEY": "test-key", "WANDB_PROJECT": "test-project",
                                    "WANDB_ENTITY": "test-team"}, clear=True):
            options = train_job.wandb_options("test-run")
        self.assertIn("--wandb.enable=true", options)
        self.assertIn("--wandb.disable_artifact=true", options)
        self.assertIn("--wandb.project=test-project", options)
        self.assertIn("--wandb.entity=test-team", options)
        self.assertIn("--job_name=test-run", options)
        self.assertNotIn("test-key", " ".join(options))
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(train_job.wandb_options("test-run"), [])

    def test_calibration_maps_real_demo_start_and_round_trips(self):
        # Pinned episode 0, frame 0: the previous code sent lift=-47.5 to a
        # checkpoint whose shoulder-lift q01 is +84.8 degrees.
        motor = [-16.2, -47.5, 55.2, 47.9, 4.5, 4.0]
        model = calibration.to_policy(motor)
        self.assertGreater(model[1], 84.8)
        self.assertLess(model[1], 184.3)
        self.assertGreater(model[2], 61.4)
        self.assertEqual(model[5], motor[5])
        for actual, expected in zip(calibration.to_motor(model), motor, strict=True):
            self.assertAlmostEqual(actual, expected)

    def test_calibration_transforms_episode_statistics(self):
        stats = {
            key: {"min": [-30, -90, -90, 20, -10, 0],
                  "max": [50, 60, 100, 100, 50, 90],
                  "mean": [0, -10, 5, 40, 10, 20],
                  "std": [2, 3, 4, 5, 6, 7], "count": [10]}
            for key in ("action", "observation.state")
        }
        converted = calibration.transform_stats(stats)
        self.assertAlmostEqual(converted["action"]["min"][1], 30)
        self.assertAlmostEqual(converted["action"]["max"][1], 180)
        self.assertAlmostEqual(converted["action"]["mean"][1], 100)
        self.assertAlmostEqual(converted["action"]["std"][2], 3.8)
        self.assertEqual(converted["action"]["count"], [10])

    def test_source_parquet_and_stats_use_same_calibration(self):
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            import numpy as np
            from safetensors.numpy import save_file
        except ImportError:
            self.skipTest("parquet and safetensors readers are installed in the training image")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data/chunk-000").mkdir(parents=True)
            (root / "meta").mkdir()
            path = root / "data/chunk-000/episode_000000.parquet"
            motor = [-16.2, -47.5, 55.2, 47.9, 4.5, 4.0]
            pq.write_table(pa.table({
                "observation.state": [motor], "action": [motor],
            }), path)
            stats = {
                key: {"min": motor, "max": motor, "mean": motor,
                      "std": [0] * 6, "count": [1]}
                for key in ("action", "observation.state")
            }
            (root / "meta/episodes_stats.jsonl").write_text(
                json.dumps({"episode_index": 0, "stats": stats}) + "\n"
            )
            policy = root / "policy"
            policy.mkdir()
            save_file({
                "state.q01": np.array([-200, 84.8, -200, -200, -200, -1], dtype=np.float32),
                "state.q99": np.array([200, 184.3, 200, 200, 200, 101], dtype=np.float32),
            }, policy / "policy_preprocessor_step_3_flux3_observation_history_normalizer.safetensors")
            with self.assertRaisesRegex(ValueError, "shoulder_lift"):
                calibration.check_model_overlap(root, policy, root / "before.json")
            prepare_dataset.calibrate_source(root, 1)
            report = calibration.check_model_overlap(root, policy, root / "after.json")
            self.assertEqual(report["outside_q01_q99_fraction"][1], 0)
            mapped = pq.read_table(path).to_pylist()[0]
            converted_stats = json.loads((root / "meta/episodes_stats.jsonl").read_text())["stats"]
            for key in ("action", "observation.state"):
                self.assertAlmostEqual(mapped[key][1], calibration.to_policy(motor)[1], places=5)
                self.assertAlmostEqual(converted_stats[key]["mean"][1], mapped[key][1], places=5)

    def test_dataset_contract_rejects_wrong_camera_or_joint_order(self):
        recipe = json.loads((ROOT / "recipe.json").read_text())
        source = recipe["dataset"]
        features = {
            key: {"dtype": "float32", "shape": [6], "names": prepare_dataset.JOINTS.copy()}
            for key in ("action", "observation.state")
        }
        features.update({key: {"dtype": "video"} for key in source["cameras"]})
        info = {
            "codebase_version": "v2.1", "fps": 30,
            "total_episodes": 60, "total_frames": 36293,
            "features": features,
        }
        prepare_dataset.check_info(info, source, "v2.1")
        info["features"]["action"]["names"].reverse()
        with self.assertRaisesRegex(ValueError, "joint order"):
            prepare_dataset.check_info(info, source, "v2.1")
        info["features"]["action"]["names"].reverse()
        del info["features"][source["cameras"][0]]
        with self.assertRaisesRegex(ValueError, "camera keys"):
            prepare_dataset.check_info(info, source, "v2.1")

    def test_episode_statistics_accept_source_schema_and_reject_missing_episode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episodes_stats.jsonl"
            stats = {
                key: {"min": [-30, -90, -90, 20, -10, 0],
                      "max": [50, 60, 100, 100, 50, 90],
                      "mean": [0, -10, 5, 40, 10, 20],
                      "std": [2, 3, 4, 5, 6, 7]}
                for key in ("action", "observation.state")
            }
            path.write_text("".join(json.dumps({"episode_index": i, "stats": stats}) + "\n" for i in range(2)))
            prepare_dataset.check_episode_stats(path, 2)
            with self.assertRaisesRegex(ValueError, "expected 3 episode statistics"):
                prepare_dataset.check_episode_stats(path, 3)

    def test_publication_requires_last_checkpoint_and_hashes_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "local/checkpoints/000100/pretrained_model"
            checkpoint.mkdir(parents=True)
            (checkpoint / "adapter_model.safetensors").write_bytes(b"adapter")
            (checkpoint / "adapter_config.json").write_text("{}")
            ema = checkpoint.parent / "pretrained_model_ema"
            ema.mkdir()
            (ema / "adapter_model.safetensors").write_bytes(b"ema-adapter")
            (ema / "adapter_config.json").write_text("{}")
            target = root / "bucket"
            self.assertEqual(publish.publish(root / "local", target), [])
            (root / "local/checkpoints/last").symlink_to("000100")
            records = publish.publish(root / "local", target)
            self.assertEqual(records[0]["step"], 100)
            self.assertEqual(records[0]["directory"], "000100")
            marker = target / "checkpoints/000100/COMPLETE.json"
            self.assertTrue(marker.is_file())
            published = target / "checkpoints/000100"
            self.assertEqual(publish.verify_adapter(published / "pretrained_model", records[0]),
                             records[0]["adapter_sha256"])
            self.assertEqual(publish.verify_adapter(published / "pretrained_model_ema", records[0]),
                             records[0]["ema_adapter_sha256"])
            self.assertNotEqual(records[0]["adapter_sha256"], records[0]["ema_adapter_sha256"])
            self.assertEqual(publish.publish(root / "local", target), records)
            with self.assertRaisesRegex(ValueError, "no published checksum"):
                publish.verify_adapter(published / "pretrained_model_ema",
                                       {"adapter_sha256": records[0]["adapter_sha256"]})
            (published / "pretrained_model_ema/adapter_model.safetensors").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                publish.verify_adapter(published / "pretrained_model_ema", records[0])
            with self.assertRaisesRegex(ValueError, "calibration differs"):
                publish.publish(root / "local", target, calibration.ID)

    def test_quality_gate_uses_paired_episodes(self):
        common = {
            "task": "LeIsaac-SO101-PickOrange-v0",
            "dataset_revision": "pin", "calibration_id": calibration.ID, "leisaac_revision": "pin",
            "seed_start": 42, "episode_length_s": 120, "control_hz": 30,
            "physics_hz": 60, "physics_steps_per_action": 1,
        }
        base = {
            **common, "model": "base",
            "episodes": [{"seed": 42 + i, "oranges_placed": 0, "placed": [False] * 3,
                          "full_task_success": False} for i in range(25)],
        }
        adapter = {
            **common, "model": "adapter",
            "episodes": [{"seed": 42 + i, "oranges_placed": 1, "placed": [True, False, False],
                          "full_task_success": False} for i in range(25)],
        }
        report = summarize.summarize(base, adapter)
        self.assertEqual(report["adapter_oranges_placed"], 25)
        self.assertTrue(report["quality_pass"])
        adapter["episodes"][0]["seed"] = 999
        with self.assertRaisesRegex(ValueError, "seeds"):
            summarize.summarize(base, adapter)
        adapter["episodes"][0]["seed"] = 42
        adapter["physics_steps_per_action"] = 2
        with self.assertRaisesRegex(ValueError, "physics_steps_per_action"):
            summarize.summarize(base, adapter)
        adapter["physics_steps_per_action"] = 1
        adapter["calibration_id"] = "wrong"
        with self.assertRaisesRegex(ValueError, "calibration_id"):
            summarize.summarize(base, adapter)


if __name__ == "__main__":
    unittest.main()
