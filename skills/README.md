# Agent playbooks for Nebius Serverless AI

This folder ships **agent playbooks** — markdown documents that teach any AI coding agent how to drive Nebius Serverless AI correctly from the first turn. When one of these playbooks is available, asking the agent to "run a GPU job", "push my image to Nebius", or "serve this model as an endpoint" triggers the right CLI commands with the right flags, and warns you about the traps the docs don't spell out.

They work as:

- **Claude Code skills** — auto-discovered and auto-triggered when installed as `~/.claude/skills/<name>/` or `.claude/skills/<name>/`. The YAML frontmatter in each `SKILL.md` controls trigger phrases and tool allowlists.
- **Cross-vendor agent playbooks** — any tool that follows the [AGENTS.md](https://agents.md) convention (OpenAI Codex CLI, Cursor, Aider, and others) picks them up via the repo-root [`AGENTS.md`](../AGENTS.md) and the per-skill `AGENTS.md` files (symlinked to `SKILL.md` — single source of truth).

The markdown bodies are vendor-neutral: CLI snippets, flag tables, end-to-end recipes, and failure-modes tables. The Claude-specific YAML frontmatter at the top of each `SKILL.md` is harmless to other tools — skip it.

## Structure

Each playbook is a directory containing:

```
<name>/
├── SKILL.md       # Full playbook. YAML frontmatter is Claude-specific; body is vendor-neutral.
└── AGENTS.md      # Symlink to SKILL.md, for tools that enumerate AGENTS.md per directory.
```

Claude Code auto-discovers from `~/.claude/skills/` or `.claude/skills/`. Other agents find the content via the repo-root [`AGENTS.md`](../AGENTS.md) or by reading the skill directories directly.

## Skills in this folder

| Skill | What it covers |
|---|---|
| [`nebius-serverless-job`](./nebius-serverless-job/SKILL.md) | The full `nebius ai job` surface: submit, monitor, logs, cancel, SSH, async ops. Bakes in the hard-won gotchas — the `--since 1h` log default, `--subnet-id` requirement, `linux/amd64` platform trap, the `\|\| sleep 3600` post-mortem SSH trick, preemptible + restart-policy pairing. |
| [`nebius-serverless-endpoint`](./nebius-serverless-endpoint/SKILL.md) | The full `nebius ai endpoint` surface: lifecycle, auth modes (`none` / `token` / `token-secret`), the **no in-place update** caveat, single-replica reality, a full vLLM serving recipe, and A/B + rolling-update patterns. |
| [`nebius-container-registry`](./nebius-container-registry/SKILL.md) | Build + push images the registry accepts: the short-ID path format (`cr.<region>.nebius.cloud/<short-id>/...`), mandatory `linux/amd64`, `docker buildx --push`, IAM-token login, private-pull auth via `--registry-secret` + MysteryBox, `docker manifest inspect` verification. |
| [`nebius-serverless-platform`](./nebius-serverless-platform/SKILL.md) | Cross-cutting infrastructure: interactive and non-interactive (service-account) auth, project/subnet discovery, MysteryBox secrets (`env-secret` / `token-secret` / `registry-secret`), volume types (bucket vs filesystem vs external S3), `--shm-size` defaults, disk sizing, async operations, `--dry-run` validation, pricing pointers. |
| [`nebius-serverless-recipes`](./nebius-serverless-recipes/SKILL.md) | Nine end-to-end playbooks from scratch: one-GPU training, multi-GPU single-node, vLLM serving, batch inference fan-out, fine-tuning with checkpoints, GitHub Actions CI/CD, debugging a failing job, preemptible cost-optimization, and spec validation. |

## Install

### Claude Code

Copy (or symlink) the skills into your Claude Code skills directory.

```bash
# User-level (available in every project)
cp -r skills/nebius-* ~/.claude/skills/
# or symlink so updates stay live:
ln -s "$PWD/skills"/nebius-* ~/.claude/skills/

# Project-level (ships with a specific repo)
mkdir -p .claude/skills
cp -r skills/nebius-* .claude/skills/
```

Verify: start a session and ask "why is `nebius ai job logs` returning nothing for a job I ran yesterday?" — the `nebius-serverless-job` skill should fire and explain the `--since 1h` default before you finish reading the question.

### OpenAI Codex CLI, Aider, and other AGENTS.md-aware tools

These tools read [`AGENTS.md`](../AGENTS.md) at repo root automatically. No install step — just clone or `cd` into a repo that has this folder. The root file points them at the right per-task playbook.

### Cursor

Cursor reads project rules from `.cursor/rules/`. The simplest integration is a single pointer rule that references this folder:

```bash
mkdir -p .cursor/rules
cat > .cursor/rules/nebius-serverless.mdc <<'EOF'
---
description: Nebius Serverless AI playbooks
globs: ["**/*"]
alwaysApply: false
---

For any task involving Nebius Serverless AI (`nebius ai job`, `nebius ai endpoint`, container registry, model serving, training), consult the playbooks in `skills/`:

- Jobs: skills/nebius-serverless-job/SKILL.md
- Endpoints: skills/nebius-serverless-endpoint/SKILL.md
- Container registry: skills/nebius-container-registry/SKILL.md
- Auth / secrets / volumes: skills/nebius-serverless-platform/SKILL.md
- End-to-end recipes: skills/nebius-serverless-recipes/SKILL.md
EOF
```

### GitHub Copilot

Copilot reads `.github/copilot-instructions.md`. Add a one-liner pointer:

```bash
mkdir -p .github
cat > .github/copilot-instructions.md <<'EOF'
For Nebius Serverless AI tasks, read the relevant playbook under `skills/` (see `AGENTS.md` at repo root for the index).
EOF
```

### Any other agent

If your tool supports a "read this file before acting" convention, point it at the repo-root [`AGENTS.md`](../AGENTS.md). If not, the per-skill markdown files are self-contained — they work as standalone reference docs.

## Scope & limits

- **Built for `nebius ai job` and `nebius ai endpoint`** — the two workload primitives of Serverless AI. Multi-node distributed training is called out as not supported (use Soperator/Managed Slurm or Managed Kubernetes).
- **Not a replacement for the docs.** Every skill links the canonical page on `docs.nebius.com` for the surface it covers.
- **Facts the docs don't spell out are marked** — e.g. single-replica endpoints, no in-place endpoint update, CLI log retention, the post-mortem SSH trick. These come from hands-on use, not proto files.
- **Agent-invoked, not user-invoked** — playbooks trigger from natural-language requests; you don't need to type `/skill-name`. For Claude Code, tool allowlists are narrowly scoped (`Bash(nebius *)`, `Bash(docker *)`, `Bash(curl *)`) so a skill firing never auto-approves arbitrary shell. Other agents apply their own permission models.

## Maintenance

The Nebius CLI and API evolve. When something in a skill drifts from reality:

1. Fix the skill body (and the failure-modes table if new symptoms appear).
2. Update the `description:` field if the skill now covers a new trigger phrase.
3. PRs welcome — each skill's markdown is self-contained, so changes are small and reviewable.

## Reference

- Nebius Serverless AI overview: https://docs.nebius.com/serverless/overview
- Nebius CLI reference: https://docs.nebius.com/cli/reference/ai/
- Nebius API (proto): https://github.com/nebius/api/tree/main/nebius/ai/v1
- Claude Code skills docs: https://docs.claude.com/en/docs/claude-code/skills
