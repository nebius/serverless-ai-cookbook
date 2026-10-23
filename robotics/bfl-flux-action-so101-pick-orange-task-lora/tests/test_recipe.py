import importlib.util
import hashlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "src" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare_dataset = load("prepare_dataset")
calibration = load("calibration")
publish = load("publish")
train_job = load("train_job")


class RecipeTests(unittest.TestCase):
    def test_long_full_run_uses_requested_steps(self):
        with patch.dict(os.environ, {"FULL_STEPS": "60000"}):
            self.assertEqual(train_job.training_steps("full"), 60000)
            self.assertEqual(train_job.training_steps("smoke"), 100)
        with patch.dict(os.environ, {"FULL_STEPS": "60001"}):
            with self.assertRaisesRegex(SystemExit, "multiple of 5000"):
                train_job.training_steps("full")

    def test_full_training_disables_policy_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            result = work / "result"
            result.mkdir()
            with patch.dict(os.environ, {"RUN_NAME": "test-run"}, clear=True), \
                    patch.object(train_job.subprocess, "Popen") as process, \
                    patch.object(train_job, "publish", return_value=[{"step": 60000}]):
                process.return_value.stdout = io.StringIO("training\n")
                process.return_value.wait.return_value = 0
                train_job.train(work, result, work / "policy", work / "encoders", 60000)
            command = json.loads((result / "command.json").read_text())
            self.assertIn("--steps=60000", command)
            self.assertIn("--eval_steps=0", command)

    def test_publication_failure_stops_training_before_it_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            result = work / "result"
            result.mkdir()
            process = unittest.mock.MagicMock()
            process.pid = 12345
            terminated = []
            def output():
                self.assertEqual(terminated, [12345])
                yield "trainer stopped\n"
            process.stdout = output()
            process.wait.return_value = -15
            def thread(*, target, **kwargs):
                watcher = unittest.mock.MagicMock()
                watcher.start.side_effect = target
                return watcher
            event = unittest.mock.MagicMock()
            event.wait.return_value = False
            with patch.dict(os.environ, {"RUN_NAME": "test-run"}, clear=True), \
                    patch.object(train_job.threading, "Event", return_value=event), \
                    patch.object(train_job.threading, "Thread", side_effect=thread), \
                    patch.object(train_job.subprocess, "Popen", return_value=process) as spawn, \
                    patch.object(train_job.os, "killpg", side_effect=lambda pid, sig: terminated.append(pid)), \
                    patch.object(train_job, "publish", side_effect=OSError("storage unavailable")) as publisher:
                with self.assertRaisesRegex(RuntimeError, "publication failed"):
                    train_job.train(work, result, work / "policy", work / "encoders", 60000)
            self.assertTrue(spawn.call_args.kwargs["start_new_session"])
            self.assertEqual(terminated, [12345])
            process.wait.assert_any_call(timeout=30)
            self.assertEqual(publisher.call_count, 1)
            self.assertFalse((result / "TRAIN_COMPLETE.json").exists())

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
        recipe = json.loads((ROOT / "configs/recipe.json").read_text())
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

    def test_publication_skips_replaced_last_link_but_not_other_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "local"
            checkpoint = source / "checkpoints/000100/pretrained_model"
            checkpoint.mkdir(parents=True)
            (checkpoint / "adapter_model.safetensors").write_bytes(b"adapter")
            (checkpoint / "adapter_config.json").write_text("{}")
            last = source / "checkpoints/last"
            last.symlink_to("000100")
            target = root / "bucket"
            readlink = os.readlink

            def replace_link(path):
                last.unlink()
                try:
                    return readlink(path)
                finally:
                    last.symlink_to("000100")

            with patch.object(publish.os, "readlink", side_effect=replace_link):
                self.assertEqual(publish.publish(source, target), [])
            self.assertFalse(target.exists())
            with patch.object(publish.os, "readlink", side_effect=PermissionError("denied")):
                with self.assertRaises(PermissionError):
                    publish.publish(source, target)
            with patch.object(publish.shutil, "copyfile", side_effect=FileNotFoundError("source missing")):
                with self.assertRaises(FileNotFoundError):
                    publish.publish(source, target)
            self.assertFalse((target / "checkpoints/000100/COMPLETE.json").exists())
            self.assertEqual(publish.publish(source, target)[0]["step"], 100)

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
            self.assertEqual(records[0]["adapter_sha256"], hashlib.sha256(b"adapter").hexdigest())
            self.assertEqual(records[0]["ema_adapter_sha256"], hashlib.sha256(b"ema-adapter").hexdigest())
            self.assertEqual(publish.publish(root / "local", target), records)
            with self.assertRaisesRegex(ValueError, "calibration differs"):
                publish.publish(root / "local", target, calibration.ID)

if __name__ == "__main__":
    unittest.main()
