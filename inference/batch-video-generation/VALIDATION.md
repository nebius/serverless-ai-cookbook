# Validation

## Completed 200-clip dataset: 2026-11-18 (UTC)

The run used an earlier version of the recipe (`c4e0940`), before it moved to this repository. The saved Wan dataset reached 200 clips across an interrupted execution and two resumes. The full result checker then passed. [Complete-dataset evidence](docs/resume-results/complete-200.json) · [All 200 clip records](docs/resume-results/clips-200.csv). The earlier [57-clip check](docs/resume-results/summary.json) and [its records](docs/resume-results/clips.csv) remain separate.

| Execution | New saved clips | Reused | Total saved | Result |
| --- | ---: | ---: | ---: | --- |
| Initial execution | 54 | 0 | 54 | Client interrupted; no final summary was printed |
| First resume | 3 | 54 | 57 | `Generated 3; reused 54` |
| Completion resume | 143 | 57 | 200 | `Generated 143; reused 57` |

The original 57 MP4s and completion records retained their hashes. All 200 saved file hashes match their records; the shipped checker verified the input joins and decoded 49 frames from every clip. Its result was:

```json
{
  "completed": 200,
  "dataset": "VBench",
  "frames_per_clip": [
    49
  ],
  "input_sha256": "f38cf4cb4cb1b1deb18955567f17abe289157e2636a808776b275f41648ffbd6",
  "decode_passed": true
}
```

The initial interruption followed confirmed Mac clamshell sleep; no provider preemption was established. The first resume explicitly allowed replacement of the lost unfinished request while preserving the 54 finished clips.

A separate fresh attempt was deliberately stopped after 26 clips to return to the original 54-clip collection and demonstrate recovery. That stop was intentional, with no model or provider failure. Those outputs are excluded from the dataset; their Endpoint time remains included in the cost estimate.

The [sample MP4](docs/media/vbench-scenery-0014.mp4) comes from the completion resume. Its input was VBench scenery line 14, “fireworks display in the sky at night”, seed `24530229`. Its SHA256 `d5c232e7296ae0e1dbd1a21b0affafd74ccaa6bef70c6fe2aa6315617c0aa934` matches the saved record. The article animation shows those same 49 frames at a smaller display size.

## Runtime and measured time

The runtime was `vllm/vllm-omni:v0.24.0` with `Wan-AI/Wan2.1-T2V-1.3B-Diffusers`, one preemptible H100 (`gpu-h100-sxm`, `1gpu-16vcpu-200gb`) and a 500 GiB temporary disk. Generation used 832×480, 49 frames at 16 fps and 20 steps. The pinned input contains 200 distinct VBench prompts, 25 per category. [Source, seeds and license](data/SOURCE.md).

| Measurement | Client wall-clock seconds |
| --- | ---: |
| Initial generation attempt, approximate wall span | 4721.35 |
| First resume: 3 new, 54 reused | 49.83 |
| Completion resume: 143 new, 57 reused | 5141.74 |
| Sum of these generation-command spans | 9912.92 |
| Completion Endpoint restart to Model API ready | 398.34 |
| Full 200-item result checker | 32.23 |

The initial wall span is approximate because its exact command start was not recorded; it uses the preceding readiness-phase finish. It includes the confirmed client-sleep interruption. The completion command also includes an observed client wall-clock gap of roughly 46 minutes; its cause was not confirmed. Both intervals remain in the wall sum. Between-session calendar gaps and repeated startups are outside that sum. It is not an awake, uninterrupted 200-clip benchmark.

The initial command separately recorded 927.73 monotonic seconds. Across the 200 clip records, the monotonic timers sum to 3253.000 seconds and average 16.265 seconds. These timers start after POST submission and cover polling, downloading and decoding; they exclude host suspension, POST overhead, later hashing/record writes and gallery export. They are separate from wall time and GPU busy time.

## Quoted compute and disk costs

