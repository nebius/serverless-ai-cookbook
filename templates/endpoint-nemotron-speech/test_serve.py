"""Offline adapter tests: no model load, network or GPU calls."""
import asyncio
import importlib.util
import io
import hashlib
from types import SimpleNamespace
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import httpx
from fs2_speech.contracts import RuntimeProfile

spec = importlib.util.spec_from_file_location("recipe_serve", Path(__file__).with_name("serve.py"))
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)


class Runtime:
    max_sessions = max_batch_size = 4
    def identity(self):
        return {"checkpoint_sha256": "a" * 64, "capacity_status": "configured_not_measured"}
    def step_batch(self, entries):
        raise AssertionError("no GPU call in offline tests")


def wav_bytes():
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        wav.writeframes(b"\0\0" * 16000)
    return data.getvalue()


class Adapter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.keys = serve.credentials('{"first":"' + "a" * 32 + '","second":"' + "b" * 32 + '"}')
        with patch("fs2_speech.server.gateway_token", return_value="internal-only"):
            self.app = serve.create_app(Runtime(), RuntimeProfile(model="nemotron-speech-en-0.6b"), self.keys, load=False)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://offline")
        self.addAsyncCleanup(self.client.aclose)
        self.headers = {"x-api-key": "a" * 32, "content-type": "audio/wav"}

    async def test_missing_auth_private_routes_and_live(self):
        self.assertEqual((await self.client.get("/v1/models")).status_code, 401)
        for path in ("/generate", "/docs"):
            self.assertEqual((await self.client.post(path, headers=self.headers)).status_code, 404)
        self.assertEqual((await self.client.post("/drain", headers=self.headers)).status_code, 403)
        self.assertIn("/v1/audio/stream", [getattr(r, "path", "") for r in self.app.routes])

    async def test_live_identity_rewrite_and_rejection(self):
        scopes, events = [], []
        async def native(scope, receive, send):
            scopes.append(scope)
        async def send(event):
            events.append(event)
        boundary = serve.LiveBoundary(native, keys=self.keys, private_token="internal")
        for token in ("a" * 32, "b" * 32, "wrong"):
            scope = {"type": "websocket", "path": "/v1/audio/stream", "headers": [
                (b"x-api-key", token.encode()), (b"x-fs2-scheduling-group", b"forged"),
                (b"authorization", b"Bearer external-edge-token")]}
            await boundary(scope, None, send)
        self.assertEqual(len(scopes), 2)
        self.assertEqual(events, [{"type": "websocket.close", "code": 1008}])
        one, two = [dict(scope["headers"]) for scope in scopes]
        self.assertEqual(one[b"authorization"], b"Bearer internal")
        self.assertNotEqual(one[b"x-fs2-scheduling-group"], two[b"x-fs2-scheduling-group"])

    async def test_operator_routes_keep_auth(self):
        with patch("fs2_speech.server.gateway_token", return_value="internal"):
            app = serve.create_app(Runtime(), RuntimeProfile(model="nemotron-speech-en-0.6b"), self.keys,
                admin_key="c" * 32, load=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            self.assertEqual((await client.get("/metrics", headers=self.headers)).status_code, 403)
            self.assertEqual((await client.get("/metrics", headers={"x-api-key": "c" * 32})).status_code, 200)
            self.assertEqual((await client.post("/drain", headers={"x-api-key": "c" * 32})).status_code, 200)
            self.assertTrue(app.state.runtime_state["draining"])

    async def test_success_distinct_authenticated_groups(self):
        from fs2_speech.scheduler import scheduling_group
        observed = []
        async def fake(runtime, path, options):
            observed.append((scheduling_group.get(), path.read_bytes()))
            return {"text": "Unmodified native result."}
        # Imported by factory, so recreate under the patched dependency.
        with patch("fs2_speech.audio.transcribe_file", fake), patch("fs2_speech.server.gateway_token", return_value="internal"):
            app = serve.create_app(Runtime(), RuntimeProfile(model="nemotron-speech-en-0.6b"), self.keys, load=False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://offline") as client:
            for token in ("a" * 32, "b" * 32):
                response = await client.post("/v1/audio/transcriptions", headers={**self.headers, "x-api-key": token,
                    "x-fs2-scheduling-group": "forged"}, content=wav_bytes())
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["text"], "Unmodified native result.")
        self.assertNotEqual(observed[0][0], observed[1][0])
        self.assertEqual(observed[0][1], wav_bytes())
        self.assertEqual(app.state.runtime_state["uploads"], 0)

    async def test_size_format_readiness_and_overload(self):
        self.assertEqual((await self.client.post("/v1/audio/transcriptions", headers=self.headers, content=b"bad")).status_code, 422)
        self.assertEqual((await self.client.post("/v1/audio/transcriptions", headers=self.headers, content=wav_bytes()[:44])).status_code, 422)
        with patch.object(serve, "MAX_UPLOAD", 10):
            self.assertEqual((await self.client.post("/v1/audio/transcriptions", headers=self.headers, content=wav_bytes())).status_code, 413)
        self.app.state.runtime_state["active"] = 4
        self.assertEqual((await self.client.post("/v1/audio/transcriptions", headers=self.headers)).status_code, 429)
        self.app.state.runtime_state["draining"] = True
        self.assertEqual((await self.client.post("/v1/audio/transcriptions", headers=self.headers)).status_code, 503)
        self.assertEqual(self.app.state.runtime_state["rejected"], 2)

    async def test_repeated_cancellation_joins_before_cleanup(self):
        started, closing, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        paths = []
        async def native(runtime, path, options):
            paths.append(path)
            started.set()
            try:
                await asyncio.Future()
            finally:
                closing.set()
                await release.wait()
                self.assertTrue(path.exists())
        with patch("fs2_speech.audio.transcribe_file", native), patch("fs2_speech.server.gateway_token", return_value="internal"):
            app = serve.create_app(Runtime(), RuntimeProfile(model="nemotron-speech-en-0.6b"), self.keys, load=False)
        handler = next(r.endpoint for r in app.routes if getattr(r, "path", "") == "/v1/audio/transcriptions")
        class Request:
            headers = {"content-type": "audio/wav"}
            state = SimpleNamespace(customer_group="a" * 64)
            async def stream(self):
                yield wav_bytes()
            async def is_disconnected(self):
                return False
        task = asyncio.create_task(handler(Request()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        await asyncio.wait_for(closing.wait(), 1)
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        self.assertEqual(app.state.runtime_state["active"], 0)
        self.assertEqual(app.state.runtime_state["uploads"], 0)
        self.assertEqual(app.state.runtime_state["file_errors"], 1)
        self.assertFalse(paths[0].parent.exists())

    async def test_tuned_folder_hash_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / "model.nemo"
            model.write_bytes(b"synthetic checkpoint")
            sha = hashlib.sha256(model.read_bytes()).hexdigest()
            (root / "model.sha256").write_text(sha + "  model.nemo\n")
            self.assertEqual(serve.checkpoint(str(root), None), (model, sha))
            (root / "link.nemo").symlink_to(model)
            with self.assertRaises(ValueError):
                serve.checkpoint(str(root / "link.nemo"), sha)
            self.assertEqual(serve.checkpoint(str((root / "link.nemo").resolve()), sha), (model, sha))
            model.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                serve.checkpoint(str(root), None)

    async def test_keys_and_checkpoint_fail_closed(self):
        for raw in ("{}", '{"one":"short"}', '{"a":"' + "x" * 32 + '","b":"' + "x" * 32 + '"}'):
            with self.assertRaises(ValueError):
                serve.credentials(raw)
        self.assertIsNone(serve.identify(self.keys, "wrong"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.nemo"
            path.write_bytes(b"synthetic")
            with self.assertRaises(ValueError):
                serve.checkpoint(str(path), "a" * 64)
        self.assertIsNone(serve.checkpoint(None, None))


if __name__ == "__main__":
    unittest.main()
