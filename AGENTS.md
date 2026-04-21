# Agent instructions

This file follows the cross-vendor [AGENTS.md](https://agents.md) convention and is intended for any AI coding agent that reads agent instructions from repo root — including [Claude Code](https://claude.com/claude-code), [OpenAI Codex CLI](https://github.com/openai/codex), [Cursor](https://cursor.sh), [Aider](https://aider.chat), and similar tools.

## What this repo is

`serverless-ai-cookbook` is a collection of runnable examples for [Nebius Serverless AI](https://docs.nebius.com/serverless/overview) — GPU workloads as serverless jobs and HTTP endpoints. Examples cover training, fine-tuning, inference serving, AI agents, and scientific simulations.

## Playbooks (skills)

The `skills/` folder contains self-contained Markdown playbooks for every major Nebius Serverless AI workflow. When a user asks you to perform a task in any of the areas below, **read the matching playbook before acting** — each encodes the non-obvious gotchas, correct flag sets, and end-to-end command chains.

| Task area | Playbook |
|---|---|
| Submit, monitor, debug, SSH into `nebius ai job` | [`skills/nebius-serverless-job/SKILL.md`](./skills/nebius-serverless-job/SKILL.md) |
| Deploy and manage `nebius ai endpoint` (model serving) | [`skills/nebius-serverless-endpoint/SKILL.md`](./skills/nebius-serverless-endpoint/SKILL.md) |
| Build and push container images to Nebius Container Registry | [`skills/nebius-container-registry/SKILL.md`](./skills/nebius-container-registry/SKILL.md) |
| Auth (CI service accounts), MysteryBox secrets, volumes, async operations | [`skills/nebius-serverless-platform/SKILL.md`](./skills/nebius-serverless-platform/SKILL.md) |
| End-to-end recipes: training, serving, CI/CD, debugging, preemptible | [`skills/nebius-serverless-recipes/SKILL.md`](./skills/nebius-serverless-recipes/SKILL.md) |

Each playbook is also reachable via its sibling `AGENTS.md` file (symlinked to `SKILL.md`) for agents that enumerate `AGENTS.md` in every subdirectory.

## Non-obvious facts worth knowing up front

These are documented in detail in the playbooks; listed here so they're visible to any agent skimming this file.

- **`nebius ai job logs` defaults `--since` to 1 hour.** A job that finished more than an hour ago produces zero output unless you widen the window. Always pass `--since 24h` (or longer) when reading historical logs.
- **Serverless AI GPU hosts are x86_64.** Always build container images with `--platform linux/amd64`, even on Apple Silicon.
- **Registry image paths use the short registry ID**, not the `registry-<id>` form. Strip the `registry-` prefix when constructing image URLs.
- **`--subnet-id` is required on `job create` / `endpoint create`** if the project has more than one subnet.
- **Endpoints have no in-place update.** To change the image, env, port, or auth, `delete` + `create`. The ID and public IP change.
- **Multi-node distributed training is not supported on Serverless AI.** Use Soperator/Managed Slurm or Managed Kubernetes for that.
- **Post-mortem SSH is impossible** (the VM is destroyed on terminal state). Append `|| sleep 3600` to the entrypoint of a failing job to keep it alive for debugging.

## Operating conventions for agents

- **Use `--dry-run`** on `nebius ai job create` / `endpoint create` in CI or when uncertain — it validates the spec server-side without spending GPU time.
- **Don't paste job IDs, image tags, subnet IDs, or project IDs into commits or PR descriptions** that will be pushed to public history. Use placeholders in examples.
- **Prefer `--token-secret` / `--env-secret` / `--registry-secret`** over inline `--token` / `--env` / `--registry-password` whenever the value is sensitive; the `nebius-serverless-platform` skill covers MysteryBox setup.
- **If a job is stuck in `QUEUED`**, it's a capacity issue for that platform/preset in that region — not a config bug. Suggest `--preemptible` or a different preset/region.

## Repo-level context

- Language: Python (examples), Dockerfiles, bash.
- Package manager in Python examples: **`uv`** (fast, lockfile-based). Prefer `uv pip install` over pip directly.
- License: Apache 2.0.
- Contributing guide: [`CONTRIBUTING.md`](./CONTRIBUTING.md). Developer guide: [`DEVELOPER_GUIDE.md`](./DEVELOPER_GUIDE.md).

## If you're Claude Code

You'll auto-discover the skills in `skills/` via project-level skill detection. The YAML frontmatter in each `SKILL.md` controls trigger phrases and tool allowlists; load the full file when a trigger matches.

## If you're another agent

Treat the `skills/<name>/SKILL.md` files as plain markdown playbooks. The YAML frontmatter block at the top (between `---` markers) is Claude Code metadata — you can skip it. The body is vendor-neutral.
