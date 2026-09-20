# Scientific AI skills

One customer-facing source for the Nebius Scientific AI workbench and other
MCP-compatible agents. LibreChat installs this exact directory at `/app/skill`.
Skills teach the **hosted** APIs; they do not deploy NVIDIA services, grant model
access, or install an entire workbench on a customer's computer.

## Install a release

Download the `scientific-ai-skills-*.tar.gz` and `SHA256SUMS` assets from
[Releases](https://github.com/rene-tech/serverless-ai-cookbook/releases).
Verify the checksum and extract the archive. From its `scientific-ai` directory:

```bash
python3 bundle.py verify
python3 bundle.py install --dest /absolute/path/to/your/agents/skills
```

Choose the destination documented by your agent (for example its project skills
directory). Nothing auto-installs globally. An identical install is a no-op;
conflicting existing skills are reported without overwrite. For upgrades, use
a new versioned destination and switch the client after verification. Restart
or reload the client's skills. Configure your Scientific AI MCP URL and user API
key through its normal secret configuration, never in a skill or chat message.

You can also check out a pinned `scientific-ai-skills-*` tag and run the same
commands from `skills/scientific-ai`. `main` is the integrated development source;
a release tag and checksummed asset are the reproducible installation.

## Coverage

`manifest.json` maps all 37 catalog Apps observed on 2026-09-20 to workflow skills
and records the reviewed upstream revisions. Eight new workflows cover speech,
clinical ASR evaluation, single-cell integration, microscopy, SAM2, binder
campaigns, starter data and MindEval. Existing clinical documentation and all
scientific model skills are included with their scripts/references.

Start with `scientific-gateway`; load only skills relevant to your task. For
non-LibreChat clients, see its [portable client contract](scientific-gateway/references/portable-client.md).
Client-specific tools are conditional, not promised by downloading Markdown.
Private upstream Nebius infrastructure skills are optional operator extensions
and are not redistributed here. Adapted NVIDIA guidance is attributed in
[NOTICE.md](NOTICE.md), not advertised as an unmodified NVIDIA-verified package.

## Maintain and qualify

Every model onboarding must update the model-to-skill map and supply meaningful
workflow guidance or an explicit existing route. Test examples against the exact
model contract, include failure/recovery expectations, and preserve evidence
bound to source, client and runtime. Do not add a model by editing a second skill
tree or copying upstream deployment commands into the hosted customer workflow.

```bash
python3 -m pytest tests clinical-documentation/scripts -q
python3 bundle.py lock
python3 bundle.py verify
python3 bundle.py check-catalog
python3 bundle.py build --output /absolute/release-output
```

Run the affected workbench tests from the repository root as well. `lock` updates
the release file inventory after intentional edits; it is not a test. This
release tests instruction contracts, deterministic helpers and installation.
It does not newly certify scientific accuracy or all model/GPU/snapshot modes.
See [RELEASE.md](RELEASE.md) for measured results and remaining gaps.

Historical templates still contain archived upstream/vendor skill copies. Do
not bulk-install every skill found anywhere in this repository; install this
explicit path or the release asset so there is only one active definition.
