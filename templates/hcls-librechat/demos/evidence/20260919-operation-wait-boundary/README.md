# Operation observation deadline and retained robotics recovery

As of 19 September 2026, 04:36 UTC. This is source qualification and a retained
negative customer journey, not acceptance of a newly deployed client.

## Exact customer evidence

Scientist10's existing v39/DeepSeek-V4-Pro-0813 conversation
`ab2e9c75-e5c2-52d6-b506-9baae154e0fe` received one authorized ordinary third
recovery turn. The first two turns and their zero admissions remain unchanged.
No technical hints, provider switch, budget changes or fourth prompt were used.
The third turn ran04:19:43.608–04:26:29.181 UTC (405.573s,28 tool calls).
Provider finish_reason was `stop` at04:26:29.003,3,579B content; provider usage
fields were empty. Local context estimates are not actual billed usage.

The agent chose whole-sequence edge transfer, not prefix-conditioned video
continuation. Native operation `227a8c45-9f29-448f-b544-37ff60fb769b` succeeded
04:23:16.839 after103.073s accepted-to-completed. LeRobot parent
`9fb534d6-3659-496b-a1a2-733b50485989` succeeded04:26:32.970 after187.912s,
3.789s after the final response. Its honest interim status is not a capacity
failure. Both delegated GPU children succeeded, without further user prompts.

This is still **incomplete customer delivery**:

- An initial parallel CLI plan hit the unchanged per-key concurrency policy
  (HTTP429); the agent recovered with existing receipts. Its claim of independent
  model lanes was wrong. No concurrency increase was made.
- Two status tools returned the generic interrupted error after30.392/30.427s.
- The4,357B partial report was downloaded through the actual workspace browser
  and API, SHA256`8be870692194b762b1ea36e93acbf1d1ba09818a7e50b1a71b79ef351f82b679`.
  Chat supplied raw file paths rather than clickable download links.
- Required `provenance-v39.json` exists but is **zero bytes** after an ad hoc
  NumPy float32 JSON export failed. The installed deterministic export helper
  was not used. This is not merely a cosmetic error.
- The report's float32 RGB accumulation over19.7M pixels materially changes
  the means. Independent float64 accumulation on the exact same FFmpeg RGB24
  frames measures ΔRGB`[+2.1638,-0.3117,-0.00423]`, not the reported
  `[+1.9,-1.4,-1.6]`. Its stronger blue-decrease/weighted-luma-decrease claims
  are unsupported. The original report remains unmodified; no new numerical
  implementation was added to the product to hide this natural-analysis error.
- The agent did not recover/verify the completed LeRobot bundle or finish its
  temporal comparison. No clean customer-completion or physical-alignment pass.

Independent **operator-only, read-only** recovery subsequently verified the
2,471,339B LeRobot bundle SHA256
`a77e9bbd1841e9233f3e6b7c5b29e818b353ca90391407c24d8569a258fa8b49`:
128 rows/6,144 nonvideo values exact,2×64-frame episodes,256 decoded camera
frames,640×480/25FPS, exact episode intervals and untouched wrist MP4 bytes/
pixels. Per-episode wrist stats are exact; aggregate std differs3.49e-9.
This verifies returned data integrity, **not agent delivery**, visual-action
alignment, policy fitness, or the scientific meaning of the lighting change.

### Actual snapshot witness, added after retained-log correlation

Persisted App Logs contain `serving_snapshot_runtime` with mechanism
`cuda-criu-restored` at04:22:19.287462 for Pod`…-8kgz7` and04:24:34.730482
for Pod`…-kcppj`. Direct per-Pod log reads independently contain the same
events. Actual public operation runtime attribution joins them as follows:

| Request | Actual Pod UID | Restore witness |
| --- | --- | --- |
| Native`227a8c45…` | `f9a6bf15-9c7f-4366-9887-e295cc211a2c` |04:22:19.287462 |
| LeRobot child`96febf31…` | `a335b826-434c-471f-a1e5-fcb3b2c4cd01` |04:24:34.730482 |
| LeRobot child`d5bcbede…` | same`a335b826…` | same Pod startup event |

Both Pods used node`c36d3b47-6536-4feb-aa5e-1b18bcdd4ccf` and the **same**
physical `GPU-b9790cfd-34f8-8c04-faea-56b5cedc79d7` (preemptible). This proves
two distinct restored Pods were used over time, not two GPUs or simultaneous
two-Pod service. Restore is a Pod startup event: the later child's log run-ID
association does not mean a second restore occurred for that request.
The LeRobot children reused their restored Pod. None of this repairs the
incomplete or numerically incorrect customer report.

Protected immutable-input join receipt:
`Q/robotics-natural179/joined-runtime-evidence.json`, derived read-only from
the retained public Runs response and three persisted App Logs responses.

Later complete startup-log captures also expose named subprocess timings:
native CRIU restore19.644418s, CUDA restore for PID3025.560960s and
PID1740.037010s; child Pod CRIU19.905719s, CUDA PID3025.502026s and
PID1740.034569s. Every listed command returned0. These are individual process
restore components, not full cold start, accepted-to-ready, image pull,
queue delay, or GPU occupancy. Source logs remain intact at
`Q/robotics-natural179/{native,children}-full-startup-logs.json`.

## Deadline diagnosis

Both failed tools supplied `wait_seconds:30`:

| Call ID | Operation | Retained elapsed |
| --- | --- | ---: |
| `call_6910b50129cb4ed793c4d4b5` | `227a8c45…` |30.392s |
| `call_6922425ca4fc4eafb94e256e` | `9fb534d6…` |30.427s |

The scientific-demos MCP transport allows60s; this is not the separate30s
execution-tool transport. The old wait loop slept to its deadline and used
`Date.now() <= deadline` to admit another GET. At exact equality it assigned
that GET a1ms timeout, then replaced earlier valid observations with a generic
503. A deterministic execution of the exact old function with healthy40ms
GETs produces ten valid observations followed by the1ms request at30,000ms.
Three real-clock1s probes did not hit the equality race, which is retained
rather than described as an always-reproducible failure.

Two separate public terminal reads at04:33:10/11 returned HTTP200 in0.889/0.787s.
Their headers contain operation IDs but no request-ID header. Original tool
errors also omitted request IDs. These later checks establish current normal
status latency, not proof that no independent transport problem existed in the
original window. The deadline defect is independently established in source.

## Bounded source repair — release pending

The loop now checks its deadline **before** another GET. If a later GET reaches
the same observation deadline, it returns the last valid status with
`wait_expired:true` and `last_observed_at`; it neither fabricates completion nor
resubmits inference. A first-read failure still fails because no state is known.
HTTP401/403/404/500, connection failures and cancellation remain errors;
cancelled terminal operations remain terminal. Only an internally identified
timeout at the elapsed observation deadline can retain the earlier status.

Eleven new deterministic tests plus18 existing service tests pass. Existing
30s wait/60s MCP/45s ordinary-read limits are unchanged. v39's two failures
remain live-history evidence; the fix requires a future immutable client
deployment and bounded acceptance, not an in-container overlay.

Protected reproducible evidence under
`Q=/home/tux/secure-handoff/scientific-qualification-20260918`:

- `browser-evidence/scientist-10-v39-third-turn-final` and`-final-files`
- `browser-evidence/scientist-10-v39-third-turn-independent`
- `browser-evidence/operation-wait-diagnosis`
- `browser-evidence/{reproduce-operation-wait.cjs,measure-operation-reads.py,
  verify-natural-lerobot.py,verify-native-v39.py}`

No credentials or signed artifact URLs are included in this portable note.
