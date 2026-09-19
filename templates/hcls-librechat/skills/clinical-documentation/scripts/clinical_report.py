# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx==0.28.1"]
# ///
"""Uploaded consultation audio -> transcript -> traceable report and questions.

Run with uv run clinical_report.py --help. No administrator credential is used.
The same output directory resumes only identical version/configuration stages.
v5 source anchors are not retrofitted into v4 runs: keep old completed reports
unchanged and choose a new directory to reassess an existing transcript.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlparse
from uuid import uuid4

import httpx
from document import (
    EXTRACT,
    LOCATE,
    QUESTIONS,
    VERIFY,
    VERSION,
    apply_review,
    chunks,
    completion_schema,
    digest,
    evidence_for,
    render,
    render_review,
    source_segments,
    validate_extraction,
    validate_questions,
)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        os.chmod(temporary, 0o600)
        handle.write(content)
    temporary.replace(path)


def read(path):
    return json.loads(path.read_text())


def check(response):
    if response.status_code >= 400:
        # Provider messages/URLs may contain medical text or signed handles.
        raise RuntimeError(f"HTTP {response.status_code}; request_id={response.headers.get('x-request-id', 'unavailable')}")
    return response


def same_origin_path(path):
    if not isinstance(path, str) or not path.startswith("/v1/") or path.startswith("//") or "\\" in path:
        raise ValueError("unexpected platform content path")
    return path


def resolve_result(client, value):
    if value.get("schema") != "fs2-serve.nebius.ai/operation-artifact-result/v1":
        return value
    artifact = value["artifact"]
    if value["content_type"] != "application/json" or artifact["compression"] != "none":
        raise ValueError("unexpected result artifact format")
    response = check(client.get("/v1/artifacts/" + quote(artifact["artifact_id"], safe="") + "/content"))
    if len(response.content) != artifact["size_bytes"] or digest(response.content) != artifact["sha256"]:
        raise ValueError("result artifact integrity mismatch")
    return response.json()


class Platform:
    def __init__(self, origin, key, output, run_id, timeout=1800, poll_seconds=2):
        self.client = httpx.Client(base_url=origin, headers={"authorization": "Bearer " + key},
                                   timeout=180, trust_env=False, follow_redirects=False)
        self.output, self.run_id, self.timeout, self.poll_seconds = output, run_id, timeout, poll_seconds

    def close(self):
        self.client.close()

    def require_models(self, models):
        catalog = check(self.client.get("/v1/models")).json()
        visible = {item["id"] for item in catalog["data"]}
        missing = sorted(set(models) - visible)
        if missing:
            raise ValueError("Apps unavailable to this key: " + ", ".join(missing))
        save(self.output / "catalog.json", {"checked_at": datetime.now(UTC).isoformat(),
                                           "data": [x for x in catalog["data"] if x["id"] in models]})

    def upload(self, path, model):
        target = self.output / "audio-artifact.json"
        if target.exists():
            return read(target)
        content_hash = file_digest(path)
        media_type = mimetypes.guess_type(path.name)[0]
        if media_type in {"audio/x-wav", "audio/vnd.wave"}:
            media_type = "audio/wav"
        if not media_type or not media_type.startswith(("audio/", "video/")):
            raise ValueError("unknown audio format; use WAV, FLAC, MP3, OGG or a supported media container")
        response = check(self.client.post("/v1/scientific-artifacts/uploads", json={
            "model_id": model, "sha256": content_hash, "size_bytes": path.stat().st_size,
            "media_type": media_type, "compression": "none",
        }, headers={"idempotency-key": self.run_id + "-upload"}))
        upload = response.json()
        with path.open("rb") as handle:
            if path.stat().st_size <= upload["max_content_bytes"]:
                check(self.client.put(same_origin_path(upload["content_path"]), content=handle,
                                      headers={"content-type": media_type, "content-length": str(path.stat().st_size)}))
            else:
                if urlparse(upload["handle"]["url"]).scheme != "https":
                    raise ValueError("upload handle is not HTTPS")
                # An object-storage URL must never receive the platform bearer.
                with httpx.Client(timeout=300, trust_env=False, follow_redirects=False) as storage:
                    check(storage.put(upload["handle"]["url"], content=handle, headers=upload["handle"]["headers"]))
        artifact = check(self.client.post("/v1/scientific-artifacts/uploads/" + quote(upload["upload_id"], safe="")
                                          + ":finalize", json={"operation_id": upload["operation_id"]})).json()
        save(target, artifact)
        return artifact

    def operation(self, stage, endpoint, payload):
        folder = self.output / "calls" / stage
        identity = digest({"endpoint": endpoint, "payload": payload})
        state_path = folder / "state.json"
        state = read(state_path) if state_path.exists() else {"request_sha256": identity}
        if state["request_sha256"] != identity:
            raise ValueError("request changed; use a new output directory")
        if (folder / "response.json").exists():
            return read(folder / "response.json")
        save(folder / "request.json", {"endpoint": endpoint, "payload": payload})
        started = time.monotonic()
        if not state.get("operation_id"):
            response = check(self.client.post(endpoint, json=payload, headers={
                "idempotency-key": self.run_id + "-" + stage, "x-fs2-wait-seconds": "0"}))
            value = response.json()
            if response.status_code != 202:
                result = resolve_result(self.client, value)
                save(folder / "response.json", result)
                save(state_path, {**state, "status": "succeeded", "elapsed_seconds": time.monotonic() - started})
                return result
            state["operation_id"] = value.get("id") or value["operation_id"]
            state["submitted_at"] = datetime.now(UTC).isoformat()
            save(state_path, state)
        endpoint = "/v1/operations/" + quote(state["operation_id"], safe="")
        while time.monotonic() - started < self.timeout:
            operation = check(self.client.get(endpoint)).json()
            state.update(status=operation["status"], operation=operation,
                         elapsed_seconds=time.monotonic() - started)
            save(state_path, state)
            if operation["status"] == "succeeded":
                result = resolve_result(self.client, check(self.client.get(endpoint + "/result")).json())
                save(folder / "response.json", result)
                return result
            if operation["status"] in {"failed", "cancelled", "expired", "preempted"}:
                raise RuntimeError(f"{stage}: operation {state['operation_id']} {operation['status']}; see {state_path}")
            time.sleep(self.poll_seconds)
        raise TimeoutError(f"operation {state['operation_id']} still pending; rerun the SAME command to resume")


def file_digest(path):
    import hashlib
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def parse_completion(response):
    choice = response["choices"][0]
    if choice.get("finish_reason") != "stop":
        raise ValueError("report model did not complete; no partial report accepted")
    content = choice["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("empty report-model response")
    content = content.strip()
    if content.startswith("```json\n") and content.endswith("```"):
        content = content[8:-3]
    result = json.loads(content)
    if not isinstance(result, dict):
        raise TypeError("report model returned a non-object")
    return result


class Reporter:
    def __init__(self, platform, model, provider_url=None, provider_key=None):
        self.platform, self.model = platform, model
        self.provider = None
        if provider_url:
            if not provider_key:
                raise ValueError("CLINICAL_REPORT_API_KEY is required for an explicitly selected external report provider")
            self.provider = httpx.Client(base_url=provider_url.rstrip("/") + "/", timeout=300,
                                         headers={"authorization": "Bearer " + provider_key},
                                         trust_env=False, follow_redirects=False)
            ids = {x["id"] for x in check(self.provider.get("models")).json()["data"]}
            if model not in ids:
                raise ValueError("report model absent from the selected provider catalog")

    def complete(self, stage, prompt, data):
        body = {"model": self.model, "messages": [{"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
                "temperature": 0, "max_tokens": 7000 if stage.startswith("extract") else 1800, "stream": False,
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "clinical_documentation", "strict": True,
                    "schema": completion_schema(stage, data)}}}
        if self.model in {"qwen3-8b", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"}:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        if not self.provider:
            response = self.platform.operation(stage, "/v1/chat/completions", body)
        else:
            folder = self.platform.output / "calls" / stage
            cache = folder / "response.json"
            request = {"body": body, "provider": str(self.provider.base_url)}
            if cache.exists():
                if read(folder / "request.json") != request:
                    raise ValueError("provider request changed")
                response = read(cache)
            else:
                # No claim of provider-side exactly-once execution after a lost response.
                save(folder / "request.json", request)
                started = time.monotonic()
                response = check(self.provider.post("chat/completions", json=body)).json()
                save(cache, response)
                save(folder / "state.json", {"elapsed_seconds": time.monotonic() - started,
                                              "provider": str(self.provider.base_url)})
        return parse_completion(response)

    def close(self):
        if self.provider:
            self.provider.close()


def document_transcript(text, language, reporter, output):
    if not text.strip():
        raise ValueError("empty transcript: no consultation report generated")
    facts, uncertainties, rejected, kinds = [], [], [], []
    next_id = 1
    for index, chunk in enumerate(chunks(text)):
        chunk["segments"] = source_segments(chunk)
        data = {"language": language, "segments": [{"id": s["id"], "text": s["text"]} for s in chunk["segments"]]}
        value = reporter.complete(f"extract-{index:03}", EXTRACT, data)
        current, doubts, invalid, next_id = validate_extraction(value, chunk, next_id)
        kinds.append(value["kind"])
        if current:
            def review_one(fact, index=index, data=data, chunk=chunk):
                stage = f"review-{index:03}-{fact['id']}"
                # One fact per call: another fact's evidence must not justify it.
                verdict = reporter.complete(stage, VERIFY, {"language": language, "facts": [fact]})
                kept, dropped = apply_review([fact], verdict)
                # An incomplete citation can be labelled either unsupported or
                # unclear. Locate evidence once for both; this never changes
                # the statement and still requires a fresh full fact review.
                if dropped and dropped[0].get("verdict") in {"unsupported", "unclear"}:
                    located = reporter.complete(f"locate-{index:03}-{fact['id']}", LOCATE,
                                                 {**data, "statement": fact["statement"]})
                    if located.get("source_ids"):
                        repaired = {**fact, "evidence": evidence_for(located, chunk),
                                    "citation_repair": {"original_evidence": fact["evidence"], "reason": dropped[0]["reason"]}}
                        verdict = reporter.complete(stage + "-repaired", VERIFY, {"language": language, "facts": [repaired]})
                        kept, dropped = apply_review([repaired], verdict)
                return kept, dropped

            # Bounded client parallelism, not a platform/provider quota change.
            with ThreadPoolExecutor(max_workers=3) as pool:
                checked = list(pool.map(review_one, current))
            current = [fact for kept, _ in checked for fact in kept]
            rejected.extend(item for _, dropped in checked for item in dropped)
        facts.extend(current)
        uncertainties.extend(doubts)
        rejected.extend(invalid)
    # Overlapping chunks can repeat a fact; never collapse differing statements.
    unique = {}
    for fact in facts:
        identity = (fact["section"], fact["statement"].casefold().strip())
        if identity not in unique:
            unique[identity] = fact
        else:
            prior = unique[identity]
            prior["uncertain"] |= fact["uncertain"]
            for evidence in fact["evidence"]:
                if evidence not in prior["evidence"]:
                    prior["evidence"].append(evidence)
    facts = list(unique.values())
    if not facts:
        save(output / "review.json", {"rejected": rejected, "kinds": kinds, "uncertainties": uncertainties})
        raise ValueError("no supported clinical facts; transcript retained without a report")
    # Ask about the entire fact set, not separate chunks that could contain answers.
    question_data = {"language": language, "facts": facts, "uncertainties": uncertainties}
    if len(json.dumps(question_data, ensure_ascii=False)) > 60000:
        # Preserve the full report rather than truncating a very long encounter.
        questions = []
        uncertainties.append({"description": "Question synthesis omitted: full fact set exceeds the configured context budget.", "evidence": []})
    else:
        questions = validate_questions(reporter.complete("questions", QUESTIONS, question_data), facts)
    document = {"schema": VERSION, "kind": "consultation" if "consultation" in kinds else kinds[0],
                "language": language, "transcript_sha256": digest(text), "facts": facts,
                "uncertainties": uncertainties, "questions": questions, "rejected": rejected,
                "validation": "literal medication/dose anchors and automated contextual fact review; entity omission/classification can fail; not clinical validation"}
    report, followup = render(document, language)
    save(output / "document.json", document)
    save(output / "review.json", {"uncertainties": uncertainties, "rejected": rejected})
    save(output / "review.md", render_review(document, language))
    save(output / "report.md", report)
    save(output / "follow-up.md", followup)
    return document


def run(args, key=None, provider_key=None):
    if not args.report_model:
        raise ValueError("choose --report-model or CLINICAL_REPORT_MODEL; see the skill's tested report profile")
    source = args.audio or args.transcript or args.artifact
    input_hash = file_digest(source)
    asr_model = args.asr_model or ("nemotron-speech-multilingual-0-6b" if args.language == "de" else "nemotron-speech-en-0-6b")
    config = {"schema": VERSION, "source_sha256": input_hash, "source_type": "audio" if args.audio else "transcript" if args.transcript else "artifact",
              "language": args.language, "asr_model": asr_model, "report_model": args.report_model,
              "report_provider": args.report_provider, "platform": args.base_url,
              "prompt_sha256": digest([EXTRACT, VERIFY, QUESTIONS, LOCATE]), "chunk_size": 8500}
    output = args.output
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest_path = output / "run.json"
    manifest = read(manifest_path) if manifest_path.exists() else {
        "config": config, "id": "clinical-" + uuid4().hex, "started_at": datetime.now(UTC).isoformat(),
        "source_files": {name: file_digest(Path(__file__).parent / name) for name in ("clinical_report.py", "document.py")}}
    if manifest["config"] != config:
        raise ValueError("output directory belongs to different input/configuration/document version; keep the existing run unchanged and use a new directory")
    save(manifest_path, manifest)
    if manifest.get("status") == "completed":
        return read(output / "document.json")
    platform = Platform(args.base_url, key or credential(), output, manifest["id"], args.timeout)
    reporter = None
    try:
        wanted = [] if args.transcript else [asr_model]
        if not args.report_provider:
            wanted.append(args.report_model)
        platform.require_models(wanted)
        if args.transcript:
            source_text = source.read_text(encoding="utf-8")
            if source.suffix == ".json":
                source_text = json.loads(source_text)["text"]
            text = source_text
        else:
            if asr_model not in {"nemotron-speech-en-0-6b", "nemotron-speech-multilingual-0-6b"}:
                raise ValueError("helper supports the two Nemotron speech Apps; use a transcript from another ASR tool")
            artifact = read(source) if args.artifact else platform.upload(source, asr_model)
            raw = platform.operation("asr", "/v1/models/" + asr_model + ":invoke", {
                "operation": "transcribe", "payload": {"audio": artifact, "options": {
                    "model": asr_model.replace("0-6b", "0.6b"), "language": args.language}}})
            save(output / "transcript.json", raw)
            text = raw["text"]
        if not isinstance(text, str):
            raise TypeError("ASR did not return a text transcript")
        save(output / "transcript.txt", text)
        if not provider_key:
            provider_key = os.getenv("CLINICAL_REPORT_API_KEY")
            if not provider_key and os.getenv("CLINICAL_REPORT_API_KEY_FILE"):
                provider_key = Path(os.environ["CLINICAL_REPORT_API_KEY_FILE"]).read_text().strip()
        reporter = Reporter(platform, args.report_model, args.report_provider, provider_key)
        result = document_transcript(text, args.language, reporter, output)
        manifest.update(status="completed", completed_at=datetime.now(UTC).isoformat(),
                        facts=len(result["facts"]), rejected=len(result["rejected"]),
                        transcript_sha256=digest(text))
        manifest.pop("error", None)
        save(manifest_path, manifest)
        return result
    except Exception as exc:
        manifest.update(status="incomplete", error=type(exc).__name__)
        save(manifest_path, manifest)
        raise
    finally:
        if reporter:
            reporter.close()
        platform.close()


def credential():
    if os.getenv("FS2_API_KEY"):
        return os.environ["FS2_API_KEY"].strip()
    if os.getenv("FS2_API_KEY_FILE"):
        return Path(os.environ["FS2_API_KEY_FILE"]).read_text().strip()
    raise ValueError("set FS2_API_KEY or FS2_API_KEY_FILE to an ordinary platform key")


def parser():
    value = argparse.ArgumentParser(description=__doc__)
    source = value.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio", type=Path)
    source.add_argument("--transcript", type=Path, help="UTF-8 text or ASR JSON containing text")
    source.add_argument("--artifact", type=Path, help="JSON of finalized caller-owned audio artifact")
    value.add_argument("--language", choices=("de", "en"), required=True)
    value.add_argument("--base-url", default=os.getenv("FS2_BASE_URL", "https://89.169.99.188"))
    value.add_argument("--asr-model")
    value.add_argument("--report-model", default=os.getenv("CLINICAL_REPORT_MODEL"), help="Explicit report model; no unqualified small-model default")
    value.add_argument("--report-provider", default=os.getenv("CLINICAL_REPORT_BASE_URL"), help="Explicit external OpenAI-compatible /v1 URL; requires CLINICAL_REPORT_API_KEY or CLINICAL_REPORT_API_KEY_FILE")
    value.add_argument("--output", type=Path, required=True, help="Private per-consultation directory; reuse exactly to resume")
    value.add_argument("--timeout", type=float, default=1800, help="Polling deadline per platform operation, seconds")
    return value


def main():
    args = parser().parse_args()
    try:
        result = run(args)
        print(json.dumps({"status": "completed_draft", "output": str(args.output),
                          "facts": len(result["facts"]), "review_candidates_excluded": len(result["rejected"])}))
    except (httpx.HTTPError, RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
        # Do not expose provider URLs, payloads or a bearer in exception traces.
        detail = str(exc) if isinstance(exc, (ValueError, TypeError, RuntimeError)) else type(exc).__name__
        print(json.dumps({"status": "incomplete", "reason": detail, "output": str(args.output)}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
