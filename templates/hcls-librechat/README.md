# Nebius Scientific AI Agent

A scientific workspace built on pinned LibreChat. Public Nebius Token Factory
is the default conversational provider. Retired event-specific endpoints are
not part of the reusable client. Users can also bring OpenAI or Anthropic credentials. The existing
`agent_nebius_scientific_ai` agent is enhanced, not replaced: scientific Apps,
research skills, Tavily, structure viewing, execution, durable run tracking and
workspace discovery stay attached when the chat LLM changes.

## Getting started as a user

Open **Getting started & example prompts** on the chat home page, or
`/demos?tab=getting-started`. The guide includes a no-inference workspace tour
and concrete protein, molecule, speech, aging-clock and image examples. It uses
the versioned `examples/v1/` pack in your bucket, not hidden event fixtures.
See [GETTING_STARTED.md](GETTING_STARTED.md) for the same setup and recovery steps.
The [naming contract](NAMING.md) defines the product, App and MCP names used by
the client and explains the one retained legacy alias.
The [general-client candidate receipt](GENERAL_CLIENT_RELEASE_20260920.md) records
the published image, exact UI tests and the live-upgrade work still required.

Six general research cards prepare editable prompts for literature-backed
reproduction, structures, molecular/protein design, genomics/aging, clinical
speech/imaging, and robotics data augmentation. Clicking a card does not switch
the LLM, send a message, or submit compute. `/demos` is the workbench surface:
Apps is caller-scoped live discovery, Runs reconnects durable operation IDs,
Workspace browses a deployment-mounted bucket, and the existing Clinical Report
and MindEval panels remain available.

The image contains no model or MCP credential. One non-admin gateway key is used
for both the model API and MCP service. Store it in MysteryBox under the payload
key `SCIENTIFIC_MODELS_API_KEY` and map it only as a secret environment variable.

## Deploy

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
export SCIENTIFIC_MODELS_API_KEY_SECRET_SELECTOR='nebius-scientific-model-gateway'
export TOKEN_FACTORY_SECRET_SELECTOR='<secret selector with NEBIUS_API_KEY>'
export TAVILY_SECRET_SELECTOR='<secret selector with TAVILY_API_KEY>'
# IMAGE is optional: the deployment script defaults to the tested skills release.
# Set it only when choosing a separately qualified runtime override.
# Only for a user who has no active study supervisor:
export SCIENTIFIC_STUDY_OWNER_MODE='first-instance'

