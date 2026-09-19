#!/usr/bin/env python3
"""Submit one real scientific-batch input and retain hash-verified evidence.

The output directory is the resume boundary. Re-running it polls the saved
operation; it never silently resubmits after ambiguous admission.
"""

import argparse
import asyncio
import errno
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from urllib.parse import quote, urlparse
from uuid import UUID, uuid4

import httpx2
from jsonschema import Draft202012Validator
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

# The same source is installed beside scientific_receipts.py in the image.
if Path(__file__).parent.name == 'scripts':
    sys.path.insert(0, str(Path(__file__).parent.parent))
from scientific_receipts import load as load_receipt, receipt_lock, save


TERMINAL = {"failed", "cancelled", "expired", "preempted"}
ARTIFACT_CHUNK_BYTES = 1024 * 1024


class ExplicitRejection(RuntimeError):
    def __init__(self, error: dict):
        allowed = ("type", "code", "message", "request_id", "idempotency_key",
                   "retryable", "retry_after_seconds", "durable_admission")
        self.error = {key: error[key] for key in allowed if key in error}
        super().__init__(self.error.get("message", "Gateway explicitly rejected the request."))


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check(response):
    if not response.is_success:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        if isinstance(error, dict) and error.get("durable_admission") is False:
            raise ExplicitRejection(error)
        raise RuntimeError(f"Platform returned HTTP {response.status_code}; inspect the saved evidence.")
    return response


def unpack(response):
    data = response.model_dump(mode="json", by_alias=True)
    if data.get("isError"):
        text = next((item.get("text", "") for item in data.get("content", []) if item.get("type") == "text"), "")
        try:
            error = json.loads(text).get("error", {})
        except (TypeError, ValueError, AttributeError):
            error = {}
        if error.get("durable_admission") is False:
            raise ExplicitRejection(error)
        raise RuntimeError("MCP tool failed: " + text[:500])
    if data.get("structuredContent") is not None:
        return data["structuredContent"]
    texts = [item["text"] for item in data.get("content", []) if item.get("type") == "text"]
    if len(texts) != 1:
        raise RuntimeError("Expected one JSON MCP result.")
    return json.loads(texts[0])


async def call(client, name: str, arguments: dict):
    return unpack(await client.call_tool(name, arguments))


def scientific_contract(discovery: dict) -> dict:
    contracts = discovery.get('contracts', [discovery])
    contract = next((item for item in contracts if item.get('protocol') == 'scientific-batch-v1'), {})
    # The real get_model_schema response publishes shared artifact policies at
    # its top level, alongside contracts; do not discard them while selecting a
    # transport. Keep older nested responses compatible without mutating either.
    published = {field: discovery[field] for field in
                 ('artifact_manifest_schema', 'input_artifact_contract') if field in discovery}
    return {**contract, **published} if published else contract


def preflight_source(contract: dict, parameters: dict, args, size: int) -> None:
    """Validate a published semantic role before reserving or uploading bytes."""
    policy = contract.get('input_artifact_contract')
    if not policy:
        return  # Older servers still validate the final request themselves.
    context = {'operation': getattr(args, 'operation', None), 'parameters': parameters}
    if 'entry' in policy:
        source, selection = policy['entry'], 'the published input entry'
    else:
        selector = policy.get('operation_parameter') or policy.get('source_kind_parameter', 'parameters.source.kind')
        value = context
        for part in selector.split('.'):
            value = value.get(part) if isinstance(value, dict) else None
        alternatives = policy.get('operations') if 'operation_parameter' in policy else policy.get('source_kinds')
        source = alternatives.get(value) if isinstance(alternatives, dict) else None
        selection = f'{selector}={value!r}'
    if not isinstance(source, dict) or not source:
        raise ValueError(f'Input selector {selection} is not in the published input_artifact_contract; no upload was submitted.')
    mismatches = []
    for argument, field in [('entry_name', 'name'), ('semantic_type', 'semantic_type'),
                            ('media_type', 'media_type')]:
        if field in source and getattr(args, argument) != source[field]:
            mismatches.append(f'{field} must be {source[field]!r}, received {getattr(args, argument)!r}')
    allowed_compressions = source.get('allowed_compressions')
    if allowed_compressions is not None:
        if not isinstance(allowed_compressions, list) or not allowed_compressions:
            raise ValueError('Published allowed_compressions must be a nonempty list.')
        if args.compression not in allowed_compressions:
            mismatches.append(f'compression must be one of {allowed_compressions!r}, received {args.compression!r}')
    elif 'compression' in source and args.compression != source['compression']:
        mismatches.append(f'compression must be {source["compression"]!r}, received {args.compression!r}')
    if source.get('maximum_bytes') is not None and size > source['maximum_bytes']:
        mismatches.append('input bytes exceed the published source maximum_bytes')
    if size < 1:
        mismatches.append('source_file must contain at least one byte')
    if mismatches:
        raise ValueError(f'Input artifact metadata for {selection}: ' + '; '.join(mismatches) +
                         '. The entry name is a semantic role, not the local filename. '
                         'The source media type describes the actual bytes, not the outer manifest. '
                         'No upload or inference was submitted.')


