#!/usr/bin/env python3
"""Batch synthetic-video generation with Cosmos 3 through a local vLLM-Omni server.

Reads a JSONL prompt list, submits clips to the async /v1/videos API (image-to-video when a
line has an "image", text-to-video otherwise), keeps a few jobs in flight, downloads each MP4
into OUTPUT_DIR/<RUN_ID>/ with a JSON sidecar per clip, and writes manifest.jsonl once at the
end. Clips whose MP4 already exists are skipped, so a preempted job resumes where it stopped.
Files are written in one go: mounted buckets are object storage (mountpoint-s3) and reject appends.

Configuration is by environment variables (see README):
  PROMPTS      path or URL of the prompts.jsonl              (default: bundled sample set)
  OUTPUT_DIR   where clips land, normally a mounted bucket   (default: /data/output)
  RUN_ID       sub-folder name                               (default: run-YYYYmmdd-HHMMSS)
  SHARD        "i/N" to render every N-th clip starting at i (default: 0/1)
  NUM_FRAMES / SIZE / FPS / STEPS / GUIDANCE / FLOW_SHIFT / NEGATIVE_PROMPT / GENERATE_SOUND
  CONCURRENCY  jobs kept queued on the server               (default: 2)
  MODEL        served model id                              (default: nvidia/Cosmos3-Nano)
  SERVER       vLLM-Omni base URL                            (default: http://127.0.0.1:8000)
"""
import hashlib
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SERVER = os.environ.get("SERVER", "http://127.0.0.1:8000").rstrip("/")
MODEL = os.environ.get("MODEL", "nvidia/Cosmos3-Nano")
PROMPTS = os.environ.get("PROMPTS", str(Path(__file__).with_name("prompts.jsonl")))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/data/output"))
RUN_ID = os.environ.get("RUN_ID") or time.strftime("run-%Y%m%d-%H%M%S")
SHARD_I, SHARD_N = (int(x) for x in os.environ.get("SHARD", "0/1").split("/"))
CONCURRENCY = int(os.environ.get("CONCURRENCY", "2"))
DEFAULTS = {
    "num_frames": int(os.environ.get("NUM_FRAMES", "189")),
    "size": os.environ.get("SIZE", "1280x720"),
    "fps": int(os.environ.get("FPS", "24")),
    "num_inference_steps": int(os.environ.get("STEPS", "35")),
    "guidance_scale": float(os.environ.get("GUIDANCE", "6.0")),
    "flow_shift": float(os.environ.get("FLOW_SHIFT", "10.0")),
    "negative_prompt": os.environ.get("NEGATIVE_PROMPT", "blurry, distorted, low quality, jittery, deformed"),
    "generate_sound": os.environ.get("GENERATE_SOUND", "false").lower() == "true",
}
EXTRA_PARAMS = {"use_resolution_template": False, "use_duration_template": False, "guardrails": False}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def fetch(url_or_path, timeout=120):
    if url_or_path.startswith(("http://", "https://")):
        with urllib.request.urlopen(url_or_path, timeout=timeout) as r:
            return r.read()
    return Path(url_or_path).read_bytes()


