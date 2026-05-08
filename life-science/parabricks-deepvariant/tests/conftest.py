import pytest


@pytest.fixture
def s3_env(monkeypatch):
    """Populate the standard env vars the pipeline reads. Tests can override."""
    env = {
        "S3_BUCKET": "test-bucket",
        "S3_ENDPOINT_URL": "https://storage.eu-north1.nebius.cloud",
        "S3_INPUT_PREFIX": "parabricks/demo/hg002",
        "S3_REF_PREFIX": "parabricks/ref/grch38",
        "S3_OUTPUT_PREFIX": "parabricks/out",
        "SAMPLE_ID": "HG002",
        "AWS_ACCESS_KEY_ID": "test-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
        "AWS_DEFAULT_REGION": "eu-north1",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env
