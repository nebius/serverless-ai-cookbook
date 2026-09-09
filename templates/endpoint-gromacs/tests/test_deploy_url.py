from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


README = Path(__file__).parents[1] / "README.md"
IMAGE = (
    "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/"
    "hcls/gromacs-md-api:20260908-6bd2a84-dynamic"
)


def deploy_query() -> dict[str, list[str]]:
    match = re.search(
        r'href="(https://console\.nebius\.com/serverless/endpoint/create\?[^\"]+)"',
        README.read_text(encoding="utf-8"),
    )
    assert match, "README must contain a Console endpoint-create link"
    return parse_qs(urlsplit(html.unescape(match.group(1))).query, keep_blank_values=True)


def test_deploy_url_contains_complete_customer_contract() -> None:
    query = deploy_query()
    assert query == {
        "image": [IMAGE],
        "targetPort": ["8000"],
        "platform": ["gpu-l40s-a"],
        "preset": ["1gpu-8vcpu-32gb"],
        "diskSize": ["100GiB"],
        "preemptible": ["false"],
        "auth": ["true"],
        "env": [
            "NGC_API_KEY",
            "GROMACS_VERSION=latest",
            "GROMACS_CPU_BUILD=avx2_256",
        ],
        "volumeMountPath": ["/mnt/hcls"],
        "volumeSize": ["32"],
    }


def test_deploy_url_contains_no_secret_or_application_auth_token() -> None:
    query = deploy_query()
    assert query["env"][0] == "NGC_API_KEY"
    assert all("AUTH_TOKEN" not in value for values in query.values() for value in values)
