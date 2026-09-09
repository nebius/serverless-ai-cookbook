---
name: nebius-infrastructure-prep
description: Apply the ten installed Nebius infrastructure skills to a hackathon compute plan and prepare a participant-side MCP setup handoff. Use for workload architecture, cloud readiness and choosing the relevant compute or Serverless skills.
---

# Nebius infrastructure preparation

This hosted scientific workspace includes the official Nebius infrastructure
skills and their reference files. Load the relevant skills to prepare a concrete
infrastructure project, configuration, commands and benchmark plan. It is not
connected to the participant's Nebius cloud account and has no
local terminal for that account. The scientific-model gateway and Token Factory
credentials are not credentials for the participant's cloud project.

Ask only for the details needed: workload, success metric, operating system,
local coding agent, account readiness, intended region and budget. Never request
tokens, private keys, CLI configuration files or identifiable patient records.

## Account and MCP handoff

Use the official installation guide as the source of truth:
https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md

Offer this copyable prompt for the participant's **local coding agent**:

> Fetch and follow the installation guide: https://github.com/nebius/mcp-server/blob/main/AGENT_SETUP.md

The guide inspected on 2026-09-09 requires Python 3.13+, uv/uvx, Nebius CLI
0.12.65 or newer, and a usable participant-owned CLI profile. The CLI runs on
macOS/Linux; native Windows users need WSL2 Ubuntu. Recheck the current guide
before providing installation commands. Tailor the handoff to their actual
client instead of copying a different client's configuration.

The participant authenticates interactively on their own machine and chooses
their own tenant/project. Keep `SAFE_MODE=true`. Preserve existing local MCP
configuration; do not replace the entire configuration file. Restart the local
agent after setup, inspect connection status, and begin with read-only discovery
such as available compute platforms or an inventory in the chosen project.
Listing a configured MCP server alone does not prove an authenticated connection.

The public server README describes safe-mode restrictions:
https://github.com/nebius/mcp-server
Do not suggest disabling safe mode to finish a tutorial. A plan or setup handoff
does not authorize provisioning, deletion, paid benchmarks or account changes.
Do not install this MCP server into the shared hosted app or borrow operator
cloud credentials. Report the handoff as **prepared, not connected** until the
participant verifies it locally.

## Nebius skills

Official source: https://github.com/nebius/skills

The following official skills and their supporting files are installed in this
deployment, pinned to revision `292c7e65a46d0c29994d2babfc19da129d16fa62`:

| Skill | Use it here for |
| --- | --- |
| `nebius-cloud-basics` | CLI setup, profiles, project context and command structure |
| `nebius-compute-inventory` | Preparing resource discovery and interpreting participant-provided inventory |
| `nebius-capacity-quotas` | Planning capacity/quota checks for a chosen workload |
| `nebius-compute-provision` | VM, disk and GPU configuration templates |
| `nebius-serverless-setup` | Explaining participant-side authentication setup |
| `nebius-serverless-jobs` | A bounded batch-job configuration and timeout |
| `nebius-serverless-endpoints` | Container serving, health checks and endpoint configuration |
| `nebius-serverless-data-secrets` | Storage mounts and secret references |
| `nebius-serverless-troubleshooting` | Diagnosing provided status and redacted logs |
| `nebius-serverless-recipes` | Training, inference and batch workflow recipes |

Load `nebius-cloud-basics` and the task-specific skill. Read its attached
references or assets when preparing commands. The CLI instructions describe
execution in the participant's connected environment; they do not establish a
terminal or cloud connection in this hosted chat. Use Tavily to check current
official documentation and return useful configurations or handoffs rather than
stopping at “you need to install skills.” Local installation is needed only if
the participant wants the same skills in a separate coding agent. Source-repo
access may still require organizer access; it is not needed to use the bundled
skills here. Skill instructions do not authenticate a cloud account.

## Useful output here

Help define the smallest demonstrable longevity-compute workload, its input
data requirements, deployment shape and evaluation plan. Separate measured
results from targets. Specify reproducible inputs, baseline, throughput/latency,
failure rate, approximate cost assumptions and a cleanup owner. Check current
official documentation for prices and region availability instead of inventing
quota or GPU availability. Leave actual execution to the participant's connected
local environment, with their explicit approval and budget.
