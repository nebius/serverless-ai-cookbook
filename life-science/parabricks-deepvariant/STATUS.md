# Parabricks DeepVariant Recipe — Implementation Status

Working notes for the in-progress `feature/parabricks-deepvariant` branch. **Remove this file before opening the PR (Task 27).**

Spec: `docs/superpowers/specs/2026-05-08-parabricks-on-nebius-design.md` (gitignored, local only).
Plan: `docs/superpowers/plans/2026-05-08-parabricks-on-nebius.md` (gitignored, local only).

## Done

| Plan | Commit(s) | Summary |
|---|---|---|
| T1  | (no commit) | Tooling verified: uv 0.11.11, shellcheck 0.11, docker 28.1, python 3.14, pytest. |
| T2  | `ca9e928` | Recipe scaffold: `pyproject.toml`, `uv.lock`, `.gitignore`, `.dockerignore`, `pipeline/__init__.py`, `tests/{__init__.py, conftest.py}` (with `s3_env` fixture), `qa/.gitkeep`, `scripts/.gitkeep`, `bench/results/.gitkeep`. |
| T3  | `8df331b` | `pipeline/stage.py`: `make_client()` boto3 factory with env-driven kwargs and fail-fast on missing endpoint. |
| T4  | `49c75e7` | `pipeline/stage.py`: `download_file()` with parent-directory creation. |
| T5  | `4719624` | `pipeline/stage.py`: `download_prefix()` + `upload_prefix()` (paginator-based recursive helpers). |
| T6  | `74c8572` | `pipeline/run.py`: `build_pbrun_command()` and `run_germline()` orchestrator (download ref + FASTQ → invoke pbrun → upload outputs; non-zero pbrun exit propagates). |
| T7  | `023be96` | `pipeline/run.py`: `emit_metadata()` parses `nvidia-smi --query-gpu=name` and `pbrun --version`; writes `run_metadata.json` (sample_id, wall_clock_seconds, gpu_name, parabricks_version) before upload. |
| T8  | `226d61b` | `pipeline/cli.py`: `validate_env()` against 9 required env vars + `main()` dispatch. Full pipeline module: 21 tests, ruff clean. |
| Fix | `8ca6b61` | FASTQ glob broadened to match `.R1.fq.gz` / `_R1.fq.gz` / `.fastq.gz`; `S3_OUTPUT_PREFIX` trailing slash no longer produces `bucket/prefix//sample/`. **Pipeline module: 24 tests, ruff clean.** |
| T9  | `<pending>` | Pipeline `Dockerfile` written (FROM `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`, install Python 3 + uv-pinned boto3, copy `pipeline/`, ENTRYPOINT `python3 -m pipeline.cli`, runs as root with documented rationale). Local image build succeeded from cached NGC base as `parabricks-deepvariant:dev`; smoke checks passed (`pipeline` import, missing-env failure, `pbrun --version` = `4.7.0-1`). Clean-cache pulls still require NGC auth/login; `~/.docker/config.json` has no `nvcr.io` auth. |
| T10 | `58933bf` + pending edits | `scripts/run_nvidia_tutorial.sh` (Mode A) — three tutorials now self-contain data download in each ephemeral job, NGC inline auth default + MysteryBox `--registry-secret`, optional `PARENT_ID`/`SUBNET_ID`, `--help` works, shellcheck clean. |
| T11 | `f400925` + pending edits | `scripts/stage_demo_data.sh` submits a CPU-only Nebius AI Job to stage GRCh38 reference + HG002 35x FASTQ; optional `PARENT_ID`/`SUBNET_ID`; no xtrace secret leakage. Public source URLs were checked with HTTP 200 responses. |
| T12 | `30ae089` + pending edits | `scripts/run_serverless.sh` wraps `nebius ai job create` with all `pipeline.cli` env vars; optional `PARENT_ID`/`SUBNET_ID`; no xtrace secret leakage. |
| T13 | `1c8c7e4` + pending edits | `qa/validate.py` + tests fetch GIAB v4.2.1 truth and GRCh38 reference at runtime, strip trailing output-prefix slashes, pass `-r` to `hap.py --engine=vcfeval`, parse summary, and gate SNP F1 ≥ 0.999. |
| T14 | `<pending>` | QA `Dockerfile` fixed and built locally as `parabricks-qa:verify`. It copies BioContainers hap.py into `python:3.11-slim-bookworm`, installs pinned boto3 deps from `qa/requirements.txt`, uses Python 3 for `validate.py`, and routes `hap.py` through the bundled Python 2 runtime. Smoke checks: missing-env failure, Python 3 `boto3` import, and `hap.py --version`. |
| T15 | `<pending>` | `scripts/run_qa.sh` added: CPU-only QA submission with `QA_IMAGE`, S3 envs, optional `PARENT_ID`/`SUBNET_ID`, `--help`, and no xtrace secret leakage. Shellcheck clean. |
| T16 | `<pending>` | `bench/run_bench.sh` added: wraps `run_serverless.sh`, requires `PARENT_ID` for `get-by-name`, polls with visible CLI errors, fetches `run_metadata.json` with AWS CLI, writes `bench/results/<date>-<sku>.md`, and has `--help`. Shellcheck clean. |
| T17 | `<pending>` | Customer README added with Mode A/Mode B walkthroughs, NGC inline-vs-MysteryBox auth, working-directory guidance, Container Registry auth links, staging/build/submit/inspect flows, GPU guidance, QA, benchmarking, and troubleshooting. External links checked. |
| T18 | `<pending>` | Top-level cookbook `README.md` links the Parabricks DeepVariant recipe under Life Science. |
| T19 (partial) | (no commit) | Local dev gate passed: `uv run pytest -v` (29 passed), `uv run ruff check .`, `shellcheck scripts/*.sh bench/*.sh`, `git diff --check`, QA Docker build + smoke, and cached pipeline Docker build + smoke. Runtime bench flow is not smoke-tested because AWS CLI and real Object Storage credentials are missing. |
| Spec | (gitignored) | Spec + plan revised to add **RTX6000 Ada** to the SKU verification matrix. v1 now requires bench results on **L40S, RTX6000 Ada, H200, B200, B300** (five SKUs). |