def source_reference(path: Path, data: bytes, args) -> dict:
    reference = json.loads(path.read_text())
    return validate_source_reference(reference, data, args)


def validate_source_reference(reference: dict, data: bytes, args) -> dict:
    for field, expected in {'sha256': digest(data), 'size_bytes': len(data),
                            'media_type': args.media_type, 'compression': args.compression}.items():
        if reference.get(field) != expected:
            raise ValueError('Existing artifact reference does not match exact source bytes and format: ' + field)
    if not isinstance(reference.get('artifact_id'), str) or not reference['artifact_id']:
        raise ValueError('Existing artifact reference must include its finalized artifact_id.')
    return {field: reference[field] for field in ('artifact_id', 'sha256', 'size_bytes', 'media_type', 'compression')}


async def upload(http, model: str, data: bytes, media_type: str, compression: str,
                 idempotency_key: str) -> dict:
    measured = {"model_id": model, "sha256": digest(data), "size_bytes": len(data),
                "media_type": media_type, "compression": compression}
    begun = check(await http.post("/v1/scientific-artifacts/uploads", json=measured,
                                 headers={"idempotency-key": idempotency_key})).json()
    if len(data) <= begun["max_content_bytes"]:
        target = begun["content_path"]
        if not isinstance(target, str) or not target.startswith("/") or target.startswith("//"):
            raise RuntimeError("Unsafe same-origin upload path.")
        check(await http.put(target, content=data, headers={"content-type": media_type,
                                                            "content-length": str(len(data))}))
    else:
        handle = begun.get("handle", {})
        if urlparse(handle.get("url", "")).scheme != "https":
            raise RuntimeError("Large upload did not return an HTTPS object-storage handle.")
        async with httpx2.AsyncClient(timeout=600, trust_env=False, follow_redirects=False) as storage:
            check(await storage.put(handle["url"], content=data, headers=handle.get("headers", {})))
    result = check(await http.post(
        "/v1/scientific-artifacts/uploads/" + quote(begun["upload_id"], safe="") + ":finalize",
        json={"operation_id": begun["operation_id"]},
    )).json()
    for key, value in measured.items():
        if key != "model_id" and result.get(key) != value:
            raise RuntimeError("Finalized artifact metadata mismatch.")
    return result


def artifact_file_measurement(path: Path) -> tuple[int, str]:
    """Hash retained files without loading an entire scientific dataset."""
    size, checksum = 0, hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(ARTIFACT_CHUNK_BYTES):
            size += len(chunk)
            checksum.update(chunk)
    return size, checksum.hexdigest()


def verify_artifact_file(path: Path, reference: dict) -> None:
    if artifact_file_measurement(path) != (reference['size_bytes'], reference['sha256']):
        raise RuntimeError('Existing artifact bytes differ from the declared result; preserve them and use a new recovery directory.')


def publish_artifact(staged: Path, target: Path, reference: dict) -> str:
    """Publish verified local bytes without overwriting prior evidence.

    A same-filesystem hard link is atomic and exclusive. Object Storage mounts
    do not support that operation (or reliable rename); there the final copy is
    exclusive, streamed, fsynced and read back before its receipt is published.
    It is deliberately not described as atomically visible on a bucket mount.
    """
    try:
        os.link(staged, target)
        return 'atomic-link'
    except FileExistsError:
        verify_artifact_file(target, reference)
        return 'verified-existing'
    except OSError as error:
        if error.errno not in {errno.EXDEV, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EPERM, errno.ENOSYS}:
            raise
    created = False
    try:
        with open(target, 'xb', opener=lambda path, flags: os.open(path, flags, 0o600)) as output:
            created = True
            with staged.open('rb') as source:
                while chunk := source.read(ARTIFACT_CHUNK_BYTES):
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        verify_artifact_file(target, reference)
        return 'verified-copy'
    except FileExistsError:
        verify_artifact_file(target, reference)
        return 'verified-existing'
    except BaseException as error:
        # Only the partial file exclusively created by this attempt is removed.
        # Existing files and all operation/admission receipts remain untouched.
        if created:
            try:
                target.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f'Partial artifact remains at {target}; cleanup failed: {cleanup_error}. No verified receipt was published.')
        raise


