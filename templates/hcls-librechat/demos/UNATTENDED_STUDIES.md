# Durable whole studies

This extends the existing `run_scientific_workflow` tool and native/batch clients;
it is not another agent product. The deployment remains one LibreChat instance
per user. Different users may intentionally share a tenant bucket.

## Deployment and ownership

The ordinary `scripts/deploy.sh` requires `SCIENTIFIC_STUDY_OWNER_MODE`:

- `first-instance`: operator has confirmed no active study supervisor for this
  user. Historical v45-and-earlier clients have no such supervisor.
- `stopped-predecessor`: save the previous endpoint configuration/chat evidence,
  stop that exact previous user instance, verify it is stopped, then enable its
  successor with the same user, platform, key and mounted bucket.

The qualification deployment helper inherits this environment variable. Do not
use rolling overlap for the same user. The worker's local `flock` is not a
distributed S3 lease. No endpoint ID enters the stable owner namespace. The
bucket contains user-hashed state and key fingerprints, never configured key
values. Rotating a key does not authorize silently continuing its predecessor's
work. No multiuser shared-instance or multi-replica guarantee is made.

Without the explicit deployment preflight the API still starts, but the study
supervisor is disabled and v2 submission explains the missing configuration.
Runs reports worker availability rather than describing an absent worker as
GPU capacity waiting.

## Existing tool, typed complete plan

Call `run_scientific_workflow_mcp_environment-execution` with `output_directory`
and inline `study` OR `plan_file` pointing to existing `scientific-workflow/v2`
JSON. Both use the same durable submitter. The executable typed schema is
`scientific_study_schema.py`, not an opaque command string. A plan has a title,
ordered steps, and final deliverables. File values are existing mounted paths
or `{ "step": "earlier-id", "file": "published-name" }`. The plan, original
input hashes, helper hashes, selected models, parameters and request keys are
frozen before admission. A changed plan cannot take over an existing output.

`describe_scientific_workflow_mcp_environment-execution` is read-only and
returns a compact list by default. Select only required `methods` for their
exact launcher schemas and guaranteed versus conditional output filenames.
It includes a small versioned file-plan example, not a fixture-specific plan.
For longer plans, `compose_scientific_workflow_mcp_environment-execution` accepts
small groups of the **same** typed steps and deliverables, avoiding a generated
shell program just to serialize JSON. Create with `draft_directory`, `title`,
and initial steps/deliverables. Edit with the returned `current_sha256` as
`expected_sha256`. Existing IDs/names replace in place; new ones append in the
supplied order. Explicit removals are supported; the composer never reorders
scientific dependencies. Several related steps can share one call.

`finalize: true` can accompany the last group. It invokes the existing complete
study validator and returns `finalized`, `validation_error`, and the immutable
`plan_file`/SHA256. Partial or invalid plans remain drafts and submit no inference.
Only then call the existing launcher with `plan_file` and `output_directory`;
admission revalidates and freezes current input/helper bytes as before. Reading
with only `draft_directory` recovers its current receipt. Exact repeated edits
return their retained revision without rolling back later edits. Stale edits
fail without changing the draft. Plan revisions use the existing closed-file
verified publisher and journal, not a second workflow engine or distributed lock.

Python stages still reference an existing saved script, not inline source.
Write unsupported-science source in bounded logical pieces; never put an entire
program plus plan into one argument. This changes no tool/provider budget or
runtime policy. Only v1 plan files retain legacy native/batch-only behavior.

Supported phases reuse installed implementations:

| Kind/method | Existing implementation |
|---|---|
| preparation/write-json | UTF-8 JSON; earlier-file references resolve to verified paths |
| preparation/parquet-export | Numeric Arrow/Parquet → NPZ, HDF5, ZIP/CSV, closed SQLite; independently reopen/compare every field |
| preparation/proteinmpnn-input | Explicit returned backbone/index/chain → actual ProteinMPNN input JSON, preserving declared seed/temperature/count |
| preparation/esmfold2-fast-input | Exact original ProteinMPNN input + selected generated FASTA row → refolding source JSON and parameters; no implicit sequence choice |
| preparation/design-refold-correspondence | Exact original design/query/returned chain → full hash-bound query-position residue map for the existing structure evaluator |
| preparation or analysis/python-script | Saved hash-frozen scientific Python source and declared files → private scratch outputs, verified publication and retained source/provenance; unchanged 120-second phase budget |
| native | `invoke-native.py` with unchanged model/input/idempotency identity |
| batch | `invoke-scientific-batch.py` with published input contract and verified artifact transport |
| clinical | Existing bounded clinical runner, explicit model at the existing Token Factory provider, audio/artifact/transcript input |
| analysis/structure, docking, docking-batch, aging | Existing deterministic domain helpers |
| analysis/clinical-study | Existing clinical study assembler; source selection and optional WER remain separate |
| analysis/report | Existing deterministic report assembler and typed measured-domain sections |
| analysis/mindeval | Full frozen record paths → existing score renderer, row-level CSVs, exact records/transcripts and source-bound final report; no provider/catalog calls |

