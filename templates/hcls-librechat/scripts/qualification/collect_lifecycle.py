#!/usr/bin/env python3
"""Capture customer-visible progress and existing operator GPU accounting.

This does not submit, retry, cancel or otherwise change a model operation.
API reads are diagnostic traffic, never counted as scientific model calls.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
from pathlib import Path

import httpx

from manage_campaign import ORIGIN, admin_client, save


def event_pages(client, operation_id):
    after = 0
    events = []
    while True:
        response = client.get(f"/v1/operations/{operation_id}/events",
                              params={"after_sequence": after, "limit": 1000})
        response.raise_for_status()
        page = response.json()["data"]
        if not page:
            return events
        sequence = [row["sequence"] for row in page]
        if sequence != sorted(set(sequence)) or sequence[0] <= after:
            raise ValueError("Scientific event pagination did not advance uniquely")
        events.extend(page)
        after = sequence[-1]
        if len(page) < 1000:
            return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--scientists", type=Path, required=True)
    parser.add_argument("--operator-accounting", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    people = {p["id"]: p for p in json.loads(args.scientists.read_text())["scientists"]}
    with (admin_client() if args.operator_accounting else nullcontext(None)) as admin:
        for receipt_path in sorted(args.cohort.glob("scientist-*/*/receipt.json")):
            receipt = json.loads(receipt_path.read_text())
            folder = receipt_path.parent
            operation_path = folder / "operation.json"
            if not operation_path.exists():
                continue
            operation = json.loads(operation_path.read_text())
            if operation["status"] not in {"succeeded", "failed", "cancelled", "expired", "preempted"}:
                continue
            if operation["protocol"] != "scientific-batch-v1":
                continue
            person = people[receipt["scientist"]]
            events_path = folder / "scientific-events.json"
            if args.refresh or not events_path.exists():
                with httpx.Client(base_url=ORIGIN, timeout=90, trust_env=False,
                                  headers={"authorization": "Bearer " + person["api_key"]}) as client:
                    events = event_pages(client, operation["id"])
                save(events_path, {"operation_id": operation["id"], "events": events})
            if admin and (args.refresh or not (folder / "operator-accounting.json").exists()):
                response = admin.get("/admin/api/v1/scientific-runs/" + operation["id"])
                response.raise_for_status()
                save(folder / "operator-accounting.json", response.json())
            print(json.dumps({"case_id": receipt["case_id"], "operation_id": operation["id"],
                              "captured": str(events_path)}), flush=True)


if __name__ == "__main__":
    main()
