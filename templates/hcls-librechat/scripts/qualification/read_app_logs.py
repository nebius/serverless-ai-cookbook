#!/usr/bin/env python3
"""Capture existing customer-App operator logs without printing credentials."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from manage_campaign import admin_client, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--search", default="")
    parser.add_argument("--pod", default="")
    parser.add_argument("--from-at", default="2026-09-18T18:00:00Z")
    parser.add_argument("--to-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    with admin_client() as client:
        catalog = client.get("/admin/api/v1/apps")
        catalog.raise_for_status()
        app = next(a for a in catalog.json()["data"]["items"] if a["public_model_id"] == args.model)
        response = client.get(f"/admin/api/v1/apps/{app['app_id']}/logs", params={
            "from": args.from_at, "to": args.to_at, "search": args.search, "pod": args.pod, "limit": 500,
        })
        save(args.output, {"http_status": response.status_code, "body": response.json()})
        response.raise_for_status()
        data = response.json()["data"]
        print({"state": data.get("state"), "reason": data.get("reason"),
               "keys": list(data), "output": str(args.output)})


if __name__ == "__main__":
    main()
