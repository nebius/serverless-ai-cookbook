---
name: gromacs
description: Prepare, submit, resume and analyze NVIDIA-packaged GROMACS molecular-dynamics workflows on Scientific AI. Use for prepared TPRs, protein/system preparation, equilibration, production MD, independent replicas, free-energy windows, trajectory analysis and native checkpoint recovery. Distinguish MD from docking and unqualified enhanced-sampling or multi-node extensions.
license: Apache-2.0
---

# GROMACS on Scientific AI

Read `scientific-gateway` first. App ID: **gromacs**. This is the NVIDIA NGC
GROMACS HPC distribution behind the existing durable scientific-batch API,
not an NVIDIA NIM HTTP API, a folding neural network, or a docking engine.
Installing this skill does not establish that a particular runtime is released.
Read its live schema and qualification limitations before promising a workflow.

## Establish the scientific protocol

Identify supplied files, question, system composition, force field/water model,
protonation and ligand parameters, ensemble, temperature/pressure, timestep,
duration, replica seeds and required analyses. Prefer the customer's prepared
TPR/topology/MDP. When these choices are missing, ask which scientific choices
to make; do not quietly select settings and describe them as industry standards.
Operational defaults and scientifically valid sampling are different things.

- `pdb2gmx` handles supported residues, not arbitrary ligand parameterization.
  A predicted fold or docking pose is not a fully parameterized MD system.
- Docking uses a separate App such as DiffDock. Preserve the selected pose,
  molecule identity, protonation, charges and topology provenance before MD.
- Run preparation → minimization → appropriate equilibration → production →
  analysis explicitly. Use `grompp` checks; never suppress warnings with
  `-maxwarn` merely to make a run succeed.
- Independent replicas need distinct deliberate seeds. Reusing the same
  checkpoint or process snapshot is continuation, not independent sampling.

## Submit through the existing client

1. Read `get_model_schema(model_id="gromacs", protocol="scientific-batch-v1")`.
   Use its exact typed tool, operations, parameter schema and input artifact
   contract. The initial operation is `run-workflow`, with typed tool
   `submit_gromacs_workflow`; discovery remains authoritative.
2. Put every required input in one directory: coordinates, topology plus all
   includes, MDP/TPR, index groups and optional `.cpt`. Paths inside the archive
   are relative. Do not include credentials, symlinks, another tenant's files
   or unnecessary results. Use [the bundle helper](scripts/make-input-bundle.py)
   to create a deterministic gzip tar outside the input directory. It prints
   the actual digest and byte count; never invent those values.
3. Save a parameter JSON document separately. Start with
   [prepared TPR parameters](examples/prepared-tpr.json), replacing filenames
   with inspected inputs, or [explicit preparation](references/workflows.md).
   This is the model parameters document, **not** a scientific-run envelope.
4. Use the installed scientific-batch client or the durable study executor
   from `scientific-batch`. The published source role is `gromacs-inputs`,
   semantic type `gromacs-input-bundle/v1`, media type `application/x-tar`,
   compression `gzip`. Verify these against discovery before submission.
   The client uploads the file, finalizes the canonical input manifest and
   submits once with a stable idempotency key. Do not paste archive bytes into
   a tool call or invent artifact IDs.
5. Save the operation ID and receipt directory. Queued work is not a failure
   and client disconnect is not cancellation. Resume observation of the same
   operation; do not submit duplicates. A campaign can contain multiple jobs;
   each job gets one GPU and may wait for the shared queue.

For a direct client, the installed command shape is:

```sh
/opt/scientific-client/bin/python /opt/bionemo/invoke-scientific-batch.py \
  --model gromacs --tool submit_gromacs_workflow --operation run-workflow \
  --source /workspace/md/input.tar.gz --parameters /workspace/md/parameters.json \
  --entry-name gromacs-inputs --semantic-type gromacs-input-bundle/v1 \
  --media-type application/x-tar --compression gzip \
  --output /workspace/md/receipt --idempotency-key md-study-replica-01 \
  --display-name 'MD study replica 01'
```

Authentication comes from the configured client environment. The legacy
`/opt/bionemo` installation path is not a separate product/server name. In
LibreChat prefer the durable study executor so observation survives disconnect.

## Parameters and native commands

The versioned parameter schema has `jobs`: independently scheduled named jobs
with ordered named `steps`. Each step selects a supported native `command`,
explicit `args`, optional `stdin` group selections, relative `directory` and
`expected_outputs`. No shell, executable path or environment injection is
accepted. Select groups by inspecting the system, not by guessing group numbers.
For multiple trajectory parts, the explicit argument `{"files":"md.part*.xtc"}`
expands files without a shell. A literal `*.xtc` string does not do that.

The initial shape is one GPU, one thread-MPI rank, up to eight CPU threads.
Native automatic offload is the default. Do not force PME/update onto the GPU
without checking algorithm compatibility and a matched-system benchmark.
Do not request multi-node, replica exchange, PLUMED, CP2K or NNPot through
undocumented flags. See [capability boundaries](references/workflows.md).

Operational defaults: five-minute local checkpoints and remote segments,
six-hour per-job wall budget, 4 GiB output budget, and customer-bucket export.
Read the live bounds before changing `threads`, `segment_minutes`,
`checkpoint_minutes`, `max_wall_seconds`, `max_output_bytes`,
`output_destination` or `output_prefix`. Output cadence is controlled by the
customer's MDP/TPR and is not silently rewritten. Platform/bucket quotas still
apply; a larger request budget does not purchase or create storage.

## Restart, storage and results

Native `.cpt` continuation and CUDA/CRIU snapshots are distinct. Do not claim
GPU snapshots are enabled unless the exact runtime's evidence says so. The
runner segments finite MD, commits closed files and a manifest, and continues
with native checkpoints and `-noappend`. Failed-attempt recovery uses the last
committed generation of the same operation/job; it can replay uncommitted work.
After cancellation the final uncommitted generation may not be recoverable.

`-noappend` produces `.partNNNN` files. Preserve them all. Use `trjcat` and
`eneconv` deliberately and check frame times/overlap; never concatenate binary
files with shell `cat`. The runner exposes the latest final coordinate at the
normal `-c`/`-deffnm` path for a subsequent explicit `grompp` step.

Customer export resolves the submitting user's assigned bucket; a payload
cannot select someone else's bucket. Under the chosen prefix, operation and
job IDs identify content-addressed `objects/<sha256>` and immutable
`attempt-NNN/checkpoint-NNNNNNNN.json` manifests. The manifest maps original
names to object keys and byte hashes. These remain until customer deletion or
bucket lifecycle expiry. They are not files mounted live by the GROMACS engine.

Download the completed platform result and every promised artifact using the
verified file helpers. `result.json` records exact inputs/runtime, commands,
native checkpoint generations, step outcomes, file names/hashes and available
performance. The outer batch client's `output-NN.artifact` names are transport
names, not native file names; use the output manifest and native result mapping.

Report simulation duration/steps, atoms, trajectories/frames, temperature and
energy sanity checks, warnings, achieved ns/day, wall and queue time separately.
For free energy report lambda schedule, estimator, equilibration discard,
overlap, uncertainty and convergence limitations. A terminal `succeeded` run
proves execution and verified outputs, not equilibration or a valid biological
conclusion. Do not treat the short tutorial fixtures as production science.

## References and tested examples

Read [workflows and source documentation](references/workflows.md) for native
command recipes, free energy, extension boundaries and official references.
When a protocol fails, preserve its operation ID, diagnostics and inputs; fix
the scientific cause instead of suppressing it or changing models silently.
