"""Offline result-envelope and byte-integrity checks for the acceptance clients."""
import hashlib
from types import SimpleNamespace

import pytest

pytest.importorskip("mcp")
pytest.importorskip("httpx2")
from live_serving import unpack
from live_batch import canonical, verify_bytes


def response(**value):
    return SimpleNamespace(model_dump=lambda **kwargs: value)


def test_tool_error_is_not_success_even_with_http_success():
    with pytest.raises(ValueError, match="isError"):
        unpack(response(isError=True, content=[{"type": "text", "text": "execution failed"}]))


def test_structured_and_text_result_envelopes():
    assert unpack(response(structuredContent={"id": "operation"})) == {"id": "operation"}
    assert unpack(response(content=[{"type": "text", "text": '{"status":"queued"}'}])) == {"status": "queued"}
    with pytest.raises(ValueError, match="Expected one"):
        unpack(response(content=[]))


def test_manifest_hash_is_independent_of_dictionary_order():
    assert canonical({"b": 2, "a": 1}) == canonical({"a": 1, "b": 2}) == b'{"a":1,"b":2}'


def test_download_rejects_changed_bytes_or_size():
    data = b"synthetic input\n"
    ref = {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
    verify_bytes(ref, data)
    with pytest.raises(ValueError, match="SHA-256"):
        verify_bytes(ref, b"Synthetic input\n")
    with pytest.raises(ValueError, match="size"):
        verify_bytes(ref, data + b"\n")
