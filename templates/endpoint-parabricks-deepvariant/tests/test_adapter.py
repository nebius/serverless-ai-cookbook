from __future__ import annotations

import socket

import pytest

from app import ParabricksAdapter, validate_https_url


def test_capabilities_publish_runtime_and_bounded_public_example() -> None:
    adapter = ParabricksAdapter()
    adapter.runtime = {
        "actual_engine_version": "4.7.1-1",
        "resolved_tag": "4.7.1-1",
        "resolved_digest": f"sha256:{'a' * 64}",
    }
    capabilities = adapter.capabilities()
    example = capabilities["examples"][0]
    assert capabilities["engine"]["version"] == "4.7.1-1"
    assert example["id"] == "deepvariant-chr20-smoke"
    assert example["input"]["reads"]["sha256"]


def test_remote_inputs_require_https() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        validate_https_url("http://example.com/input.bam")
    with pytest.raises(ValueError, match="credentials"):
        validate_https_url("https://user:pass@example.com/input.bam")


def test_remote_inputs_reject_private_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="non-public"):
        validate_https_url("https://example.com/input.bam")
