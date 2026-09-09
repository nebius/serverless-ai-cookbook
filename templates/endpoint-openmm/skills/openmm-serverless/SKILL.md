---
name: openmm-serverless
description: Run and interpret bounded OpenMM GPU simulations through the Nebius Serverless REST and MCP endpoint. Use for endpoint validation, NVT or NVE argon runs, monitoring, artifact retrieval, and exact-system throughput reporting.
license: Apache-2.0
---

# OpenMM on Nebius Serverless

Use the configured OpenMM MCP server whose Streamable HTTP URL ends in `/mcp`.
Authentication is supplied by the MCP client. Never request, print, copy, or put
the endpoint bearer token in tool arguments or this skill.

Call `get_capabilities` before the first run and after a reconnect, runtime
change, or validation error. Its live runtime identity, examples, and limits win
over this skill.

## Scientific boundary

This service simulates a bounded periodic Lennard-Jones argon lattice. It does
not accept arbitrary proteins, ligands, force fields, or OpenMM scripts. Do not
present it as a biomolecular workflow or extrapolate its performance to another
system.

Choose the integrator deliberately:

- `LangevinMiddle` includes a thermostat and reports NVT dynamics.
- `Verlet` reports NVE dynamics and may be faster because it omits the thermostat.

Do not compare their throughput as if they represent the same physics. Preserve
particle count, steps, timestep, precision, temperature, friction, seed, runtime
digest, and GPU when comparing runs. Report simulation performance as
`integration_ns_per_day`; endpoint latency and cold-start time are deployment
metrics, not MD throughput.

## Run workflow

1. Call `get_capabilities` and select a live example or values within its limits.
2. Use `gpu_mode` only if it appears in the live schema; this endpoint fixes the
   OpenMM platform to CUDA.
3. Set `research_use_acknowledgement: true` only for a user-approved research run.
4. Submit once with a stable `client_request_id`. Reuse the ID only after an
   uncertain transport failure with identical input.
5. Save the returned `run_id` and poll `get_run`. Treat `queued` and `running` as
   progress; terminal states are `succeeded`, `failed`, and `cancelled`.
6. Use `list_run_artifacts` after success. Download paths use authenticated REST
   on the same host and require the same bearer token.

The endpoint runs one simulation at a time. On 429, wait and inspect existing
runs rather than resubmitting. `cancel_run` can cancel only a queued run.

## Report

Confirm CUDA was selected and report the run ID, terminal state, ensemble,
integrator, precision, particle count, steps, simulated time, OpenMM version,
NVIDIA runtime tag/digest, GPU, wall time, `integration_ns_per_day`, energies,
and artifact hashes. State that the result is a synthetic research workload and
does not establish scientific validity for another system.

Artifacts persist under `/mnt/hcls/openmm-md/runs/<run-id>` only when Object
Storage or Shared Filesystem is mounted at `/mnt/hcls`.
