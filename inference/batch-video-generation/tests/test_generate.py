"""Offline protocol and recovery checks. Fixture MP4s are not model output."""
import contextlib
import csv
from email.parser import BytesParser
from email.policy import default
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

SOURCE = Path(__file__).resolve().parents[1] / "src/generate.py"
SPEC = importlib.util.spec_from_file_location("video_batch", SOURCE)
video = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(video)


class FixtureApi:
    """An in-memory HTTP transport; actual multipart/JSON/download paths run."""
    def __init__(self, mp4):
        self.mp4 = mp4
        self.jobs = {}
        self.posts = 0
        self.hold = False
        self.truncate_once = False
        self.ambiguous_once = False

    def open(self, req, timeout=None):
        self.assert_auth(req)
        path = urllib.parse.urlsplit(req.full_url).path
        if path == "/v1/models":
            return self.response({"data": [{"id": video.MODEL}]})
        if path == "/v1/videos" and req.get_method() == "POST":
            message = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + req.get_header("Content-type").encode() + b"\r\n\r\n" + req.data
            )
            fields = {part.get_param("name", header="content-disposition"): part.get_content().strip()
                      for part in message.iter_parts()}
            if fields.get("model") != video.MODEL or not fields.get("prompt"):
                raise AssertionError("Malformed request")
            if fields.get("flow_shift") != "3.0" or fields.get("boundary_ratio") != "0.0":
                raise AssertionError("Wan settings missing")
            self.posts += 1
            job_id = f"video-{self.posts}"
            self.jobs[job_id] = fields
            if self.ambiguous_once:
                self.ambiguous_once = False
                self.error(req, 503)
            return self.response({"id": job_id, "status": "queued"})
        if path.startswith("/v1/videos/"):
            job_id = path.split("/")[3]
            if job_id not in self.jobs:
                self.error(req, 404)
            if path.endswith("/content"):
                payload = self.mp4
                if self.truncate_once:
                    self.truncate_once = False
                    payload = payload[:len(payload) // 2]
                return io.BytesIO(payload)
            return self.response({"id": job_id, "status": "queued" if self.hold else "completed"})
        self.error(req, 404)

    @staticmethod
    def assert_auth(req):
        if req.get_header("Authorization") != "Bearer fixture-token":
            raise AssertionError("Authorization header missing")

    @staticmethod
    def response(value):
        return io.BytesIO(json.dumps(value).encode())

    @staticmethod
    def error(req, status):
        raise urllib.error.HTTPError(req.full_url, status, "fixture", {}, io.BytesIO(b'{"detail":"fixture failure"}'))


class InputTests(unittest.TestCase):
    def test_dangerous_and_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            for body in ["id,prompt,seed\n../outside,test,1\n", "id,prompt,seed\nsame,a,1\nsame,b,2\n"]:
                path.write_text(body)
                with self.assertRaises(video.RecipeError):
                    video.read_prompts(path)

    def test_input_check_does_not_need_auth_or_network(self):
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(video.main(["--check-input"]), 0)

    def test_tokens_are_not_allowed_in_urls(self):
        with self.assertRaises(video.RecipeError):
            video.Client("https://user:secret@example.com", "fixture")


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is needed for decode checks")
class RecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory()
        path = Path(cls.fixture_dir.name) / "fixture.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x96:rate=5",
                        "-frames:v", "5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(path)], check=True, capture_output=True)
        cls.mp4 = path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.csv = self.root / "prompts.csv"
        self.output = self.root / "results"
        self.write_rows(3)
        self.api = FixtureApi(self.mp4)

    def tearDown(self):
        self.directory.cleanup()

    def write_rows(self, count):
        with self.csv.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "prompt", "seed"])
            for index in range(count):
                writer.writerow([f"clip-{index}", f"A paper boat number {index} on a pond.", index])

    def run_client(self, *extra):
        args = ["--input", str(self.csv), "--output", str(self.output), "--size", "160x96",
                "--frames", "5", "--fps", "5", "--steps", "1", "--poll-interval", "0.01"]
        with patch.dict(os.environ, {"BASE_URL": "http://localhost:8000", "ENDPOINT_TOKEN": "fixture-token"}), \
             patch("urllib.request.build_opener", return_value=self.api), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return video.main(args + list(extra))

    def test_completed_clips_survive_partial_batch_and_zero_request_rerun(self):
        self.assertEqual(self.run_client("--limit", "1"), 0)
        self.assertEqual(self.api.posts, 1)
        self.assertEqual(self.run_client(), 0)
        self.assertEqual(self.api.posts, 3)
        self.assertEqual(self.run_client(), 0)
        self.assertEqual(self.api.posts, 3)
        summary = json.loads((self.output / "summary.json").read_text())
        self.assertEqual(summary["completed"], 3)
        self.assertTrue(all(row["validation"]["frames_decoded"] == 5 for row in summary["outputs"]))
        self.assertIn("Powered by Nebius Serverless AI", (self.output / "index.html").read_text())

    def test_export_checker_verifies_batch_without_endpoint_calls(self):
        self.assertEqual(self.run_client(), 0)
        checker_spec = importlib.util.spec_from_file_location("video_result_checker", SOURCE.parents[1] / "scripts/check_results.py")
        checker = importlib.util.module_from_spec(checker_spec)
        checker_spec.loader.exec_module(checker)
        result = checker.check(self.output)
        self.assertEqual(result["completed"], 3)
        self.assertEqual(result["frames_per_clip"], [5])
        self.assertEqual(self.api.posts, 3)
        manifest = self.output / "clips.csv"
        manifest.write_text(manifest.read_text().replace("clip-0", "unknown", 1))
        with self.assertRaisesRegex(checker.RecipeError, "CSV clip manifest"):
            checker.check(self.output)

    def test_changed_prompt_refuses_stale_output(self):
        self.write_rows(1)
        self.assertEqual(self.run_client(), 0)
        self.csv.write_text("id,prompt,seed\nclip-0,A different scene,0\n")
        self.assertEqual(self.run_client(), 1)
        self.assertEqual(self.api.posts, 1)

    def test_truncated_download_never_becomes_complete_and_can_be_redownloaded(self):
        self.write_rows(1)
        self.api.truncate_once = True
        self.assertEqual(self.run_client(), 1)
        self.assertFalse((self.output / "clip-0.json").exists())
        self.assertTrue((self.output / ".pending/clip-0.json").exists())
        self.assertEqual(self.run_client(), 0)
        self.assertEqual(self.api.posts, 1)  # Redownload, no second paid generation.

    def test_lost_server_job_requires_explicit_resubmission(self):
        self.write_rows(1)
        self.api.hold = True
        self.assertEqual(self.run_client("--generation-timeout", "0.02"), 1)
        self.api.jobs.clear()
        self.api.hold = False
        self.assertEqual(self.run_client(), 1)
        self.assertEqual(self.api.posts, 1)
        self.assertEqual(self.run_client("--retry-lost"), 0)
        self.assertEqual(self.api.posts, 2)

    def test_ambiguous_post_does_not_silently_duplicate_generation(self):
        self.write_rows(1)
        self.api.ambiguous_once = True
        self.assertEqual(self.run_client(), 1)
        self.assertEqual(self.run_client(), 1)
        self.assertEqual(self.api.posts, 1)
        self.api.jobs.clear()  # Represents checking/stopping/restarting the old Endpoint.
        self.assertEqual(self.run_client("--retry-lost"), 0)
        self.assertEqual(self.api.posts, 2)

    def test_hash_mismatch_refuses_corrupt_saved_clip(self):
        self.write_rows(1)
        self.assertEqual(self.run_client(), 0)
        path = self.output / "clip-0.mp4"
        path.write_bytes(path.read_bytes()[:100])
        self.assertEqual(self.run_client(), 1)
        self.assertEqual(self.api.posts, 1)


if __name__ == "__main__":
    unittest.main()
