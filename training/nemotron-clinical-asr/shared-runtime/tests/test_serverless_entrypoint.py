import os
import stat

import pytest

from fs2_speech.serverless_entrypoint import SECRET_ENV, secret_file
from fs2_speech.worker_auth import gateway_token


def test_secret_removed_from_environment_private_file_and_exact_cleanup(tmp_path, monkeypatch):
    secret = "unit-test-not-a-credential-" + "x" * 32
    monkeypatch.setenv(SECRET_ENV, secret)
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    unrelated = tmp_path / "preserve"
    unrelated.write_text("untouched")
    with secret_file(temporary_root=str(tmp_path)) as path:
        assert SECRET_ENV not in os.environ
        assert secret not in str(path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert gateway_token() == secret
    assert not path.exists() and not path.parent.exists()
    assert "FS2_STT_GATEWAY_TOKEN_FILE" not in os.environ
    assert unrelated.read_text() == "untouched"


@pytest.mark.parametrize("token", [None, "short", "x" * 4097, "x" * 32 + " secret", "ü" * 32])
def test_invalid_secret_never_listens_or_retains_material(tmp_path, monkeypatch, token):
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    monkeypatch.delenv(SECRET_ENV, raising=False)
    if token is not None:
        monkeypatch.setenv(SECRET_ENV, token)
    with pytest.raises(ValueError, match="serverless_gateway_secret"):
        with secret_file(temporary_root=str(tmp_path)):
            pytest.fail("must not start serving")
    assert SECRET_ENV not in os.environ
    assert not list(tmp_path.iterdir())


def test_exception_cleanup_and_mandatory_auth(tmp_path, monkeypatch):
    monkeypatch.setenv(SECRET_ENV, "x" * 32)
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "0")
    with pytest.raises(ValueError, match="requires_gateway_auth"):
        with secret_file(temporary_root=str(tmp_path)):
            pass
    monkeypatch.setenv(SECRET_ENV, "x" * 32)
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    monkeypatch.delenv("FS2_STT_GATEWAY_TOKEN_FILE", raising=False)
    with pytest.raises(RuntimeError, match="server failed"):
        with secret_file(temporary_root=str(tmp_path)) as path:
            raise RuntimeError("server failed")
    assert not path.exists() and not list(tmp_path.iterdir())


def test_existing_token_file_is_not_overwritten(tmp_path, monkeypatch):
    original = tmp_path / "existing"
    original.write_text("x" * 32)
    monkeypatch.setenv(SECRET_ENV, "y" * 32)
    monkeypatch.setenv("FS2_STT_REQUIRE_GATEWAY_AUTH", "1")
    monkeypatch.setenv("FS2_STT_GATEWAY_TOKEN_FILE", str(original))
    with pytest.raises(ValueError, match="ambiguous"):
        with secret_file(temporary_root=str(tmp_path)):
            pass
    assert original.read_text() == "x" * 32
