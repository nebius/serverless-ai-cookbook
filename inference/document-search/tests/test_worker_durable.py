"""Offline document-level recovery checks; fixture vectors are not model results."""
from dataclasses import replace
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "worker/durable.py"
SPEC = importlib.util.spec_from_file_location("simple_worker_durable", SOURCE)
durable = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = durable
SPEC.loader.exec_module(durable)


def docs(count=3, words=12):
    return [{"id": f"document-{i}", "title": f"Fixture {i}", "source_url": f"https://example.invalid/{i}",
             "text": " ".join(f"word{j}" for j in range(words))} for i in range(count)]


def config(**changes):
    values = dict(manifest_sha256="a" * 64, model="fixture", model_revision="b" * 40,
                  dimensions=3, chunk_words=20, encoder_settings={"normalize": True})
    return durable.RunConfig(**{**values, **changes})


class Encoder:
    def __init__(self):
        self.calls = []

    def __call__(self, texts):
        self.calls.append(list(texts))
        return [[1.0, 0.0, 0.0] for _ in texts]


class Missing(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakeS3:
    def __init__(self):
        self.objects, self.calls = {}, []

    def get_object(self, *, Bucket, Key):
        self.calls.append(("GET", Key))
        if Key not in self.objects:
            raise Missing()
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, *, Bucket, Key, Body):
        self.calls.append(("PUT", Key))
        self.objects[Key] = Body

    def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):
        self.calls.append(("LIST", Prefix))
        names = sorted(k for k in self.objects if k.startswith(Prefix))
        start = int(ContinuationToken or 0)
        result = {"Contents": [{"Key": k} for k in names[start:start + 2]],
                  "IsTruncated": start + 2 < len(names)}
        if result["IsTruncated"]:
            result["NextContinuationToken"] = str(start + 2)
        return result


class DocumentRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "index"
        self.store = durable.LocalStore(self.root)
        self.documents, self.settings = docs(), config()

    def test_one_result_per_document_batching_progress_and_complete_reuse(self):
        encoder, progress = Encoder(), []
        documents = docs(2, words=45)  # Three chunks per document.
        result = durable.index_documents(documents, self.store, encoder, self.settings,
                                         batch_size=2, progress=lambda s: progress.append(s))
        self.assertEqual([len(batch) for batch in encoder.calls], [2, 1, 2, 1])
        self.assertEqual((result["documents_completed"], result["chunks_saved"]), (2, 6))
        self.assertEqual(len(self.store.keys()), 3)  # run.json and two document results.
        self.assertEqual([s["documents_completed"] for s in progress], [0, 1, 2])
        self.assertTrue(result["complete"])
        never = Mock(side_effect=AssertionError("finished documents must not be encoded"))
        again = durable.index_documents(documents, self.store, never, self.settings)
        self.assertEqual((again["documents_reused"], again["chunks_reused"], again["documents_new"]), (2, 6, 0))
        never.assert_not_called()
        records = durable.load_records(documents, self.store, self.settings)
        self.assertEqual((records[0]["source"], records[0]["title"]), ("document-0", "Fixture 0"))
        for key in ("scan_seconds", "embedding_seconds", "save_seconds", "wall_seconds"):
            self.assertGreaterEqual(result[key], 0)

    def test_data_model_manifest_encoder_and_chunk_changes_are_refused(self):
        durable.index_documents(self.documents, self.store, Encoder(), self.settings)
        variants = [replace(self.settings, model="other"), replace(self.settings, model_revision="c" * 40),
                    replace(self.settings, manifest_sha256="c" * 64), replace(self.settings, dimensions=4),
                    replace(self.settings, chunk_words=10), replace(self.settings, encoder_settings={"normalize": False})]
        before = {key: self.store.get(key) for key in self.store.keys()}
        for altered in variants:
            with self.subTest(config=altered), self.assertRaisesRegex(durable.DurableError, "fresh"):
                durable.index_documents(self.documents, self.store, Mock(), altered)
        changed = json.loads(json.dumps(self.documents))
        changed[0]["text"] += " changed"
        with self.assertRaises(durable.DurableError):
            durable.index_documents(changed, self.store, Mock(), self.settings)
        with self.assertRaises(durable.DurableError):
            durable.index_documents(list(reversed(self.documents)), self.store, Mock(), self.settings)
        self.assertEqual(before, {key: self.store.get(key) for key in self.store.keys()})

    def test_mid_document_interruption_preserves_prior_documents_not_partial_chunks(self):
        documents = docs(2)
        documents[1]["text"] = " ".join(f"long{n}" for n in range(45))
        seen = 0
        def interrupt(_):
            nonlocal seen
            seen += 1
            if seen == 2:
                raise RuntimeError("controlled interruption")
        with self.assertRaisesRegex(RuntimeError, "controlled"):
            durable.index_documents(documents, self.store, Encoder(), self.settings,
                                     after_chunk_embedded=interrupt)
        status = durable.inspect_documents(documents, self.store, self.settings)["stats"]
        self.assertEqual((status["documents_completed"], status["chunks_saved"]), (1, 1))
        encoder = Encoder()
        resumed = durable.index_documents(documents, self.store, encoder, self.settings)
        self.assertEqual((resumed["documents_reused"], resumed["documents_new"],
                          resumed["chunks_reused"], resumed["chunks_new"]), (1, 1, 1, 3))
        self.assertEqual(sum(map(len, encoder.calls)), 3)  # Entire unfinished document recomputed.

    def test_failed_document_put_leaves_previous_results_reusable(self):
        class FailingStore(durable.LocalStore):
            saved = 0
            def put(self, key, value):
                if key.startswith("documents/"):
                    self.saved += 1
                    if self.saved == 2:
                        raise RuntimeError("injected document upload failure")
                super().put(key, value)
        with self.assertRaisesRegex(RuntimeError, "upload failure"):
            durable.index_documents(self.documents, FailingStore(self.root), Encoder(), self.settings)
        status = durable.inspect_documents(self.documents, self.store, self.settings)["stats"]
        self.assertEqual(status["documents_completed"], 1)
        resumed = durable.index_documents(self.documents, self.store, Encoder(), self.settings)
        self.assertEqual((resumed["documents_reused"], resumed["documents_new"]), (1, 2))

    def test_invalid_vectors_never_complete_current_document(self):
        for value in ([1.0], [float("nan"), 0.0, 1.0], [float("inf"), 0.0, 1.0], [True, 0.0, 1.0]):
            with self.subTest(value=value), self.assertRaises(durable.DurableError):
                durable.index_documents(docs(1), self.store, lambda texts: [value], self.settings)
            self.assertEqual(self.store.keys(), ["run.json"])
        with self.assertRaises(durable.DurableError):
            durable.index_documents(docs(1), self.store, lambda texts: [], self.settings)

    def test_saved_vector_shape_and_metadata_are_checked(self):
        durable.index_documents(self.documents, self.store, Encoder(), self.settings)
        key = next(key for key in self.store.keys() if key.startswith("documents/"))
        original = self.store.get(key)
        for field, value in (("vector", [1.0]), ("text", "changed passage")):
            saved = json.loads(original)
            saved["chunks"][0][field] = value
            self.store.put_json(key, saved)
            with self.subTest(field=field), self.assertRaises(durable.DurableError):
                durable.inspect_documents(self.documents, self.store, self.settings)
            self.store.put(key, original)

    def test_legacy_chunk_marker_prefix_requires_fresh_prefix(self):
        self.store.put_json("run.json", {"schema": 1, "run_fingerprint": "legacy"})
        self.store.put_json("chunks/old.json", {"old": True})
        encoder = Mock()
        with self.assertRaisesRegex(durable.DurableError, "legacy.*fresh|fresh.*legacy"):
            durable.index_documents(self.documents, self.store, encoder, self.settings)
        encoder.assert_not_called()
        self.assertEqual(json.loads(self.store.get("chunks/old.json")), {"old": True})

    def test_partial_load_and_local_store_four_file_protocol(self):
        result = durable.index_documents(self.documents, self.store, Encoder(), self.settings, stop_after_documents=1)
        self.assertFalse(result["complete"])
        with self.assertRaises(durable.DurableError):
            durable.load_records(self.documents, self.store, self.settings)
        self.assertEqual(len(durable.load_records(self.documents, self.store, self.settings, require_complete=False)), 1)
        portable = durable.LocalStore(Path(self.directory.name) / "inputs")
        for name in ("documents.jsonl", "manifest.json", "LICENSE", "SOURCE.md"):
            portable.put(name, b"fixture")
        (portable.root / ".pending-test").write_bytes(b"uncommitted")
        self.assertEqual(set(portable.keys()), {"documents.jsonl", "manifest.json", "LICENSE", "SOURCE.md"})

    def test_fresh_processes_finish_600_then_400_with_same_limit(self):
        program = '''
import json,sys
sys.path.insert(0,sys.argv[1])
from durable import LocalStore,RunConfig,index_documents
documents=[{"id":str(i),"title":"fixture","source_url":"https://example.invalid/","text":"one two three"} for i in range(1000)]
count=0
def encode(texts):
 global count
 count+=len(texts)
 return [[1.0,0.0,0.0] for _ in texts]
stats=index_documents(documents,LocalStore(sys.argv[2]),encode,RunConfig("a"*64,"fixture","b"*40,3),stop_after_documents=600)
print(json.dumps({"stats":stats,"encoded":count}))
'''
        command = [sys.executable, "-c", program, str(SOURCE.parent), str(self.root)]
        first = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
        self.assertEqual((first["stats"]["documents_completed"], first["encoded"]), (600, 600))
        before = {key: self.store.get(key) for key in self.store.keys()}
        second = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)
        self.assertEqual((second["stats"]["documents_reused"], second["stats"]["documents_new"],
                          second["stats"]["chunks_reused"], second["stats"]["chunks_new"],
                          second["encoded"]), (600, 400, 600, 400, 400))
        self.assertTrue(second["stats"]["complete"])
        self.assertEqual(before, {key: self.store.get(key) for key in before})


