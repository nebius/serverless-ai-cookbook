#!/usr/bin/env python3
"""Read-only latency/reliability probe for exact retained scientific run details."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import time
from uuid import UUID

import httpx

from manage_campaign import admin_client, save


def run_probe(client, operations, repetitions, output, *, clock=time.monotonic, pause=time.sleep):
    """Keep every planned read, including non-JSON/transport failures; never retry."""
    operations = [UUID(str(operation)) for operation in operations]
    if not operations or not 1 <= repetitions <= 20:
        raise ValueError("Choose at least one operation and 1–20 repetitions")
    if output.exists():
        raise ValueError("Preserve an existing evidence directory; choose a fresh run")
    output.mkdir(parents=True, mode=0o700)
    rows = []
    for repetition in range(repetitions):
        for operation in operations:
            row = {"operation_id": str(operation), "repetition": repetition,
                   "http_status": None, "request_id": None, "data_keys": [],
                   "detail_envelope_valid": False}
            retained = {}
            started = clock()
            try:
                response = client.get("/admin/api/v1/scientific-runs/" + str(operation))
            except httpx.RequestError as error:
                row["elapsed_seconds"] = clock() - started
                # Exception strings can contain URLs/credentials; retain only the type.
                row["transport_error"] = type(error).__name__
            else:
                row["elapsed_seconds"] = clock() - started
                row["http_status"] = response.status_code
                row["request_id"] = response.headers.get("x-request-id")
                row["content_type"] = response.headers.get("content-type")
                try:
                    body = response.json()
                except ValueError:
                    retained["body_text"] = response.text
                    row["body_error"] = "non_json_response"
                else:
                    retained["body"] = body
                    if isinstance(body, dict):
                        meta, data = body.get("meta"), body.get("data")
                        if isinstance(meta, dict) and isinstance(meta.get("request_id"), str):
                            row["request_id"] = meta["request_id"]
                        if isinstance(data, dict):
                            row["data_keys"] = sorted(data)
                            row["detail_envelope_valid"] = isinstance(data.get("run"), dict)
            row["at"] = datetime.now(timezone.utc).isoformat()
            save(output / f"{repetition}-{operation}.json", {"observation": row, **retained})
            rows.append(row)
            save(output / "observations.json", rows)
            pause(1)
    statuses = [str(row["http_status"]) if row["http_status"] is not None else "transport_error" for row in rows]
    report = {"read_only": True, "requests": len(rows), "all_http_200": all(row["http_status"] == 200 for row in rows),
              "all_detail_envelopes_valid": all(row["detail_envelope_valid"] for row in rows),
              "median_seconds": statistics.median(row["elapsed_seconds"] for row in rows),
              "maximum_seconds": max(row["elapsed_seconds"] for row in rows),
              "status_counts": {code: statuses.count(code) for code in sorted(set(statuses))},
              "scope": "Bounded sequential real-admin read evidence, not a broad latency/SLO guarantee."}
    save(output / "summary.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", type=UUID, action="append", required=True)
    parser.add_argument("--repetitions", type=int, default=6, choices=range(1, 21))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Preserve an existing evidence directory; choose a fresh run")
    with admin_client() as client:
        report = run_probe(client, args.operation, args.repetitions, args.output)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
