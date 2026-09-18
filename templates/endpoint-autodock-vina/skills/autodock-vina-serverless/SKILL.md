---
name: autodock-vina-serverless
description: Run and inspect bounded AutoDock Vina CPU docking through the Nebius Serverless REST and MCP endpoint. Use for public redocking validation, custom PDBQT inputs, explicit search boxes, run monitoring, poses, scores, and artifact retrieval.
license: Apache-2.0
---

# AutoDock Vina on Nebius Serverless

Use the configured Vina MCP server whose Streamable HTTP URL ends in `/mcp`.
Authentication is supplied by the MCP client. Never request, print, copy, or put
the endpoint bearer token in tool arguments or this skill.

Call `get_capabilities` before the first submission and after a reconnect or
validation error. Its live schema, limits, engine version, and example win over
this skill.

## Prepare a docking run

Use the bundled 1IEP/STI input only to validate endpoint behavior. For a custom
run, use caller-supplied PDBQT receptor and ligand text and require explicit
`center` and `size` coordinates. Do not invent a binding site, protonation state,
charges, rotatable bonds, receptor preparation, or search box. Ask for missing
scientific inputs.

Choose exhaustiveness, pose count, CPU count, and seed within the live limits.
Higher exhaustiveness or a larger box costs more time and does not by itself make
the molecular preparation scientifically valid.

## Submit and monitor

1. Call `get_capabilities` and prepare one bounded input.
2. Set `research_use_acknowledgement: true` only for a user-approved research run.
3. Submit once with a stable `client_request_id`. Reuse it only to recover an
   identical request after an uncertain transport failure.
4. Save `run_id` and poll `get_run`. Treat `queued` and `running` as progress;
   terminal states are `succeeded`, `failed`, and `cancelled`.
5. Call `list_run_artifacts` after success. Download paths are authenticated REST
   paths on the same endpoint and use the same bearer token.

On 429, wait for existing work rather than resubmitting. `cancel_run` can cancel
only queued work.

## Interpret and report

Report run ID, state, Vina version, box, exhaustiveness, pose count, seed, wall
time, ranked affinity and energy components in kcal/mol, and artifact hashes.
Verify downloaded hashes when authenticated file transfer is available.

Vina scores are research heuristics, not binding free energies or experimental
measurements. Do not compare their raw values with AutoDock-GPU/AutoDock4 scores
or claim biological conclusions. A successful run does not validate molecule
preparation or the selected binding site.

Artifacts persist under `/mnt/hcls/autodock-vina/runs/<run-id>` only when Object
Storage or Shared Filesystem is mounted at `/mnt/hcls`.
