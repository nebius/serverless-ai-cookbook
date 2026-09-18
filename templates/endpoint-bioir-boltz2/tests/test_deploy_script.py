import os
import subprocess
from pathlib import Path

import pytest


TEMPLATE = Path(__file__).parents[1]
DIGEST = "sha256:" + "a" * 64


@pytest.mark.parametrize("matching", [True, False])
def test_short_alias_requires_matching_digest(tmp_path, matching):
    crane = tmp_path / "crane"
    crane.write_text(
        "#!/bin/sh\nprintf '%s\\n' '"
        + (DIGEST if matching else "sha256:" + "b" * 64)
        + "'\n"
    )
    crane.chmod(0o755)
    nebius = tmp_path / "nebius"
    nebius.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    nebius.chmod(0o755)
    env = dict(
        os.environ,
        PATH=str(tmp_path) + os.pathsep + os.environ["PATH"],
        PARENT_ID="project-test",
        SUBNET_ID="subnet-test",
        IMAGE_REFERENCE="registry.example/bioir@" + DIGEST,
        DEPLOY_IMAGE_REFERENCE="registry.example/bioir:pinned",
        AUTH_TOKEN_SECRET="test-secret-selector",
    )
    result = subprocess.run(
        ["bash", str(TEMPLATE / "scripts/deploy-endpoint.sh")],
        env=env,
        capture_output=True,
        text=True,
    )
    if matching:
        assert result.returncode == 0
        args = result.stdout.splitlines()
        assert args[args.index("--image") + 1] == env["DEPLOY_IMAGE_REFERENCE"]
        assert "--token-secret" in args
    else:
        assert result.returncode == 2
        assert not result.stdout
        assert "does not match" in result.stderr


def test_lock_covers_all_exact_direct_requirements():
    direct = (TEMPLATE / "requirements.txt").read_text().splitlines()
    locked = set((TEMPLATE / "requirements.lock.txt").read_text().splitlines())
    for line in direct:
        if not line or line.startswith("#"):
            continue
        assert "==" in line
        assert line.replace("[standard]", "") in locked
