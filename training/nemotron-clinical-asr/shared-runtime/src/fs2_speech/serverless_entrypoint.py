"""Mandatory worker auth from a secret injection; no secret in image or CLI args."""

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .worker_auth import gateway_token, validate_token_bytes

SECRET_ENV = "FS2_STT_GATEWAY_TOKEN_MATERIAL"


@contextmanager
def secret_file(*, temporary_root: str | None = None):
    # Remove plaintext before any runtime import, subprocess or model load.
    value = os.environ.pop(SECRET_ENV, None)
    if os.environ.get("FS2_STT_REQUIRE_GATEWAY_AUTH") != "1":
        raise ValueError("serverless_requires_gateway_auth")
    if os.environ.get("FS2_STT_GATEWAY_TOKEN_FILE"):
        raise ValueError("serverless_secret_delivery_ambiguous")
    if value is None:
        raise ValueError("serverless_gateway_secret_missing")
    try:
        token = validate_token_bytes(value.encode("ascii"))
    except (UnicodeError, ValueError):
        raise ValueError("serverless_gateway_secret_invalid") from None
    del value
    directory = Path(tempfile.mkdtemp(prefix="fs2-stt-auth-", dir=temporary_root))
    directory.chmod(0o700)
    path = directory / "gateway-token"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(token.encode("ascii"))
        del token
        os.environ["FS2_STT_GATEWAY_TOKEN_FILE"] = str(path)
        gateway_token()  # Fail closed before selecting or importing a server.
        yield path
    finally:
        os.environ.pop("FS2_STT_GATEWAY_TOKEN_FILE", None)
        # Only this newly created exact private file/directory; never recursive.
        path.unlink(missing_ok=True)
        directory.rmdir()


def main():
    with secret_file():
        family = os.environ.get("FS2_STT_RUNTIME", "speech")
        if family == "speech":
            from .server import main as serve
        elif family == "voice":
            from fs2_voice.server import main as serve
        else:
            raise ValueError("unregistered_stt_runtime")
        serve()


if __name__ == "__main__":
    main()
