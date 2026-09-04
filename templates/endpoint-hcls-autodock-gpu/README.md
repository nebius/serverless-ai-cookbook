# AutoDock-GPU API (AutoDock4 scoring)

CUDA-accelerated docking and bounded ligand screening with AutoDock-GPU v1.6.
This is AutoDock 4.2.6 acceleration, not a GPU build of AutoDock Vina.

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fautodock-gpu-api%3A20260904-08f6532&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=100GiB&amp;preemptible=false"><img src="../assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Before creating the endpoint, enable token authentication in the Console. The H100
configuration above is the live-qualified fallback after L40S capacity was unavailable;
the image also contains SM89 code for a future L40S qualification.

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

The guided 1STP/biotin case uses bundled public affinity maps:

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
