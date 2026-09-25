#!/usr/bin/env python3
"""Upload only selected manifests, referenced WAVs and requested provenance.

Uses the standard AWS credential provider chain; never prints credentials. Every
PUT is create-only and every object is read back and SHA-256 verified. This
mutates only the explicitly named bucket and requires its owner's authorization.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

from prepare_corpus import digest


def inputs(root, manifests, provenance, container_root="/data/clinical-speech"):
    root = root.resolve()
    result = {}
    def add(key):
        path = (root / key).resolve()
        if not path.is_relative_to(root) or not path.is_file() or Path(key).is_absolute():
            raise ValueError("Missing or out-of-scope input:" + key)
        result[key] = path
        return path
    for name in manifests:
        manifest = add(name)
        for line in manifest.read_text().splitlines():
            row = json.loads(line)
            source = Path(row["audio_filepath"])
            key = source.relative_to(container_root).as_posix()
            path = add(key)
            if path.suffix != ".wav":
                raise ValueError("Only prepared WAV inputs supported")
            if row.get("audio_sha256") and digest(path) != row["audio_sha256"]:
                raise ValueError("Manifest audio checksum mismatch")
    for name in provenance:
        add(name)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--manifest", action="append", required=True, help="Relative to data root; repeat for multiple manifests")
    parser.add_argument("--provenance", action="append", default=[])
    parser.add_argument("--container-root", default="/data/clinical-speech")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.receipt.exists():
        raise ValueError("Receipt already exists; refuse replacement")
    import boto3
    client = boto3.client("s3", endpoint_url=os.environ["AWS_ENDPOINT_URL"], region_name=os.getenv("AWS_DEFAULT_REGION", "eu-north1"))
    def create_only(request, **kwargs):
        request.headers["If-None-Match"] = "*"
    client.meta.events.register("before-sign.s3.PutObject", create_only)
    report = []
    for key, path in sorted(inputs(args.data_root, args.manifest, args.provenance, args.container_root).items()):
        expected, size = digest(path), path.stat().st_size
        try:
            with path.open("rb") as stream:
                client.put_object(Bucket=args.bucket, Key=key, Body=stream, ContentLength=size, Metadata={"sha256": expected})
            state = "uploaded"
        except client.exceptions.ClientError as exc:
            # Nebius Object Storage reports HTTP412/KeyAlreadyExists for the
            # exercised If-None-Match:* collision; AWS uses PreconditionFailed.
            # Neither permits overwrite: independently full-GET verify below.
            if exc.response["Error"]["Code"] not in {"412", "PreconditionFailed", "KeyAlreadyExists"}:
                raise
            state = "verified_existing"
        response = client.get_object(Bucket=args.bucket, Key=key)
        check = hashlib.sha256()
        try:
            for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                check.update(chunk)
        finally:
            response["Body"].close()
        if response["ContentLength"] != size or check.hexdigest() != expected or digest(path) != expected:
            raise ValueError("Object/local content mismatch; no overwrite:" + key)
        report.append({"key": key, "sha256": expected, "bytes": size, "state": state})
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    with args.receipt.open("x") as stream:
        stream.write(json.dumps({"bucket": args.bucket, "objects": report, "verification": "full_GET_SHA256"}, indent=2) + "\n")
    print(json.dumps({"objects": len(report), "receipt": str(args.receipt)}))


if __name__ == "__main__":
    main()
