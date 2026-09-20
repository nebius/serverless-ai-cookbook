---
name: clawbio-catalog
description: Discover the installed ClawBio bioinformatics skills and their local CPU or hosted-model execution path, dependencies and measured qualification. Check runtime availability before choosing or running a workflow.
license: Apache-2.0 AND CC-BY-4.0
---

# ClawBio on Scientific AI

ClawBio is optional: downloading this public skill bundle does not install its
runtime, upstream methods or external services. Check the client's installed
skills and local execution capability first. If `clawbio-<name>` skills and the
runner below are absent, explain that gap; do not invent an MCP server or claim
the workflow ran. Older demo-only ClawBio adapters, if separately configured,
remain limited by their actual registered tool schemas.

## ClawBio-enabled LibreChat images

Use the existing environment-execution tools; there is no separate ClawBio MCP
server. List the actual installed selection:

```bash
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py list
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py describe analyze-fasta
```

Load only the relevant `clawbio-<name>` skill and its upstream method reference.
Local CPU workflows use the isolated ClawBio Python environment. Structure
prediction, Cellpose and scVI/scANVI route to authorized hosted Apps through
existing Scientific AI skills and live schemas, not locally installed GPU models.
Use the existing execution job ID to poll long jobs instead of resubmitting them.

Installation, demo execution, scientific validity and customer readiness are
different claims. Check the manifest's qualification before making any claim.
Missing external binaries, reference data or an App grant are explicit blockers.
Never claim a synthetic demo analyzed the user's data. Some annotation tools send
variants or gene lists to external public APIs; consult that skill's bundled
data-handling guidance before processing non-public data.

Stage analysis on local disk and export completed, verified outputs to the user's
bucket using the existing workspace tools. `/data` is temporary; `/workspace`
is durable Object Storage and is not a general POSIX analysis filesystem.

The complete selection, exclusions and pinned source are in the enabled image at
`/opt/clawbio/manifest.json`. No upstream bot, shared API key or unconfigured
hosted service is installed by this integration. Outputs are for research and
education, not validated clinical diagnosis or treatment recommendations.
