# AutoDock-GPU API (AutoDock4 scoring)

CUDA-accelerated docking and bounded ligand screening with AutoDock-GPU. This is
AutoDock 4 acceleration, not a GPU build of AutoDock Vina.

## NVIDIA runtime compatibility status

The dynamic REST + MCP wrapper in this directory pulls only the official
`nvcr.io/hpc/autodock` runtime. Its explicit inputs match the other dynamic templates:

| Setting | Value |
| --- | --- |
| Plain environment variable | `AUTODOCK_VERSION=latest` or an exact NVIDIA tag |
| Secret environment variable | `NGC_API_KEY` from a MysteryBox payload key named `NGC_API_KEY` |
| Authentication | Serverless **Token authentication** for both REST and MCP |
| Persistent storage | Object Storage or Shared Filesystem, read-write at `/mnt/hcls` |

As of 2026-09-08, NVIDIA publishes only tag `2020.06` for that repository, digest
`sha256:6170944542063c7417343bec5e4001239e4ce113c2faf7f5824cb20a08373d9c`.
Its included executable fails its real docking startup probe on H100, and the image
does not contain corresponding source that the wrapper could rebuild. The available
Nebius Serverless GPU families are newer than the architectures qualified by that
2020 runtime. Consequently, the dynamic NVIDIA template is implemented but not
published as a customer deploy button: `latest` would create an endpoint that cannot
run docking.

When NVIDIA publishes a compatible stable tag, `AUTODOCK_VERSION=latest` will select
it without an API-wrapper code change. An exact old tag remains fail-closed if its
GPU startup probe does not pass.

## Existing compatibility build

The previously qualified source build remains available for H100 testing while the
official NGC repository catches up:

<a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fautodock-gpu-api%3A20260904-08f6532&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=100GiB&amp;preemptible=false"><img src="../assets/create-endpoint.svg" alt="Create source-build fallback endpoint" width="138" height="20"></a>

That fallback is not the dynamic NVIDIA-image pattern requested here. It bundles a
pinned upstream AutoDock-GPU v1.6 source build with SM80, SM86, SM89, and SM90 code.

The guided 1STP/biotin case uses public affinity maps:

```json
{
  "input": {"nrun": 5, "max_evaluations": 250000, "seed": 17},
  "research_use_acknowledgement": true
}
```

For a small batch, provide up to 32 `{ "id", "pdbqt" }` ligand objects. Results
include per-ligand estimated binding energy plus DLG/XML/log artifacts. AutoDock4
scores are research heuristics and are not interchangeable with Vina scores.

See [the common API](../hcls-common/README.md) and
[HCLS Workbench](../hcls-workbench/README.md).
