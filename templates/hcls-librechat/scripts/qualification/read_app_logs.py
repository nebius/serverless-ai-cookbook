#!/usr/bin/env python3
"""Capture existing customer-App operator logs without printing credentials."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import time

from manage_campaign import admin_client, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--app-id", help="Previously captured exact App UUID; avoids unrelated catalog/usage reads")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--search", default="")
    parser.add_argument("--pod", default="")
    parser.add_argument("--limit", type=int, choices=range(1, 501), default=500)
    parser.add_argument("--cursor")
    parser.add_argument("--from-at", default="2026-09-18T18:00:00Z")
    parser.add_argument("--to-at", default=datetime.now(timezone.utc).isoformat())
    args = parser.parse_args()
    with admin_client() as client:
        if args.app_id:
            from uuid import UUID
            app_id = str(UUID(args.app_id))
        else:
            catalog = client.get("/admin/api/v1/apps")
            if catalog.is_error:
                save(args.output, {"stage": "app_catalog_lookup", "http_status": catalog.status_code,
                                   "request_id": catalog.headers.get("x-request-id"), "body_text": catalog.text})
            catalog.raise_for_status()
            app = next(a for a in catalog.json()["data"]["items"] if a["public_model_id"] == args.model)
            app_id = app["app_id"]
        params = {"from": args.from_at, "to": args.to_at, "search": args.search,
                  "pod": args.pod, "limit": args.limit}
        if args.cursor:
            params["cursor"] = args.cursor
        started = time.monotonic()
        response = client.get(f"/admin/api/v1/apps/{app_id}/logs", params=params)
        elapsed = time.monotonic() - started
        save(args.output, {"http_status": response.status_code, "elapsed_seconds": elapsed,
                           "request": params, "body": response.json()})
        response.raise_for_status()
        data = response.json()["data"]
        print({"state": data.get("state"), "reason": data.get("reason"),
               "rows": len(data.get("items", [])), "elapsed_seconds": elapsed,
               "keys": list(data), "output": str(args.output)})


if __name__ == "__main__":
    main()