async def download(http, reference: dict, target: Path) -> dict:
    expected_size = reference['size_bytes']
    if type(expected_size) is not int or expected_size < 0:
        raise ValueError('Artifact size_bytes must be a nonnegative integer.')
    expected_hash = reference['sha256']
    if not isinstance(expected_hash, str) or len(expected_hash) != 64 or any(c not in '0123456789abcdef' for c in expected_hash):
        raise ValueError('Artifact sha256 must be a canonical SHA-256 digest.')
    if target.exists():
        verify_artifact_file(target, reference)
        publication = 'verified-existing'
    else:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Stage outside the customer bucket so an interrupted network transfer
        # never appears as a completed artifact. No new global size cap: the
        # exact server-declared size bounds every chunk and the resulting file.
        with tempfile.TemporaryDirectory(prefix='scientific-artifact-') as folder:
            staged = Path(folder) / 'download.partial'
            size, checksum = 0, hashlib.sha256()
            path = '/v1/artifacts/' + quote(reference['artifact_id'], safe='') + '/content'
            async with http.stream('GET', path) as response:
                if not response.is_success:
                    raise RuntimeError(f'Platform returned HTTP {response.status_code}; inspect the saved evidence.')
                length = response.headers.get('content-length')
                if length is not None and int(length) != expected_size:
                    raise RuntimeError('Artifact Content-Length differs from the declared size.')
                with open(staged, 'xb', opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
                    # Stored gzip/zstd bytes are the checksum identity; do not
                    # transparently decode HTTP Content-Encoding during hashing.
                    async for chunk in response.aiter_raw(chunk_size=ARTIFACT_CHUNK_BYTES):
                        size += len(chunk)
                        if size > expected_size:
                            raise RuntimeError('Downloaded artifact exceeds its declared size.')
                        checksum.update(chunk)
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            if size != expected_size or checksum.hexdigest() != expected_hash:
                raise RuntimeError('Downloaded artifact hash or size mismatch.')
            publication = publish_artifact(staged, target, reference)
    return {'artifact_id': reference['artifact_id'], 'path': str(target),
            'size_bytes': expected_size, 'sha256': expected_hash, 'publication': publication}


async def collect_outputs(http, result: dict, output: Path) -> dict:
    """One flat published manifest, using the existing hash-verified transport."""
    if result.get('terminal_status') != 'succeeded' or result.get('semantic_validation', {}).get('status') != 'passed':
        raise RuntimeError('Published result did not pass semantic validation.')
    manifest = await download(http, result['output_manifest'], output / 'output-manifest.json')
    entries = json.loads((output / 'output-manifest.json').read_text())['entries']
    artifacts = []
    for index, entry in enumerate(entries):
        downloaded = await download(http, entry['artifact'], output / f'output-{index:02d}.artifact')
        artifacts.append({**entry['artifact'], **downloaded,
                          'name': entry['name'], 'semantic_type': entry['semantic_type']})
    return {'output_manifest': manifest, 'verified_artifacts': artifacts}


async def recover_completed(args) -> dict:
    """Only status/result reads: never reserve, upload, admit, cancel or infer."""
    operation_id = str(UUID(args.recover_operation_id))
    endpoint = os.environ['SCIENTIFIC_MODELS_MCP_URL']
    key = os.environ['SCIENTIFIC_MODELS_API_KEY']
    origin = endpoint.removesuffix('/mcp').removesuffix('/mcp/')
    identity = {'operation_id': operation_id, 'endpoint': endpoint,
                'caller_fingerprint': digest(key.encode())}
    path = args.output / 'recovery-receipt.json'
    receipt = load_receipt(path)
    if receipt is None:
        # The caller's existing run directory and any rejected receipts remain
        # untouched. Use a new recovery directory, then reuse its exact identity.
        existing = [item for item in args.output.iterdir()] if args.output.exists() else []
        if existing:
            raise ValueError('Use an empty recovery directory; existing study files are preserved.')
        receipt = {'identity': identity, 'operation_id': operation_id, 'state': 'prepared'}
    if receipt['identity'] != identity:
        raise ValueError('Recovery directory belongs to a different operation or caller.')
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    save(path, receipt)
    headers = {'authorization': 'Bearer ' + key}
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        async with httpx2.AsyncClient(headers=headers, timeout=180, trust_env=False) as mcp_http:
            async with Client(streamable_http_client(endpoint, http_client=mcp_http)) as client:
                # This is one bounded observation, not a polling/admission loop.
                status = await call(client, 'get_scientific_status', {'operation_id': operation_id})
                save(args.output / 'status.json', status)
                operation = status.get('operation', status)
                receipt['state'] = operation['status']
                save(path, receipt)
                if operation['status'] != 'succeeded' or not status.get('batch', {}).get('result_published'):
                    raise RuntimeError('Existing operation is not a published successful result: ' + operation['status'] + '. No model work was submitted.')
                result = await call(client, 'get_scientific_result', {'operation_id': operation_id})
                if result.get('operation_id') != operation_id:
                    raise RuntimeError('Result operation identity differs from requested operation.')
                save(args.output / 'result.json', result)
                receipt.update(await collect_outputs(http, result, args.output), state='verified')
                save(path, receipt)
                print(json.dumps({'operation_id': operation_id, 'state': 'verified',
                                  'receipt_file': str(path), 'artifacts': receipt['verified_artifacts'],
                                  'inference_submitted': False}), flush=True)
                return receipt


async def run(args) -> dict:
    endpoint = os.environ["SCIENTIFIC_MODELS_MCP_URL"]
    key = os.environ["SCIENTIFIC_MODELS_API_KEY"]
    origin = endpoint.removesuffix("/mcp").removesuffix("/mcp/")
    source = args.source.read_bytes()
    parameters = json.loads(args.parameters.read_text())
    identity = {"model_id": args.model, "source_sha256": digest(source),
                "parameters_sha256": digest(canonical(parameters)), "endpoint": endpoint,
                "caller_fingerprint": digest(key.encode()), "idempotency_key": args.idempotency_key}
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    receipt_path = args.output / "receipt.json"
    receipt = load_receipt(receipt_path)
    if receipt is None:
        receipt = {"identity": identity, "state": "prepared", "manifest_id": "scientist-cohort-" + str(uuid4())}
    if receipt["identity"] != identity:
        raise ValueError("Output directory belongs to a different request.")
    if receipt.get("state") == "verified":
        return receipt
    save(receipt_path, receipt)
    headers = {"authorization": "Bearer " + key}
    async with httpx2.AsyncClient(base_url=origin, headers=headers, timeout=180,
                                  trust_env=False, follow_redirects=False) as http:
        async with httpx2.AsyncClient(headers=headers, timeout=180, trust_env=False) as mcp_http:
            async with Client(streamable_http_client(endpoint, http_client=mcp_http)) as client:
                tools = (await client.list_tools()).tools
                tool = next((item for item in tools if item.name == args.tool), None)
                if tool is None:
                    raise RuntimeError("Requested scientific-batch tool is unavailable.")
                save(args.output / "contract.json", tool.model_dump(mode="json", by_alias=True))
                if not receipt.get("operation_id"):
                    if receipt["state"] in {"submitting", "admission_unknown"}:
                        raise RuntimeError("Previous admission is ambiguous; inspect evidence before retrying.")
                    discovery = await call(client, 'get_model_schema', {'model_id': args.model,
                                                                       'protocol': 'scientific-batch-v1'})
                    save(args.output / 'model-contract.json', discovery)
                    contract = scientific_contract(discovery)
                    preflight_source(contract, parameters, args, len(source))
                    descriptor = {'entry_name': args.entry_name, 'semantic_type': args.semantic_type,
                                  'media_type': args.media_type, 'compression': args.compression,
                                  'tool': args.tool, 'operation': args.operation}
                    if receipt.get('request_descriptor', descriptor) != descriptor:
                        raise ValueError('Saved manifest role or operation differs; preserve the original receipt for explicit recovery.')
                    previous_manifest = args.output / 'input-manifest.json'
                    if 'manifest_artifact' in receipt and previous_manifest.exists():
                        previous = json.loads(previous_manifest.read_text())['entries'][0]
                        if previous['name'] != args.entry_name or previous['semantic_type'] != args.semantic_type:
                            raise ValueError('Existing uploaded manifest has a different semantic role; do not reuse it under changed arguments.')
                    receipt['request_descriptor'] = descriptor
                    save(receipt_path, receipt)
                    if "source_artifact" not in receipt:
                        reused_source = getattr(args, 'source_artifact', None)
                        receipt["source_artifact"] = source_reference(reused_source, source, args) if reused_source else await upload(
                            http, args.model, source, args.media_type, args.compression,
                            args.idempotency_key + "-source")
                        save(receipt_path, receipt)
                    receipt['source_artifact'] = validate_source_reference(receipt['source_artifact'], source, args)
                    if parameters.get("source", {}).get("kind") == "uploaded-bundle":
                        parameters = {**parameters, "source": {
                            "kind": "uploaded-bundle", **receipt["source_artifact"]}}
                    manifest = {"schema": "fs2-serve.nebius.ai/scientific-artifact-manifest/v1",
                                "manifest_id": receipt["manifest_id"], "entries": [{
                                    "name": args.entry_name, "semantic_type": args.semantic_type,
                                    "artifact": receipt["source_artifact"]}]}
                    if contract.get('artifact_manifest_schema'):
                        Draft202012Validator(contract['artifact_manifest_schema']).validate(manifest)
                    save(args.output / "input-manifest.json", manifest)
                    if "manifest_artifact" not in receipt:
                        receipt["manifest_artifact"] = await upload(
                            http, args.model, canonical(manifest),
                            "application/vnd.fs2.scientific-manifest+json", "none",
                            args.idempotency_key + "-manifest")
                        save(receipt_path, receipt)
                    request = {"schema": "fs2-serve.nebius.ai/scientific-run-request/v1",
                               "operation": args.operation, "service_class": args.service_class,
                               "input_manifest": receipt["manifest_artifact"], "parameters": parameters,
                               "client_context": {"display_name": args.display_name,
                                                  "correlation_id": args.idempotency_key},
                               "idempotency_key": args.idempotency_key}
                    Draft202012Validator(tool.input_schema).validate(request)
                    save(args.output / "request.json", request)
                    receipt["state"] = "submitting"
                    save(receipt_path, receipt)
                    try:
                        accepted = await call(client, args.tool, request)
                    except ExplicitRejection as error:
                        receipt.update(state="rejected", last_rejection=error.error)
                        save(receipt_path, receipt)
                        raise
                    except Exception:
                        receipt["state"] = "admission_unknown"
                        save(receipt_path, receipt)
                        raise
                    save(args.output / "submission.json", accepted)
                    operation = accepted.get("operation", accepted)
                    receipt.update(operation_id=operation.get("id") or operation["operation_id"],
                                   state=operation.get("status", "queued"))
                    save(receipt_path, receipt)
                deadline = time.monotonic() + args.wait_seconds
                while True:
                    status = await call(client, "get_scientific_status", {"operation_id": receipt["operation_id"]})
                    save(args.output / "status.json", status)
                    operation = status.get("operation", status)
                    receipt["state"] = operation["status"]
                    save(receipt_path, receipt)
                    if operation["status"] in TERMINAL:
                        raise RuntimeError("Scientific batch ended in " + operation["status"] + ".")
                    if status.get("batch", {}).get("result_published"):
                        result = await call(client, "get_scientific_result", {"operation_id": receipt["operation_id"]})
                        save(args.output / "result.json", result)
                        collected = await collect_outputs(http, result, args.output)
                        receipt.update(state="verified", **collected)
                        save(receipt_path, receipt)
                        print(json.dumps({"model": args.model, "operation_id": receipt["operation_id"],
                                          "state": "verified", "artifacts": len(collected['verified_artifacts'])}))
                        return receipt
                    if time.monotonic() >= deadline:
                        print(json.dumps({"model": args.model, "operation_id": receipt["operation_id"],
                                          "state": receipt["state"], "resume": str(args.output)}))
                        return receipt
                    await asyncio.sleep(args.poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    if '--recover-operation-id' in sys.argv:
        parser.add_argument('--recover-operation-id', required=True)
        parser.add_argument('--output', required=True, type=Path)
        args = parser.parse_args()
        # The lock is held in the existing local receipt-lock area, not S3/FUSE.
        with receipt_lock(args.output):
            asyncio.run(recover_completed(args))
        return
    parser.add_argument("--model", required=True)
    parser.add_argument("--tool", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument('--source-artifact', type=Path,
                        help='Optional finalized artifact JSON matching exact source bytes; never a filename substituted for an artifact ID.')
    parser.add_argument("--media-type", required=True)
    parser.add_argument("--compression", choices=("none", "gzip", "zstd"), default="none")
    parser.add_argument("--entry-name", required=True)
    parser.add_argument("--semantic-type", required=True)
    parser.add_argument("--parameters", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--service-class", choices=("customer-batch", "bulk-backfill"), default="customer-batch")
    parser.add_argument("--wait-seconds", type=float, default=1800)
    parser.add_argument("--poll-seconds", type=float, default=10)
    args = parser.parse_args()
    with receipt_lock(args.output):
        result = asyncio.run(run(args))
    # An observation timeout is a resumable incomplete operation, not shell
    # success. This also prevents `first && second` from overlapping admissions.
    raise SystemExit(0 if result['state'] == 'verified' else 75)


if __name__ == "__main__":
    main()
