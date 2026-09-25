"""Optional durable storage for one-replica demo endpoints on ephemeral disks."""
import hashlib
import os
from pathlib import Path, PurePosixPath

from .common import sha256_file


def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"],
                        region_name=os.getenv("AWS_DEFAULT_REGION", "eu-north1"),
                        config=Config(signature_version="s3v4", retries={"max_attempts": 8},
                                      s3={"addressing_style": "path"}))


class ObjectStore:
    def __init__(self, bucket, prefix):
        path = PurePosixPath(prefix)
        if path.is_absolute() or ".." in path.parts or not prefix.startswith("endpoint-state/"):
            raise ValueError("STATE_PREFIX_requires_isolated_endpoint-state_subdirectory")
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.client = s3_client()

    def upload(self, path, relative):
        self.client.upload_file(str(path), self.bucket, self.prefix + "/" + relative)

    def exists(self, relative):
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=self.prefix + "/" + relative)
            return True
        except ClientError as exc:
            if str(exc.response["Error"]["Code"]) in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise

    def download(self, relative, path, expected_sha=None):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".download")
        self.client.download_file(self.bucket, self.prefix + "/" + relative, str(temp))
        if expected_sha and sha256_file(temp) != expected_sha:
            temp.unlink()
            raise ValueError("artifact_checksum_mismatch")
        temp.replace(path)

    def restore_operations(self, directory):
        paginator = self.client.get_paginator("list_objects_v2")
        count = 0
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix + "/operations/"):
            for item in page.get("Contents", []):
                relative = item["Key"][len(self.prefix) + 1:]
                path = PurePosixPath(relative)
                if len(path.parts) != 2 or path.suffix != ".json":
                    continue
                count += 1
                if count > 10000:
                    raise RuntimeError("operation_retention_limit_requires_archive")
                self.download(relative, Path(directory) / path.name)


def stage_model_from_env():
    key = os.getenv("MODEL_S3_KEY")
    if not key:
        return os.getenv("MODEL_PATH")
    expected_sha = os.environ["MODEL_SHA256"]
    bucket = os.environ["MODEL_BUCKET"]
    key_path = PurePosixPath(key)
    if key_path.is_absolute() or ".." in key_path.parts or key_path.suffix != ".nemo":
        raise ValueError("invalid_checkpoint_object_key")
    target = Path(os.getenv("MODEL_CACHE_DIR", "/cache/models")) / (expected_sha + ".nemo")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or sha256_file(target) != expected_sha:
        temp = target.with_suffix(".download")
        s3_client().download_file(bucket, key, str(temp))
        if sha256_file(temp) != expected_sha:
            temp.unlink()
            raise ValueError("checkpoint_sha256_mismatch")
        temp.replace(target)
    return str(target)