class S3OperationTests(unittest.TestCase):
    def test_storage_errors_show_safe_code_without_request_or_credential_details(self):
        secret = "https://private.invalid/request?X-Amz-Credential=fixture-secret"
        for code in ("AccessDenied", "NoSuchBucket"):
            for action in ("get", "put", "keys"):
                with self.subTest(code=code, action=action):
                    error = RuntimeError(secret)
                    error.response = {"Error": {"Code": code, "Message": secret},
                                      "ResponseMetadata": {"RequestId": "private-request-detail"}}
                    client = Mock()
                    for operation in ("get_object", "put_object", "list_objects_v2"):
                        getattr(client, operation).side_effect = error
                    store = durable.S3Store("s3://fixture-bucket/run", endpoint_url="https://example.invalid", client=client)
                    with self.assertRaises(durable.DurableError) as raised:
                        if action == "get":
                            store.get("document.json")
                        elif action == "put":
                            store.put("document.json", b"{}")
                        else:
                            store.keys()
                    shown = str(raised.exception) + "".join(traceback.format_exception(raised.exception))
                    self.assertIn("(" + code + ")", shown)
                    self.assertNotIn("fixture-secret", shown)
                    self.assertNotIn("private.invalid", shown)
                    self.assertNotIn("private-request-detail", shown)

    def test_unsafe_or_missing_storage_code_uses_unknown(self):
        secret = "https://private.invalid/?token=fixture-secret"
        for response in ({}, None, {"Error": None},
                         *({"Error": {"Code": code}} for code in (None, "", secret, "x" * 65, ["AccessDenied"]))):
            with self.subTest(response=response):
                error = RuntimeError(secret)
                error.response = response
                client = Mock()
                client.put_object.side_effect = error
                store = durable.S3Store("s3://fixture-bucket/run", endpoint_url="https://example.invalid", client=client)
                with self.assertRaisesRegex(durable.DurableError, r"\(Unknown\)") as raised:
                    store.put("document.json", b"{}")
                self.assertNotIn("fixture-secret", str(raised.exception))

    def test_missing_key_get_still_returns_none_but_failed_put_does_not(self):
        for code in ("NoSuchKey", "NotFound", "404"):
            with self.subTest(code=code):
                error = RuntimeError("private request details")
                error.response = {"Error": {"Code": code}}
                client = Mock()
                client.get_object.side_effect = error
                client.put_object.side_effect = error
                store = durable.S3Store("s3://fixture-bucket/run", endpoint_url="https://example.invalid", client=client)
                self.assertIsNone(store.get("missing.json"))
                with self.assertRaisesRegex(durable.DurableError, code):
                    store.put("document.json", b"{}")

    def test_document_puts_have_no_get_before_put_or_readback(self):
        client = FakeS3()
        store = durable.S3Store("s3://fixture-bucket/run", endpoint_url="https://example.invalid", client=client)
        documents, settings = docs(2), config()
        durable.index_documents(documents, store, Encoder(), settings, stop_after_documents=1)
        self.assertEqual([action for action, _ in client.calls], ["LIST", "PUT", "PUT"])
        client.calls = []
        resumed = durable.index_documents(documents, store, Encoder(), settings)
        self.assertEqual([action for action, _ in client.calls], ["LIST", "GET", "GET", "PUT"])
        self.assertEqual((resumed["documents_reused"], resumed["documents_new"]), (1, 1))
        self.assertEqual(len(client.objects), 3)


if __name__ == "__main__":
    unittest.main()
