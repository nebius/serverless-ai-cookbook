# Qwen3-0.6B

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-0.6B%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500Gi&amp;shmSize=16Gi&amp;preemptible=true"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Qwen3-0.6B is a compact Apache-2.0 chat LLM served OpenAI-compatibly via vLLM on preemptible L40S.

**License:** [Apache-2.0](https://huggingface.co/Qwen/Qwen3-0.6B/blob/main/LICENSE) · **Source:** [Hugging Face](https://huggingface.co/Qwen/Qwen3-0.6B)

<!-- /factory:intro -->

## Test request

After the endpoint is READY, copy its public URL from the console (`BASE_URL`).
This template leaves authentication **off** by default so you can try it quickly.

**First boot:** Nebius can show RUNNING while weights are still downloading.
`GET /v1/models` may return `502 failed to connect to local service` until the
API binds port 8000 (often several minutes). Wait until `/v1/models` returns
JSON before calling `/v1/chat/completions`.

Optional: in the console, add env `HF_TOKEN=<your Hugging Face token>` so the
first Hub pull is authenticated and usually faster (not required).

### curl

```bash
export BASE_URL='https://…'   # Public endpoints URL from the console

curl -sS "$BASE_URL/v1/models"

curl -sS -X POST "$BASE_URL/v1/chat/completions" \
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
out_path = "reply.txt"

# Wait until the API is up (not just Nebius RUNNING)
for _ in range(60):  # up to ~15 min
    try:
        with urllib.request.urlopen(f"{base}/v1/models", timeout=30) as resp:
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
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=120) as resp:
    payload = json.load(resp)

text = payload["choices"][0]["message"]["content"]
open(out_path, "w", encoding="utf-8").write(text)
print(f"wrote {out_path} ({len(text)} chars)")
print(text)
```

For production, enable token auth when creating the endpoint and send
`Authorization: Bearer <token>` — see
[How to call an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-call-an-endpoint).

> ⚠️ When you are done testing, **delete the endpoint** so it stops billing — see
> [How to delete an endpoint](https://docs.nebius.com/serverless/endpoints/manage#how-to-delete-an-endpoint).

<!-- factory:cli -->

## CLI alternative

```bash
nebius ai endpoint create \
  --image vllm/vllm-openai:v0.19.1 \
  --public \
  --platform gpu-l40s-a \
  --preset 1gpu-8vcpu-32gb \
  --preemptible \
  --container-port 8000 \
  --shm-size 16Gi \
  --disk-size 500Gi \
  --container-command bash \
  --args '-c python3 -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-0.6B --host 0.0.0.0 --port 8000'
```

<!-- /factory:cli -->

## Troubleshooting

- **`502 failed to connect to local service`** — tunnel is up but the container has not bound port 8000 yet (weight download / load). Poll `/v1/models` until it returns JSON; do not treat Nebius RUNNING as “API ready”.
- **Very slow first pull** — add optional env `HF_TOKEN` in the console; prefer a larger disk (template asks for 500 Gi) so Hub throughput is higher.
- **Wrong image or port** — `vllm/vllm-openai:v0.19.1` on container port `8000` (`gpu-l40s-a` / `1gpu-8vcpu-32gb`, preemptible).
