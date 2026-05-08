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


class FakePaginator:
    def __init__(self, pages):
        self._pages = pages

    def paginate(self, **_):
        for p in self._pages:
            yield p


class FakeClient:
    def __init__(self, pages):
        self.paginator = FakePaginator(pages)
        self.downloaded = []
        self.uploaded = []

    def get_paginator(self, _name):
        return self.paginator

    def download_file(self, bucket, key, dest):
        self.downloaded.append((bucket, key, dest))

    def upload_file(self, src, bucket, key):
        self.uploaded.append((src, bucket, key))


def test_download_prefix_downloads_all_keys_under_prefix(tmp_path):
    pages = [{"Contents": [
        {"Key": "ref/grch38/a.fa"},
        {"Key": "ref/grch38/sub/b.fa.fai"},
    ]}]
    client = FakeClient(pages)
    stage.download_prefix(client, "buck", "ref/grch38", tmp_path)
    keys_downloaded = sorted(d[1] for d in client.downloaded)
    assert keys_downloaded == ["ref/grch38/a.fa", "ref/grch38/sub/b.fa.fai"]
    # Files written under tmp_path keep the relative structure
    expected_dests = sorted([str(tmp_path / "a.fa"), str(tmp_path / "sub" / "b.fa.fai")])
    assert sorted(d[2] for d in client.downloaded) == expected_dests


def test_upload_prefix_uploads_files_recursively(tmp_path):
    (tmp_path / "out.vcf").write_text("hi")
    nested = tmp_path / "logs" / "run.log"
    nested.parent.mkdir()
    nested.write_text("ok")
    client = FakeClient(pages=[])
    stage.upload_prefix(client, tmp_path, "buck", "out/HG002")
    keys = sorted(u[2] for u in client.uploaded)
    assert keys == ["out/HG002/logs/run.log", "out/HG002/out.vcf"]
