"""Optional authenticated private-worker scheduling metadata.

Without a configured gateway token, retain legacy cluster-private inference but
ignore all claimed customer groups. That mode proves session fairness only.
"""

import hmac
import os
import re
from pathlib import Path


def gateway_token() -> str | None:
    required = os.environ.get("FS2_STT_REQUIRE_GATEWAY_AUTH", "0")
    if required not in {"0", "1"}:
        raise ValueError("invalid_private_gateway_auth_policy")
    path = os.environ.get("FS2_STT_GATEWAY_TOKEN_FILE")
    if not path:
        if required == "1":
            raise ValueError("private_gateway_token_required")
        return None
    with Path(path).open("rb") as handle:
        value = handle.read(4097)
    return validate_token_bytes(value)


def validate_token_bytes(value: bytes) -> str:
    """Shared bounded validation for mounted and secret-injected credentials."""
    try:
        token = value.decode("ascii").strip()
    except UnicodeError:
        raise ValueError("invalid_private_gateway_token") from None
    if len(value) > 4096 or not 32 <= len(token) <= 1024 or any(c.isspace() or ord(c) < 33 for c in token):
        raise ValueError("invalid_private_gateway_token")
    return token


def authorized_group(headers, token: str | None) -> str:
    if token is None:
        return "unattributed"
    supplied = headers.get("authorization", "")
    if not supplied.isascii() or len(supplied) > 1100 or not hmac.compare_digest(supplied, "Bearer " + token):
        raise PermissionError("private_gateway_authentication_required")
    group = headers.get("x-fs2-scheduling-group")
    if group is None:
        return "unattributed"
    if re.fullmatch(r"[a-f0-9]{64}", group) is None:
        raise PermissionError("invalid_private_scheduling_metadata")
    return group
