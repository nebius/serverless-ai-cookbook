import os
from pathlib import Path

import boto3


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise KeyError(name)
    return value


def make_client():
    return boto3.client(
        "s3",
        endpoint_url=_required_env("S3_ENDPOINT_URL"),
        aws_access_key_id=_required_env("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=_required_env("AWS_SECRET_ACCESS_KEY"),
        region_name=_required_env("AWS_DEFAULT_REGION"),
    )


def download_file(client, bucket: str, key: str, dest: Path) -> None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket, key, str(dest))


def download_prefix(client, bucket: str, prefix: str, dest_dir: Path) -> None:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paginator = client.get_paginator("list_objects_v2")
    prefix_clean = prefix.rstrip("/")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix_clean):
        for obj in page.get("Contents", []) or []:
            key = obj["Key"]
            rel = key[len(prefix_clean):].lstrip("/")
            target = dest_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(bucket, key, str(target))


def upload_prefix(client, src_dir: Path, bucket: str, prefix: str) -> None:
    src_dir = Path(src_dir)
    prefix_clean = prefix.rstrip("/")
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_dir).as_posix()
        key = f"{prefix_clean}/{rel}"
        client.upload_file(str(path), bucket, key)
