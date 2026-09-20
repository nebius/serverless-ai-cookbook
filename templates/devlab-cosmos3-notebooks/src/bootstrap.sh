#!/usr/bin/env bash
# Cosmos 3 notebooks DevLab bootstrap. Runs as the container command inside
# quay.io/jupyter/minimal-notebook: prepares the persistent workspace, then starts JupyterLab.
#
# Env (set on the DevLab):
#   JUPYTER_TOKEN            required — 16 alphanumeric chars, the JupyterLab sign-in token
#   COSMOS3_REASONER_URL     https FQDN of a Cosmos 3 Reasoner endpoint (optional)
#   COSMOS3_REASONER_TOKEN   its bearer token (optional)
#   COSMOS3_GENERATOR_URL    https FQDN of a Cosmos 3 Generator endpoint (optional)
#   COSMOS3_GENERATOR_TOKEN  its bearer token (optional)
#   COSMOS_REF               nvidia/cosmos git ref to clone (default main)
set -euo pipefail
WORK=/home/jovyan/work; mkdir -p "$WORK"; cd "$WORK"
log() { echo "$(date +%H:%M:%S) [cosmos3-devlab] $*"; }

log "installing notebook dependencies"
python -m pip install --disable-pip-version-check --no-cache-dir -q "openai>=1.50" requests pillow ipywidgets >/dev/null

if [ ! -d "$WORK/cosmos/.git" ]; then
  log "cloning nvidia/cosmos (${COSMOS_REF:-main}) into $WORK/cosmos"
  git clone -q --depth 1 --branch "${COSMOS_REF:-main}" https://github.com/nvidia/cosmos.git "$WORK/cosmos"
else
  log "nvidia/cosmos already present — keeping your copy"
fi

# Persist the endpoint settings so notebooks can read them even after a restart with changed env
python - <<'PY'
import json, os, pathlib
cfg = {k: os.environ.get(k, "") for k in ("COSMOS3_REASONER_URL", "COSMOS3_REASONER_TOKEN", "COSMOS3_GENERATOR_URL", "COSMOS3_GENERATOR_TOKEN")}
pathlib.Path("/home/jovyan/work/nebius_endpoints.json").write_text(json.dumps(cfg, indent=2))
PY

