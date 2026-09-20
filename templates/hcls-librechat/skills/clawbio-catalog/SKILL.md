---
name: clawbio-catalog
description: Discover the installed, pinned ClawBio analysis skills, their local CPU or hosted-model execution path, dependencies and measured qualification. Use for choosing a bioinformatics workflow; not for an unconfigured ClawBio MCP server.
license: MIT
---

# ClawBio on Scientific AI

Use the existing environment-execution tools. There is no separate ClawBio MCP
server. List the actual installed selection:

```bash
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py list
/opt/clawbio-venv/bin/python /opt/clawbio/runner.py describe analyze-fasta
```

Load only the relevant `clawbio-<name>` skill and its upstream method reference.
Local CPU workflows use the isolated ClawBio Python environment. Structure
prediction, Cellpose and scVI/scANVI are routed to authorized hosted Apps through
existing Scientific AI skills and live schemas, not locally installed GPU models.

Installation, demo execution, scientific validity and customer readiness are
different claims. Check the manifest's qualification before making any claim.
Missing external binaries, reference data or an App grant are explicit blockers.
Never claim a synthetic demo analyzed the user's data. Some annotation tools send
variants or gene lists to external public APIs; consult the bundled data-handling
document before processing non-public data.

Stage analysis on local disk and export completed, verified outputs to the user's
bucket using the existing workspace tools. `/data` is temporary; `/workspace`
is durable Object Storage and is not a general POSIX analysis filesystem.

The complete selection, exclusions and pinned source are in the image at
`/opt/clawbio/manifest.json`. No upstream bot, shared hackathon API key, or
unconfigured hosted service is installed by this integration.
