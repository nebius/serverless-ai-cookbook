import pytest

from fs2_speech.worker_auth import authorized_group, gateway_token


def test_untrusted_group_is_ignored_not_a_fairness_claim():
    assert authorized_group({"x-fs2-scheduling-group": "a" * 64}, None) == "unattributed"


def test_only_authenticated_gateway_can_group_sessions():
    secret = "unit-test-token-" + "x" * 32
    headers = {"authorization": "Bearer " + secret, "x-fs2-scheduling-group": "a" * 64}
    assert authorized_group(headers, secret) == "a" * 64
    assert authorized_group({"authorization": "Bearer " + secret}, secret) == "unattributed"
    for modified in ({}, {**headers, "authorization": "Bearer wrong"},
                     {**headers, "x-fs2-scheduling-group": "raw-tenant-name"}):
        with pytest.raises(PermissionError):
            authorized_group(modified, secret)


def test_mounted_token_is_bounded_and_never_echoed(tmp_path, monkeypatch):
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    assert gateway_token() is None
    path = tmp_path / "test-secret"
    monkeypatch.setenv("FS2_STT_GATEWAY_TOKEN_FILE", str(path))
    path.write_text("x" * 32)
    assert gateway_token() == "x" * 32
    for data in (b"too-short", b"x" * 4097, b"x" * 32 + b" bad", b"\xff" * 32):
        path.write_bytes(data)
        with pytest.raises(ValueError, match="^invalid_private_gateway_token$"):
            gateway_token()


def test_serverless_required_auth_fails_closed_without_mounted_token(monkeypatch):
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    with pytest.raises(ValueError, match="^private_gateway_token_required$"):
        gateway_token()
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "true")
    with pytest.raises(ValueError, match="^invalid_private_gateway_auth_policy$"):
        gateway_token()
