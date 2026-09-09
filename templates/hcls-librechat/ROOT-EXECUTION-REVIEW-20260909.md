# Root execution and GLM acceptance — 2026-09-09

The operator requested unrestricted root execution in the scientific workspace
and additional inference/skill tests through the default GLM 5.3 Flash.

## Implementation

- The application and stdio execution MCP run as UID/GID 0. Bash, Python,
  apt, pip, npm, downloads and arbitrary container/mounted paths are available.
  This is container root, not access to the underlying Serverless host.
- `execute_command` starts real commands; `read_execution` resumes their saved
  job IDs. Output is paged, exit codes are explicit, and commands survive an
  MCP disconnect. Receipts live in `/data/hcls-execution`; a container restart
  interrupts running commands. A timeout of zero allows an unbounded command.
- All model specs and saved tutorial agents include the execution server.
  The landing page and infrastructure guidance describe the actual terminal.
- `/opt/scientific-client/bin/python /opt/bionemo/invoke-native.py` provides
  file-backed native MCP inference. It validates the live schema, keeps large
  data out of chat, retains caller/input/idempotency identity, and saves results.
  An output-directory lock prevents concurrent helper execution. Reusing a
  completed receipt does not submit again; an ambiguous admission refuses retry
  unless a matching accepted operation can be recovered from the saved envelope.
- MCP client dependencies are pinned to mcp 2.2.0, httpx2 2.12.0 and jsonschema
  4.26.0. The helper is for native models, not scientific-batch artifact uploads.
- No bucket was created or mounted. Root commands will see volumes attached to
  the deployed container; the future 1 TB mount still needs actual I/O testing.

## Validation

45 offline checks passed, including actual subprocess execution, failure/timeout
reporting, output paging, reconnects, and native-client receipt recovery without
resubmission. Production client build passed. Final root UI smoke passed all six
starters, provider-key dialogs, preserved chat model, mobile Send and zero compute
requests from card selection.

All browser inference/workflow tests below used `zai-org/GLM-5.3-Flash`.

| Workflow | Observed result |
| --- | --- |
| Root execution | UID 0; wrote and reread `/root/root-smoke/probe.txt`; pip installed humanize 4.16.0; downloaded 12,116 bytes; Python calculated 338350 and saved a verified JSON receipt. Five execution calls, all exit 0. |
| Clinical PhenoAge | PASS. Operation `5e907fbf-8f59-4892-b883-17884f568076`; one synthetic clinical sample; result retrieved through MCP; `phenotypic_age_years=41.90792243377997`. Actual submission tool was generic `invoke_model`, after skill/schema discovery. |
| GenMol | PASS. Named typed tool; operation `6a73a960-17c8-41f7-95a1-e287d4fabce1`; one returned molecule; `score=0.7745095304980193`; final result retrieved through MCP. |
| OpenFold2 | RECOVERY PASS. The first named-tool call returned the bare `Error executing tool infer_openfold2_native` before returning a receipt. Replaying the exact public input under the same idempotency key accepted operation `14d87d2c-fd59-4f26-af2e-cad679a290a2` with `reused=false`, establishing that the first call had not reached durable admission. The operation succeeded with HTTP 200 and `semantic_outcome=protocol_valid`; confidence was `75.11457118988037`, `ptm_score=0.04927242919802666`, and inference time `1.0396960689686239` s. The final cloud agent then retrieved that existing operation without another submission and rendered its real 167-atom PDB in the interactive structure viewer. |
| AltumAge | ASSISTED PASS. GLM invoked the file helper for one 665,948-byte synthetic reference-center fixture with all 20,318 canonical CpGs. Named MCP tool accepted operation `6241fa80-1275-407e-8d8d-5296d275781a`. The helper initially misparsed the flat receipt's `operation` string; after fixing it, the operator resumed that saved operation without a second submission and retrieved the result. GLM subsequently read the saved results with Python and independently checked the same operation through MCP. CUDA result: `predicted_chronological_age_years=38.22121047973633`, `imputed_cpg_count=0`, `feature_count=20318`. |
| Cloud root + infrastructure skills + Tavily | PASS for tool execution/access. GLM installed Debian tree, verified UID 0, wrote/reread `/root/cloud-root-check.json`, loaded nebius-cloud-basics and nebius-serverless-data-secrets, read an attached reference, used Tavily, and wrote/validated a proposed storage-plan JSON. Cloud provisioning and that plan's mount commands were not executed or accepted as validated infrastructure. |