The launch quote was USD 2.118611/hour for the initial session and USD 2.418611/hour for the November 18 sessions. The GPU price cap was USD 2.50/hour, with disk charges additional. The rough cost calculation applies each launch quote to its observed create/start-to-STOPPED window:

| Session window | Window seconds | Quote-based estimate, USD |
| --- | ---: | ---: |
| Initial interrupted execution | 5404.83 | 3.18 |
| Separate 26-clip attempt and first resume | 1007.37 | 0.68 |
| Brief start-response recovery | 19.67 | 0.01 |
| Completion and any optional test that ran | 5628.01 | 3.78 |
| Listed-window total | | 7.65 |

These approximations include startup, idle/sleep time, the excluded 26-clip attempt and the listed cleanup windows. They hold each launch quote constant; actual spot-rate history and invoices are unavailable. Windows can include unbilled allocation waiting and polling overhead. One additional brief diagnostic restart has no recorded interval and is not costed. Tax and charges outside quoted compute/disk are excluded. This is a rough validation-session cost, not an invoice or a per-clip price.

## Recovery exercise and cleanup

The separate 20/180 exercise was not run live because the remaining validation window was too short. Its README commands describe a deliberate client limit, not a provider preemption.

The Endpoint was stopped and confirmed STOPPED at 2026-11-18T11:44:57.935846+00:00. The earlier Endpoints were also confirmed STOPPED. Downloaded clips, records and galleries remain on the client’s disk.

## Live stop and resume · November 20, 2026

We ran [revision `0621fe9`](https://github.com/nebius/serverless-ai-cookbook/tree/0621fe97442657d36c340740d1785b74f7f991d5/inference/batch-video-generation) with the README’s coffee and coast prompts on one preemptible H100. Both invocations used `--limit 1` and the same initially empty output folder.

| Invocation | Client output | Endpoint state after download |
| --- | --- | --- |
| Generate the coffee clip | `Generated 1; reused 0` | STOPPED |
| Restart the same Endpoint and resume | `Generated 1; reused 1` | STOPPED |

The first restart request returned an error. We checked that the Endpoint was still stopped and no new start operation had been recorded before retrying. The accepted restart reached RUNNING in 225.62 seconds. The model API was ready another 176.39 seconds later. The client skipped the saved coffee clip and generated the coast clip. Both the coffee MP4 and its completion record kept their original SHA-256 hashes. The result checker decoded both MP4s to 49 frames each at 832×480. A final independent status check confirmed STOPPED. [Timings, checksums and checker output](docs/resume-results/two-clip-restart.json)

We stopped the Endpoint by hand. The live restart to RUNNING took less than five minutes. The 405-second case below tests the longer path.

## Local checks

44 tests passed with `python3 -m unittest discover -s tests`. They cover input provenance, request/download handling, reuse, changed or corrupt results, lost or ambiguous requests, opt-in replacement of retained failed or cancelled IDs, and the Endpoint helper. The terminal-state retry checks use a local fixture. The GPU dataset above predates that fix. The actual CLI 0.12.305 returned a plain operation ID for an asynchronous lifecycle command; the helper now accepts that response and polls the resulting state. This compatibility case is covered by a test.

The launcher tests cover selecting a different GPU platform and preset, retaining the price cap on the dry run and create, and refusing to reuse mismatched hardware. The cloud runs above used an H100 in `eu-north1`. We did not run Wan on another GPU or in another region.

A restart regression test simulates an Endpoint that still reports STOPPED just after the request and reaches RUNNING after 405 seconds. Other tests cover terminal states, an in-progress start and a caller-supplied timeout.

Earlier local API simulations used fixture-video bytes rather than Wan inference:

| Local fixture run | New requests | Reused | Completed |
| --- | ---: | ---: | ---: |
| Full default batch | 200 | 0 | 200 |
| Unchanged rerun | 0 | 200 | 200 |
| Controlled limit | 20 | 0 | 20 |
| Resume from saved files | 180 | 20 | 200 |

These fixture checks are separate from the live dataset evidence above. No VBench quality score is calculated.
