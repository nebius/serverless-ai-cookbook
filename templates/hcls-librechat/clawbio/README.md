# ClawBio skills in the Scientific AI workbench

Source/image integration only. This change does **not** deploy, restart or alter
any user's LibreChat instance, cloud resource, tenant, key or model App.

The reviewed upstream is [ClawBio](https://github.com/ClawBio/ClawBio) at
`4848cc280c446093b1364a2445db3137d455cc17`. Its deprecated MCP server is not used.
The old catalog skill pointing at that absent server is replaced in the existing
template overlay. Agent instructions and normal skill discovery expose the new
skills without adding another tool schema or dumping all skill bodies into chat.

## What is included

`selection.json` accounts for all **97** upstream skills: **48 installed**
(45 local workflows, three hosted-App adaptations), **49 excluded** with an
individual reason. This is a reviewed selection, not an assertion that every
ClawBio method, optional dependency or dataset is supported.

Local coverage includes sequence analysis, population/genotype analysis, variant
annotation, pharmacogenomics reporting, GWAS/PRS, ABF fine mapping, eQTL/GWAS
regional retrieval, LD, bulk/single-cell RNA analysis, proteomics, QC, enrichment,
public literature/trial discovery, data retrieval and research reports.

Hosted adaptations use existing caller-authorized Apps and live schemas:

| ClawBio skill | Existing platform path |
| --- | --- |
| struct-predictor | Boltz/OpenFold/ESMFold/Protenix model skills |
| cell-detection | Cellpose native model skill |
| scrna-embedding | scVI/scANVI App; local QC remains separate |

No GPU runtime or model weights are installed in the CPU workbench. Hosted
adaptations are guidance, not newly qualified model implementations.

Excluded items include separate external accounts/services, unsupported
Nextflow/R/reference-database stacks, incomplete upstream implementations,
unreviewed licensing or model-weight requirements, and duplicate agent/MCP
layers. Notable findings: clinical-variant-prioritizer has no executable CLI and
omits its default panel; data-extractor assumes Anthropic-specific models/keys;
methylation-clock requires a separate PyAging model runtime. Existing AltumAge
support is preserved but is not described as all PyAging clocks.

## Execution and adaptations

```sh
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py list
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py describe rnaseq-de
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py help rnaseq-de
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py run rnaseq-de -- \
  --counts /data/study/counts.csv --metadata /data/study/metadata.csv \
  --formula '~condition' --contrast condition,treated,control \
  --output /data/clawbio-runs/study-001
```

Use the existing `execute_command` / `read_execution` job lifecycle. Long jobs
continue after a chat timeout; observe the saved job instead of resubmitting it.
Inputs are staged under `/data`, and completed outputs exported with the existing
workspace tools. `/workspace` is the caller's durable bucket, not a general POSIX
analysis filesystem. The integration creates no storage credentials.

- The runner calls each native CLI, not ClawBio's generic dispatcher: the latter
  rejects valid RNA-seq `--counts` inputs without a redundant `--input`.
- Python packages are hash-locked in an isolated venv. Existing Scientific AI,
  MCP and clinical-client dependency environments remain unchanged.
- PyDESeq2 gets an explicit worker limit: one by default, configurable with
  `SCIENTIFIC_CLAWBIO_CPUS` to match the actual instance allocation. This avoids
  spawning a worker per host CPU inside a small container. The only upstream
  source adaptation changes this parallelism setting, not the statistical method;
  its original and adapted hashes are recorded. Scrublet and SomaData are included;
  optional CellTypist model downloads remain outside this installation.
- PLINK 1.9 is installed as a separate distribution package. Native tabix/libcurl
  uses a valid CA bundle, retaining TLS verification.
- Article retrieval is headless with explicit file-type selection. It verifies
  downloaded artifacts, fixes decompressed paths in the manifest and records
  size/SHA256. Failed/partial downloads exit unsuccessfully even if a report was
  written. External repositories still require availability/access.
- Fine mapping is explicitly **Wakefield ABF without LD**, not SuSiE. Missing
  SuShiE/JAX is not replaced silently by another method.
- Public annotation/enrichment tools may send variants or gene lists externally.
  Skills require explaining that transfer; no external API account is fabricated.
- Demo data is only for requested examples, never a substitute for user inputs.
  Clinical/genetic findings remain unvalidated research outputs.

## Prepare, test and build

Run from `templates/hcls-librechat`, in an isolated worktree. No preparation
command changes running services. `prepare.py` requires a fresh output directory
and reads committed blobs from the exact pinned revision, retaining licenses,
original method references and per-file SHA256. It copies no upstream bot or
hidden environment files. Generated vendor bundles are not committed.

```sh
git clone https://github.com/ClawBio/ClawBio /tmp/clawbio-source
git -C /tmp/clawbio-source checkout --detach 4848cc280c446093b1364a2445db3137d455cc17
python3 clawbio/prepare.py --source /tmp/clawbio-source --output vendor/clawbio
bash scripts/prepare-nebius-skills.sh
uv venv /tmp/clawbio-tests --python 3.11
uv pip sync --python /tmp/clawbio-tests/bin/python --require-hashes clawbio/requirements.lock
uv pip install --python /tmp/clawbio-tests/bin/python pytest==8.4.2
/tmp/clawbio-tests/bin/python -m pytest clawbio/test_integration.py -q
/tmp/clawbio-tests/bin/python clawbio/qualify.py --root vendor/clawbio \
  --runner clawbio/runner.py --output /tmp/clawbio-probes --record
/tmp/clawbio-tests/bin/python clawbio/upstream_checks.py --root vendor/clawbio \
  --output /tmp/clawbio-upstream-tests
```

Build from the repository root using the existing Dockerfile and a new local tag:

```sh
docker buildx build --builder default --platform linux/amd64 --load \
  -f templates/hcls-librechat/Dockerfile \
  --build-arg HCLS_IMAGE_REVISION="$(git rev-parse HEAD)" \
  -t scientific-ai-librechat:clawbio-candidate .
```

The Dockerfile-specific context filter excludes unrelated repository content and
credentials. The image includes `/opt/clawbio/manifest.json`,
`/opt/clawbio/qualification.json`, preserved upstream source/licenses and the
namespaced skills under `/app/skill`.

## Evidence and limitations

`test_integration.py` tests real-input CLI execution, independent expected FASTA
statistics and Wakefield ABF probabilities, known-direction RNA-seq contrasts,
failure propagation, source hashes, discovery and actual MCP job/reconnect flow.
The artifact-retrieval adapter is tested with mocked transport, not customer data.
`upstream_checks.py` adds selected offline upstream regressions.

`qualify.py` records every installed local help/example outcome, warnings and
output hashes. External-network failures, missing binaries, timeouts and hosted
guidance-only paths stay visible. A non-empty demo output is only
`example-executed`, **not scientific or customer qualification**. Read the
per-skill report before claiming a mode such as LD coloring worked.

Before any later production rollout: test the exact candidate image in a
customer-shaped LibreChat instance, verify skill discovery/loading and real
workspace exports, call each hosted adaptation using that user's grant, and
exercise representative larger datasets, interruption/recovery and failure
paths. No such live deployment is authorized by this source/image-only change.
