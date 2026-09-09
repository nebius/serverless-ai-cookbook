from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


TEMPLATE = Path(__file__).parents[1]
REPOSITORY = TEMPLATE.parents[1]
IMAGE = "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/autodock-gpu-api:20260909-rest-mcp-sm80-sm90"
EXPECTED = {
    "image": [
        "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/autodock-gpu-api:20260909-rest-mcp-sm80-sm90"
    ],
    "targetPort": [
        "8000"
    ],
    "platform": [
        "gpu-h100-sxm"
    ],
    "preset": [
        "1gpu-16vcpu-200gb"
    ],
    "diskSize": [
        "100GiB"
    ],
    "preemptible": [
        "false"
    ],
    "auth": [
        "true"
    ],
    "volumeMountPath": [
        "/mnt/hcls"
    ],
    "volumeSize": [
        "32"
    ]
}


def matching_queries(path: Path) -> list[dict[str, list[str]]]:
    links = re.findall(
        r"(https://console\.nebius\.com/serverless/endpoint/create\?[^)\"\s]+)",
        path.read_text(encoding="utf-8"),
    )
    queries = [
        parse_qs(urlsplit(html.unescape(link)).query, keep_blank_values=True)
        for link in links
    ]
    return [query for query in queries if query.get("image") == [IMAGE]]


def test_all_catalog_links_match_complete_customer_contract() -> None:
    paths = [TEMPLATE / "README.md", REPOSITORY / "README.md", REPOSITORY / "templates/README.md"]
    for path in paths:
        queries = matching_queries(path)
        assert queries == [EXPECTED], f"unexpected deploy link in {path}"


def test_deploy_url_contains_no_secret_value_or_application_auth_token() -> None:
    query = matching_queries(TEMPLATE / "README.md")[0]
    assert all("AUTH_TOKEN" not in value for values in query.values() for value in values)
    for value in query.get("env", []):
        if value == "NGC_API_KEY":
            continue
        assert not value.startswith("NGC_API_KEY=")
