"""Exercise Job wiring without downloading packages or using cloud/model access."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("document_job_runner", ROOT / "scripts/run_job.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class JobRunnerTests(unittest.TestCase):
    def execute(self, *, complete=True, index_code=0, extra_env=None):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            calls, output = [], io.StringIO()
            store, prepare = Mock(), Mock()

            def fetch(target):
                self.assertEqual(target, folder)
                (target / "worker").mkdir()
                (target / "worker/requirements.txt").write_text(
                    "torch==2.7.1\ntransformers==4.51.3\nboto3==1.38.46\n")

            def cli(args):
                calls.append(args)
                if args[0] == "index":
                    if index_code:
                        return index_code
                    report = folder / ".state/index.json"
                    report.parent.mkdir()
                    report.write_text(json.dumps({"complete": complete, "documents_total": 1000, "documents_completed": 1000 if complete else 600,
                        "documents_reused": 0, "documents_new": 1000 if complete else 600,
                        "documents_remaining": 0 if complete else 400, "chunks_saved": 1970 if complete else 1206}))
                else:
                    target = Path(args[args.index("--output-dir") + 1])
                    target.mkdir()
                    (target / "search.json").write_text('{"matches": []}')
                    (target / "search.html").write_text("<html>Recorded search</html>")
                return 0

            env = {"RUN_ROOT": "s3://test-bucket/recipe", "AWS_SECRET_ACCESS_KEY": "test-secret",
                   **(extra_env or {})}
            with patch.dict(os.environ, env, clear=True), patch.object(runner, "WORKSPACE", folder), \
                    patch.object(runner, "fetch_recipe", side_effect=fetch), \
                    patch.object(runner.subprocess, "run") as pip, \
                    patch.object(runner, "load_worker", return_value=(prepare, cli, Mock(return_value=store))) as load, \
                    contextlib.redirect_stdout(output):
                code = runner.main()
            self.assertNotIn("test-secret", output.getvalue())
            prepare.assert_called_once_with(folder / "data/job-documents", folder / ".state/job-data-cache")
            self.assertNotIn("torch==2.7.1", pip.call_args.args[0])
            self.assertIn("transformers==4.51.3", pip.call_args.args[0])
            return code, calls, store, load.return_value[2], output.getvalue()

    def test_explicit_600_limit_publishes_report_without_query(self):
        code, calls, store, open_store, output = self.execute(
            complete=False, extra_env={"MAX_NEW_DOCUMENTS": "600"})
        self.assertEqual(code, 0)
        self.assertEqual([args[0] for args in calls], ["index"])
        self.assertEqual(calls[0][calls[0].index("--max-new-documents") + 1], "600")
        open_store.assert_called_once_with("s3://test-bucket/recipe/outputs")
        name, report = store.put_json.call_args.args
        self.assertRegex(name, r"^[0-9a-f]{32}\.json$")
        self.assertEqual(report["documents_completed"], 600)
        self.assertIn("preparation_seconds", report)
        store.put.assert_not_called()
        self.assertIn("s3://test-bucket/recipe/outputs/", output)

    def test_default_job_indexes_all_and_publishes_search_results(self):
        code, calls, store, _, output = self.execute(
            extra_env={"SEARCH_QUERY": "chess draw"})
        self.assertEqual(code, 0)
        self.assertNotIn("--max-new-documents", calls[0])
        report = store.put_json.call_args.args[1]
        self.assertEqual((report["documents_completed"], report["documents_new"], report["documents_reused"]),
                         (1000, 1000, 0))
        self.assertEqual(calls[1][:5], ["query", "--store", "s3://test-bucket/recipe/index", "--text", "chess draw"])
        self.assertEqual([c.args[0] for c in store.put.call_args_list], ["search.json", "search.html"])
        self.assertIn("s3://test-bucket/recipe/outputs/search.html", output)

    def launch(self, **settings):
        with tempfile.TemporaryDirectory() as temp:
            executable = Path(temp) / "nebius"
            executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            executable.chmod(0o755)
            env = {"PATH": temp + os.pathsep + os.defpath, "NEBIUS_PROJECT_ID": "project-fixture",
                   "NEBIUS_SUBNET_ID": "vpcsubnet-fixture", "S3_SECRET_ID": "mbsec-fixture",
                   "RUN_ROOT": "s3://fixture-bucket/run", "JOB_NAME": "document-index", **settings}
            return subprocess.run(["bash", str(ROOT / "scripts/submit.sh"), "--dry-run"], cwd=temp,
                                  env=env, capture_output=True, text=True)

    def test_launcher_defaults_to_no_cap_and_forwards_explicit_limit(self):
        for extra, expected in (({}, "0"), ({"MAX_NEW_DOCUMENTS": "600"}, "600")):
            with self.subTest(limit=expected):
                result = self.launch(**extra)
                result.check_returncode()
                args = result.stdout.splitlines()
                position = args.index("MAX_NEW_DOCUMENTS=" + expected)
                self.assertEqual(args[position - 1], "--env")
                self.assertEqual(args[-1], "--dry-run")

    def test_launcher_uses_selected_gpu_and_regional_storage(self):
        for region, platform, preset, settings in [
            ("eu-north1", "gpu-l40s-d", "1gpu-16vcpu-96gb", {}),
            ("eu-west1", "gpu-h200-sxm", "1gpu-16vcpu-200gb",
             {"NEBIUS_REGION": "eu-west1", "GPU_PLATFORM": "gpu-h200-sxm", "GPU_PRESET": "1gpu-16vcpu-200gb"}),
        ]:
            with self.subTest(region=region):
                result = self.launch(**settings)
                result.check_returncode()
                args = result.stdout.splitlines()
                self.assertEqual(args[args.index("--platform") + 1], platform)
                self.assertEqual(args[args.index("--preset") + 1], preset)
                self.assertEqual(args[args.index("--image") + 1], "pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime")
                self.assertIn(f"AWS_DEFAULT_REGION={region}", args)
                self.assertIn(f"S3_ENDPOINT_URL=https://storage.{region}.nebius.cloud", args)
                self.assertIn("--preemptible", args)

    def test_launcher_selects_blackwell_cuda_image(self):
        for region, platform, preset in [
            ("us-central1", "gpu-b200-sxm", "1gpu-20vcpu-224gb"),
            ("me-west1", "gpu-b200-sxm-a", "1gpu-20vcpu-224gb"),
            ("us-central1", "gpu-rtx6000", "1gpu-24vcpu-218gb"),
            ("eu-south1", "gpu-rtx6000-a", "1gpu-24vcpu-218gb"),
            ("eu-west2", "gpu-b300-sxm", "1gpu-24vcpu-346gb"),
        ]:
            with self.subTest(platform=platform):
                result = self.launch(NEBIUS_REGION=region, GPU_PLATFORM=platform, GPU_PRESET=preset)
                result.check_returncode()
                args = result.stdout.splitlines()
                self.assertEqual(args[args.index("--image") + 1], "pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime")

    def test_launcher_needs_a_gpu_pair_for_another_region(self):
        for settings in ({"NEBIUS_REGION": "eu-west1"}, {"GPU_PLATFORM": "gpu-h200-sxm"}):
            with self.subTest(settings=settings):
                result = self.launch(**settings)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("GPU_PRESET", result.stderr)

    def test_index_failure_does_not_publish_or_search(self):
        code, calls, store, open_store, _ = self.execute(index_code=1)
        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 1)
        open_store.assert_not_called()
        store.put_json.assert_not_called()

    def test_crash_flag_and_exit_code_are_preserved(self):
        code, calls, store, _, _ = self.execute(index_code=75, extra_env={"CRASH_AFTER_CHUNKS": "17"})
        self.assertEqual(code, 75)
        self.assertEqual(calls[0][-2:], ["--crash-after-chunks", "17"])
        store.put_json.assert_not_called()

    def test_downloads_only_the_recipe_allowlist_at_the_selected_revision(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"RECIPE_REF": "a" * 40}), \
                patch.object(runner, "urlopen", side_effect=lambda *a, **k: io.BytesIO(b"public source")) as fetch:
            runner.fetch_recipe(Path(temp))
            paths = {p.relative_to(temp).as_posix() for p in Path(temp).rglob("*") if p.is_file()}
        self.assertEqual(paths, set(runner.FILES))
        self.assertTrue(all((ROOT / path).is_file() for path in paths))
        self.assertTrue(all(c.args[0].startswith(
            "https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/" + "a" * 40 + "/inference/document-search/")
            for c in fetch.call_args_list))
        self.assertTrue(all(p.startswith(("worker/", "src/", "scripts/", "docs/brand/")) for p in paths))
