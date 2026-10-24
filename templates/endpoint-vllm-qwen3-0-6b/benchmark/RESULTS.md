# Qwen3-0.6B runtime tuning results

**Decision: retain the existing BF16 serving defaults for the tested workload.** None of the three candidate profiles confirmed a >=20% latency or cost-per-valid-request reduction in both confirmation rounds. This is a negative result for these tested profiles, not proof that the defaults are globally optimal.

Measured on 19 October 2026 on one RTX PRO 6000 Blackwell Server Edition (96 GB) per endpoint: `gpu-rtx6000-a` / `1gpu-24vcpu-218gb`, `eu-south1`, 500 GiB network SSD, 16 GiB shared memory, on-demand. Both sides used the same immutable vLLM 0.19.1 AMD64 image and pinned Qwen3 model/tokenizer revision; exact commands and digests are in [results.json](results.json). The full 40,960-token context window remained fixed. Online FP8 is an explicit numerical precision change.

Workload: the documented hello prompt, 64-token limit, temperature 0.2, and thinking disabled, as in the established benchmark workaround. Successful completions had 10 tokens. Three sequential and eight concurrent warmup requests preceded timing. Each C1/C8 phase ran for at least 100 attempts and 60 seconds, without retries. One exploratory round was followed by two confirmation rounds, with alternating profile order.

Across all 36 phases: **65,372 attempts; 65,369 technically valid responses**. Three transport resets occurred in the fresh-connection experiment. GPU utilization, VRAM headroom, 1 Hz coverage and list costs are retained in [results.csv](results.csv).

| Profile | Candidate argument change | Transport used by both sides | Outcome |
|---|---|---|---|
| Interactivity | `--performance-mode interactivity` | Fresh HTTPS per request | No confirmed material gain; one additional candidate transport failure in screening, also transport failures in default confirmation traffic. |
| FlashInfer profile | `--performance-mode interactivity --attention-backend FLASHINFER` | Persistent HTTPS per worker | Worse latency/throughput in confirmation traffic. |
| Online FP8 | `--quantization fp8` | Persistent HTTPS per worker | Small throughput differences; no confirmed 20% latency/cost reduction. |

Only compare default/candidate values **within each profile**. Client transport differs across experiments. Connection reuse reduces client overhead; that difference is not attributed to model configuration. Variants also used different physical GPU/VM identities without crossover; client/network resources and provider caches were uncontrolled.

## Confirmation measurements

Each row is one matched round; round 1 screening remains in the data files. Values are default / candidate.

| Profile / round | C | p50, s | p95, s | Valid req/s | USD/1k valid | Mean completion tokens |
|---|---|---|---|---|---|---|
| interactivity / 2 | c1 | 0.196 / 0.197 | 0.275 / 0.286 | 4.35 / 4.18 | 0.1181 / 0.1228 | 10.0 / 10.0 |
| interactivity / 2 | c8 | 0.214 / 0.216 | 0.285 / 0.289 | 19.43 / 19.26 | 0.0264 / 0.0267 | 10.0 / 10.0 |
| interactivity / 3 | c1 | 0.195 / 0.197 | 0.274 / 0.274 | 4.28 / 4.29 | 0.1200 / 0.1196 | 10.0 / 10.0 |
| interactivity / 3 | c8 | 0.215 / 0.217 | 0.285 / 0.283 | 21.06 / 19.78 | 0.0244 / 0.0260 | 10.0 / 10.0 |
| flashinfer / 2 | c1 | 0.084 / 0.092 | 0.171 / 0.162 | 10.08 / 9.30 | 0.0510 / 0.0552 | 10.0 / 10.0 |
| flashinfer / 2 | c8 | 0.095 / 0.105 | 0.147 / 0.208 | 73.68 / 62.47 | 0.0070 / 0.0082 | 10.0 / 10.0 |
| flashinfer / 3 | c1 | 0.083 / 0.090 | 0.113 / 0.166 | 11.07 / 9.41 | 0.0464 / 0.0546 | 10.0 / 10.0 |
| flashinfer / 3 | c8 | 0.095 / 0.104 | 0.154 / 0.203 | 72.63 / 63.49 | 0.0071 / 0.0081 | 10.0 / 10.0 |
| fp8 / 2 | c1 | 0.087 / 0.086 | 0.173 / 0.173 | 9.80 / 9.96 | 0.0524 / 0.0516 | 10.0 / 10.0 |
| fp8 / 2 | c8 | 0.095 / 0.094 | 0.150 / 0.155 | 73.61 / 74.20 | 0.0070 / 0.0069 | 10.0 / 10.0 |
| fp8 / 3 | c1 | 0.088 / 0.086 | 0.173 / 0.172 | 9.71 / 10.16 | 0.0529 / 0.0505 | 10.0 / 10.0 |
| fp8 / 3 | c8 | 0.095 / 0.092 | 0.151 / 0.158 | 72.47 / 73.27 | 0.0071 / 0.0070 | 10.0 / 10.0 |

## Quality and interpretation

The first two profiles passed 3/3 small semantic checks on both settings. The expanded FP8 comparison scored 11/12 on both: both answered `1` to “What is 1 plus 1? Reply with only the digit.” Exact-response compliance was 8/12 on both. Every baseline-correct and baseline-format-compliant check had to remain correct/compliant in the candidate, and responses had to be technically valid. The shared baseline errors remain reported; perfect accuracy and general quality equivalence are not claimed.

FP8 used the original checkpoint with online weight conversion and dynamic activation quantization. Startup logs selected `CutlassFP8ScaledMMLinearKernel` for `Fp8OnlineLinearMethod`, and actual generations succeeded on the tested image. This establishes support in that binary, not numerical equivalence to BF16.

Adoption required the same ≥20% p95 or cost-per-valid-request reduction in both confirmation rounds at one concurrency, no greater than 5% regression in the other metrics at C1 or C8, no added quality/error failures, and mean output-token counts within 5%. A 20% throughput increase alone gives about 16.7% lower cost at a fixed hourly price.

Costs use a held-constant public USD on-demand rate of $1.848630/hour, including 500 GiB SSD, captured on 16 October 2026. These are measured-phase estimates, not invoices. The experiment does not establish TTFT/TPOT, maximum server capacity, broader workload or quality results, or H100/L40S configuration recommendations.

## Reproduction and evidence

Use the [standalone client](README.md) against fresh default/candidate deployments with the exact configuration, model revision, workload and matched transport in results.json. The portable client follows the measurement contract but differs from the original orchestration harness in SSL-context and connection-cleanup placement; its README explains those differences. All 65,369 saved successful responses had `finish_reason=stop`, so the stricter completion rule preserves the published valid-output denominator.

Independent checks recomputed timings, percentiles, raw response hashes/bytes, actual token usage, GPU statistics/coverage and costs for all 36 phases. Raw per-attempt bodies and telemetry remain in the task archive; original phase-record SHA256 values are in results.csv. Three pre-traffic setup/calibration attempts were excluded and retained separately. All 12 created endpoints, 12 VMs and 12 identified disks freshly returned `NotFound`; task credentials were removed.
