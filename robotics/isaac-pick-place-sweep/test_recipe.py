import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from launch import expand_sweep, job_command, job_id_from_output
from run import evaluate, main as run_case, upload


class RecipeTest(unittest.TestCase):
    def test_four_independent_jobs(self):
        points = expand_sweep(json.loads(Path(__file__).with_name("sweep.json").read_text()))
        self.assertEqual(points, [
            {"pick_x": 0.4, "place_y": 0.2},
            {"pick_x": 0.4, "place_y": 0.22},
            {"pick_x": 0.42, "place_y": 0.2},
            {"pick_x": 0.42, "place_y": 0.22},
        ])
        options = SimpleNamespace(
            image="example/image:tag", platform="gpu-l40s-a", preset="1gpu-8vcpu-32gb",
            timeout="2h", bucket="bucket", region="eu-north1", s3_secret="storage-keys",
            prefix="isaac-pick-place", subnet_id=None,
            profile=None, record_motion=False,
        )
        commands = [job_command(options, "run-1", f"case-{i:03d}", point) for i, point in enumerate(points)]
        self.assertEqual(len({command[command.index("--name") + 1] for command in commands}), 4)
        self.assertTrue(all(command.count("--env-secret") == 2 for command in commands))
        self.assertTrue(all("--args" in command for command in commands))
        self.assertTrue(all("--async" in command for command in commands))
        self.assertTrue(all("--container-command" not in command for command in commands))
        self.assertTrue(all("--inject-file" not in command for command in commands))
        self.assertTrue(all(command[command.index("--image") + 1] == options.image for command in commands))
        self.assertTrue(all("AWS_ACCESS_KEY_ID=storage-keys" in command for command in commands))
        self.assertTrue(all("AWS_SECRET_ACCESS_KEY=storage-keys" in command for command in commands))
        self.assertTrue(all("S3_ENDPOINT_URL=https://storage.eu-north1.nebius.cloud" in command for command in commands))
        self.assertTrue(all("/opt/isaac-sweep/run.py" not in command[command.index("--args") + 1] for command in commands))
        options.record_motion = True
        recorded = job_command(options, "run-1", "case-000", points[0])
        self.assertIn("--record-motion", recorded[recorded.index("--args") + 1])

    def test_task_success_needs_controller_and_final_pose(self):
        target = [-0.4, 0.2, 0.02575]
        self.assertTrue(evaluate(True, target, target)["success"])
        self.assertFalse(evaluate(False, target, target)["success"])
        self.assertFalse(evaluate(True, [-0.2, 0.2, 0.02575], target)["success"])
        self.assertFalse(evaluate(True, [float("nan"), 0.2, 0.02575], target)["success"])

    def test_cli_job_id_from_human_output(self):
        output = "Job ID: aijob-abc123\nJob created successfully.\nID: aijob-abc123\n"
        self.assertEqual(job_id_from_output(output), "aijob-abc123")

    def test_upload_marks_complete_last(self):
        calls = []
        client = SimpleNamespace(
            upload_file=lambda *args: calls.append(("result", args)),
            put_object=lambda **kwargs: calls.append(("complete", kwargs)),
        )
        env = {
            "S3_BUCKET": "bucket", "S3_ENDPOINT_URL": "https://storage.example",
            "AWS_DEFAULT_REGION": "eu-north1", "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
            "S3_PREFIX": "isaac-pick-place",
        }
        with tempfile.TemporaryDirectory() as directory:
            result = Path(directory) / "result.json"
            result.write_text("{}")
            with patch.dict(os.environ, env), patch.dict(sys.modules, {"boto3": SimpleNamespace(client=lambda *a, **k: client)}):
                recording = Path(directory) / "trajectory.json"
                recording.write_text("{}")
                upload(result, "run-1", "case-000", recording)
        self.assertEqual([name for name, _ in calls], ["result", "result", "complete"])
        self.assertEqual(calls[0][1][2], "isaac-pick-place/run-1/case-000/trajectory.json")
        self.assertEqual(calls[1][1][2], "isaac-pick-place/run-1/case-000/result.json")
        self.assertEqual(calls[2][1]["Key"], "isaac-pick-place/run-1/case-000/COMPLETE")

    def test_upload_error_keeps_job_failed(self):
        closed = []
        app = SimpleNamespace(close=lambda: closed.append(True))
        env = {
            "S3_BUCKET": "bucket", "S3_ENDPOINT_URL": "https://storage.example",
            "AWS_DEFAULT_REGION": "eu-north1", "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
        }
        with tempfile.TemporaryDirectory() as directory:
            arguments = [
                "run.py", "--run-id", "run-1", "--case-id", "case-000",
                "--pick-x", "0.4", "--place-y", "0.2", "--output-dir", directory,
            ]
            with patch.dict(os.environ, env), patch.dict(sys.modules, {"isaacsim": SimpleNamespace(SimulationApp=lambda _: app)}):
                with patch.object(sys, "argv", arguments), patch("run.simulate", return_value={"success": True}):
                    with patch("run.upload", side_effect=RuntimeError("upload failed")):
                        with self.assertRaisesRegex(RuntimeError, "upload failed"):
                            run_case()
        self.assertEqual(closed, [])


if __name__ == "__main__":
    unittest.main()
