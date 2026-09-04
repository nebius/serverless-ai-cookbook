# HCLS Serverless live acceptance and handoff

Accepted on 2026-09-04 in project `project-e00z6b02t8ddk96c49`, region
`eu-north1`, subnet `vpcsubnet-e00p701fa30cj5f7wq`. The endpoints in this
document intentionally remain running for owner verification and continue to incur
Compute and disk charges until stopped or deleted.

## Start here: browser workbench

Open:

<https://port8000-thst0zdky40gzr6.tunnel.applications.eu-north1.nebius.cloud>

Retrieve the workbench login key from MysteryBox. The command prints the secret only
to your terminal; do not paste it into chat, a URL, source, or task notes.

```bash
nebius mysterybox payload get-by-key \
  --secret-id mbsec-e00m4f38savwher5j8 \
  --key HCLS_UI_ACCESS_KEY \
  --format json | jq -r .data.string_value
```

After login, select one of the five provisioned templates. Retrieve the shared compute
endpoint token the same way and paste it into **Endpoint bearer token**:

```bash
nebius mysterybox payload get-by-key \
  --secret-id mbsec-e00hndv0kqn0cz6kf8 \
  --key AUTH_TOKEN \
  --format json | jq -r .data.string_value
```

Click **Verify & connect**, keep the preloaded bounded input, and click **Launch
research run**. Opening or connecting the UI never starts a scientific run. The UI
will show queued/running/terminal state, engine-specific results, and verified artifact
downloads. All examples and outputs are research-only and require domain validation.

## Running endpoints

| Service | Endpoint ID | Platform / preset | Managed HTTPS URL |
| --- | --- | --- | --- |
| HCLS Workbench | `aiendpoint-e00qk0ndgrcgm2s59g` | `cpu-d3` / `4vcpu-16gb` | <https://port8000-thst0zdky40gzr6.tunnel.applications.eu-north1.nebius.cloud> |
| AutoDock Vina | `aiendpoint-e00yfespk6bp7zx24b` | `cpu-d3` / `4vcpu-16gb` | <https://port8000-fjygetfhyrce73y.tunnel.applications.eu-north1.nebius.cloud> |
| AutoDock-GPU | `aiendpoint-e00vyn1wpp2xct606p` | `gpu-h100-sxm` / `1gpu-16vcpu-200gb` | <https://port8000-adec1gy56rzerrr.tunnel.applications.eu-north1.nebius.cloud> |
| GROMACS | `aiendpoint-e00h2zxmtc1qeh0s8r` | `gpu-l40s-a` / `1gpu-8vcpu-32gb` | <https://port8000-e0gvbx1awd7sa8w.tunnel.applications.eu-north1.nebius.cloud> |
| OpenMM | `aiendpoint-e00qa16gz8zagqddpf` | `gpu-l40s-a` / `1gpu-8vcpu-32gb` | <https://port8000-ved78f87qvvz1y0.tunnel.applications.eu-north1.nebius.cloud> |
| Parabricks DeepVariant | `aiendpoint-e00rgzznthxp5ykjvq` | `gpu-h100-sxm` / `1gpu-16vcpu-200gb` | <https://port8000-rheedqtq0aj6y5n.tunnel.applications.eu-north1.nebius.cloud> |

All six use regular capacity. Compute APIs use Nebius token authentication. The
workbench has no Nebius edge token because ordinary browsers cannot add that header;
it instead requires its MysteryBox-backed application login and keeps compute tokens
only in expiring server memory.

## Accepted images

| Image | Registry visibility | Immutable digest |
| --- | --- | --- |
| `hcls/autodock-vina-api:20260904-08f6532` | public | `sha256:f3ea7d1a387d91f81a4aab921dfb8c116fd86d921c9f0704889839438c4562f3` |
| `hcls/autodock-gpu-api:20260904-08f6532` | public | `sha256:b777239caacd24705ccc69607d263285de05ae37c60106853cf019fcb118161b` |
| `hcls/gromacs-md-api:20260904-08f6532` | public | `sha256:e9efb05055a3189a32360226b195df4d7e5ea27e16c1ad06ac8d4222fe17a243` |
| `hcls/openmm-md-api:20260904-08f6532` | public | `sha256:5227555386f1df0d2a40a770b58115d02b93a94fcf4dfb824149ba98f2cb4c1a` |
| `hcls/workbench:20260904-2eb701e` | public | `sha256:39fa2f1167516ab21d1ca41409dee0ece343f18aec07493b25bb97d124126c96` |
| `hcls/parabricks-deepvariant-api:20260904-deb6e34` | private, same project | `sha256:8ed6541d80d99bc932020dbb9568449d5a1e743cd37f353b4c66c4ce70c23102` |

