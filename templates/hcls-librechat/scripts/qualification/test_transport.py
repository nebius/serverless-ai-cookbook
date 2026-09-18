import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import httpx

from batch_transport import materialize, resolve, upload
from run_campaign import ToolError, artifact, interleave, unpack


class TransportTests(unittest.TestCase):
    def test_direct_operation_string_is_not_an_envelope(self):
        value = {"id": "op", "operation": "predict-structure", "status": "queued"}
        self.assertEqual(unpack({"structuredContent": value}), value)

    def test_error_preserves_admission_facts(self):
        with self.assertRaises(ToolError) as captured:
            unpack({"isError": True, "structuredContent": {"error": {
                "code": "concurrency_exhausted", "retryable": True, "durable_admission": False}}})
        self.assertFalse(captured.exception.error["durable_admission"])
        self.assertTrue(captured.exception.error["retryable"])

    def test_models_interleave_stably_without_dropping_cases(self):
        cases = [{"model_id": model, "id": i} for i, model in enumerate(("a", "a", "b", "b", "c"))]
        self.assertEqual([c["id"] for c in interleave(cases)], [0, 2, 4, 1, 3])

    def test_hash_verification_is_required(self):
        data = b'{"x":1}'
        with httpx.Client(base_url="https://platform.invalid", transport=httpx.MockTransport(
                lambda req: httpx.Response(200, content=data))) as client, tempfile.TemporaryDirectory() as root:
            ref = {"artifact_id": "abc", "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            self.assertEqual(artifact(client, ref, Path(root)), data)
            with self.assertRaises(ValueError):
                artifact(client, {**ref, "sha256": "0" * 64}, Path(root))

    def test_gzipped_structure_and_archive_are_materialized(self):
        data = b"ATOM  example"
        self.assertEqual(materialize(gzip.compress(data), {"media_type": "chemical/x-pdb", "compression": "gzip"}, "structure"),
                         {"structure": data.decode()})
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as bundle:
            member = tarfile.TarInfo("nested/prediction.pdb")
            member.size = len(data)
            bundle.addfile(member, io.BytesIO(data))
        parsed = materialize(buffer.getvalue(), {"media_type": "application/x-tar"}, "outputs")
        self.assertEqual(parsed["structures"][0]["structure"], data.decode())

    def test_upload_roundtrip_verifies_final_metadata(self):
        data = b"sequence"
        measured = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data),
                    "media_type": "text/plain", "compression": "none"}
        requests = []
        def transport(request):
            requests.append(request)
            if request.url.path.endswith(":finalize"):
                return httpx.Response(200, json={"artifact_id": "ref", **measured})
            if request.method == "PUT":
                self.assertEqual(request.content, data)
                return httpx.Response(204)
            self.assertEqual(json.loads(request.content), {"model_id": "test-model", **measured})
            return httpx.Response(200, json={"upload_id": "u", "operation_id": "op", "max_content_bytes": 1024,
                                             "content_path": "/v1/scientific-artifacts/uploads/u/content"})
        with httpx.Client(base_url="https://platform.invalid", transport=httpx.MockTransport(transport)) as client:
            result = upload(client, "test-model", data, "text/plain", "none", "study-1")
        self.assertEqual(result["artifact_id"], "ref")
        self.assertEqual(len(requests), 3)

    def test_batch_result_retains_verified_artifact_roles_and_csv_rows(self):
        data = b'id_gen,self_binder_scRMSD_ca\n0,1.87\n'
        digest = hashlib.sha256(data).hexdigest()
        manifest = {"schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1", "entries": [{
            "name": "results.1", "semantic_type": "proteina-complexa-results-csv/v1",
            "artifact": {"artifact_id": "csv", "media_type": "text/csv", "sha256": digest},
        }]}
        def download(client, ref, folder):
            return json.dumps(manifest).encode() if ref["artifact_id"] == "manifest" else data
        with tempfile.TemporaryDirectory() as root:
            result = resolve(None, {"terminal_status": "succeeded", "output_manifest": {"artifact_id": "manifest"},
                                   "semantic_validation": {"status": "passed"}}, Path(root), download)
        self.assertEqual(result["outputs"], [{"artifact_name": "results.1",
            "semantic_type": "proteina-complexa-results-csv/v1", "verified_sha256": digest,
            "csv_rows": [{"id_gen": "0", "self_binder_scRMSD_ca": "1.87"}]}])

    def test_resume_write_conflict_requires_matching_finalized_bytes(self):
        data = b"sequence"
        for correct in (True, False):
            def transport(request):
                if request.url.path.endswith(":finalize"):
                    return httpx.Response(200, json={"artifact_id": "ref", "size_bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest() if correct else "0" * 64,
                        "media_type": "text/plain", "compression": "none"})
                if request.method == "PUT":
                    return httpx.Response(409)
                return httpx.Response(201, json={"upload_id": "u", "operation_id": "op", "max_content_bytes": 1024,
                                                "content_path": "/v1/scientific-artifacts/uploads/u/content"})
            with httpx.Client(base_url="https://platform.invalid", transport=httpx.MockTransport(transport)) as client:
                if correct:
                    self.assertEqual(upload(client, "test-model", data, "text/plain", "none", "study-1")["artifact_id"], "ref")
                else:
                    with self.assertRaisesRegex(ValueError, "metadata mismatch"):
                        upload(client, "test-model", data, "text/plain", "none", "study-1")


if __name__ == "__main__":
    unittest.main()
