"""Scientific input manifests and verified terminal artifacts for study cases."""
from __future__ import annotations

import gzip
import copy
import csv
import hashlib
import io
import json
import tarfile
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from manage_campaign import save


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def checked(response):
    response.raise_for_status()
    return response


def upload(client, model, data, media_type, compression, request_id):
    measured = {"model_id": model, "sha256": hashlib.sha256(data).hexdigest(),
                "size_bytes": len(data), "media_type": media_type, "compression": compression}
    begun = checked(client.post("/v1/scientific-artifacts/uploads", json=measured,
                                headers={"idempotency-key": request_id})).json()
    if len(data) <= begun["max_content_bytes"]:
        target = begun["content_path"]
        if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
            raise ValueError("Upload did not provide a relative content path")
        written = client.put(target, content=data, headers={"content-type": media_type})
        if written.status_code != 409:
            checked(written)
    else:
        handle = begun["handle"]
        if urlparse(handle["url"]).scheme != "https":
            raise ValueError("Large upload handle must be HTTPS")
        # Object storage receives only its signed headers, never the model key.
        with httpx.Client(timeout=600, trust_env=False, follow_redirects=False) as storage:
            written = storage.put(handle["url"], content=data, headers=handle.get("headers", {}))
            if written.status_code not in {409, 412}:
                checked(written)
    # A resumed write-once upload may already contain its exact bytes. Always
    # independently finalize and compare metadata; a conflict alone is never
    # evidence of a successful upload.
    reference = checked(client.post(
        "/v1/scientific-artifacts/uploads/" + quote(begun["upload_id"], safe="") + ":finalize",
        json={"operation_id": begun["operation_id"]})).json()
    for key, value in measured.items():
        if key != "model_id" and reference.get(key) != value:
            raise ValueError("Finalized artifact metadata mismatch")
    return reference


def prepare_arguments(client, case, root, folder, request_id, receipt):
    receipt.setdefault("input_artifacts", {})
    entries = []
    for item in case.get("preparation", {}).get("inputs", []):
        data = (root / item["local_path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["size_bytes"]:
            raise ValueError("Study input changed after manifest was prepared")
        if item["name"] not in receipt["input_artifacts"]:
            reference = upload(client, case["model_id"], data, item["media_type"],
                               item.get("compression", "none"), request_id + "-" + item["name"])
            receipt["input_artifacts"][item["name"]] = reference
            save(folder / "receipt.json", receipt)
        entries.append({"name": item["name"], "semantic_type": item["semantic_type"],
                        "artifact": receipt["input_artifacts"][item["name"]]})
    if not entries:
        raise ValueError("Scientific batch case has no declared inputs")
    manifest = {"schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
                "manifest_id": request_id, "entries": entries}
    save(folder / "input-manifest.json", manifest)
    if "input_manifest" not in receipt:
        receipt["input_manifest"] = upload(client, case["model_id"], canonical(manifest),
            "application/vnd.fs2.scientific-manifest+json", "none", request_id + "-manifest")
        save(folder / "receipt.json", receipt)
    return {**case["arguments"], "input_manifest": receipt["input_manifest"],
            "idempotency_key": request_id,
            "client_context": {"display_name": case["case_id"], "correlation_id": request_id}}


def prepare_native_arguments(client, case, root, folder, request_id, receipt):
    fields = [item for item in case.get("preparation", {}).get("artifact_fields", [])
              if "field" in item or item.get("transport") == "artifact"]
    if not fields:
        return case["arguments"]
    arguments = copy.deepcopy(case["arguments"])
    receipt.setdefault("input_artifacts", {})
    for item in fields:
        field = item.get("field", item.get("argument_path"))
        parts = field.split(".") if isinstance(field, str) else field
        if not parts:
            raise ValueError("Native artifact field must identify an argument path")
        identity = json.dumps(parts, separators=(",", ":"))
        data = (root / item["local_path"]).read_bytes()
        if len(data) != item["size_bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Native study input differs from the frozen manifest")
        if identity not in receipt["input_artifacts"]:
            reference = upload(client, case["model_id"], data, item["media_type"], item.get("compression", "none"),
                               request_id + "-artifact-" + hashlib.sha256(identity.encode()).hexdigest()[:12])
            receipt["input_artifacts"][identity] = reference
            save(folder / "receipt.json", receipt)
        target = arguments
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = receipt["input_artifacts"][identity]
    return arguments


def materialize(raw, reference, name):
    """Parse outputs, including archived structures, without extracting paths."""
    if reference.get("compression") == "gzip":
        raw = gzip.decompress(raw)
    media = reference.get("media_type", "")
    if "json" in media:
        return json.loads(raw)
    if media == "text/csv" or name.endswith(".csv"):
        return {"csv_rows": list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))}
    if "pdb" in media or "cif" in media or name.endswith((".pdb", ".cif")):
        return {"structure": raw.decode()}
    if "tar" in media or name.endswith((".tar", ".tar.gz", ".tgz")):
        structures = []
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:*") as bundle:
            for member in bundle:
                if member.isfile() and member.name.lower().endswith((".pdb", ".cif")):
                    source = bundle.extractfile(member)
                    if source is not None:
                        structures.append({"structure": source.read().decode(), "member": member.name})
        return {"structures": structures}
    return {"name": name, "media_type": media, "bytes": len(raw), "artifact_verified": True}


def resolve(client, envelope, folder, download):
    if envelope.get("terminal_status") != "succeeded":
        raise ValueError("Scientific result has no successful terminal state")
    reference = envelope["output_manifest"]
    manifest = json.loads(download(client, reference, folder))
    save(folder / "output-manifest.json", manifest)
    if manifest.get("schema") != "fs2-serve.nebius.ai/scientific-artifact-manifest/v1":
        raise ValueError("Unexpected output manifest schema")
    outputs = []
    for entry in manifest.get("entries", []):
        data = download(client, entry["artifact"], folder)
        parsed = materialize(data, entry["artifact"], entry["name"])
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        outputs.append({**parsed, "artifact_name": entry["name"], "semantic_type": entry["semantic_type"],
                        "verified_sha256": entry["artifact"]["sha256"]})
    if not outputs:
        raise ValueError("Successful scientific operation published an empty manifest")
    return {"outputs": outputs, "platform_semantic_validation": envelope.get("semantic_validation"),
            "verified_artifacts": len(outputs)}
