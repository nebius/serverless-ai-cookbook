# Scientific AI workbench and clinical workflows inside LibreChat

Source for the existing Scientific AI workbench, not another workshop website.
The authenticated `/demos` route provides Apps, Runs, Workspace, Clinical Report
and MindEval. The model selector includes the main scientific agent and two
saved agents under **Clinical demos**.

## Runs and waiting for capacity

Runs reads the caller-scoped `/v1/operations` history automatically, including
model calls submitted through chat or the API. Older pages use the backend's
cursor. Each row shows submission time, elapsed time, time before execution,
reported activation time, status, attempts and returned error details. An
activation measurement does not establish that a GPU snapshot was restored.
Incomplete runs have status/details and cancellation controls; only successful
runs offer result retrieval. Refresh and browser reconnect never resubmit work.

On an older backend without the history route, Runs clearly states that only
explicitly saved operations are available. Saved labels and explicit tracking
use atomic files per operation and platform key; simultaneous MCP/UI writes
cannot erase other operations. Admission errors retain whether work was
accepted, whether retry is possible, its retry delay and any existing operation
ID, so the client can distinguish waiting from an unknown submission outcome.

## Isolated scientist qualification clients

`deploy-scientist-workbenches.py` uses the existing deployment template to give
each test scientist an endpoint, login, assigned platform key and bucket mount.
This matches the dedicated root-execution topology of the Rene installation.
Scientists may share a lab bucket deliberately, while different labs use
different buckets. Ten logins on a single deployment with a shared model key
do not qualify independent principal attribution.

The helper consumes a private manifest outside Git. Top-level fields are
`project_id`, `subnet_id`, `token_factory_secret_selector`,
`tavily_secret_selector` and `scientists`. Each scientist requires `id`, `email`,
`password`, `api_key`, `tenant_id`, `principal_id`, `bucket_name`,
`s3_access_key_id` and `s3_secret_access_key`. Pass `--image`, `--manifest`,
`--output` and `--execute`; `--only scientist-01,scientist-02` starts a subset.
Protected receipts and browser session state remain in the output directory.
An interrupted cloud creation is reconciled before retrying, never silently
duplicated. Setup verifies login and assigned bucket; it is not scientific
acceptance evidence. The campaign manager owns lifecycle and cleanup.

## Connections and identity

- User enters their ordinary Scientific AI key in the demo panel or the
  `scientific-demos` MCP settings. It is encrypted using LibreChat's existing
  plugin credential store. Saving in the panel reconnects that MCP server.
- The platform key, not an admin key, is forwarded to the existing workshop
  APIs. Their tenant/principal identity controls runs and inference permissions.
- The operator supplies `NEBIUS_API_KEY` for global Token Factory. It is never
  a tool argument or browser configuration value. No regional routing is added.
- Workshop patient: Qwen3-30B-A3B-Instruct-2507; pilot judge: Gemma-3-27B.
  The backend advertises contract-qualified clinicians from the full public
  shortlist. Private Sword MindGuard v2 is not selectable until its separate
  approved event artifact arrives. Never use Sword's paid production endpoint.
- Existing root execution and shared scientific-model credentials are retained
  for legacy agents. These new per-user routes do **not** make the old shared
  root environment an isolated multi-tenant sandbox. Use public/synthetic
  demonstration recordings; real patient-data hosting needs a separate decision.

## Clinical reports

Upload a transcript (`txt` or ASR `json`) or an English/German recording in the
panel. Audio bytes do not enter LLM arguments. Files are spooled to disk, with a
512 MiB transport limit. The exact supported audio formats appear in the UI.
This limit is not a clinical-duration qualification or disk storage quota.

The packaged `clinical-documentation` helper is copied from the solutions
library's `k8s-inference/integrations/librechat/skills/clinical-documentation`.
Keep helper changes synchronized with that source; do not develop competing
report implementations. Its report profile uses Qwen-235B and the existing
Nemotron English/multilingual speech Apps. A completed job contains the original
transcript, `report.md`, `review.md`, `follow-up.md`, structured facts and receipts.

Jobs live in `/data/hcls-demos/<user-hash>/<request-hash>` and survive closing
the browser. Repeating an unchanged idempotency key returns the same job; using
it with different data is rejected. Same-key clinical jobs queue using an OS
file lock. Interrupted/incomplete jobs can resume their cached stages with
the original platform key. A timeout receives one automatic retry; explicit
busy responses receive bounded backoff. Lost provider responses may incur
usage twice; this is **not** a provider exactly-once billing guarantee.

The chat agent can submit transcript text, poll jobs and read saved outputs.
Audio and large-file uploads use the panel; an ordinary chat attachment is not
automatically transferred to this workflow yet. Do not pretend otherwise.

