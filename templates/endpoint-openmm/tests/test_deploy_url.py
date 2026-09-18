from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


TEMPLATE = Path(__file__).parents[1]
REPOSITORY = TEMPLATE.parents[1]
IMAGE = "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb24@sha256:4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184"
EXPECTED = {
    "image": [
        "cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/cb24@sha256:4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184"
    ],
    "targetPort": ["8000"],
    "platform": ["gpu-l40s-a"],
    "preset": ["1gpu-8vcpu-32gb"],
    "diskSize": ["100GiB"],
    "preemptible": ["false"],
    "auth": ["true"],
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
    paths = [
        TEMPLATE / "README.md",
        REPOSITORY / "README.md",
        REPOSITORY / "templates/README.md",
    ]
    for path in paths:
        queries = matching_queries(path)
        assert queries == [EXPECTED], f"unexpected deploy link in {path}"
