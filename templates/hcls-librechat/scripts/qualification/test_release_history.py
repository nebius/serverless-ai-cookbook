import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from release_history import verify_published_image


def test_checks_exact_repository_and_manifest_bytes():
    manifest = b'{"schemaVersion":2}'
    image = {"repository": "registry.example/platform/control-plane",
             "digest": "sha256:" + hashlib.sha256(manifest).hexdigest()}
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=manifest)) as run:
        result = verify_published_image(image)
    assert run.call_args.args[0][-1] == "docker://" + image["repository"] + "@" + image["digest"]
    assert result["readable"] is True


def test_missing_repository_fails_without_disclosing_registry_stderr():
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=1, stderr=b"private")):
        with pytest.raises(ValueError, match="not readable") as error:
            verify_published_image({"repository": "registry.example/missing", "digest": "sha256:" + "a" * 64})
    assert "private" not in str(error.value)


def test_wrong_manifest_bytes_rejected():
    with patch("release_history.subprocess.run", return_value=SimpleNamespace(returncode=0, stdout=b"other")):
        with pytest.raises(ValueError, match="do not match"):
            verify_published_image({"repository": "registry.example/right", "digest": "sha256:" + "a" * 64})
