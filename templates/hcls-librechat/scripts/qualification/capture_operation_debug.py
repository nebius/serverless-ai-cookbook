#!/usr/bin/env python3
"""Privately preserve existing operation diagnostics; never submit inference."""

import argparse
from pathlib import Path

from manage_campaign import admin_client, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with admin_client() as client:
        response = client.get(f"/admin/api/v1/operations/{args.operation}")
        save(args.output / "operation.json", {"http_status": response.status_code, "body": response.json()})
        response.raise_for_status()
        listing = client.get("/admin/api/v1/requests", params={"operation_id": args.operation, "limit": 200})
        listing.raise_for_status()
        save(args.output / "exchanges.json", listing.json())
        rows = listing.json()["data"]["items"]
        for row in rows:
            exchange_id = row.get("exchange_id") or row.get("id")
            if not exchange_id:
                raise ValueError("debug exchange has no identity")
            detail = client.get(f"/admin/api/v1/requests/{exchange_id}")
            detail.raise_for_status()
            save(args.output / f"exchange-{exchange_id}.json", detail.json())
    print({"operation_id": args.operation, "exchanges": len(rows), "output": str(args.output)})


if __name__ == "__main__":
    main()
