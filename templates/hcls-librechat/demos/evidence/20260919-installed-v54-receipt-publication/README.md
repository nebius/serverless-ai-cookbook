# Exact installed v54 qualification and prepare-only migration binding

The installed-component gate passed on its first execution for source
`12fb896b4dd6c3b856b4b07da903bad08546a0ec`, OCI index
`sha256:c5d01a265447b6d89c155c6266acdad18e158b78eba8888fa2586b41234d421a`,
and amd64 runtime manifest
`sha256:88a70502e8a56e2997286017988ab5fd09b296524d9b2dbd20b1859f435a24a5`.
The registry index and source label were independently verified before testing.

This is **installed-component qualification, not natural-customer acceptance**.
No cloud resources, customer migration, hosted inference or provider calls were
performed by this gate. Earlier failed natural studies remain unchanged.

## Installed transport, contracts and final artifacts

The immutable image ran with Docker networking disabled. Tests exercised its
installed renderer, LibreChat `processMCPEnv`, real MCP SDK stdio transport and
Python helpers. Mounted files were external tests/evidence, isolated workspaces
and pytest support packages; none replaced runtime modules.

- All 11 baseline SDK cases passed, including owner transport, rejected owner
  configurations, clinical credential preflight without a provider call,
  grouped composer persistence, immutable admission and reconnect.
- Semantic preflight rejected compact MindEval summaries and directory
  deliverables. Correcting the saved draft to full records admitted and
  completed the unchanged valid workflow. The exact retained 381-character
  one-line title was preserved, with SHA-256
  `d9a5ad8a26d471d4b25fa25d80761fc9c4aeb1ec34ae2308ee040251f76ae8cc`.
- A typed four-phase study analyzed saved GenMol inputs/results and a real
  mmCIF artifact using installed `gemmi==0.7.3`. Invalid, duplicate and
  underfilled molecule rows remained explicit measurements. Manifest-order
  artifact bytes were verified; no filename-based artifact selection was used.
- Wrong JSON filenames, impossible known-helper outputs and predicted future
  filesystem paths failed before admission, without automatic renaming or
  protocol changes.
- Five CPU studies completed after SDK disconnect. Reconnect and a separate
  reader verified **30 nonempty final artifact/manifest files**, including their
  exact byte lengths and SHA-256 values. This is not a browser-disconnect or
  hosted-model qualification claim.

Ten installed runtime hashes matched the frozen source: execution MCP, report
assembly, study runner, study schema, protein-design helper, molecule helper,
scientific batch client, shared qualification evaluator, receipt module and
observer service. Full hashes are in the protected aggregate receipt.

## Installed receipt publication regression

All **10 installed receipt publication tests passed in 2.29 seconds**. The test
file imports the installed receipt module and native helper; only its fixture
root was rebound to the installed directory. Controlled pauses/crashes and
simulated external admission are test-only, with networking disabled.

The tests cover the short same-owner local reader/writer publication lock,
concurrent loads, strict partial/corrupt-journal rejection, and no duplicate
submission after uncertain admission. A writer crash does not permit an older
snapshot fallback. The existing one-instance-per-owner boundary remains; this
does not establish distributed multi-replica coordination or change retry,
timeout, model or budget policy.

The historical v52 observer 503 has no retained underlying Python exception.
Controlled tests independently reproduced a publication race, but do not prove
that race caused the historical incident. The installed observer now reports
bounded static failure codes without exposing private stderr; it still does
not retain a more specific Python exception category.

## Protected evidence

Here `U` is the protected `scientific-unattended-20260919` handoff directory.

| Receipt | SHA-256 |
| --- | --- |
| `U/workbench-v54-installed.kKgevj/acceptance.json` | `c0907518eb8e8637fbd778c1c2fd79cea751895f24920705a94b0087b2a38db2` |
| Baseline SDK receipt | `52a9ecc2c566679ae6ca3d73868e289b54086ee442e89b0f2f5f807f245f9b7e` |
| Semantic SDK receipt | `96ead351f98c0b7404617a5b0029dc1f914f847b7c91e6ec8031241788b2d0c3` |
| Typed analysis SDK receipt | `a7a504c1529ed4c558b56104bab5e7cfda6919d4b3265f7cf770cbccfec1f1e8` |
| Installed receipt-lock JUnit | `b38bd65b59c4986a0f467fe847050359aaba88391a35dddc1c69f84605e7ff83` |

The aggregate binds the external test hashes, image/source identities, runtime
hashes, artifact inventories and independent readback. Its adjacent `run.py`
records exact commands and execution receipts. It uses fresh isolated output
directories and is intentionally not an overwrite-in-place rerun mechanism.

## Rene prepare-only binding

The existing migration helper was rebound to the exact v54 source/image while
preserving the original customer endpoint identity, bucket and credential
selectors, resource limits, hold/restore flow and explicit candidate planner
configuration. Six binding tests passed. Only the local `prepare` action ran;
no customer endpoint creation, stop, deletion, migration or activation occurred.

- Helper: `U/rene-replacement/rene_replacement_v54.py`, SHA-256
  `a714825b337f7b8b9a2e249df9444d9c7a3e3a67eb23a3cbec68b3e7143de945`.
- Prepared plan: `U/rene-replacement/prepared-20260919T175515039605Z/plan.json`,
  SHA-256 `0c782d2932df96e473d866e5ef0da77c0cd6e31499f771b767c651f3d7314438`.
- Binding JUnit: `U/workbench-v54-installed.kKgevj/rene-binding-tests.xml`,
  SHA-256 `709108a2d135a48d9d98153f300446367727d245d2646e7e4c7c98dc9b7e23ec`.

The earlier actual local Mongo restore/customer-state/login proof under
`U/rene-replacement/local-v50-20260919T160931354670Z` remains historical. These
binding tests are not a new v54 migration replay or a customer-readiness claim.
Cloud activation remains the release owner's separately gated action.
