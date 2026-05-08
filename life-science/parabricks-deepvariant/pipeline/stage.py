import os

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
