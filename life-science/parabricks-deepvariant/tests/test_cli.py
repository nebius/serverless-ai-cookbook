from unittest.mock import patch

import pytest

from pipeline import cli

REQUIRED = [
    "S3_BUCKET", "S3_ENDPOINT_URL", "S3_INPUT_PREFIX", "S3_REF_PREFIX",
    "S3_OUTPUT_PREFIX", "SAMPLE_ID",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION",
]


def test_validate_env_passes_when_all_present(s3_env):
    cli.validate_env()  # should not raise


@pytest.mark.parametrize("missing", REQUIRED)
def test_validate_env_fails_fast_on_missing_var(s3_env, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(SystemExit) as exc:
        cli.validate_env()
    assert missing in str(exc.value)


def test_main_invokes_run_germline(s3_env, tmp_path):
    with patch("pipeline.cli.run.run_germline") as mock_run:
        cli.main(scratch=str(tmp_path))
    mock_run.assert_called_once()
