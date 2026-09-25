import hashlib
import threading
import time
from pathlib import Path

import pytest
from clinical_asr.cloud import upload_outputs


class Body:
    def __init__(self, value): self.value, self.closed = value, False
    def iter_chunks(self, chunk_size): yield self.value
    def close(self): self.closed = True


class S3:
    def __init__(self, corrupt=False):
        self.data, self.bodies = {}, []
        self.active = self.peak = 0
        self.lock = threading.Lock()
        self.corrupt = corrupt

    def upload_file(self, path, bucket, key, **kwargs):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(0.005)
            self.data[key] = Path(path).read_bytes()
        finally:
            with self.lock: self.active -= 1

    def get_object(self, *, Bucket, Key):
        value = self.data[Key]
        body = Body(value + b"corrupt" if self.corrupt else value)
        self.bodies.append(body)
        return {"Body": body, "ContentLength": len(value)}


def test_parallel_verified_outputs_keep_deterministic_receipt(tmp_path):
    for index in range(12): (tmp_path / f"{index:02d}.bin").write_bytes(bytes([index]))
    (tmp_path / "optimizer.ckpt").write_bytes(b"not-uploaded")
    (tmp_path / "completed.json").write_text("old-marker-never-uploaded")
    client = S3()
    result = upload_outputs(client, "bucket", "runs/test", tmp_path, workers=3)
    assert 1 < client.peak <= 3
    assert len(result) == 12
    assert [row["key"] for row in result] == sorted(client.data)
    assert all(row["sha256"] == hashlib.sha256(client.data[row["key"]]).hexdigest() for row in result)
    assert all(body.closed for body in client.bodies)
    assert not any(key.endswith(("completed.json", ".ckpt")) for key in client.data)


def test_corrupt_readback_aborts_without_success_marker(tmp_path):
    for index in range(20): (tmp_path / f"{index:02d}.bin").write_bytes(b"expected")
    client = S3(corrupt=True)
    with pytest.raises(RuntimeError, match="output_upload_verification_failed"):
        upload_outputs(client, "bucket", "runs/test", tmp_path, workers=2)
    assert all(body.closed for body in client.bodies)
    assert not any(key.endswith("completed.json") for key in client.data)


def test_publication_worker_limit_is_bounded(tmp_path):
    with pytest.raises(ValueError, match="upload_workers"):
        upload_outputs(S3(), "bucket", "runs/test", tmp_path, workers=17)
