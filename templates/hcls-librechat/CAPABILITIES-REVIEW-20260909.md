# Event starters and installed infrastructure skills

The previous event release (`5470618`, acceptance `571e548`) was recovered from
the saved handover and verified at endpoint `aiendpoint-e00vw7asvgvc2kxrrm`.
Its source was clean and present in both source/tracking remotes. Login, six
starter drafts, provider-key dialogs, mobile Send, scientific schema discovery,
Tavily and an existing OpenFold2 result viewer all worked during recovery.

The requested continuation is to install the official Nebius infrastructure
skills and make the six event starters demonstrate capabilities. The user
confirmed AltumAge and Clinical PhenoAge are the two event models.

## Changes

Each card now visibly names its models/tools and installed skills. Its prompt
introduces those capabilities and requests concrete input/output workflows:

| Challenge | Capabilities introduced |
| --- | --- |
| AI infrastructure | Ten Nebius skills, hosted model discovery, Tavily and a compute/configuration handoff |
| Aging biology | Event models AltumAge and Clinical PhenoAge, aging-models and primary-source research |
| Target exploration | OpenFold2, DiffDock, protein/drug-discovery skills and interactive structure results |
| Communication, trust and policy | Tavily evidence research plus interpretation of aging-model contracts |
| Healthspan research | Clinical PhenoAge, NV-Reason-CXR-3B, NV-Segment-CT and imaging/aging skills |
| Wildcard | Evo2, GenMol, ProteinMPNN and hosted batch structure/design models |

Ten official skills are bundled at upstream revision
`292c7e65a46d0c29994d2babfc19da129d16fa62`, with all 13 supporting references and
assets. The preparation script retains the Apache-2.0 license and a SHA256
manifest. Since the upstream skills repository requires access, its content is
prepared in an ignored build directory rather than committed to this public
repository. Run `scripts/prepare-nebius-skills.sh` before building.

The application has 32 deployment skills in total. Its infrastructure-preparation
skill and shared instructions now use the installed skills rather than telling
participants to install them before this chat can help. They can prepare actual
configurations, templates and handoffs. Participant cloud accounts remain
separate from the hosted scientific gateway.

## Validation

- 39 offline checks passed with `/tmp/hcls-endpoint-client-venv/bin/python`.
  The older `/home/tux/fs2-skill-adaptation/.venv` lacks MCP test dependencies and
  skips the four client checks; use the complete environment when reporting totals.
- Production client build and pinned TypeScript check passed.
- The candidate loaded all 32 skills; authenticated skill/file APIs exposed all
  ten official skills and their 13 reference/asset contents matched upstream hashes.
- Browser checks passed six distinct drafts, visible model/tool and skill labels,
  unchanged selected chat model, provider-key dialogs and mobile Send readiness.
  Selecting cards sent no chat or compute requests.

## Continuing boundaries

Catalog availability does not establish runtime readiness. Prompts inspect live
contracts and access before offering execution, and obtain the participant's
go-ahead before inference or batch work. In particular, AltumAge needs the full
20,318-CpG input; it is not a tiny hand-written payload. The two event models
consume different data and are not interchangeable clocks.

This update does not add an attachment-to-gateway bridge, batch-result downloader,
clinical integration or participant cloud authentication. Earlier endpoints and
their chat data must be preserved when publishing a new release.

## Release provenance

Source: `d4e3e26485c2a69ae6714a6857bee5d7e4ba1f28` (including `dd1916d`).
Image: `cr.eu-north1.nebius.cloud/e00jz93pkqx2m4vqj4/hcls/nebius-scientific-ai-agent:20260909-d4e3e26`.
Digest: `sha256:020bdbb54621f45f7c63d6b29bcf2e76998ccc5b736b95cdd67eec80381fdc0d`.
Endpoint: `aiendpoint-e00r6bmnz10rtfbxre`, project `project-e00z6b02t8ddk96c49`,
CPU D3 / 4 vCPU / 16 GB / 100 GiB, same three secret-version bindings as the
previous release. Existing endpoint `aiendpoint-e00vw7asvgvc2kxrrm` remains intact.

Local final release: `scientific-capabilities-release`, port 13088. Final-image
production build, TypeScript, all 39 offline checks and browser smoke pass.
The image label matches the full source revision and it loads all 32 skills.

The first infrastructure trial loaded the installed skill bodies, retrieved the
endpoint command reference, used Tavily and produced an unexecuted configuration.
It loaded six skills and the full scientific catalog, exceeding the 120-second
browser wait. The follow-up commit narrows the starter to cloud basics and one
workload-specific skill, and avoids full-catalog discovery for a cloud-only task.
Model-dependent response time remains a practical limitation.

### Cloud acceptance

The new endpoint is RUNNING and `/health` returns 200:
https://port3080-j49j8a0re45wb0c.tunnel.applications.eu-north1.nebius.cloud

Cloud login with the existing deployment demo account succeeds. Authenticated
APIs expose all 32 skills, including every official Nebius skill; all 13
supporting-file contents match the pinned upstream hashes.

The final-image aging starter completed in local chat
`c319f494-4bdf-5aee-aa7f-4e97342d2ae2`: two skills loaded, Tavily research returned,
both live model schemas retrieved, and both named typed tools discovered. It
explained the distinct inputs and offered starting demos without submitting
inference. This verifies routing and tool use, not scientific accuracy of all
model-generated prose or clinical validity.

Cloud browser smoke passed all six capability-labelled starters, unchanged model
selection, both provider-key dialogs, copyable infrastructure handoff and mobile
Send readiness. Card selection sent zero chat/compute requests. No console errors
were recorded in the fresh cloud browser session. The served client bundle
`index.CSZjiHMM.js` matches the final local image.
