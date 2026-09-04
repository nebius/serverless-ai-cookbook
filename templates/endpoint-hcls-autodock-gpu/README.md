# AutoDock-GPU API (AutoDock4 scoring)

CUDA-accelerated docking and bounded ligand screening with AutoDock-GPU v1.6.
This is AutoDock 4.2.6 acceleration, not a GPU build of AutoDock Vina.

**License:** GPL-2.0 with bundled LGPL components ·
**Source:** [AutoDock-GPU](https://github.com/ccsb-scripps/AutoDock-GPU) at
`e63e6f6280ebfad18caa3e8f48afdc269e79e063`

The image includes the upstream licenses and a corresponding-source archive for the
compiled binary. CUDA cubins target SM80, SM86, SM89, and SM90. Build from the
repository root:

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-autodock-gpu/Dockerfile \
  -t hcls-autodock-gpu-api:local .
```

Deploy first on `gpu-l40s-a` / `1gpu-8vcpu-32gb`. The guided 1STP/biotin case uses
bundled public affinity maps:

```json
{
  "input": {"nrun": 5, "max_evaluations": 250000, "seed": 17},
  "research_use_acknowledgement": true
}
```

For a small batch, provide up to 32 `{ "id", "pdbqt" }` ligand objects; this initial
template docks them against the bundled 1STP maps. The result reports per-ligand
estimated binding energy and returns DLG/XML/log artifacts. AutoDock4 scores are
research heuristics and are not interchangeable with Vina scores.

See [the common API](../hcls-common/README.md) and deploy the
[HCLS Workbench](../hcls-workbench/README.md) for capability-aware configuration.
