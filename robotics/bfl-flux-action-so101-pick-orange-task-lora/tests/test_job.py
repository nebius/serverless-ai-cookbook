"""Exercise job submission without contacting Nebius or launching compute."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODES = ['smoke', 'full']


class JobTests(unittest.TestCase):
    def test_submission_summary_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            cli = Path(directory) / "nebius"
            cli.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "print(json.dumps(sys.argv[1:]))\n"
                "sys.exit(int(os.environ.get('STUB_EXIT', '0')))\n"
            )
            cli.chmod(0o755)
            env = {"PATH": directory + os.pathsep + os.environ["PATH"],
                   "NEBIUS_PROFILE": "test-profile", "NEBIUS_PROJECT_ID": "test-project",
                   "NEBIUS_SUBNET_ID": "test-subnet", "NEBIUS_BUCKET_ID": "test-bucket",
                   "NEBIUS_IMAGE": "test-image", "RUN_NAME": "test-run",
                   "FULL_STEPS": "60000"}
            for mode in MODES:
                for dry_run in (False, True):
                    with self.subTest(mode=mode, dry_run=dry_run):
                        result = subprocess.run(
                            ["bash", str(ROOT / "scripts/job.sh"), mode]
                            + (["dry-run"] if dry_run else []),
                            env=env, capture_output=True, text=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        args = json.loads(result.stdout.splitlines()[0])
                        self.assertEqual(args[-1], "--dry-run" if dry_run else "--async")
                        if dry_run:
                            self.assertNotIn("Submitted:", result.stdout)
                        else:
                            name = args[args.index("--name") + 1]
                            self.assertIn(f"Submitted: {name}", result.stdout)
                            self.assertIn(f'--name "{name}"', result.stdout)
                            self.assertIn("nebius ai job logs JOB_ID", result.stdout)
                            self.assertIn("runs/test-run/", result.stdout)
                            self.assertIn("TRAIN_COMPLETE.json", result.stdout)
            removed = subprocess.run(
                ["bash", str(ROOT / "scripts/job.sh"), "check"],
                env=env, capture_output=True, text=True,
            )
            self.assertEqual(removed.returncode, 2)
            self.assertNotIn("Submitted:", removed.stdout)
            failed = subprocess.run(
                ["bash", str(ROOT / "scripts/job.sh"), "smoke"],
                env={**env, "STUB_EXIT": "7"}, capture_output=True, text=True,
            )
            self.assertEqual(failed.returncode, 7)
            self.assertNotIn("Submitted:", failed.stdout)


if __name__ == "__main__":
    unittest.main()
