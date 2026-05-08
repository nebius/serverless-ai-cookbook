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
| T9  | `<this commit>` | Pipeline `Dockerfile` written (FROM `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1`, install Python 3 + uv-pinned boto3, copy `pipeline/`, ENTRYPOINT `python3 -m pipeline.cli`, runs as root with documented rationale). **Image build was at ~700 MB / 4.37 GB pull when interrupted — not yet smoke-tested locally.** |
| T10 | `58933bf` | `scripts/run_nvidia_tutorial.sh` (Mode A) — three tutorials (get-sample-data / fq2bam / haplotypecaller), NGC inline auth default + MysteryBox `--registry-secret` alternative, `--help` works, shellcheck clean (one justified `SC2016` disable for the literal `'$oauthtoken'` username). |
| T11 | `f400925` | `scripts/stage_demo_data.sh` — submits a CPU-only Nebius AI Job that downloads GRCh38 reference + HG002 FASTQ from public buckets into the customer's S3 bucket. |
| T12 | `30ae089` | `scripts/run_serverless.sh` (Mode B) — wraps `nebius ai job create` with all the env vars `pipeline.cli` requires; defaults `gpu-h200-sxm` / `1gpu-16vcpu-200gb` / `500Gi`. |
| T13 | `1c8c7e4` | `qa/validate.py` + `qa/__init__.py` + `tests/test_validate.py` — fetches GIAB v4.2.1 truth from NIH at runtime, downloads customer's VCF from S3, runs `hap.py`, parses summary, gates SNP F1 ≥ 0.999. **Suite: 28 tests, ruff clean.** |
| T14 (partial) | `<this commit>` | QA `Dockerfile` written. **Plan/spec corrected:** original `pkrusche/hap.py:v0.3.15` does not exist on Docker Hub and pkrusche's available tags use a deprecated manifest format that modern Docker refuses to pull. Swapped to `quay.io/biocontainers/hap.py:0.3.15--py27hcb73b3d_0` (BioContainers/Bioconda — verified pullable, modern manifest). New Dockerfile uses a Python 3 venv at `/opt/qa-venv` to avoid colliding with the conda env hap.py runs in. **Build never attempted.** |
| Spec | (gitignored) | Spec + plan revised to add **RTX6000 Ada** to the SKU verification matrix. v1 now requires bench results on **L40S, RTX6000 Ada, H200, B200, B300** (five SKUs). |

## Not done

### Code/docs (autonomous range, blocked only by tooling)

- **T9 finish:** Build pipeline image locally (`docker build -t parabricks-deepvariant:dev life-science/parabricks-deepvariant/`) and run two smoke tests (entrypoint imports + missing-env-var error). Cache from the interrupted ~700 MB pull should make resumption faster.
- **T14 finish:** Build QA image (`docker build -t parabricks-qa:dev life-science/parabricks-deepvariant/qa/`) and smoke-test entrypoint.
- **T15:** `scripts/run_qa.sh` — wraps `nebius ai job create` for the QA validation submission.
- **T16:** `bench/run_bench.sh` — submits a Mode B run, polls completion, pulls `run_metadata.json` from S3, renders Markdown to `bench/results/<date>-<sku>.md`.
- **T17:** Recipe `README.md` (the customer-facing surface; ~400–500 lines mirroring `life-science/openmm-simulation/README.md`).
- **T18:** Top-level cookbook `README.md` row under "Life Science".
- **T19:** Final lint + test gate (rebuild both images, full pytest, ruff, shellcheck on all scripts).

### Real-world (require Rene Schönfelder)

- **T20:** `docker tag` + `docker push` pipeline + QA images to Nebius Container Registry.
- **T21:** Run `scripts/stage_demo_data.sh` against Rene's bucket (~10–40 min one-shot).
- **T22:** Mode A H200 smoke test (catches NGC auth + `bash -c` quoting issues before SKU matrix burns time).
- **T23–T26 + T23b:** End-to-end Mode B + QA + bench commit on **L40S, RTX6000 Ada, H200, B200, B300** (five SKUs, ~3–5 hours total wall time of real Nebius GPU compute).
- **T27:** `gh pr create` after STATUS.md is removed.

## Resume from here

1. `cd life-science/parabricks-deepvariant && docker build -t parabricks-deepvariant:dev .` (cached layers should resume the NGC pull quickly).
2. `cd qa && docker build -t parabricks-qa:dev .` (BioContainers base, ~3–5 min total).
3. `docker run --rm --entrypoint python3 parabricks-deepvariant:dev -c "from pipeline import cli; print('ok')"` (expect `ok`).
4. `docker run --rm parabricks-qa:dev || true` (expect non-zero exit with `Missing required environment variable: ...`).
5. Continue with T15.
