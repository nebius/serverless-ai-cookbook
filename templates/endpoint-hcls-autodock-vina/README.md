# AutoDock Vina CPU API

Low-cost interactive redocking and small docking runs with official AutoDock Vina
1.2.7. Vina is CPU software; this template intentionally uses a CPU endpoint.

**License:** [Apache-2.0](https://github.com/ccsb-scripps/AutoDock-Vina/blob/develop/LICENSE) ·
**Source:** [AutoDock Vina](https://github.com/ccsb-scripps/AutoDock-Vina) ·
**Bundled example:** official 1IEP/STI redocking assets at commit
`8eb40404f4f45608acb3b01427587ac049f27c1f`

Build from the repository root:

```bash
docker build --platform linux/amd64 \
  -f templates/endpoint-hcls-autodock-vina/Dockerfile \
  -t hcls-autodock-vina-api:local .
```

After deploying on `cpu-d3` / `4vcpu-16gb`, submit the guided example:

```bash
export HCLS_API_URL='https://…'
export HCLS_API_TOKEN='<endpoint token>'

run_id=$(curl -fsS -X POST "$HCLS_API_URL/v1/runs" \
  -H "Authorization: Bearer $HCLS_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"input":{"exhaustiveness":8,"n_poses":9,"seed":17},"research_use_acknowledgement":true}' \
  | jq -r .run_id)
curl -fsS "$HCLS_API_URL/v1/runs/$run_id" -H "Authorization: Bearer $HCLS_API_TOKEN" | jq
```

Custom receptor and ligand inputs are PDBQT text and require an explicit center and
box size. Limits are published by `/v1/capabilities`. Returned Vina energy components
are kcal/mol research heuristics. They are not RMSDs and must not be compared as if
they were AutoDock4/AutoDock-GPU scores.

See [the common API](../hcls-common/README.md) and deploy the
[HCLS Workbench](../hcls-workbench/README.md) for a browser flow.
