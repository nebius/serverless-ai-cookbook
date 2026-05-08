from unittest.mock import patch

import pytest

from pipeline import stage


def test_make_client_uses_env_vars(s3_env):
    with patch("pipeline.stage.boto3.client") as mock_client:
        stage.make_client()
        mock_client.assert_called_once_with(
            "s3",
            endpoint_url="https://storage.eu-north1.nebius.cloud",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="eu-north1",
        )


def test_make_client_raises_when_endpoint_missing(s3_env, monkeypatch):
    monkeypatch.delenv("S3_ENDPOINT_URL")
    with pytest.raises(KeyError, match="S3_ENDPOINT_URL"):
        stage.make_client()


def test_download_file_calls_boto3_with_correct_args(tmp_path):
    fake = type("F", (), {})()
    calls = {}

    def fake_download(bucket, key, dest):
        calls["args"] = (bucket, key, dest)

    fake.download_file = fake_download
    dest = tmp_path / "x.fq.gz"
    stage.download_file(fake, "mybucket", "prefix/x.fq.gz", dest)
    assert calls["args"] == ("mybucket", "prefix/x.fq.gz", str(dest))


def test_download_file_creates_parent_dir(tmp_path):
    fake = type("F", (), {})()
    fake.download_file = lambda *_: None
    nested = tmp_path / "a" / "b" / "c.txt"
    stage.download_file(fake, "b", "k", nested)
    assert nested.parent.is_dir()
