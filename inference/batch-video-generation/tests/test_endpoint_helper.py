"""Offline launcher contract checks: subprocesses and HTTP are mocked."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SOURCE = Path(__file__).resolve().parents[1] / "scripts/endpoint.py"
SPEC = importlib.util.spec_from_file_location("endpoint_launcher", SOURCE)
endpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(endpoint)

FIXTURE_TOKEN = "fixture-endpoint-credential-not-a-real-token"


class EndpointHelperTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "config").mkdir()
        self.config = {"image": "vllm/vllm-omni:v0.24.0", "model": "sample-model",
                       "platform": "gpu-h100-sxm", "preset": "1gpu-16vcpu-200gb",
                       "container_command": "vllm", "args": "serve sample-model --omni"}
        (self.root / "config/endpoint.json").write_text(json.dumps(self.config))
        self.patches = [patch.object(endpoint, "ROOT", self.root),
                        patch.object(endpoint, "STATE", self.root / ".state/endpoint.json")]
        for item in self.patches:
            item.start()
        self.ep = {"metadata": {"id": "aiendpoint-recipe", "name": "recipe-spot", "parent_id": "project-test"},
                   "spec": {"preemptible": True, "platform": self.config["platform"], "preset": self.config["preset"],
                            "auth_token": FIXTURE_TOKEN},
                   "status": {"state": "RUNNING", "public_endpoints": ["https://endpoint.invalid"]}}
        endpoint.save_state({"id": "aiendpoint-recipe", "project_id": "project-test", "model": "sample-model"})

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.directory.cleanup()

    @staticmethod
    def create_args(**changes):
        values = dict(project_id="project-test", name="recipe-spot", subnet_id="vpcsubnet-test",
                      spot_pricing_policy_id=None, dry_run=False, yes=True)
        return argparse.Namespace(**{**values, **changes})

    def test_create_rejects_invalid_project_id_before_version_or_cli_calls(self):
        invalid = ("", " ", "YOUR_PROJECT_ID", "<PROJECT_ID>", "project-YOUR_PROJECT_ID",
                   "project-", "project-placeholder", "vpcsubnet-test", "tenant-test",
                   " project-test", "project-test ")
        for value in invalid:
            with self.subTest(project_id=value), \
                 patch("sys.argv", ["endpoint.py", "create", "--project-id", value,
                                    "--name", "recipe-spot", "--dry-run"]), \
                 patch.object(endpoint, "version_check") as version, \
                 patch.object(endpoint, "cli") as cli, \
                 patch("subprocess.run") as process, \
                 contextlib.redirect_stderr(io.StringIO()) as error, \
                 self.assertRaises(SystemExit) as result:
                endpoint.main()
            self.assertEqual(result.exception.code, 2)
            self.assertIn("--project-id", error.getvalue())
            self.assertIn("project-", error.getvalue())
            version.assert_not_called()
            cli.assert_not_called()
            process.assert_not_called()

    def test_create_rejects_explicit_invalid_subnet_before_version_or_cli_calls(self):
        invalid = ("", " ", "YOUR_SUBNET_ID", "<SUBNET_ID>", "vpcsubnet-YOUR_SUBNET_ID",
                   "vpcsubnet-", "vpcsubnet-placeholder", "project-test", "subnet-test",
                   " vpcsubnet-test", "vpcsubnet-test ")
        for value in invalid:
            with self.subTest(subnet_id=value), \
                 patch("sys.argv", ["endpoint.py", "create", "--project-id", "project-test",
                                    "--subnet-id", value, "--name", "recipe-spot", "--dry-run"]), \
                 patch.object(endpoint, "version_check") as version, \
                 patch.object(endpoint, "cli") as cli, \
                 patch("subprocess.run") as process, \
                 contextlib.redirect_stderr(io.StringIO()) as error, \
                 self.assertRaises(SystemExit) as result:
                endpoint.main()
            self.assertEqual(result.exception.code, 2)
            self.assertIn("--subnet-id", error.getvalue())
            self.assertIn("vpcsubnet-", error.getvalue())
            version.assert_not_called()
            cli.assert_not_called()
            process.assert_not_called()

    def test_create_accepts_valid_ids_and_an_omitted_optional_subnet(self):
        project_id = "project-e00abcdefghijklmnopqrst"
        for subnet_id in (None, "vpcsubnet-e00abcdefghijklmnopqrst"):
            argv = ["endpoint.py", "create", "--project-id", project_id,
                    "--name", "recipe-spot", "--dry-run"]
            if subnet_id is not None:
                argv += ["--subnet-id", subnet_id]
            with self.subTest(subnet_id=subnet_id), patch("sys.argv", argv), \
                 patch.object(endpoint, "version_check") as version, \
                 patch.object(endpoint, "cli", return_value={}) as cli, \
                 patch("subprocess.run") as process, \
                 contextlib.redirect_stdout(io.StringIO()):
                endpoint.main()
            version.assert_called_once_with()
            cli.assert_called_once()
            command = cli.call_args.args[0]
            self.assertEqual(command[command.index("--parent-id") + 1], project_id)
            if subnet_id is None:
                self.assertNotIn("--subnet-id", command)
            else:
                self.assertEqual(command[command.index("--subnet-id") + 1], subnet_id)
            process.assert_not_called()

    def test_create_never_prints_or_persists_generated_credential(self):
        output = io.StringIO()
        with patch.object(endpoint, "version_check"), \
             patch.object(endpoint, "cli", side_effect=[None, {"resource_id": "aiendpoint-recipe"}, self.ep]), \
             contextlib.redirect_stdout(output):
            endpoint.create(self.create_args())
        self.assertNotIn(FIXTURE_TOKEN, output.getvalue())
        self.assertNotIn(FIXTURE_TOKEN, endpoint.STATE.read_text())
        self.assertEqual(json.loads(endpoint.STATE.read_text())["id"], "aiendpoint-recipe")

    def test_child_receives_token_in_memory_without_printing_it(self):
        seen, output = [], io.StringIO()
        def run(command, **kwargs):
            seen.append((command, kwargs))
            return 0
        with patch("sys.argv", ["endpoint.py", "run", "--", "python3", "worker.py"]), \
             patch.object(endpoint, "cli", return_value=self.ep), \
             patch("subprocess.call", side_effect=run), contextlib.redirect_stdout(output), \
             self.assertRaises(SystemExit) as result:
            endpoint.main()
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(seen[0][1]["env"]["ENDPOINT_TOKEN"], FIXTURE_TOKEN)
        self.assertNotIn(FIXTURE_TOKEN, output.getvalue() + endpoint.STATE.read_text())

    def test_stop_refuses_project_mismatch_before_mutating(self):
        other = json.loads(json.dumps(self.ep))
        other["metadata"]["parent_id"] = "project-other"
        with patch("sys.argv", ["endpoint.py", "stop"]), patch.object(endpoint, "cli", return_value=other) as cli, \
             contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as result:
            endpoint.main()
        self.assertEqual(result.exception.code, 1)
        self.assertEqual(cli.call_count, 1)
        self.assertEqual(cli.call_args.args[0][:3], ["ai", "endpoint", "get"])

    def test_stop_targets_only_tracked_endpoint_and_disables_write_retries(self):
        stopped = json.loads(json.dumps(self.ep))
        stopped["status"]["state"] = "STOPPED"
        with patch("sys.argv", ["endpoint.py", "stop"]), \
             patch.object(endpoint, "cli", side_effect=[self.ep, {}, stopped]) as cli, \
             contextlib.redirect_stdout(io.StringIO()):
            endpoint.main()
        mutation = cli.call_args_list[1].args[0]
        self.assertEqual(mutation[:3], ["ai", "endpoint", "stop"])
        self.assertEqual(mutation[mutation.index("--id") + 1], "aiendpoint-recipe")
        self.assertEqual(mutation[mutation.index("--retries") + 1], "1")

    def test_async_lifecycle_text_acknowledgement_is_followed_by_state_verification(self):
        stopped = json.loads(json.dumps(self.ep))
        stopped["status"]["state"] = "STOPPED"
        for action, before, after in (("start", stopped, self.ep), ("stop", self.ep, stopped)):
            responses = [subprocess.CompletedProcess([], 0, json.dumps(before), ""),
                         subprocess.CompletedProcess([], 0, "operation-example\n", ""),
                         subprocess.CompletedProcess([], 0, json.dumps(after), "")]
            output = io.StringIO()
            with self.subTest(action=action), patch("sys.argv", ["endpoint.py", action]), \
                 patch("subprocess.run", side_effect=responses) as run, \
                 contextlib.redirect_stdout(output):
                endpoint.main()
            self.assertEqual(json.loads(output.getvalue())["state"], after["status"]["state"])
            self.assertEqual(run.call_count, 3)
            self.assertEqual(run.call_args_list[1].args[0][1:4], ["ai", "endpoint", action])
            self.assertEqual(run.call_args_list[2].args[0][1:4], ["ai", "endpoint", "get"])
            self.assertNotIn(FIXTURE_TOKEN, output.getvalue() + endpoint.STATE.read_text())

    def test_wait_does_not_try_http_until_managed_url_exists(self):
        pending = json.loads(json.dumps(self.ep))
        pending["status"] = {"state": "STARTING", "public_endpoints": []}
        response = io.BytesIO(b'{"data":[{"id":"sample-model"}]}')
        with patch.object(endpoint, "endpoint", side_effect=[pending, self.ep]), \
             patch("urllib.request.urlopen", return_value=response) as http, \
             patch("time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            endpoint.wait(argparse.Namespace(timeout=5))
        self.assertEqual(http.call_count, 1)
        self.assertEqual(sleep.call_count, 1)

    def test_wait_fails_fast_for_wrong_model(self):
        with patch.object(endpoint, "endpoint", return_value=self.ep), \
             patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"data":[{"id":"wrong-model"}]}')), \
             patch("time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "different model"):
                endpoint.wait(argparse.Namespace(timeout=5))
        sleep.assert_not_called()

    def test_wait_fails_fast_for_authentication_failure(self):
        error = urllib.error.HTTPError("https://endpoint.invalid/v1/models", 401, "Unauthorized", {}, io.BytesIO(b"auth failed"))
        with patch.object(endpoint, "endpoint", return_value=self.ep), \
             patch("urllib.request.urlopen", side_effect=error), \
             patch("time.monotonic", side_effect=[0, 0, 20, 20]), \
             patch("time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                endpoint.wait(argparse.Namespace(timeout=5))
        sleep.assert_not_called()

    def test_api_not_found_is_distinct_from_dns_failure(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "rpc error: code = NotFound desc = absent")):
            self.assertIsNone(endpoint.cli(["ai", "endpoint", "get-by-name"], required=False))
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "DNS host not found")):
            with self.assertRaisesRegex(RuntimeError, "not found"):
                endpoint.cli(["ai", "endpoint", "get-by-name"], required=False)

    def test_unexpected_query_output_does_not_become_empty_resource(self):
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "unexpected plain output", "")):
            with self.assertRaises(RuntimeError):
                endpoint.cli(["ai", "endpoint", "get-by-name"], required=False)
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "Dry run: validated", "")):
            self.assertEqual(endpoint.cli(["ai", "endpoint", "create", "--dry-run"]), {})

    def test_error_redacts_bare_credential_formats(self):
        jwt = "eyJhbGciOiJub25lIn0.eyJ0ZXN0Ijp0cnVlfQ.signature-test"
        hf = "hf_1234567890abcdefghijkl"
        stderr = "API request failed\n" + jwt + "\n" + hf
        with patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", stderr)):
            with self.assertRaises(RuntimeError) as error:
                endpoint.cli(["ai", "endpoint", "get"])
        self.assertNotIn(jwt, str(error.exception))
        self.assertNotIn(hf, str(error.exception))

    def test_cli_preserves_existing_agent_label_and_sets_fallback(self):
        for value, expected in [("custom-agent", "custom-agent"), ("codex", "codex"), ("", "cookbook")]:
            with patch.dict(os.environ, {"AI_AGENT": value}), \
                 patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "{}", "")) as run:
                endpoint.cli(["ai", "endpoint", "get"])
            self.assertEqual(run.call_args.kwargs["env"]["AI_AGENT"], expected)

    def test_existing_uncapped_endpoint_is_not_reused_for_new_cap(self):
        with patch.object(endpoint, "version_check"), \
             patch.object(endpoint, "cli", side_effect=[None, {"resource_id": "aiendpoint-recipe"}, self.ep]), \
             contextlib.redirect_stdout(io.StringIO()):
            endpoint.create(self.create_args())
        with patch.object(endpoint, "version_check"), patch.object(endpoint, "cli", return_value=self.ep), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                endpoint.create(self.create_args(spot_pricing_policy_id="pricingpolicy-cap"))


if __name__ == "__main__":
    unittest.main()
