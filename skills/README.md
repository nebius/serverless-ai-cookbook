# Claude Code skills for Nebius Serverless AI

This folder ships [Claude Code](https://claude.com/claude-code) **skills** — markdown playbooks that teach Claude how to drive Nebius Serverless AI correctly from the first turn. When one of these skills is installed, asking Claude to "run a GPU job", "push my image to Nebius", or "serve this model as an endpoint" triggers the right CLI commands with the right flags, and warns you about the traps the docs don't spell out.

## What's a skill?

A skill is a directory containing a `SKILL.md` file with YAML frontmatter (name, description, allowed tools) and a markdown body. Claude Code auto-discovers skills from:

- `~/.claude/skills/` — user-level, available in every project
- `.claude/skills/` — project-level, shipped with a repo

Claude matches the user's request against every skill's `description` field and loads the full `SKILL.md` when a skill fires. More: [Claude Code docs → Skills](https://docs.claude.com/en/docs/claude-code/skills).

## Skills in this folder

| Skill | What it covers |
|---|---|
| [`nebius-serverless-job`](./nebius-serverless-job/SKILL.md) | The full `nebius ai job` surface: submit, monitor, logs, cancel, SSH, async ops. Bakes in the hard-won gotchas — the `--since 1h` log default, `--subnet-id` requirement, `linux/amd64` platform trap, the `\|\| sleep 3600` post-mortem SSH trick, preemptible + restart-policy pairing. |
| [`nebius-serverless-endpoint`](./nebius-serverless-endpoint/SKILL.md) | The full `nebius ai endpoint` surface: lifecycle, auth modes (`none` / `token` / `token-secret`), the **no in-place update** caveat, single-replica reality, a full vLLM serving recipe, and A/B + rolling-update patterns. |
| [`nebius-container-registry`](./nebius-container-registry/SKILL.md) | Build + push images the registry accepts: the short-ID path format (`cr.<region>.nebius.cloud/<short-id>/...`), mandatory `linux/amd64`, `docker buildx --push`, IAM-token login, private-pull auth via `--registry-secret` + MysteryBox, `docker manifest inspect` verification. |
| [`nebius-serverless-platform`](./nebius-serverless-platform/SKILL.md) | Cross-cutting infrastructure: interactive and non-interactive (service-account) auth, project/subnet discovery, MysteryBox secrets (`env-secret` / `token-secret` / `registry-secret`), volume types (bucket vs filesystem vs external S3), `--shm-size` defaults, disk sizing, async operations, `--dry-run` validation, pricing pointers. |
| [`nebius-serverless-recipes`](./nebius-serverless-recipes/SKILL.md) | Nine end-to-end playbooks from scratch: one-GPU training, multi-GPU single-node, vLLM serving, batch inference fan-out, fine-tuning with checkpoints, GitHub Actions CI/CD, debugging a failing job, preemptible cost-optimization, and spec validation. |

## Install

Copy (or symlink) the skills you want into your Claude Code skills directory.

### User-level (available in every project)

```bash
cp -r skills/nebius-* ~/.claude/skills/
# or to symlink so updates stay live:
ln -s "$PWD/skills"/nebius-* ~/.claude/skills/
```

### Project-level (ships with a repo)

```bash
mkdir -p .claude/skills
cp -r skills/nebius-* .claude/skills/
```

Verify Claude Code sees them — start a session in any directory and ask something like:

> "Why is `nebius ai job logs` returning nothing for a job I ran yesterday?"

The `nebius-serverless-job` skill should fire and Claude should tell you about the `--since 1h` default before you finish reading the question.

## Scope & limits

- **Built for `nebius ai job` and `nebius ai endpoint`** — the two workload primitives of Serverless AI. Multi-node distributed training is called out as not supported (use Soperator/Managed Slurm or Managed Kubernetes).
- **Not a replacement for the docs.** Every skill links the canonical page on `docs.nebius.com` for the surface it covers.
- **Facts the docs don't spell out are marked** — e.g. single-replica endpoints, no in-place endpoint update, CLI log retention, the post-mortem SSH trick. These come from hands-on use, not proto files.
- **Claude-invoked, not user-invoked** — skills trigger from natural-language requests; you don't need to type `/skill-name`. All tool allowlists are narrowly scoped (`Bash(nebius *)`, `Bash(docker *)`, `Bash(curl *)`) so a skill firing never auto-approves arbitrary shell.

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
