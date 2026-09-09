---
name: autodock-gpu-serverless
description: Run and inspect bounded AutoDock-GPU docking through the Nebius Serverless REST and MCP endpoint. Use for supported-GPU validation, 1STP redocking, ligand batches, AutoDock4 scores, run monitoring, and artifact retrieval.
license: Apache-2.0
---

# AutoDock-GPU on Nebius Serverless

Use the configured AutoDock-GPU MCP server whose Streamable HTTP URL ends in
`/mcp`. Authentication is supplied by the MCP client. Never request, print,
copy, or put the endpoint bearer token in tool arguments or this skill.

Call `get_capabilities` before submitting. Its live schema and limits win over
this skill. Confirm that readiness reports a passed CUDA docking probe and that
the GPU compute capability is supported by the image.

## GPU boundary

This source build contains native SM80, SM86, SM89, and SM90 cubins only. It does
not support Blackwell SM100 or SM103. Do not submit work merely because a
Blackwell container process or `nvidia-smi` started; CUDA docking cannot execute
there. Use the default proven H100 unless the user has deliberately selected and
validated another supported architecture.

## Prepare docking input

The bundled 1STP/biotin case validates the deployment. Custom `ligands` contain
safe unique IDs and bounded PDBQT text and are docked against the bundled 1STP
maps. The service does not accept arbitrary receptor maps. Do not invent ligand
preparation, protonation, charges, grid maps, or scientific parameters.

AutoDock-GPU uses AutoDock4 scoring. Never compare its raw scores directly with
AutoDock Vina scores or describe it as GPU Vina.

## Submit and monitor

1. Call `get_capabilities` and select inputs within the live bounds.
2. Set `research_use_acknowledgement: true` only for a user-approved research run.
3. Submit once with a stable `client_request_id`; reuse it only for an identical
   request after an uncertain transport failure.
4. Save `run_id` and poll `get_run`. Treat `queued` and `running` as progress;
   terminal states are `succeeded`, `failed`, and `cancelled`.
5. Call `list_run_artifacts` after success. Its download paths are authenticated
   REST paths using the same endpoint bearer token.

On 429, inspect and wait for existing work rather than resubmitting. A run can be
cancelled only while queued.

## Interpret and report

Report run ID, state, engine/source revision, compiled compute capabilities, GPU
and driver, number of ligands, runs/evaluations, seed, wall time, each ligand's
best estimated binding energy, and artifact hashes. Verify downloaded DLG/XML,
score, summary, and log artifacts when authenticated transfer is available.

Docking scores and poses are research heuristics. A successful run does not
validate molecule preparation, the bundled receptor grid for a new ligand, or a
biological conclusion.

Artifacts persist under `/mnt/hcls/autodock-gpu/runs/<run-id>` only when Object
Storage or Shared Filesystem is mounted at `/mnt/hcls`.
