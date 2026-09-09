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
