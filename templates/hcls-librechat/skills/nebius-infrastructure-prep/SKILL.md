---
name: nebius-infrastructure-prep
description: Prepare a Stockholm hackathon infrastructure project, Nebius skills selection and participant-side MCP setup handoff. Use for cloud-account readiness and infrastructure planning, not for executing cloud changes from this hosted scientific chat.
---

# Nebius infrastructure preparation

This hosted scientific workspace can plan an infrastructure project and explain
setup. It is not connected to the participant's Nebius cloud account and has no
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

This repository required authenticated access when checked on 2026-09-09.
Participants may need organizer-granted access. Do not claim its contents are
public, already installed or enabled unless verified in their environment.
Once they can access it, have their local agent review the repository's current
installation instructions and choose skills relevant to the workload. Skill
instructions do not install an MCP server or authenticate a cloud account.

If access is unavailable, the public MCP guide still provides a setup path.
Do not substitute an unrelated third-party skill pack without asking.

## Useful output here

Help define the smallest demonstrable longevity-compute workload, its input
data requirements, deployment shape and evaluation plan. Separate measured
results from targets. Specify reproducible inputs, baseline, throughput/latency,
failure rate, approximate cost assumptions and a cleanup owner. Check current
official documentation for prices and region availability instead of inventing
quota or GPU availability. Leave actual execution to the participant's connected
local environment, with their explicit approval and budget.
