"""Exercise the reader-facing artifact check with real files and corrupted weights."""

import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class VerifyTests(unittest.TestCase):
    def test_readme_stops_on_remote_errors_and_existing_results(self):
        block = re.search(r"## Verify your result.*?```bash\n(.*?)```",
                          (ROOT / "README.md").read_text(), re.S).group(1)
        for case in ("existing_results", "download_failure", "job_failure"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "bin").mkdir()
                (root / "scripts").mkdir()
                (root / "scripts/verify.py").write_text('print("PASS: reached verifier")')
                for name, body in {
                    "nebius": 'exit "$NEBIUS_STATUS"',
                    "aws": 'echo AWS_CALLED; exit 1',
                }.items():
                    path = root / "bin" / name
                    path.write_text("#!/bin/sh\n" + body + "\n")
                    path.chmod(0o755)
                if case == "existing_results":
                    results = root / "results/test-run"
                    results.mkdir(parents=True)
                    (results / "TRAIN_COMPLETE.json").write_text(json.dumps({
                        "selected_checkpoint": "checkpoints/000100/pretrained_model",
                        "checkpoint": "checkpoints/step-4",
                    }))
                env = os.environ | {
                    "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                    "NEBIUS_STATUS": "1" if case == "job_failure" else "0",
                    "NEBIUS_PROFILE": "test", "RUN_NAME": "test-run",
                    "NEBIUS_BUCKET": "test", "NEBIUS_S3_ENDPOINT": "https://example.invalid",
                }
                result = subprocess.run(["bash"], input=block, text=True, cwd=root,
                                        env=env, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("PASS:", result.stdout)
                if case != "download_failure":
                    self.assertNotIn("AWS_CALLED", result.stdout)

    def test_complete_corrupt_and_missing_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            weights = b"small deterministic weights"
            digest = hashlib.sha256(weights).hexdigest()
            checkpoint = root / "checkpoints/000100"
            for name in ("pretrained_model", "pretrained_model_ema"):
                path = checkpoint / name
                path.mkdir(parents=True)
                (path / "adapter_model.safetensors").write_bytes(weights)
            marker = checkpoint / "COMPLETE.json"
            record = {"step": 100, "calibration_id": "test", "adapter_sha256": digest,
                      "ema_adapter_sha256": digest}
            marker.write_text(json.dumps(record))
            receipt = {"status": "trained", "microsteps": 100, "calibration_id": "test",
                       "selected_checkpoint": "checkpoints/000100/pretrained_model", "checkpoints": [record]}
            model = checkpoint / "pretrained_model_ema/adapter_model.safetensors"
            (root / "TRAIN_COMPLETE.json").write_text(json.dumps(receipt))
            command = [sys.executable, str(ROOT / "scripts/verify.py"), str(root)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PASS:", result.stdout)
            model.write_bytes(b"corrupted")
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256 mismatch", result.stderr)
            model.write_bytes(weights)
            marker.unlink()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
