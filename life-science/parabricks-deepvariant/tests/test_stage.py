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