Public images are under
`cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/`. Parabricks is under
`cr.eu-north1.nebius.cloud/e00j70hx633t3qcj0f/`; anonymous pull was explicitly
verified to return HTTP 401. It must not be promoted publicly until an authorized
owner clears the current NVIDIA terms. Serverless cannot currently use these 64-byte
digests directly because of an underlying Compute label-length validation failure, so
the deployments use unique, non-overwritten release tags and separately recorded
digests.

## Live acceptance evidence

| Service | Accepted run | Result | Representative artifact SHA-256 |
| --- | --- | --- | --- |
| AutoDock Vina 1.2.7 | `4d34d4d7242149ac978e5d38432bc8f1` | 1 pose; best Vina affinity `-13.263 kcal/mol`; 10.62 s | `docking-summary.json`: `69d8d1705a4d026552d4572bdc058b64b5fae96d2c63312430c315205513383c` |
| AutoDock-GPU 1.6 | `2e1c74cc40dd4eacb6845a096887e2be` | H100 detected; AutoDock4 score `-2.77 kcal/mol`; 0.51 s | `docking-summary.json`: `d206088bdcb69ec1b97a760330247cf88e4331239052831c63e5b6903042d2a3` |
| GROMACS 2023.2 | `5e07147548b547d8823e1c965cece3b2` | GPU offload selected; `4265.75 ns/day`; 0.64 s wall | `result.json`: `d7ec7e617eefdbaa8fc281f468ecd86db450cf6828651dea2539e05029053f4f` |
| OpenMM 8.5.1 | `58460453b23441d79f7664a9a9f5888a` | CUDA mixed precision; `3708.874 ns/day`; 2.78 s wall | `result.json`: `43f4cc02d9b6396e71703fa4d52849f4bb63dafe54b2de8b7559066c1edcca0c` |
| Parabricks 4.7.0-1 | `37a304770f0a404c9b827ccb972792b3` | H100 detected; 78 chr20 records; 11.33 s wall | `deepvariant-summary.json`: `d1d3b80d5067265d8c5229fddf116a59f0385eeb5598e3f981b955d521e1f9c6` |

The final workbench browser run `bcf79807a759429599e00d2e1a41424b` also called
Parabricks successfully, returned 78 records, rendered 11 artifacts, and downloaded
`deepvariant-summary.json`. Browser console errors and warnings were both zero.
AutoDock Vina and AutoDock-GPU use different scoring engines; their numeric scores are
not scientifically interchangeable.

## Direct API smoke test

Set `HCLS_API_URL` to one of the compute URLs above, then run:

```bash
export HCLS_API_URL='https://port8000-…tunnel.applications.eu-north1.nebius.cloud'
export HCLS_API_TOKEN="$(nebius mysterybox payload get-by-key \
  --secret-id mbsec-e00hndv0kqn0cz6kf8 \
  --key AUTH_TOKEN --format json | jq -r .data.string_value)"

curl -fsS -H "Authorization: Bearer $HCLS_API_TOKEN" \
  "$HCLS_API_URL/healthz" | jq

payload="$(curl -fsS -H "Authorization: Bearer $HCLS_API_TOKEN" \
  "$HCLS_API_URL/v1/capabilities" | \
  jq -c '{input:.examples[0].input,research_use_acknowledgement:true}')"

run_id="$(curl -fsS -X POST \
  -H "Authorization: Bearer $HCLS_API_TOKEN" \
  -H 'Content-Type: application/json' \
  --data "$payload" "$HCLS_API_URL/v1/runs" | jq -r .run_id)"

curl -fsS -H "Authorization: Bearer $HCLS_API_TOKEN" \
  "$HCLS_API_URL/v1/runs/$run_id" | jq
unset HCLS_API_TOKEN payload
```

Poll the final command until `status` is `succeeded`, or use the workbench. Vina's
accepted smoke took about 11 seconds; the other bounded tests were below 12 seconds
after their endpoints were warm.

## Operations and cost control

Inspect state and logs without revealing credentials:

```bash
nebius ai endpoint list --parent-id project-e00z6b02t8ddk96c49
nebius ai endpoint logs --tail 100 aiendpoint-e00rgzznthxp5ykjvq
```

When owner testing is complete, stop the retained endpoints to stop compute charges
(network disks may remain billable). Do not run this block until that handoff test is
finished:

```bash
for endpoint_id in \
  aiendpoint-e00qk0ndgrcgm2s59g \
  aiendpoint-e00yfespk6bp7zx24b \
  aiendpoint-e00vyn1wpp2xct606p \
  aiendpoint-e00h2zxmtc1qeh0s8r \
  aiendpoint-e00qa16gz8zagqddpf \
  aiendpoint-e00rgzznthxp5ykjvq
do
  nebius ai endpoint stop "$endpoint_id"
done
```

The pre-existing `bionemo-3` endpoint (`aiendpoint-e00cezrse2c4e3aeam`) was used as
the native-HTTPS and release-process reference. It was not modified or included in
the HCLS stop list.