`clinical` is a draft-generation stage, not a diagnosis or clinical validation.
Its original extraction/review/question budgets and algorithm stay unchanged.
Complete provider responses are checkpointed and reused. A request without a
saved response is ambiguous; no automatic duplicate paid call is made. Audio
upload uses the same existing idempotent byte uploader. The configured clinical
credential stays in memory/environment, not in the plan or checkpoint.

Example CPU-only whole study:

```json
{
  "schema": "scientific-workflow/v2",
  "title": "Lossless recorded-data exports",
  "steps": [{
    "id": "export", "kind": "preparation", "method": "parquet-export",
    "arguments": {"source": "/workspace/study/input.parquet", "formats": ["npz", "hdf5", "zip", "sqlite"]}
  }],
  "deliverables": [
    {"name": "Report", "role": "report", "source": {"step": "export", "file": "report.md"}},
    {"name": "Measured comparisons", "role": "metrics", "source": {"step": "export", "file": "comparison.json"}},
    {"name": "NPZ", "role": "data", "source": {"step": "export", "file": "data.npz"}},
    {"name": "HDF5", "role": "data", "source": {"step": "export", "file": "data.h5"}},
    {"name": "ZIP", "role": "data", "source": {"step": "export", "file": "data.zip"}},
    {"name": "SQLite", "role": "data", "source": {"step": "export", "file": "data.sqlite"}}
  ]
}
```

Arrow supports primitive/fixed-size-list numeric and boolean fields here. Nulls,
variable-length/non-numeric columns, nonfinite values and nonportable field names
need an explicit policy and fail usefully, never silently disappear. SQLite is
a closed standalone export, not live SQLite/WAL or shared POSIX storage. All
seekable writers use private scratch; only closed/readback-verified files publish.

