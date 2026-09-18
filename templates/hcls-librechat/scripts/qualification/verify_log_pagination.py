#!/usr/bin/env python3
"""Compare fixed-window live App log pages with one unpaginated public read."""
import argparse
import time
from pathlib import Path

from manage_campaign import admin_client, save


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--from-at", required=True)
    parser.add_argument("--to-at", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    base = {"from": args.from_at, "to": args.to_at, "search": "", "pod": ""}
    with admin_client() as client:
        response = client.get("/admin/api/v1/apps")
        response.raise_for_status()
        app = next(a for a in response.json()["data"]["items"] if a["public_model_id"] == args.model)
        path = f"/admin/api/v1/apps/{app['app_id']}/logs"

        def read(name, **params):
            started = time.monotonic()
            response = client.get(path, params={**base, **params})
            elapsed = time.monotonic() - started
            response.raise_for_status()
            body = response.json()
            save(args.output / (name + ".json"), {"http_status": response.status_code,
                 "elapsed_seconds": elapsed, "request": {**base, **params}, "body": body})
            data = body["data"]
            if data["state"] != "available":
                raise ValueError("Live logs are not available: " + str(data.get("reason")))
            return data, elapsed

        single, single_elapsed = read("single-500", limit=500)
        rows, cursor, times = [], None, []
        for index in range(3):
            page, elapsed = read(f"page-{index + 1}-200", limit=200,
                                 **({"cursor": cursor} if cursor else {}))
            rows.extend(page["items"])
            times.append(elapsed)
            cursor = page.get("next_cursor")
            if not cursor:
                break
        # The window is fixed in the past, so a live append cannot justify a
        # missing/repeated boundary row. Comparison is ordered and lossless.
        same = rows[:len(single["items"])] == single["items"]
        result = {"verified": same and len(single["items"]) == 500,
                  "single_rows": len(single["items"]), "paged_rows": len(rows),
                  "ordered_prefix_exact": same, "single_elapsed_seconds": single_elapsed,
                  "page_elapsed_seconds": times, "model": args.model, "window": base}
        save(args.output / "verification.json", result)
        print(result)
        raise SystemExit(0 if result["verified"] else 1)


if __name__ == "__main__":
    main()