# Nebius copy of NVIDIA's Reasoner notebook: same cells, but the OpenAI client points at the endpoint
python - <<'PY'
import json, pathlib, re
src = pathlib.Path("/home/jovyan/work/cosmos/cookbooks/cosmos3/reasoner/run_with_vllm.ipynb")
dst = pathlib.Path("/home/jovyan/work/cosmos/cookbooks/cosmos3/reasoner/run_with_vllm_nebius.ipynb")
if src.exists() and not dst.exists():
    nb = json.loads(src.read_text())
    setup = ("import json, os\n"
             "_cfg = json.load(open('/home/jovyan/work/nebius_endpoints.json'))\n"
             "REASONER_BASE = (os.environ.get('COSMOS3_REASONER_URL') or _cfg['COSMOS3_REASONER_URL']).rstrip('/') + '/v1'\n"
             "REASONER_KEY = os.environ.get('COSMOS3_REASONER_TOKEN') or _cfg['COSMOS3_REASONER_TOKEN'] or 'EMPTY'\n"
             "print('Reasoner endpoint:', REASONER_BASE)\n")
    nb["cells"].insert(0, {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": setup})
    n = 0
    for c in nb["cells"]:
        if c["cell_type"] != "code": continue
        s = "".join(c["source"])
        s2 = re.sub(r'base_url\s*=\s*["\']http://localhost:\d+/v1["\']', "base_url=REASONER_BASE", s)
        s2 = re.sub(r'api_key\s*=\s*["\']EMPTY["\']', "api_key=REASONER_KEY", s2)
        if s2 != s: n += 1; c["source"] = s2
    dst.write_text(json.dumps(nb, indent=1))
    print(f"[cosmos3-devlab] wrote {dst.name} ({n} cells re-pointed at the Nebius endpoint)")
PY

# Quickstart notebook: connectivity check, one Reasoner call, one Generator call
python - <<'PY'
import json, pathlib
dst = pathlib.Path("/home/jovyan/work/00_cosmos3_on_nebius.ipynb")
if not dst.exists():
    md = lambda s: {"cell_type": "markdown", "metadata": {}, "source": s}
    code = lambda s: {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s}
    cells = [
        md("# Cosmos 3 on Nebius — start here\n\nThis DevLab has NVIDIA's [Cosmos cookbooks](cosmos/cookbooks/cosmos3/) cloned into `cosmos/` and talks to your Cosmos 3 **endpoints** instead of a local server. Endpoint URLs and tokens come from the DevLab's environment (`nebius_endpoints.json` keeps a copy)."),
        code("import base64, json, os, time, requests\nfrom IPython.display import Image, Video, display\ncfg = json.load(open('nebius_endpoints.json'))\nR = (os.environ.get('COSMOS3_REASONER_URL') or cfg['COSMOS3_REASONER_URL']).rstrip('/')\nG = (os.environ.get('COSMOS3_GENERATOR_URL') or cfg['COSMOS3_GENERATOR_URL']).rstrip('/')\nRH = {'Authorization': f\"Bearer {os.environ.get('COSMOS3_REASONER_TOKEN') or cfg['COSMOS3_REASONER_TOKEN']}\"}\nGH = {'Authorization': f\"Bearer {os.environ.get('COSMOS3_GENERATOR_TOKEN') or cfg['COSMOS3_GENERATOR_TOKEN']}\"}\nfor name, base, h in (('Reasoner', R, RH), ('Generator', G, GH)):\n    if base:\n        r = requests.get(f'{base}/v1/models', headers=h, timeout=20); print(name, r.status_code, [m['id'] for m in r.json().get('data', [])] if r.ok else r.text[:200])\n    else:\n        print(name, 'not configured')"),
        md("## Reasoner: caption an image\nNVIDIA's sample asset, straight from GitHub. Sampling values follow the Cosmos 3 prompt guide."),
        code("ASSETS = 'https://raw.githubusercontent.com/nvidia/cosmos/main/cookbooks/cosmos3/reasoner/assets'\nbody = {'model': 'nvidia/Cosmos3-Nano', 'max_tokens': 256, 'seed': 0, 'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'presence_penalty': 1.5,\n        'messages': [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': f'{ASSETS}/robot_153.jpg'}}, {'type': 'text', 'text': 'Caption the image in one paragraph.'}]}]}\nr = requests.post(f'{R}/v1/chat/completions', headers=RH, json=body, timeout=120); r.raise_for_status()\ndisplay(Image(url=f'{ASSETS}/robot_153.jpg', width=480)); print(r.json()['choices'][0]['message']['content'])"),
        md("## Generator: text-to-image, then an async video job\nVideo takes minutes, so the Generator's `/v1/videos` job API is used (submit, poll, download)."),
        code("if G:\n    r = requests.post(f'{G}/v1/images/generations', headers=GH, json={'model': 'nvidia/Cosmos3-Nano', 'prompt': 'A warehouse robot folds a blue cloth on a clean workbench.', 'size': '1024x1024', 'n': 1, 'response_format': 'b64_json', 'num_inference_steps': 50, 'guidance_scale': 7.0, 'seed': 0}, timeout=300); r.raise_for_status()\n    display(Image(data=base64.b64decode(r.json()['data'][0]['b64_json']), width=512))\nelse:\n    print('Generator endpoint not configured')"),
        code("if G:\n    job = requests.post(f'{G}/v1/videos', headers=GH, data={'model': 'nvidia/Cosmos3-Nano', 'prompt': 'A small warehouse robot moves a blue box across a clean floor.', 'size': '1280x720', 'num_frames': 81, 'fps': 24, 'num_inference_steps': 35, 'guidance_scale': 6.0, 'flow_shift': 10.0, 'seed': 42,\n                        'extra_params': '{\"use_resolution_template\":false,\"use_duration_template\":false,\"guardrails\":false}'}, timeout=60).json()\n    while (s := requests.get(f\"{G}/v1/videos/{job['id']}\", headers=GH, timeout=30).json())['status'] not in ('completed', 'failed'):\n        print(s['status'], end=' '); time.sleep(10)\n    open('cosmos3_t2v.mp4', 'wb').write(requests.get(f\"{G}/v1/videos/{job['id']}/content\", headers=GH, timeout=180).content)\n    display(Video('cosmos3_t2v.mp4', embed=True, width=640))"),
        md("## Next\n- `cosmos/cookbooks/cosmos3/reasoner/run_with_vllm_nebius.ipynb` — NVIDIA's full Reasoner tour, re-pointed at your endpoint (captioning, temporal localization, grounding, embodied reasoning…).\n- `cosmos/cookbooks/cosmos3/generator/` — the Generator notebooks; replace `http://localhost:8000` with your Generator URL and add the bearer header.\n- Endpoints are billed while running — delete them when you are done."),
    ]
    nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}, "nbformat": 4, "nbformat_minor": 5}
    dst.write_text(json.dumps(nb, indent=1)); print("[cosmos3-devlab] wrote 00_cosmos3_on_nebius.ipynb")
PY

# Self-test at start so the DevLab log shows whether the Reasoner endpoint is reachable
if [ -n "${COSMOS3_REASONER_URL:-}" ]; then
  python - <<'PY' || log "reasoner self-test failed (endpoint not ready?) — JupyterLab starts anyway"
import os, requests
base = os.environ["COSMOS3_REASONER_URL"].rstrip("/"); h = {"Authorization": f"Bearer {os.environ.get('COSMOS3_REASONER_TOKEN','')}"}
r = requests.get(f"{base}/v1/models", headers=h, timeout=20); r.raise_for_status()
print(f"[cosmos3-devlab] reasoner self-test OK: {[m['id'] for m in r.json()['data']]}")
PY
fi

log "starting JupyterLab on :8888 (root_dir=$WORK)"
exec start-notebook.py --ServerApp.token="$JUPYTER_TOKEN" --ServerApp.root_dir="$WORK"
