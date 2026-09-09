---
name: gromacs-serverless
description: Run and inspect bounded GROMACS molecular-dynamics workloads through the Nebius Serverless REST and MCP endpoint. Use for endpoint validation, GPU smoke tests, prepared TPR runs, custom GROMACS inputs, run monitoring, artifact retrieval, and result interpretation.
license: Apache-2.0
---

# GROMACS on Nebius Serverless

Use the configured GROMACS MCP server. Its Streamable HTTP URL ends in `/mcp`.
The MCP client supplies the Nebius endpoint bearer token; never request, print,
copy, or place that token in tool arguments. If the server is not configured,
tell the user that its URL and bearer token must be added to the agent's MCP
configuration outside the conversation.

## Discover the live contract

Call `get_capabilities` before the first submission and again after a reconnect,
runtime change, or validation error. The returned limits, engine version,
runtime tag and digest, accepted inputs, and examples win over this skill.

The available tools are:

- `get_capabilities`: inspect the live engine and request limits.
- `submit_run`: enqueue one bounded simulation.
- `get_run`: inspect one run by ID.
- `list_runs`: find recent runs known to this endpoint.
- `cancel_run`: cancel a queued run only.
- `list_run_artifacts`: list authenticated REST download paths and SHA-256
  hashes for a run.

REST and MCP share the same queue, run IDs, state, artifacts, and endpoint token.

## Choose an input mode

Use exactly one of these modes:

1. **Guided argon smoke:** omit molecular input files and supply bounded controls
   such as `steps`, `gpu_mode`, and `threads`. Use this only to validate the
   endpoint, NVIDIA runtime, GPU offload, and persistence. It is not a research
   protocol and its throughput does not predict biomolecular performance.
2. **Prepared TPR:** supply `tpr_base64`. Prefer this for a reviewed,
   reproducible research setup. Check that the TPR is compatible with the live
   GROMACS version. Set `steps` to the intended bounded run length because the
   service passes it to `mdrun -nsteps`; set `timestep_ps` to the TPR timestep so
   reported `simulated_ns` is meaningful.
3. **Custom text:** supply `coordinate_gro`, `topology_top`, and `mdp` together.
   Never send only part of this group. Treat includes, force-field availability,
   molecule counts, atom ordering, units, constraints, ensemble, timestep, and
   equilibration as scientific inputs that require independent validation.

Do not invent missing structures, topologies, force-field parameters, or
simulation settings. Ask for the missing material or explain precisely why the
requested run is not scientifically specified. A successful `grompp` or `mdrun`
does not establish scientific validity.

## Submit once, then monitor

1. Prepare the selected `input` object within the advertised limits. Prefer
   `gpu_mode: "gpu"` when validating the GPU service.
2. Set `research_use_acknowledgement` to `true` only when the user is asking for
   research use and has supplied or approved the inputs.
3. Create a stable `client_request_id` using only letters, digits, `.`, `_`, `:`,
   or `-`, up to 128 characters. Reuse it only to recover the same logical
   submission after an uncertain transport failure; changed inputs require a
   new ID.
4. Call `submit_run` once and retain its `run_id`.
5. Poll `get_run` until `succeeded`, `failed`, or `cancelled`. Treat `queued` and
   `running` as progress. Do not resubmit merely because a tool or chat wait
   ended.

The endpoint executes one run at a time. A 429 response means its bounded queue
is full; wait and inspect existing runs. `cancel_run` works only while a run is
still queued. Do not repeatedly attempt to cancel a running process.

## Validate and report results

For a successful GPU run, confirm `gpu_selected: true`. Report:

- run ID and terminal state;
- input mode, steps, timestep, and simulated nanoseconds;
- GROMACS version plus NVIDIA runtime tag and digest;
- wall-clock/`mdrun` time and `ns_per_day` when returned;
- artifact names, sizes, and SHA-256 hashes;
- the scientific assumptions and validation still required.

Use `list_run_artifacts` after success. Its `download_path` values are REST paths
on the same endpoint and require the same bearer token. If the agent has an
authenticated HTTP/file-transfer capability, download the required artifacts
and verify their SHA-256 hashes. Otherwise return the paths and hashes so the
user can retrieve them without exposing their token in chat.

Do not treat request latency or endpoint cold-start time as MD throughput; use
`ns_per_day`. Do not generalize the argon smoke result to another molecular
system or claim a biological, clinical, or materials conclusion from execution
or performance data alone.

Artifacts persist under `/mnt/hcls/gromacs-md/runs/<run-id>` only when the
endpoint has Object Storage or Shared Filesystem mounted at `/mnt/hcls`.
Without that mount, outputs are endpoint-local and may disappear when the worker
is replaced.