Every document is a **draft requiring clinician review**, not a validated
medical record. The automatic source checker can withhold a correct fact or
miss an incorrect one. The review queue is part of the deliverable, not optional
hidden diagnostics. Prompt experiments during integration improved one German
symptom but worsened an unclear English medication name; those changes were
reverted, with negative evidence retained. No clinical accuracy claim is made.

## MindEval

Select up to twenty profiles and the desired clinicians, then run ten rounds.
The backend remains responsible for durable queueing, role-relative prompts,
hidden patient details, fixed judge and team worker limits (at most five;
an existing key with a lower limit stays lower). Browser controls directly call
pause/nudge/takeover/say/resume/abort; they do not depend on the chat model deciding
to issue the command. A run ID in the URL restores selection after refresh.

Paired means include only profiles completed, without intervention, by every
clinician in the selected batch and under one judge. Incomplete, failed,
intervened and missing rows stay visible. JSON exports carry the transcript and
configuration; per-run reports additionally contain backend events. The latest
200 runs are visible; an incomplete batch is explicitly labelled.

**Open recorded example** loads a real historical six-clinician/one-profile
rehearsal without inference. It is explicitly labelled as recorded, including
export filenames and JSON metadata. It is a fallback for practicing score
interpretation, not evidence that the current endpoint or a full cohort works.
Source: solutions-library gateway evidence `20260916-final-frozen-r10`, first
batch `a30236f5-0809-492a-8caf-a731a3030a35`. Only public synthetic transcripts
and scores are packaged; no user credentials or hidden-profile data.

## Validation and deployment status (17 September 2026)

Isolated Docker candidates were exercised locally against real Scientific AI
speech Apps and global Token Factory. Production has **not** been changed.

- r2: synthetic DE transcript and full 421.86s DE / 457.92s EN recordings
  completed; original workflow times including queue were 18.881s / 86.415s /
  129.168s. These are workflow times on the warm platform, **not cold starts**.
  Replays are separately marked and do not masquerade as fast inference.
- r3: saved MindEval agent called its typed catalog tool; native UI pause,
  nudge, takeover, human turn and resume worked; CSV download succeeded.
  A report provider timeout remained incomplete and same-job browser resume
  subsequently completed. Missing MCP tool bindings and lost selected-run URL
  were found and fixed rather than treated as successful acceptance.
- Unit tests cover idempotency, identity, queue serialization, bounded timeout
  recovery, MCP schemas and paired comparisons. The existing 34 cookbook
  regression tests pass. Frozen source `03d70b8` passed full EN/DE recording
  workflows, native browser upload, typed clinical-agent output retrieval,
  create/refresh/abort, and a local data-preserving upgrade test. See
  `evidence/20260917-frozen-03d70b8/README.md` for exact coverage and limitations.
- Expanded global model qualification passed 40/40 ten-round conversations with
  judging (20 each for Nemotron Super and GLM-5.2); one truncated patient
  response required the bounded identical-payload retry. Final eight-clinician
  public customer-path and ten-team acceptance of the integrated client remain
  separate release gates.
  Historical backend ten-team evidence is not claimed as new-client acceptance.

Run offline tests with `node --test demos/service.test.cjs` and
`TYPESCRIPT_MODULE=<typescript-package> node --test demos/comparison.test.cjs`
from this template's directory. Existing Python tests are in `tests.py` and
`test_*.py`. `demos/acceptance.py` exercises an isolated authenticated candidate;
`--audio` uses the documented public teaching assets. `--evidence` persists
receipts. `validate_documentation.py` is a diagnostic fidelity challenge, not a
green release gate; r4/r5 experimental results failed and were not promoted.

The installed Serverless endpoint CLI has no in-place image update. The owner
has been asked to choose a data-preserving replacement URL or a coordinated
same-URL cutover. Do not delete the old endpoint or assume an empty replacement
is an acceptable migration. Preserve MongoDB (`/data/db`), runtime encryption
keys (`/data/hcls-librechat`), uploads (`/app/uploads`), workspace (`/workspace`)
and new report data (`/data/hcls-demos`). Take a consistent Mongo backup and
restore-test it before switching users; copying live database files is not
a backup procedure. Existing endpoint SSH has no authorized key configured.

Old endpoint: `aiendpoint-e00mhcnw5jpbsg95dk`, project
`project-e00z6b02t8ddk96c49`, URL
`https://port3080-ryrr5n43y5yz12g.tunnel.applications.eu-north1.nebius.cloud`.
Previous image digest:
`sha256:9c6ec39287eb52c864c710e60521836b6edef31a01623a02c7c4fb962a5b0c87`.
Retain it as rollback until final acceptance and explicit cleanup.