For an actual dependent protein-design study, declare the RFdiffusion model
phase, `proteinmpnn-input` with its `output-manifest.json` (the existing batch
client's verified sibling artifacts), a PDB file or inline-coordinate JSON
result, then native ProteinMPNN using that phase's `input.json`. Manifest PDB
selection is checked again against the exact published byte count and SHA256;
there is no additional download transport or guessed artifact ID.
Follow with `esmfold2-fast-input` referencing both this original `input.json` and
the actual ProteinMPNN `result.json`, with explicit zero-based `design_index`
and seed. Its `input.json` and `parameters.json` feed the existing ESMFold2-Fast
batch phase. Then use `design-refold-correspondence` with `design_input`,
`design_result`, `refold_input`, `refold_parameters`, `prediction` and explicit
zero-based `design_index`, `structure_index`, and `prediction_chain`. The
prediction can be an inline result, coordinate file, or the existing batch
output manifest and verified sibling artifacts (PDB or mmCIF). It validates the
exact selected designed sequence against the saved query and every returned
C-alpha position. Its `reference.pdb`, `prediction-result.json` and
`residue-map.json` feed the existing `structure` phase using `reference`,
`result`, `residue_map` and optional explicit reference:prediction `chain_map`.
Without chain_map, exact pairs are derived only from that hash-bound map; an
explicit contradictory mapping is rejected. Both structure hashes and every
mapped position still pass the existing evaluator. For a future returned
single-chain output, explicitly choose `{selection:"sole-protein-chain"}` for
the preparation's chain/prediction_chain; it records the observed ID and fails
on zero/multiple chains. No chain letter is guessed before inference.
Original confidence data remains separate from reference agreement. This is
not a sequence-identity-only fit or an arbitrary observed-output tolerance.
Declare the final structural analysis/report separately. Input
FASTA rows are excluded from generated-design indexes; indexes are not seeds.
These single-chain adapters require complete N/CA/C/O coordinates and explicit
chain selection. Numbering gaps, insertions, noncanonical residues, mismatched
source sequences and ambiguous multi-chain splitting stop with a useful error,
not inferred scientific policy. Every preparation saves its measured source
hashes, selection and original sampling settings in `provenance.json`.

### Other scientific analysis, without another model turn

Prefer the installed deterministic helpers above. For other scientific work,
save source before launch and declare `method: "python-script"` with:

```json
{
  "script": "/workspace/study/analyze.py",
  "inputs": [{"name": "model_result", "file": {"step": "model", "file": "result.json"}}],
  "parameters": {"reference_prefix": "ACGT"},
  "outputs": ["metrics.json", "report.md"]
}
```

The script accepts `--inputs FILE --output-dir DIRECTORY`. The bindings file is
JSON with `schema: scientific-python-bindings/v1`, `inputs` mapping names to
resolved verified file paths, and the exact `parameters` object. Read original
data from those inputs; write and close every declared output under the private
seekable output directory. It is the installed scientific Python interpreter
(NumPy, Biopython, RDKit, Arrow/Pandas, HDF5), not a new shell or model client.
Hosted inference belongs in explicit native/batch/clinical phases, not this
analysis stage. Source code must already exist at study submission; source and
existing input hashes are frozen then. Earlier-step inputs are resolved and
verified only after their dependencies finish. External input files needed by
the script must be declared rather than discovered from mutable ambient state.

The unchanged 120-second per-phase subprocess budget applies. Every declared
file must be nonempty before publication; missing, changed, or incomplete output
fails visibly. The exact `script.py`, `input-bindings.json` and
`script-provenance.json` publish with the outputs. Declared files may be nested
relative paths; create their subdirectories in scratch. The existing immutable
generation publisher and receipt determine completion. Restart does not rerun
a committed script phase; an interrupted uncommitted local computation can
rerun against the same frozen inputs in a new private scratch directory. This
is not a guarantee of scientific correctness or a mechanism for external side
effects. Do not rely on an arbitrary analysis script to submit paid work.

## Lifecycle and recovery

The application supervisor runs the existing Node API and one receipt worker.
The worker serializes whole studies and dependent model phases, including
uploads. Existing server policy still controls other work and admission. An
explicit no-admission 429 waits using the existing bounded policy; an unknown
admission stops the queue for inspection instead of inventing another request.

`queued → preparation → native/batch/clinical → analysis → publication → completed`

One phase observation returns control to the worker. No additional LLM turns,
tool rounds, model limits or completion-token budgets are introduced. Generic
shell jobs and v1 model-only workflows retain their old process-bound behavior;
only v2 declares and supervises the complete study.

State is in `/workspace/.scientific-studies/<user-hash>/<study-id>` and each
study's chosen output directory. Existing immutable receipt journals survive
interrupted canonical writes. On process restart, already-completed phases and
accepted operation IDs are recovered. A saved batch acceptance is reusable only
when its model, operation, protocol and idempotency key exactly match. No new
admission is made to reconstruct a missing response.

Local phase outputs and the final manifest use immutable publication generations
so a killed FUSE copy does not force overwriting an earlier partial object.
Clinical mutable working files use private seekable scratch restored from a
hash-verified checkpoint. Child phase processes die with their worker; an orphan
cannot keep issuing provider calls while a replacement worker resumes.

Cancellation preserves completed work, cancels the known active operation, and
does not start later phases. Unknown provider/backend admissions cannot be
truthfully confirmed cancelled and remain an explicit attention/queue hold.
A cancellation whose POST response is lost is read back once by its known
operation ID. A terminal status resolves it; a still-active operation becomes
`cancellation_unknown`/attention and holds the queue, rather than polling forever
or silently repeating a POST. This does not increase any retry allowance.
Final publication requires nonempty declared reports and verifies every output.
The manifest records inputs, helper hashes, operation identities and file hashes;
it explicitly makes no scientific-validity claim.

Runs → Whole studies lists phase progress, failure/attention, cancellation and
authenticated Workspace download links. `read_execution` accepts the same study
job ID after reconnect. A pending response is an honest accepted-work update,
not an instruction to send a mechanical “continue”.

## Acceptance gate (root owns live deployment)

1. Build an exact commit; verify pinned preparation dependencies and helpers in
   the image. Enable one task-owned user supervisor after stop-first preflight.
2. Freeze an uncoached public-data natural task requiring model work plus
   deterministic analysis/report. Capture its complete typed plan and original
   request identities. Close the browser after acceptance.
3. Reconnect under the same ordinary user and observe Runs without relaunching.
   Restart that exact task-owned instance at a saved accepted-operation boundary;
   confirm the same IDs/request keys continue and no dependent call overlaps.
4. Wait for final manifest, download every declared deliverable through the UI,
   and independently verify bytes and scientific quantities. No manual continue
   to run declared analysis is a clean-pass requirement.
5. Separately qualify audio/full-transcript clinical drafts with the unchanged
   bounded runner, review/source evidence and honest coverage limits. Cached
   completed responses must not be re-billed on recovery; ambiguous responses
   must stop visibly, not be silently regenerated.
6. Preserve failures, cancellation, wrong-plan/key/mutated-file negatives and
   any operator intervention. Offline tests or an accepted model operation do
   not establish natural-client completion or production readiness.

Offline evidence includes a real worker SIGKILL/restart, exact accepted-response
recovery, isolated shared-bucket user namespaces, partial publication recovery,
clinical checkpoint/provider ambiguity, and all-four-format actual recorded
ALOHA exports (128 rows, nine numeric fields, 6,144 scalars). Live image/browser
qualification remains a separate gate.

The dependent-input offline replay also uses an actual retained 48-residue
RFdiffusion backbone and the corresponding four-design ProteinMPNN result.
Explicit design index 0 reproduces the original selected sequence SHA256
`f261e7b6a86fdc69bb21c507ea33a612b71255324ab23cd4b5314288235a3d75`.
It is a preparation/recovery test without new inference, not a live whole-study
or biological-quality claim.

The correspondence follow-up replays the actual retained 48-residue refold and
maps all 48 query positions, although only one residue is identical to the
original generated backbone sequence. The unchanged structure evaluator reports
global C-alpha RMSD 2.101842663898239 Å with explicit provenance. It does not
silently switch to the one-residue identity-only fit. Script-phase tests also
perform real suffix-only GC and RDKit QED calculations, reject changed source or
inputs and missing/empty outputs, and kill/restart the worker after the script
receipt while proving the completed script is not reexecuted. These are offline
implementation gates, not inherited natural-client acceptance.
