# Qwen3-0.6B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-0.6B%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Qwen3-0.6B is a compact Apache-2.0 chat LLM served OpenAI-compatibly via vLLM on a single L40S.

**License:** [Apache-2.0](https://huggingface.co/Qwen/Qwen3-0.6B/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen3-0.6B)

<!-- /factory:intro -->

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template's 1-click link **enables token authentication** — you generate the token in the create form, and every call must send `Authorization: Bearer <token>`. Set `TOKEN` below; the examples add the header. For a quick public test, set Authentication to None (or drop `auth=true` from the link) and leave `AUTH` empty.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes). Wait until `/v1/models` returns
JSON before calling `/v1/chat/completions`.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console
export TOKEN='<endpoint-auth-token>'   # generated in the create form (or printed once by the CLI)
AUTH=(-H "Authorization: Bearer $TOKEN")   # AUTH=() if the endpoint has no auth

curl -sS "${AUTH[@]}" "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/chat/completions" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Say hello in one short sentence."}],"max_tokens":64,"temperature":0.2}' \
  | tee reply.json
python3 -c 'import json; t=json.load(open("reply.json"))["choices"][0]["message"]["content"]; open("reply.txt","w").write(t); print(f"wrote reply.txt ({len(t)} chars)")'
```

### Python

```python
import json
import os
import time
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")
token = os.environ.get("TOKEN")            # bearer token; leave unset if the endpoint has no auth
auth = {"Authorization": f"Bearer {token}"} if token else {}
out_path = "reply.txt"

# Wait until the API is up (not just Nebius RUNNING)
for _ in range(60):  # up to ~15 min
    try:
        with urllib.request.urlopen(urllib.request.Request(f"{base}/v1/models", headers=auth), timeout=30) as resp:
            if resp.status == 200:
                break
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        pass
    print("waiting for /v1/models…")
    time.sleep(15)
else:
    raise SystemExit("timed out waiting for /v1/models")

body = json.dumps(
    {
        "model": "Qwen/Qwen3-0.6B",
        "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
        "max_tokens": 64,
        "temperature": 0.2,
    }
).encode()
req = urllib.request.Request(
    f"{base}/v1/chat/completions",
    data=body,
    headers={"Content-Type": "application/json", **auth},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    payload = json.load(resp)

text = payload["choices"][0]["message"]["content"]
open(out_path, "w", encoding="utf-8").write(text)
print(f"wrote {out_path} ({len(text)} chars)")
print(text)
```

Token auth is on by default for this template. Keep it on in production; the token is shown once at
creation and cannot be recovered later (recreate the endpoint to rotate it) — see
[How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --image vllm/vllm-openai:v0.19.1 \
  --public \
  --auth token \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-0.6B --host 0.0.0.0 --port 8000'
```

`--auth token` makes Nebius generate a bearer token and print it **once** (`Token: …`) — copy it into
`TOKEN`. Pass `--token <value>` to set your own, or `--token-secret <secret-version-id>` for CI.

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Wrong image or port** — `vllm/vllm-openai:v0.19.1` on container port `8000` (`gpu-l40s-a` / `1gpu-8vcpu-32gb`, preemptible).