def api(method, path, data=None, headers=None, timeout=120):
    req = urllib.request.Request(SERVER + path, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def multipart(fields, files):
    boundary = "----cosmos3-" + uuid.uuid4().hex
    body = bytearray()
    for name, value in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
    for name, (filename, content, ctype) in files.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n".encode()
        body += content + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return bytes(body), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def wait_for_server():
    log(f"waiting for {SERVER}/v1/models …")
    for _ in range(240):  # 40 min
        try:
            api("GET", "/v1/models", timeout=10)
            log("server ready")
            return
        except Exception:
            time.sleep(10)
    sys.exit("vLLM-Omni server did not become ready in 40 minutes")


def load_clips():
    raw = fetch(PROMPTS).decode()
    clips = []
    for n, line in enumerate(l for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")):
        c = json.loads(line)
        c.setdefault("id", f"{n:03d}")
        c.setdefault("seed", n)
        clips.append(c)
    mine = [c for i, c in enumerate(clips) if i % SHARD_N == SHARD_I]
    log(f"{len(clips)} clips in {PROMPTS}; shard {SHARD_I}/{SHARD_N} renders {len(mine)}")
    return mine


def submit(clip):
    p = {**DEFAULTS, **{k: v for k, v in clip.items() if k in DEFAULTS}}
    fields = {
        "model": MODEL, "prompt": clip["prompt"], "negative_prompt": p["negative_prompt"],
        "size": p["size"], "num_frames": p["num_frames"], "fps": p["fps"],
        "num_inference_steps": p["num_inference_steps"], "guidance_scale": p["guidance_scale"],
        "max_sequence_length": 4096, "flow_shift": p["flow_shift"], "seed": clip["seed"],
        "extra_params": json.dumps(EXTRA_PARAMS),
    }
    if p["generate_sound"]:
        fields["generate_sound"] = "true"
        fields["sound_duration"] = f"{(p['num_frames'] / p['fps']):.3f}"
    files = {}
    if clip.get("image"):
        img = fetch(clip["image"])
        ctype = mimetypes.guess_type(clip["image"])[0] or "image/jpeg"
        files["input_reference"] = (Path(clip["image"]).name, img, ctype)
    body, headers = multipart(fields, files)
    headers["Accept"] = "application/json"
    resp = json.loads(api("POST", "/v1/videos", data=body, headers=headers))
    return resp["id"], p


def status(job_id):
    return json.loads(api("GET", f"/v1/videos/{job_id}", timeout=30))


def write_once(path, text):
    """Bucket mounts reject appends; keep earlier runs' files by writing a timestamped sibling if it exists."""
    if path.exists():
        path = path.with_name(f"{path.stem}-{time.strftime('%Y%m%d-%H%M%S')}{path.suffix}")
    path.write_text(text)
    return path


def main():
    out = OUTPUT_DIR / RUN_ID
    out.mkdir(parents=True, exist_ok=True)
    wait_for_server()
    clips = load_clips()
    todo = [c for c in clips if not (out / f"{c['id']}.mp4").exists()]
    if len(todo) < len(clips):
        log(f"resuming: {len(clips) - len(todo)} clips already rendered in {out}")
    inflight, done, failed = {}, 0, []
    t_start = time.time()
    while todo or inflight:
        while todo and len(inflight) < CONCURRENCY:
            clip = todo.pop(0)
            try:
                job_id, params = submit(clip)
                inflight[job_id] = (clip, params, time.time())
                log(f"submitted {clip['id']} ({'i2v' if clip.get('image') else 't2v'}, {params['num_frames']}f {params['size']}) → {job_id}")
            except urllib.error.HTTPError as e:
                failed.append((clip["id"], f"submit HTTP {e.code}: {e.read().decode()[:200]}"))
                log(f"FAILED to submit {clip['id']}: {failed[-1][1]}")
        time.sleep(5)
        for job_id in list(inflight):
            clip, params, t0 = inflight[job_id]
            try:
                s = status(job_id)
            except Exception as e:  # server hiccup — keep polling
                log(f"poll error for {clip['id']}: {e}")
                continue
            if s["status"] == "completed":
                mp4 = api("GET", f"/v1/videos/{job_id}/content", timeout=300)
                path = out / f"{clip['id']}.mp4"
                path.write_bytes(mp4)
                rec = {"id": clip["id"], "file": path.name, "bytes": len(mp4), "sha256": hashlib.sha256(mp4).hexdigest(),
                       "prompt": clip["prompt"], "image": clip.get("image"), "seed": clip["seed"],
                       **{k: params[k] for k in ("num_frames", "size", "fps", "num_inference_steps", "guidance_scale", "flow_shift", "generate_sound")},
                       "model": MODEL, "render_seconds": round(time.time() - t0, 1)}
                (out / f"{clip['id']}.json").write_text(json.dumps(rec, indent=1))   # sidecar, write-once
                done += 1
                log(f"clip {done}/{len(clips)} {clip['id']} {params['num_frames']}f {params['size']} {rec['render_seconds']}s → {path}")
                del inflight[job_id]
            elif s["status"] == "failed":
                failed.append((clip["id"], str(s.get("error"))[:300]))
                log(f"FAILED {clip['id']}: {failed[-1][1]}")
                del inflight[job_id]
    elapsed = time.time() - t_start
    records = [json.loads(p.read_text()) for p in sorted(out.glob("*.json")) if p.stem not in ("summary",) and not p.stem.startswith("summary-") and not p.stem.startswith("manifest")]
    if records:
        mpath = write_once(out / "manifest.jsonl", "".join(json.dumps(r) + "\n" for r in records))
        log(f"manifest: {len(records)} clips → {mpath}")
    summary = {"run_id": RUN_ID, "rendered_this_run": done, "total_clips_on_disk": len(records), "failed": failed,
               "elapsed_seconds": round(elapsed), "output": str(out), "model": MODEL, "defaults": DEFAULTS}
    write_once(out / "summary.json", json.dumps(summary, indent=2))
    log(f"done: {done} rendered this run, {len(records)} total, {len(failed)} failed, {elapsed/60:.1f} min → {out}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
