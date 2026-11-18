#!/usr/bin/env python3
"""Generate a Wan video dataset; preserve completed clips outside the GPU VM."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
PROVENANCE_FIELDS = {"category", "source_path", "source_line", "source_revision"}
CATEGORIES = {"animal", "architecture", "food", "human", "lifestyle", "plant", "scenery", "vehicles"}
TRANSIENT = {429, 502, 503, 504}


class RecipeError(Exception):
    pass


class ApiError(RecipeError):
    def __init__(self, status: int, detail: str):
        self.status = status
        super().__init__(f"Endpoint returned HTTP {status}: {detail}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the Endpoint token to another URL.


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".part")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecipeError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise RecipeError(f"Expected an object in {path}.")
    return value


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def read_prompts(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not {"id", "prompt", "seed"}.issubset(reader.fieldnames or []):
            raise RecipeError("CSV needs the columns id,prompt,seed.")
        columns = set(reader.fieldnames or [])
        if columns & PROVENANCE_FIELDS and not PROVENANCE_FIELDS <= columns:
            raise RecipeError("Keep all VBench source columns together, or use only id,prompt,seed for your own input.")
        rows, used = [], set()
        for line, row in enumerate(reader, start=2):
            clip_id, prompt = (row.get("id") or "").strip(), (row.get("prompt") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clip_id):
                raise RecipeError(f"CSV line {line}: use a short, filename-safe id.")
            if clip_id in used:
                raise RecipeError(f"CSV line {line}: duplicate id {clip_id!r}.")
            if not prompt or len(prompt) > 3000:
                raise RecipeError(f"CSV line {line}: prompt must contain 1–3000 characters.")
            try:
                seed = int(row["seed"])
            except (TypeError, ValueError) as exc:
                raise RecipeError(f"CSV line {line}: seed must be an integer.") from exc
            if not 0 <= seed < 2**31:
                raise RecipeError(f"CSV line {line}: seed must be between 0 and 2147483647.")
            item = {"id": clip_id, "prompt": prompt, "seed": seed}
            if PROVENANCE_FIELDS <= columns:
                category, relative, revision = row["category"], row["source_path"], row["source_revision"]
                try:
                    source_line = int(row["source_line"])
                except (TypeError, ValueError) as exc:
                    raise RecipeError(f"CSV line {line}: source_line must be an integer.") from exc
                if category not in CATEGORIES or relative != f"prompts/prompts_per_category/{category}.txt" or not re.fullmatch(r"[0-9a-f]{40}", revision) or not 1 <= source_line <= 100:
                    raise RecipeError(f"CSV line {line}: invalid VBench source metadata.")
                if clip_id != f"vbench-{category}-{source_line:04d}":
                    raise RecipeError(f"CSV line {line}: prompt ID differs from its source category/line.")
                item.update(category=category, source_path=relative, source_line=source_line, source_revision=revision)
            rows.append(item)
            if len(rows) > 1000:
                raise RecipeError("Use at most 1,000 prompts in one batch.")
            used.add(clip_id)
    if not rows:
        raise RecipeError("CSV contains no prompts.")
    return rows


def request_fields(row: dict, args: argparse.Namespace) -> dict:
    return {
        "model": args.model, "prompt": row["prompt"], "seed": row["seed"],
        "size": args.size, "num_frames": args.frames, "fps": args.fps,
        "num_inference_steps": args.steps, "guidance_scale": 5.0,
        "flow_shift": 3.0, "boundary_ratio": 0.0,
    }


def fingerprint(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def multipart(fields: dict) -> tuple[bytes, str]:
    boundary = "nebius-" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    body.extend(f"--{boundary}--\r\n".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


class Client:
    def __init__(self, base: str, token: str, request_timeout: int = 60):
        self.base = base.rstrip("/").removesuffix("/v1")
        parsed = urllib.parse.urlsplit(self.base)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise RecipeError("BASE_URL must be the Endpoint URL, without credentials, query or fragment.")
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}):
            raise RecipeError("Use an https Endpoint URL (http is allowed only for local tests).")
        if not token:
            raise RecipeError("ENDPOINT_TOKEN is empty. Use scripts/endpoint.py run, or set it privately in your shell.")
        self.token, self.request_timeout = token, request_timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, path: str, method: str = "GET", body: bytes | None = None,
                content_type: str | None = None, destination: Path | None = None):
        headers = {"Authorization": "Bearer " + self.token}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        # POST is deliberately not retried: a lost reply can still mean a paid request was accepted.
        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                with self.opener.open(req, timeout=self.request_timeout) as response:
                    if destination is None:
                        return json.load(response)
                    size = 0
                    with destination.open("wb") as stream:
                        while chunk := response.read(1024 * 1024):
                            size += len(chunk)
                            if size > 200 * 1024 * 1024:
                                raise RecipeError("Video exceeds the per-clip download limit of 200 MiB.")
                            stream.write(chunk)
                        stream.flush()
                        os.fsync(stream.fileno())
                    return None
            except urllib.error.HTTPError as exc:
                detail = exc.read(1000).decode("utf-8", errors="replace").replace(self.token, "[redacted]")
                if exc.code in TRANSIENT and attempt + 1 < attempts:
                    time.sleep(2 ** attempt)
                    continue
                raise ApiError(exc.code, detail[:500]) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt + 1 < attempts:
                    time.sleep(2 ** attempt)
                    continue
                # Exception text can include URLs; avoid exposing headers or private configuration.
                raise RecipeError("Cannot reach the Endpoint. Progress is saved; check its state and rerun after recovery.") from exc


def wait_ready(client: Client, timeout: int, model: str) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            result = client.request("/v1/models")
            if model not in {item.get("id") for item in result.get("data", [])}:
                raise RecipeError(f"The Endpoint is ready but is not serving {model}.")
            print("Model API is ready.", flush=True)
            return
        except ApiError as exc:
            if exc.status not in TRANSIENT | {404}:
                raise
        except RecipeError as exc:
            if "not serving" in str(exc):
                raise
        if time.monotonic() >= deadline:
            raise RecipeError("Readiness timed out. Check Endpoint logs; stop unused GPU compute.")
        print("Waiting for model download/load…", flush=True)
        time.sleep(min(10, max(0, deadline - time.monotonic())))


def validate_video(path: Path, fields: dict) -> dict:
    if path.stat().st_size < 100 or b"ftyp" not in path.read_bytes()[:64]:
        raise RecipeError(f"{path.name} is not a complete MP4 response.")
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,nb_read_frames,duration", "-of", "json", str(path)],
            check=True, capture_output=True, text=True, timeout=60,
        )
        streams = json.loads(probe.stdout).get("streams", [])
        if not streams:
            raise ValueError("no video stream")
        video = streams[0]
        expected_width, expected_height = (int(x) for x in fields["size"].split("x"))
        if int(video["width"]) != expected_width or int(video["height"]) != expected_height:
            raise ValueError("unexpected output dimensions")
        frames = int(video["nb_read_frames"])
        if frames != fields["num_frames"]:
            raise ValueError(f"decoded {frames}, expected {fields['num_frames']} frames")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-xerror", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
            check=True, capture_output=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.SubprocessError, ValueError, KeyError) as exc:
        raise RecipeError(f"{path.name} failed MP4 decode validation; it is not marked complete. Install ffmpeg/ffprobe and inspect the file.") from exc
    return {"width": expected_width, "height": expected_height, "frames_decoded": frames,
            "duration_seconds": float(video.get("duration", frames / fields["fps"])), "decode_passed": True}


def completed(output: Path, row: dict, fields: dict) -> dict | None:
    meta_path, video_path = output / f"{row['id']}.json", output / f"{row['id']}.mp4"
    if not meta_path.exists():
        return None
    meta = read_json(meta_path)
    if meta.get("input_row", row if not PROVENANCE_FIELDS <= row.keys() else None) != row:
        raise RecipeError(f"{row['id']}: saved source metadata changed. Use a new output directory.")
    if meta.get("fingerprint") != fingerprint(fields):
        raise RecipeError(f"{row['id']}: prompt/model/settings changed. Use a new --output directory.")
    if meta.get("status") != "completed" or not meta.get("validation", {}).get("decode_passed"):
        raise RecipeError(f"{row['id']}: invalid completion record; use a new output directory or inspect this one.")
    if not video_path.exists() or digest(video_path) != meta.get("sha256"):
        raise RecipeError(f"{row['id']}: saved MP4 is missing or changed. Restore it or use a new output directory.")
    return meta


def generate_one(client: Client, row: dict, fields: dict, output: Path, args: argparse.Namespace) -> dict:
    pending_path = output / ".pending" / f"{row['id']}.json"
    pending = read_json(pending_path) if pending_path.exists() else None
    if pending and pending.get("input_row", row) != row:
        raise RecipeError(f"{row['id']}: pending source metadata changed. Use a new output directory.")
    if pending and pending.get("fingerprint") != fingerprint(fields):
        raise RecipeError(f"{row['id']}: pending request has different settings. Use a new output directory.")
    if pending and (pending.get("endpoint") != client.base or not pending.get("video_id")):
        if not args.retry_lost:
            raise RecipeError(f"{row['id']}: submission outcome or Endpoint changed. After checking/stopping the old Endpoint, rerun with --retry-lost to allow a new paid request.")
        pending = None
    if pending:
        try:
            client.request("/v1/videos/" + urllib.parse.quote(pending["video_id"], safe=""))
        except ApiError as exc:
            if exc.status != 404:
                raise
            if not args.retry_lost:
                raise RecipeError(f"{row['id']}: the server no longer has this request, possibly after the GPU being reclaimed. Restart the Endpoint, then rerun with --retry-lost.") from None
            pending = None
    if pending is None:
        if (output / f"{row['id']}.mp4").exists() and not pending_path.exists():
            raise RecipeError(f"{row['id']}: untracked MP4 exists. Move it aside or use a new output directory.")
        pending = {"fingerprint": fingerprint(fields), "input_row": row, "endpoint": client.base, "submitted_at": utc_now()}
        atomic_json(pending_path, pending)  # Record intent before sending the paid POST.
        body, content_type = multipart(fields)
        try:
            response = client.request("/v1/videos", "POST", body, content_type)
        except ApiError as exc:
            if 400 <= exc.status < 500:
                pending_path.unlink(missing_ok=True)  # Server explicitly rejected this request.
            raise
        video_id = response.get("id")
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", video_id):
            raise RecipeError("Submission returned no usable video ID; check the Endpoint before using --retry-lost.")
        pending["video_id"] = video_id
        atomic_json(pending_path, pending)
    video_id = urllib.parse.quote(pending["video_id"], safe="")
    deadline = time.monotonic() + args.generation_timeout
    start = time.monotonic()
    while True:
        response = client.request("/v1/videos/" + video_id)
        status = response.get("status")
        if status == "completed":
            break
        if status in {"failed", "cancelled", "canceled"}:
            raise RecipeError(f"{row['id']}: generation {status}. Inspect logs; use a new output directory for a deliberate retry.")
        if status not in {"queued", "in_progress"}:
            raise RecipeError(f"{row['id']}: unknown server status {status!r}; progress remains saved.")
        if time.monotonic() >= deadline:
            raise RecipeError(f"{row['id']}: generation timed out. Pending ID is saved; rerunning polls the same request.")
        print(f"{row['id']}: {status}", flush=True)
        time.sleep(min(args.poll_interval, max(0, deadline - time.monotonic())))
    part, video_path = output / f"{row['id']}.mp4.part", output / f"{row['id']}.mp4"
    client.request("/v1/videos/" + video_id + "/content", destination=part)
    validation = validate_video(part, fields)
    os.replace(part, video_path)
    meta = {"id": row["id"], "input_row": row, "status": "completed", "fingerprint": fingerprint(fields),
            "request": fields, "video_id": pending["video_id"], "completed_at": utc_now(),
            "client_elapsed_seconds": round(time.monotonic() - start, 3),
            "sha256": digest(video_path), "validation": validation}
    atomic_json(output / f"{row['id']}.json", meta)
    pending_path.unlink(missing_ok=True)
    return meta


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def gallery(output: Path, rows: list[dict], args: argparse.Namespace) -> None:
    logo = ROOT / "docs" / "brand" / "nebius-logo.svg"
    if not logo.exists():
        raise RecipeError("Missing official logo at docs/brand/nebius-logo.svg.")
    (output / "brand").mkdir(exist_ok=True)
    shutil.copyfile(logo, output / "brand" / "nebius-logo.svg")
    if args.input.resolve() != (output / "input.csv").resolve():
        shutil.copyfile(args.input, output / "input.csv")
    provenance = getattr(args, "provenance", None)
    if provenance:
        atomic_json(output / "input.source.json", provenance)
        shutil.copyfile(ROOT / "data/LICENSE", output / "DATA_LICENSE")
        attribution = (ROOT / "data/SOURCE.md").read_text(encoding="utf-8")
        (output / "DATA_SOURCE.md").write_text(attribution.replace("(LICENSE)", "(DATA_LICENSE)").replace("(prompts.source.json)", "(input.source.json)"), encoding="utf-8")
        shutil.copyfile(ROOT / "data/source.json", output / "source.json")
    cards, done, exported = [], [], []
    for row in rows:
        meta_path = output / f"{row['id']}.json"
        if not meta_path.exists():
            continue
        meta = completed(output, row, request_fields(row, args))
        done.append(meta)
        file = urllib.parse.quote(row["id"] + ".mp4")
        category = row.get("category", "Custom prompt")
        title = f"{category.title()} · source line {row['source_line']}" if row.get("category") else row["id"]
        origin = ""
        source_url = ""
        if row.get("source_path"):
            source_url = f"https://github.com/Vchitect/VBench/blob/{row['source_revision']}/{row['source_path']}#L{row['source_line']}"
            origin = f'<a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Original VBench prompt ↗</a>'
        info = meta["validation"]
        cards.append(f'<article><video controls preload="metadata" src="{file}"></video><div><h2>{html.escape(title)}</h2><p>{html.escape(row["prompt"])}</p><a href="{file}" download>Download MP4 ↗</a><small>{info["frames_decoded"]} frames · {info["width"]} × {info["height"]} · seed {row["seed"]}</small>{origin}</div></article>')
        exported.append({"id": row["id"], "category": row.get("category", ""), "prompt": row["prompt"],
                         "seed": row["seed"], "file": row["id"] + ".mp4", "source_url": source_url,
                         "frames": info["frames_decoded"], "duration_seconds": info["duration_seconds"],
                         "sha256": meta["sha256"]})
    with (output / "clips.csv").open("w", newline="", encoding="utf-8") as stream:
        fields = ["id", "category", "prompt", "seed", "file", "source_url", "frames", "duration_seconds", "sha256"]
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(exported)
    summary = {"schema": 2, "model": args.model, "input_rows": len(rows), "completed": len(done),
               "input_sha256": digest(args.input),
               "input_source": {"dataset": provenance["dataset"], "revision": provenance["revision"],
                                "selection_seed": provenance["selection_seed"], "per_category": provenance["per_category"]} if provenance else {"dataset": "custom CSV"},
               "settings": {k: v for k, v in request_fields(rows[0], args).items() if k not in {"prompt", "seed"}},
               "outputs": [{"id": item["id"], "input_row": item.get("input_row"), "sha256": item["sha256"],
                            "validation": item["validation"]} for item in done],
               "note": "A generation batch for inspection. No VBench quality score is calculated."}
    atomic_json(output / "summary.json", summary)
    heading = "Video Dataset from VBench Prompts" if provenance else "Video Dataset from Your Prompts"
    source_note = 'Reproducible VBench prompts with recorded source lines and seeds. This batch does not produce a VBench score.' if provenance else 'Custom input prompts. Completed clips remain available if the GPU stops.'
    (output / "index.html").write_text(f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(heading)}</title><style>
    *{{box-sizing:border-box}}body{{margin:0;background:#f6f5ef;color:#25271f;font:16px/1.6 system-ui,sans-serif}}main{{max-width:1150px;padding:38px 24px;margin:auto}}header{{display:flex;justify-content:space-between;gap:20px;align-items:center;border-bottom:1px solid #d7d8cb;padding-bottom:22px}}header img{{width:145px;height:auto}}.badge{{font-size:13px;border:1px solid #c9ccba;border-radius:20px;padding:6px 13px}}h1{{font-size:clamp(30px,5vw,49px);line-height:1.1;max-width:880px;margin:40px 0 16px}}.intro{{color:#656a5a;max-width:850px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:22px;margin:30px 0}}article{{border:1px solid #d5d6ca;border-radius:16px;overflow:hidden;background:white}}video{{width:100%;aspect-ratio:832/480;display:block;background:#22261e}}article>div{{padding:20px}}h2{{font-size:20px;margin:0 0 8px}}p{{margin:0 0 14px}}small{{display:block;color:#747963;margin-top:14px}}a{{color:#384512;font-weight:600}}footer{{padding:20px 0;border-top:1px solid #d7d8cb;color:#72765f;font-size:13px}}@media(max-width:600px){{header{{align-items:flex-start;flex-direction:column}}}}
    </style><main><header><img src="brand/nebius-logo.svg" alt="Nebius"><span class="badge">Powered by Nebius Serverless AI</span></header><h1>{html.escape(heading)}</h1><p class="intro">{len(done)} of {len(rows)} clips saved. {html.escape(source_note)}</p><p><a href="clips.csv">Clip manifest CSV</a> · <a href="summary.json">Run metadata</a> · <a href="input.csv">Input prompts</a></p><div class="grid">{''.join(cards) or '<p>No completed clips yet. Run the batch to fill your collection.</p>'}</div><footer>Wan2.1-T2V-1.3B · {args.frames} frames at {args.fps} fps, {args.steps} inference steps. Inspect prompt alignment and motion before using generated media.</footer></main></html>''', encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=ROOT / "data/prompts.csv")
    p.add_argument("--output", type=Path, default=ROOT / "results")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--size", default="832x480")
    p.add_argument("--frames", type=int, default=49)
    p.add_argument("--fps", type=int, default=16)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--limit", type=int, help="Generate at most this many new clips; completed clips do not count.")
    p.add_argument("--readiness-timeout", type=int, default=1800)
    p.add_argument("--generation-timeout", type=float, default=900)
    p.add_argument("--poll-interval", type=float, default=5)
    p.add_argument("--request-timeout", type=int, default=60)
    p.add_argument("--retry-lost", action="store_true", help="Allow a new paid request when a pending ID was lost; check the old Endpoint first.")
    p.add_argument("--wait-only", action="store_true")
    p.add_argument("--check-input", action="store_true")
    p.add_argument("--report-only", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if not re.fullmatch(r"[1-9][0-9]{1,3}x[1-9][0-9]{1,3}", args.size):
            raise RecipeError("--size must look like 832x480.")
        if args.frames < 1 or (args.frames - 1) % 4 or args.fps < 1 or args.steps < 1:
            raise RecipeError("Use positive settings and a frame count on the 4n+1 grid (17, 33, …).")
        if args.limit is not None and args.limit < 1:
            raise RecipeError("--limit must be at least 1.")
        if min(args.readiness_timeout, args.generation_timeout, args.request_timeout, args.poll_interval) <= 0:
            raise RecipeError("Timeouts and poll interval must be positive.")
        rows = read_prompts(args.input)
        args.provenance = None
        if args.input.with_suffix(".source.json").is_file():
            if str(ROOT / "src") not in sys.path:
                sys.path.insert(0, str(ROOT / "src"))
            from vbench_data import verify
            args.provenance = verify(args.input)
        elif any(PROVENANCE_FIELDS <= row.keys() for row in rows):
            raise RecipeError("A VBench input requires its matching .source.json sidecar; use scripts/prepare_data.py.")
        if args.check_input:
            print(f"Validated {len(rows)} prompts; model={args.model}; {args.frames} frames at {args.size}.")
            return 0
        args.output.mkdir(parents=True, exist_ok=True)
        if args.report_only:
            gallery(args.output, rows, args)
            print(f"Gallery: {args.output / 'index.html'}")
            return 0
        if not shutil.which("ffprobe") or not shutil.which("ffmpeg"):
            raise RecipeError("Install ffmpeg (includes ffprobe) before requesting paid generation.")
        client = Client(os.environ.get("BASE_URL", ""), os.environ.get("ENDPOINT_TOKEN") or os.environ.get("TOKEN", ""), args.request_timeout)
        wait_ready(client, args.readiness_timeout, args.model)
        if args.wait_only:
            return 0
        generated = skipped = 0
        try:
            for row in rows:
                fields = request_fields(row, args)
                if completed(args.output, row, fields):
                    skipped += 1
                    print(f"{row['id']}: already complete; no generation request sent.", flush=True)
                    continue
                if args.limit is not None and generated >= args.limit:
                    break
                generate_one(client, row, fields, args.output, args)
                generated += 1
                print(f"{row['id']}: saved, hashed and decoded.", flush=True)
        finally:
            gallery(args.output, rows, args)
        print(f"Generated {generated}; reused {skipped}. Open {args.output / 'index.html'}")
        return 0
    except (RecipeError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped locally. Saved clips and pending IDs remain; rerun the same command to continue. Stop your Endpoint when finished.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