./templates/hcls-librechat/scripts/deploy.sh
```

The default is `cr.eu-north1.nebius.cloud/e00akg9ndpx77eaexh/lc:skills-20260920-v1`,
digest `sha256:01a9363e53e6cc7e7592af892c960e99410d201c70365c20f8a85b10efe4d94a`.
Its 31 preinstalled customer skills come from the same
[canonical public directory](https://github.com/rene-tech/serverless-ai-cookbook/tree/main/skills/scientific-ai)
as the website's **Get the Skills** button. Operators maintain this selection in
`scripts/release-image.sh`. Existing running instances do not auto-upgrade when
this default changes; upgrading their application requires a separate controlled
rollout preserving chats, credentials and workspace bindings. In particular,
this v61-based image is not a skills-only replacement for an older v11 runtime.

The script creates a public CPU D3 endpoint on port `3080`; LibreChat keeps its
own email/password sign-in page reachable. Dedicated deployments mount a user or team's
read-write Object Storage bucket at `/workspace`. Provision secrets separately; never
put real keys in commands, Git, image layers or chat prompts.

Never delete an existing endpoint without preserving `/data` and `/app/uploads`:
the self-contained image runs its own MongoDB.

### Deployment ownership: one instance per user

Each user has a **separate LibreChat instance**, its own login, execution
environment and scoped platform key. This is the supported deployment topology,
including when several users belong to one tenant. Users in the same tenant may
intentionally mount the **same tenant bucket**; a shared bucket does not imply a
shared chat instance or shared inference identity. Models remain centrally hosted
Apps shared by authorized users, not private model deployments per workbench.

Persisted execution and study-control records must be namespaced by the dedicated
user identity so two workbenches sharing a bucket do not resume each other's
work. Shared scientific files remain available according to the tenant's storage
policy. Credentials are deployment secrets, never files in the shared workspace.
Acceptance must exercise distinct dedicated instances and verify their request
attribution and intentional shared storage. Shared-instance user multiplexing is
outside this architecture and is not a release requirement.

For replacements, preserve the predecessor's chat/database state and stop its
study supervisor before using `SCIENTIFIC_STUDY_OWNER_MODE=stopped-predecessor`.
This applies to the **same user**, not to other users sharing a tenant bucket.
See [durable study ownership and recovery](demos/UNATTENDED_STUDIES.md#deployment-and-ownership).

### Personal instance with an existing tenant bucket

The same deployment script supports a separate personal instance without changing
or migrating an existing endpoint. In addition to the variables above:

```bash
export NEBIUS_PROFILE='<authorized CLI profile>'
export ENDPOINT_NAME='<unique personal endpoint name>'
export TEAM_ID='<tenant name>'
export TEAM_BUCKET_NAME='<existing bucket discovered from GET /v1/storage>'
export S3_CREDENTIAL_SECRET_SELECTOR='<secret with S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY>'
export SEED_DEFAULT_USER_EMAIL='<personal login email>'
export USER_PASSWORD_SECRET_SELECTOR='<secret with SEED_DEFAULT_USER_PASSWORD>'
export SSH_PUBLIC_KEY_FILE='<operator public key file>'
```

For the S3 mount, the CLI also needs a `default` AWS **configuration** profile
with `region` and `endpoint_url`, even when credentials come from MysteryBox.
`AWS_CONFIG_FILE` can point to a task-local configuration file; no credential
belongs in that file. The script mounts the bucket read-write at `/workspace`
using the existing user's S3 credentials. Mongo, encrypted plugin credentials
and clinical job working directories remain on the endpoint disk, not S3/FUSE.
The personal login option disables open registration. The client uses public
Token Factory models and ignores the retired dedicated-event environment flag.

`SERVERLESS_PUBLIC_IP` defaults to `true` for backward compatibility. Set it to
`false` to request a private-IP endpoint with its managed public HTTPS URL.
Unset `SSH_PUBLIC_KEY_FILE` (and omit the setup manifest's `ssh_public_key_file`)
as well for a private-only deployment: requesting SSH
access can allocate a public IP even when `SERVERLESS_PUBLIC_IP=false`; the
deployment script warns about this combination but preserves the explicit SSH
request. The scientist setup helper exits immediately on provider state `ERROR`
and retains the endpoint ID, exact provider status and a protected
`endpoint-terminal-error.json`; it does not retry creation or infer the cause
of an image-pull failure.

After first login, configure the same personal Scientific AI key in
`/demos?tab=apps` (encrypted per-user credential store). This is separate
from the server-managed key used by the legacy workbench. The bucket is available
to the workspace/file tools; the clinical panel's file picker selects **browser-local
files**, not server-mounted paths. The separate Workspace tab is the bucket browser.
Use the panel for recorded-audio uploads; live microphone capture is not qualified.

Validate the real mount with object readback and a write visible through S3,
then test complete EN/DE recordings through the public client and download all
report/review artifacts. Health checks alone are not workflow acceptance.

The installed Serverless CLI `0.12.206` may copy the complete image reference into
a Compute label. A 131-character digest reference failed creation with the
64-character label limit on 2026-09-18. If this occurs, publish a **new, short,
unique tag**, verify its registry digest equals the tested image, and record both
in the deployment receipt. Do not move an existing deployment's tag or replace
its image to work around this limitation.

## What is configured

- **Chat models:** the seeded agent defaults to Qwen3 235B on public Token Factory;
  deployments can explicitly select another discovered model. The public
  allowlist is intersected with authenticated discovery at startup
  (configured-list fallback). OpenAI
  and Claude remain optional and require a user-supplied provider key.
- **Scientific Apps:** available only through the gateway tools. The Apps page
  merges `/v1/models` and `/v1/scientific-models` for the current caller; it has
  no static availability list. Model-specific
  schemas load on demand with `tool_search`; discovery and durable operation tools
  stay ready. Gateway authorization, validation and execution are unchanged.
- **Branding:** application title, logo, welcome copy, and theme use Nebius
  Scientific AI Agent identity. The chat picker uses the official colored Token
  Factory mark, bundled locally, for its group, models and selected-chat icon.
  The footer pairs NVIDIA's green symbol/black wordmark with Nebius, using
  balanced sizing and a light NVIDIA backing that works in dark mode.
- **Runs:** six typed workbench tools save, refresh, inspect, retrieve and cancel
  accessible operation IDs. The main agent is instructed to save every returned
  ID immediately. Runs survive chat reconnection and never imply automatic
  resubmission.
- **Workspace:** dedicated deployments browse, upload and download the bucket
  mounted at `/workspace`; paths are bounded to the mount and uploads are
  atomic. A shared deployment without a mount reports its caller-owned platform
  storage but does not expose credentials or pretend it can browse it.
- **Workflows:** six goal-oriented prompts; saved tutorial agents keep stable IDs
  for existing conversations and now use the same workbench tracking tools.
- **Structure viewer:** `visualize_structure` reads completed operation results
  with the configured gateway key and sends real PDB/mmCIF/SDF coordinates into
  a sandboxed in-chat 3Dmol viewer. Spin, drag, zoom, fullscreen, reset, structure
  selection and representations work without sending the HTML/coordinates back
  through the LLM. The UI resource is stored with the chat and survives reload.
  Results are limited to 4 MiB and 20 structures; small user-provided inline
  structures are limited to 64 KiB. No arbitrary URL or filesystem access.
- **Infrastructure preparation:** the bundled `nebius-infrastructure-prep`
  uses public setup guidance and checks for any optional official Nebius skills.
  The public customer image does not depend on their private source. Guidance
  does not connect a participant cloud account or authorize resource creation.
- **Limitations:** a deployment without a mounted bucket does not yet have an S3
  file browser. The generic LibreChat attachment picker is not a scientific
  artifact upload bridge, and there is no GROMACS
  server. The viewer does not download scientific-batch artifact references or
  invent coordinates for sequences/SMILES. Inline inputs and finalized artifacts
  remain usable. Do not promise arbitrary attachment submission or fabricated
  output links. Catalog presence is not runtime readiness.
- **Pinned patches:** fail-fast client/server changes cover the picker, missing
  and expired key handling, new-chat subagent polling, deferred tool options, and
  bounded title fallback. Revalidate them when upgrading the base image.

## Verify

The public customer skill source is now `skills/scientific-ai`; it includes the
clinical helpers. No private GitHub access or vendoring is required to build.
Earlier v61 images included ten private upstream infrastructure skills; those
are optional operator extensions, not part of this public skills release.

```bash
python3 skills/scientific-ai/bundle.py verify
curl -fsS 'https://<librechat-host>/health'
python -m pytest templates/hcls-librechat/tests.py templates/hcls-librechat/test_structure_viewer.py -q
docker build --target scientific-client -t scientific-client-check \
  -f templates/hcls-librechat/Dockerfile .
docker run --rm --entrypoint /app/node_modules/.bin/tsc \
  scientific-client-check --noEmit -p /app/client/tsconfig.json
```

Verify login, all six cards, Apps discovery for the signed-in key, operation
tracking and reconnect, workspace read/write/download, chat-model switching,
provider-key setup, scientific discovery, one semantic run, literature search,
mobile/dark layout and console errors.
OpenAI/Claude inference requires valid credentials: testing setup UI alone is not
an inference acceptance test. Browser CLI checks are in `scripts/browser-smoke.js`
and `scripts/viewer-browser-smoke.js`; the latter requires an existing chat
containing a real viewer result and does not submit compute.
See [the original review](UX-REVIEW-20260909.md) and
[the event/viewer follow-up](EVENT-REVIEW-20260909.md).