Synthetic predictions establish technical execution, not scientific or clinical
validity. AltumAge fixture provenance is the pinned upstream revision
`696c477dac9b7641bf283c48af1cc9bb0a0803a3`; both preprocessing inputs were checked
against their published SHA256 values. Large inputs/results remain in private
acceptance evidence, outside Git.

## Limitations discovered

- Catalog qualification flags are insufficient: GenMol and OpenFold2 reported
  `route_active: false` but completed successfully. Runtime qualification needs
  operator review. The initial OpenFold2 call also exposed a separate caller-
  visible defect: a pre-admission MCP failure was reduced to a bare tool error
  with no structured error code or correlation receipt.
- GLM incorrectly called PhenoAge's generic submission a named-tool submission
  in its prose, and initially inferred that OpenFold2's missing ID meant no
  operation existed. At that point admission was unknown; the same-key recovery
  later established no prior durable admission. Reports here use actual tool
  receipts. Shared instructions now explicitly require that distinction; this
  is not proof prose cannot err.
- The AltumAge final prose incorrectly attributed the helper error to client
  teardown and suggested reusing a methylation fixture with clinical PhenoAge.
  The actual bug was flat-receipt parsing, and those model inputs are incompatible.
  These claims were excluded from acceptance; live schema validation remains
  necessary before every new run.
- The first two AltumAge turns stopped after announcing execution. A subsequent
  explicit helper command executed. The helper reduces the required client-code
  generation, and instructions now say to finish authorized work with tool calls.
  This was an assisted workflow, not a flawless first-attempt acceptance.
- End-to-end chat times observed: root test 348.74 s; PhenoAge 567.72 s;
  OpenFold2/GenMol 407.00 s; cloud root/skills/research 613.60 s. These include
  model reasoning, tool rounds and reporting. PhenoAge's gateway acceptance-to-
  completion was about 0.705 s; GenMol about 1.329 s. Default GLM workflow latency
  remains an event-readiness concern. No chat-model switch was made.
- A separate 256-output-token Token Factory probe with upstream-style
  `thinking.type=disabled` still returned reasoning tokens and took 25.08 s for
  a trivial function call. It did not establish a suitable latency fix, so the
  production default inference settings were preserved.
- No universal model/skill acceptance, concurrent participant load test,
  cloud-account provisioning test or 1 TB storage-mount acceptance is claimed.

## Evidence and release

Code revisions: `12718ef` (root execution), `cc85e14` (native file helper).
Final image tag: `20260909-cc85e14`.
Image digest: `sha256:9c6ec39287eb52c864c710e60521836b6edef31a01623a02c7c4fb962a5b0c87`.

Private receipts: `/home/tux/fs2-skill-adaptation/root-glm-20260909/`.
OpenFold2 recovery receipts:
`/home/tux/fs2-skill-adaptation/root-glm-20260909/openfold2-run/`.
Local candidate: `scientific-root-candidate`, port 13089.
Root UI release: `scientific-root-release`, port 13090.
Root cloud acceptance endpoint: `aiendpoint-e00cxvmvtm3gaccr30` (12718ef), chat
`dc247b2e-6215-5a8d-a6d2-a22ea375011c`.

Previous user endpoints and their chats remain intact.

Final deployment: `aiendpoint-e00mhcnw5jpbsg95dk`, name
`scientific-root-cc85e14`, CPU D3 / 4 vCPU / 16 GB / 100 GiB.
URL: https://port3080-ryrr5n43y5yz12g.tunnel.applications.eu-north1.nebius.cloud

Final cloud `/health` returns 200 and login succeeds. Authenticated APIs expose
32 skills and all four MCP connections report `connected`: environment-execution,
bionemo-models, Tavily and structure-viewer. The final image's installed native
client imports its pinned dependencies and its CLI help runs successfully.

Final-image GLM cloud execution acceptance also passed in chat
`6bcddfa6-2165-5b7d-bb16-ad1d2575fcb4`: one execute_command ran `id` and the
installed native helper's `--help`, returned UID 0 and exit code 0, with execution
job `ef6285b4-f21e-4bf4-bc07-6659baa269bb`. This checks actual deployed execution
and dependency imports; the help invocation did not submit another inference.

OpenFold2 recovery acceptance passed on the final deployment in chat
`412a9965-ca4b-5bd1-a38f-1dcde84a7bc0`. GLM used `get_operation`,
`get_operation_result`, and `visualize_structure` for the existing operation;
the viewer reported 167 atoms, PDB format, reset/rotation/representation/fullscreen
controls, and the authenticated browser recorded zero console errors. No inference
submission tool was called from that chat.