## Not done / blocked

### Code/docs

- Fresh pipeline image pulls require NGC registry auth/login. The current workstation can rebuild from cached layers, but `~/.docker/config.json` has no persisted `nvcr.io` auth, so a clean environment still needs `NGC_API_KEY` or equivalent Docker auth.
- `bench/run_bench.sh` runtime also requires AWS CLI; it is not installed on this workstation (`command -v aws` returned empty). Static lint is clean, but an actual metadata download was not smoke-tested.

### Real-world (require Rene Schönfelder authorization / credentials)

- **T20:** `docker tag` + `docker push` pipeline + QA images to Nebius Container Registry.
- **T21:** Run `scripts/stage_demo_data.sh` against Rene's bucket (~10–40 min one-shot).
- **T22:** Mode A H200 smoke test (NGC auth + `bash -c` quoting validation).
- **T23–T26 + T23b:** End-to-end Mode B + QA + bench commit on **L40S, RTX6000 Ada, H200, B200, B300** (paid Nebius GPU jobs).
- **T27:** `gh pr create` after `STATUS.md` is removed.

## Resume from here

1. Provide local NGC auth so the pipeline image can be rebuilt from a clean cache, not only from this workstation's cached base.
2. Install/configure AWS CLI if `bench/run_bench.sh` will be run locally.
3. Provide Object Storage bucket/keys, NGC auth or MysteryBox selector, Container Registry target refs, and explicit approval to spend Nebius GPU time.
4. Push images and run the real Nebius staging/tutorial/QA/benchmark jobs.
