# Admin Apps readback after release 182

2026-09-19, approximately 05:10–05:15 UTC. This is bounded operator-journey
evidence, not a sustained-load, latency-SLO, whole-cluster or model-quality claim.

## Original faults remain retained

Two release-179 `GET /admin/api/v1/apps` requests failed with HTTP500 at
04:38:11 UTC after 31.53/31.64 seconds. Both reached the PostgreSQL Apps usage
projection and timed out; they failed before any App-log query. No request IDs
were retained by the original caller. A separate bounded pre-fix read returned
35 Apps, HTTP200, in 5.576 seconds: the problem was intermittent, not every read.

Repair `61f98ae00` gives list/detail summaries their exact count/lifetime query
instead of computing every full usage report. Full usage now selects the latest
lifecycle rollup only for matching operations. Tenant/App scoping, time-window
counts, unknown measurements and lifetime last-used semantics are retained.
There is no timeout, pool, index, schema, quota or resource increase.

Read-only, same-snapshot SQL comparison retained all 35 counts/lifetime values;
the representative full usage result was JSON-equal and took 0.165 seconds
versus 0.889 seconds. This isolated query result is not an HTTP latency promise.

Release 180 also exposed a separate snapshot-status failure. Strict server-side
apply converted an emptied selector map to null and the unchanged CRD rejected
it. Source `8e747def5` omits that optional empty wire field without changing
qualification, nonempty evidence, runtime/spec or write fences. Correctly formed
live **dry-run-only** requests reproduced HTTP422 → HTTP200 on both affected
Apps. Release 180's atomic failure/181 rollback are not rewritten as successes.

## Exact installed release

- Release 182, source `8e747def5f31b82014d9daeba97d4711b960adca`.
- Image index
  `sha256:f3a3d6c2d4e28b6f8693e6cc65c6d9b63ecd4e54e8e13d170059f4e85d0a60f6`.
- Three Ready gateways matched the expected image and installed source hashes
  for Apps service/repository, status projection and worker-error compatibility.
- The release owner ran the full selected backend suite: 2,760 passed,
  5 skipped, 130 deselected. The status repair's focused suite passed 135 tests;
  Ruff and source mypy passed. These remain distinct from the live checks below.

| Readback | Observed result |
| --- | --- |
| Two external 35-App list reads | Both HTTP200; 5.123s and 2.859s. All historical-window counts equal the retained pre-fix response. |
| External Cosmos, Qwen and ESMFold2-Fast detail/usage pairs | Six HTTP200; 0.322–1.495s. List/detail/usage logical counts agree: 5, 0 and 34 respectively. |
| Two exact-pod handler reads per gateway | Six HTTP200 across three gateways; 1.533–5.395s. Same 35 counts. Authenticated localhost reads are explicitly **not ingress** tests. |
| Installed worker-error parser | Current exact-alignment and legacy static detail accepted; each with appended arbitrary text rejected. Static strings only, no failing inference. |
| Actual admin browser | Apps table rendered 35 rows; ESMFold2-Fast detail and Usage opened. All 32 captured admin GETs returned200; no console errors/warnings. |

The real browser initially used its ordinary 15-second refresh, then switched to
a fixed range. The UI window was 04:12:54–05:12:54; the independent historical
API comparison used 03:41:36–04:41:36. They must not be conflated. UI Usage showed
24 logical runs for its window and retained “Not observed” measurements;
successful run counts do not establish scientific correctness. Screenshots,
DOM snapshots and network status evidence are retained. The isolated browser
session was closed; no settings, keys or model policies were changed.

One initial localhost probe helper attempted JSON decoding before retaining the
HTTP status of a non-JSON response. Its traceback is preserved. It is **not**
claimed as an application500 or silently included in passing counts. A separate
corrected explicit Host/proto probe produced the six retained per-gateway reads.

Multi-second list latency remains visible. No new 500 was observed in this
bounded post-release window; this does not prove absence under future load.

## Portable evidence references

Paths are relative to the protected campaign evidence root; raw logs, operator
cookies and tenant records are not published here.

| Receipt | SHA256 |
| --- | --- |
| `apps-projection-500-20260919/incident.json` | `156d9d9c69a79bcf68475c73ff6a4343659335fdaa7ebf8203e1a25cb82eb7da` |
| `apps-projection-500-20260919/query-comparison.json` | `f6beb237baa272897b10e7f120daa16b904daabb2282584ad2f4542319cdd97d` |
| `snapshot-status-422-20260919/http-dry-run.json` | `195d5c31ffaca7c39107af07174925bea11af154c4432135f754680751a6eb80` |
| `apps-projection-500-20260919/release182/verification.json` | `f936a5b9ae3c4dfa0f2c09b004964d12d47c4d98865410be5c66c5398c3912a8` |

The final receipt binds individual responses, installed source hashes, three
gateway manifests, screenshots and browser network/DOM snapshots. Original
failed requests and the probe limitation remain part of that evidence chain.
