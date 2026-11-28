# Standalone Qwen3 HTTP benchmark

See [measured configurations and results](RESULTS.md) for the 19 October 2026 RTX evaluation.

`bench.py` measures an **already deployed** Qwen3-0.6B endpoint with Python 3 and the standard library. It does not deploy endpoints, alter model/serving configuration, collect GPU telemetry, or clean up cloud resources. It makes no performance-gain claim on its own.

Set `NEBIUS_ENDPOINT_TOKEN` securely in your shell environment or secret manager. There is no token command-line option. Never put bearer credentials in the URL. Only HTTPS URLs without embedded credentials, query strings or fragments are accepted. Certificate and hostname checks remain enabled; `SSL_CERT_FILE` can select a trusted CA file. The macOS native `/etc/ssl/cert.pem` is used when available, otherwise Python’s normal trust configuration applies.

Example, with `$ENDPOINT_URL` pointing to your existing endpoint:

```bash
python3 bench.py --base-url "$ENDPOINT_URL" --concurrency 1 \
  --duration 60 --min-requests 100 --max-requests 10000 \
  --transport persistent --out results-default-c1

python3 bench.py --base-url "$ENDPOINT_URL" --concurrency 8 \
  --duration 60 --min-requests 100 --max-requests 10000 \
  --transport persistent --out results-default-c8
```

Use a fresh or empty output directory for every phase. Duration must be at least 60 seconds and minimum request count at least 100. Workers continue until both minimums are satisfied, unless the maximum count is reached. Reaching the cap before the duration target, or a worker failure, produces an unsuccessful process exit and explicit evidence fields. Inspect failure/validation counts even after a normal exit: successful script execution alone does not mean every endpoint request passed.

## Fixed request and measurement

The POST payload is exactly:

```json
{
  "model": "Qwen/Qwen3-0.6B",
  "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
  "max_tokens": 64,
  "temperature": 0.2,
  "chat_template_kwargs": {"enable_thinking": false}
}
```

Closed-loop concurrency is either 1 or 8. In the default `persistent` mode, each worker authenticates a GET `/v1/models` before timing its first generation and then reuses that verified HTTPS connection. GET preflight and connection establishment are excluded from individual generation timers, but included in phase wall time. A broken connection is discarded; only a later, separately counted request reconnects. No generation is retried, even if server execution became uncertain after a connection failure. A preflight failure also consumes a counted client attempt; `generation_transmission_attempts` distinguishes attempts that reached POST transmission.

`--transport fresh` opens a new HTTPS connection for each POST, with no preliminary GET. Its generation timer includes connection/TLS establishment. **Use the same transport for both serving profiles.** Comparing a persistent client to historical fresh-connection results is a transport comparison, not evidence of model-serving improvement.

POST timing covers transmission through complete response-body receipt. Hashing, response parsing and chat validation happen outside that timer. Phase wall time includes normal worker setup, preflight, hashing, recording, disk spooling and connection cleanup; deferred validation duration is separate. There is no untimed generation warmup in this compact tool. Warm both profiles comparably before collecting warmed-serving evidence, and disclose your warmup procedure.

Nearest-rank p50/p95 cover complete HTTP 200 responses. Technical validation runs after traffic and requires nonempty final chat content, no unfinished reasoning block, and `finish_reason="stop"`. Length-limited responses remain HTTP successes but fail technical validation. This is not a semantic or general quality assessment.

Completion-token statistics use API-reported `usage.completion_tokens`, with coverage recorded against technically valid responses. Mean, median, p95, observed total and observed tokens per phase second are reported. At incomplete coverage these are observed subsets, not inferred complete totals. The short stochastic prompt may finish at different token counts despite identical `max_tokens`; compare actual token distributions before calling a latency/request-throughput change a serving speedup. No TTFT or TPOT is measured.

## Outputs and optional cost

- `summary.json`: payload, transport, actual counts, successful HTTP percentiles, validated goodput, errors, duration/cap status, token coverage and optional cost estimates.
- `requests.jsonl`: every recorded client attempt, UTC/epoch/monotonic timing, status, response hash/bytes, transmission/preflight flags and deferred validation results.
- `responses/<sha256>.json`: one raw body per distinct response, including HTTP failures. These files may contain invalid JSON. Repeated bodies still count as separate requests.

The target URL and authorization headers are not written to artifacts. Transport errors retain exception types, not potentially sensitive messages. A response containing the literal endpoint token is suppressed from disk and cannot pass deferred validation; its digest/byte count and suppression flag remain. Other response content is retained, so handle the artifact directory as endpoint output data.

`--hourly-cost 1.23` optionally supplies your timestamped public USD on-demand list rate for all resources you intend to price. Keep the source, effective date, included resources and region in accompanying notes. The client multiplies that rate by phase wall time and reports USD per 1,000 technically valid requests; API token cost is available only at complete usage coverage. These estimates are not invoices and exclude startup/idle outside the measured phase, taxes, discounts and account billing adjustments. Missing prices or zero denominators remain unavailable.

## Fair profile comparisons

Use a fresh matched default control and candidate with the same model/tokenizer revision, context limit, GPU resource configuration, payload, client host/network and transport. Record exact image digests, dtype/quantization, serving arguments, GPU/driver identity, resource allocation and warmup. Identify the intentional candidate change explicitly (including any precision change), and hold other settings fixed. Alternate profile order and repeat paired measurements. Different physical GPUs/VMs, clocks, client/network load and provider cache behavior remain confounders unless independently controlled.

Keep screening separate from confirmation. For the ticket’s 20% latency-or-cost criterion, a 20% goodput increase alone is only about 16.7% lower cost per request at a fixed hourly rate. Require repeated actual latency or cost improvements, comparable output lengths and no meaningful error/quality regression. Model quality checks and deployment cleanup belong to the wider experiment, outside this client.

## Optional companion GPU observations

GPU metrics are **not captured by this script**. If authorized to access the existing GPU VM, start a verified read-only 1 Hz capture before the client phase, then stop it after the phase:

```bash
nvidia-smi --query-gpu=timestamp,index,uuid,name,driver_version,utilization.gpu,memory.used,memory.total \
  --format=csv,noheader,nounits -l 1 > gpu-observations.csv
```

Verify that rows arrive about once per second, record VM clock/timezone and GPU identity, and align observations to the client’s UTC phase interval. Check sample coverage and buffering before calculating mean/p95 utilization, peak used memory or minimum free memory. Do not infer GPU metrics from client latency. If telemetry is unavailable, disclose that limitation instead of substituting estimated values.

Offline tests:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile bench.py
```

Artifact references are relative to the output directory, so the retained subset can be moved together. No third-party Python packages or outside source helpers are required.

### Comparability with the recorded experiment harness

Use this exact client version for both sides of a new A/B comparison. It follows the experiment's workload and HTTP timing contract, but is a portable reproduction client rather than a byte-for-byte copy of the original orchestration harness. Its shared SSL context is built before a phase; the original fresh-connection harness built a context for each request inside phase wall time. This client's connection cleanup is included in phase wall time; the original persistent wrapper closed its connections afterward. These differences can affect throughput and cost denominators. Do not attribute differences between client versions or transports to model configuration.

This client also requires `finish_reason="stop"` for technical validity. The original recorder accepted nonempty final chat content. Before combining recorded results with this client's stricter valid-output counts, recheck the saved responses under the same rule; any discrepancy must be reported, not silently reclassified.
