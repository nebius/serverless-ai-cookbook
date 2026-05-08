# Parabricks on Nebius — Design

**Ticket:** [ARCHVTEAMS-1827](https://nebius.atlassian.net/browse/ARCHVTEAMS-1827) — Parabricks implementation
**Author:** René Schönfelder
**Date:** 2026-05-08
**Status:** Revised 2026-05-08 with implementation decisions: GIAB assets fetched at runtime (not committed), NGC inline auth as default with MysteryBox alternative documented, `BioContainers hap.py copied into a Python 3 QA image, all five target SKUs (L40S, RTX6000 Ada, H200, B200, B300) verified end-to-end as part of v1.

---

## 1. Goal

Make NVIDIA Parabricks runnable on Nebius so customers can execute GPU-accelerated genomics secondary-analysis workflows (alignment + variant calling) on Nebius compute. Strategic, proactive parity with AWS / GCP / Azure / OCI, who all publish Parabricks tutorials. No customer is gating delivery; build it right.

## 2. Non-goals (v1)

- Multi-node Parabricks (it's single-node multi-GPU by design).
- Somatic / Mutect2 / RNA-seq workflows beyond what NVIDIA's tutorials cover.
- Customer-facing UI (no JupyterLab, no web frontend).
- Promotion to the public Nebius Applications marketplace.
- Terraform / Helm / Slurm / VM tracks in `nebius-solutions-library` — replaced by the cookbook approach below.
- A Nebius-mirrored public reference-data bucket.
- A Nebius-published Docker image for Parabricks.

## 3. Constraints (verified)

- **Distribution:** Parabricks 4.7 ships as `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1` on NGC.
- **License:** No fee. NVIDIA AI Enterprise is optional for support.
- **GPU:** CUDA arch 75 / 80 / 86 / 89 / 90 / 100 / 103 / 120 / 121 + ≥16 GB VRAM. Every Nebius SKU (L40S, RTX6000 Ada [arch 89], H100, H200, B200, B300) clears this.
- **Driver:** NVIDIA driver compatible with CUDA 12.9.1.
- **Runtime:** Linux + Docker + NVIDIA Container Toolkit.
- **Topology:** Single-node, multi-GPU within the node.
- **Nebius GPU SKUs:** No A100 offered. L40S and RTX6000 Ada sit at the lower-cost tier; H100 / H200 / B200 / B300 are higher tiers.
- **Repo target:** `github.com/nebius/serverless-ai-cookbook` — the same repo as `life-science/openmm-simulation`.

## 4. High-level approach

A single new recipe folder under `life-science/`, modelled on `life-science/openmm-simulation/`. Two run modes inside one recipe:

- **Mode A — NVIDIA tutorials on Nebius.** Use `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1` directly via `nebius ai job create`. Customer follows NVIDIA's three step-by-step tutorials (`get-sample-data`, `fq2bam`, `haplotypecaller`) verbatim, executing on Nebius L40S/H100/H200/B200. Zero artifacts to maintain on Nebius side.
- **Mode B — Production DeepVariant runs against the customer's own S3 data.** The customer builds a small image (`FROM` NGC + thin Python wrapper for S3 staging), pushes to their Nebius Container Registry, runs `nebius ai job create --image <their-cr>/parabricks-deepvariant:4.7.0-1`. BYO image; no Nebius-hosted artifact.

This matches `nebius ai job create`'s shape exactly: single container, one CLI invocation, single-node GPU, batch, auto-terminates, per-second billing.

## 5. Repository layout

All new files live under `life-science/parabricks-deepvariant/` in `nebius/serverless-ai-cookbook`. One existing file changes: the top-level cookbook `README.md` adds a row under "Life Science".

```
life-science/parabricks-deepvariant/
├── README.md                       # Two-mode walkthrough (see §6)
├── Dockerfile                      # Mode B pipeline image: FROM NGC + boto3 + pipeline/
├── pyproject.toml                  # boto3 (shared by pipeline and qa wrapper)
├── pipeline/                       # Mode B Python wrapper
│   ├── __init__.py
│   ├── stage.py                    # S3 download/upload with retries
│   ├── run.py                      # stage_in → pbrun germline → stage_out
│   └── cli.py                      # entrypoint: python -m pipeline.cli
├── scripts/
│   ├── run_nvidia_tutorial.sh      # Mode A: nebius ai job create with NGC image + NGC auth
│   ├── run_serverless.sh           # Mode B: nebius ai job create with BYO pipeline image + S3 envs
│   ├── run_qa.sh                   # Mode B QA: nebius ai job create with QA image
│   └── stage_demo_data.sh          # One-shot: stage HG002 FASTQ + GRCh38 ref into customer bucket
├── qa/
│   ├── Dockerfile                  # FROM BioContainers hap.py + Python 3 + boto3 + validate.py (thin)
│   └── validate.py                 # Fetches output VCF + GIAB truth at runtime; runs hap.py
├── bench/
│   └── results/                    # Committed wall-clock + $/sample per SKU (L40S, H200, B200, B300)
├── .dockerignore
└── .gitignore
```

No reference, demo, or truth data is committed to the repo. All large artifacts (GRCh38 reference, HG002 FASTQ, GIAB truth VCF + BED) are fetched from public sources at job runtime.

## 6. README structure

The README is the deliverable's primary surface. It follows the OpenMM example's progressive-disclosure pattern (frontmatter → table of contents → numbered sections), with two distinct mode tracks:

1. **What you'll learn / prerequisites.** Nebius CLI installed and authenticated; an NGC API key (free, from `ngc.nvidia.com`) for pulling Parabricks; for Mode B, an Object Storage bucket and a Container Registry repository.
2. **Mode A — Run NVIDIA's step-by-step tutorials on Nebius.**
   - 2.0 *NGC authentication.* `nvcr.io/nvidia/clara/clara-parabricks:4.7.0-1` requires NGC auth. **Default (lower-friction):** export `NGC_API_KEY` and pass `--registry-username '$oauthtoken' --registry-password "$NGC_API_KEY"` inline. README flags the trade-off: the key lands in shell history and CLI audit logs. **Secure alternative:** store the key as a Nebius MysteryBox secret with `REGISTRY_USERNAME=$oauthtoken` / `REGISTRY_PASSWORD=<key>` and reference it via `--registry-secret <selector>`. Both flows shown end-to-end.
   - 2.1 *Getting the sample data.* `nebius ai job create` using NGC image, `--container-command bash -c "<NVIDIA's data fetch>"`, no S3.
   - 2.2 *fq2bam tutorial.* `nebius ai job create` using NGC image, args from NVIDIA's `pbrun fq2bam` tutorial.
   - 2.3 *HaplotypeCaller tutorial.* Same pattern with `pbrun haplotypecaller`.
   - Each subsection links back to NVIDIA's canonical tutorial page so we never duplicate their command syntax.
3. **Mode B — Production DeepVariant runs.**
   - 3.1 *Stage demo data.* Run `scripts/stage_demo_data.sh` to stage GRCh38 + HG002 FASTQ into the customer's bucket. ~10 min, ~50 GB.
   - 3.2 *Build and push the image.* `docker build` + push to Nebius Container Registry. The Dockerfile is thin (~10 lines on top of NGC).
   - 3.3 *Submit a Serverless DeepVariant job.* `scripts/run_serverless.sh` wraps `nebius ai job create` with the right env vars (`S3_INPUT_PREFIX`, `S3_REF_PREFIX`, `S3_OUTPUT_PREFIX`, `SAMPLE_ID`, AWS creds, `S3_ENDPOINT_URL`, `S3_BUCKET`).
   - 3.4 *Inspect outputs.* List the prefix; download the resulting VCF / BAM.
4. **GPU recommendations.** A short table:

   | Tier | GPU | When to pick |
   |---|---|---|
   | Lowest cost | 1× L40S | Demo, ad-hoc runs, lowest $/sample |
   | Lowest cost (alt) | 1× RTX6000 Ada | Similar tier to L40S; 48 GB VRAM headroom for larger references or multi-sample staging |
   | Faster | 1× H200 | Throughput-sensitive workloads |
   | Highest performance | 1× B200 / B300 | Lowest single-sample latency |

   Parabricks runs on every Nebius SKU; no SKU is hard-coded in scripts.
5. **Validate accuracy (optional).** Build and push the QA image (`qa/Dockerfile` — BioContainers `hap.py` copied into a Python 3 image with `boto3` and `validate.py`), then submit `scripts/run_qa.sh`. The job downloads the output VCF and fetches the GIAB v4.2.1 truth VCF + confidence BED from public NIH at runtime. Pass criterion: SNP F1 ≥ 0.999 on HG002 35×.
6. **Benchmark and contribute results.** How to run `bench/` and submit a PR adding to `bench/results/`.
7. **Troubleshooting.** GPU/preset access, NGC image pull, S3 auth, bucket region/endpoint mismatches.

## 7. Mode B wrapper specification

The `pipeline/` Python module is the only meaningful code we author.

**Entrypoint:** `python -m pipeline.cli`. Reads inputs from environment variables:

| Variable | Purpose |
|---|---|
| `S3_BUCKET` | Customer bucket |
| `S3_ENDPOINT_URL` | e.g. `https://storage.eu-north1.nebius.cloud` |
| `S3_INPUT_PREFIX` | Prefix containing input FASTQ pair |
| `S3_REF_PREFIX` | Prefix containing GRCh38 reference + index |
| `S3_OUTPUT_PREFIX` | Prefix where outputs are uploaded |
| `SAMPLE_ID` | Logical sample identifier (used in output filenames) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` | S3 credentials |

**Sequence:**

1. Download FASTQ + reference from the bucket to `/scratch/` on the job's ephemeral disk.
2. Invoke `pbrun germline --ref … --in-fq … --out-variants /scratch/output/<sample>.vcf` against local paths.
3. Upload `<sample>.vcf` (and optionally the intermediate BAM) to `s3://${S3_BUCKET}/${S3_OUTPUT_PREFIX}/${SAMPLE_ID}/`.
4. Emit a small JSON summary (`run_metadata.json`) with wall-clock, GPU SKU detected via `nvidia-smi`, and Parabricks version. Upload alongside outputs.

**Failure handling:** Fail fast on missing env vars; surface `pbrun` non-zero exits as the job's exit code so Nebius AI Jobs marks the job failed.

## 8. Reference and demo data

All large data is fetched from public sources — nothing committed to the repo.

`scripts/stage_demo_data.sh` stages from public sources into the customer's own bucket. v1 does **not** ship a Nebius-mirrored reference bucket (revisit if traction justifies the maintenance commitment).

- **GRCh38 reference bundle:** `Homo_sapiens_assembly38.fasta` + `.fai` + `.dict` + BWA index → `s3://${S3_BUCKET}/parabricks/ref/grch38/`. Source: Broad's public bucket.
- **HG002 demo FASTQ:** NIST Genome in a Bottle HG002 35× WGS FASTQ → `s3://${S3_BUCKET}/parabricks/demo/hg002/`. Source: NIH NCBI public bucket.
- **GIAB v4.2.1 truth VCF + confidence BED:** Fetched at runtime by `qa/validate.py` directly inside the QA job, cached to `/scratch/`. Not staged to the customer bucket and not committed to the repo.

## 9. QA: GIAB truth comparison

`qa/validate.py` runs as its own Serverless job on a thin QA image — `qa/Dockerfile` is `FROM quay.io/biocontainers/hap.py:<version>` (BioContainers/Bioconda is the canonical maintained distribution; the long-stale `pkrusche/hap.py` images use a deprecated Docker manifest format that modern Docker refuses to pull) plus Python 3 plus `boto3` plus `validate.py`. We do not rebuild hap.py ourselves; upgrades are upstream's problem. The script:

1. Downloads the customer's output VCF from `s3://${S3_BUCKET}/${S3_OUTPUT_PREFIX}/${SAMPLE_ID}/`.
2. Fetches the GIAB v4.2.1 HG002 truth VCF + confidence BED from NIH at runtime, caches to `/scratch/`.
3. Runs `hap.py` to compare and emit precision, recall, and F1 for SNPs and indels.
4. Compares against a committed golden-numbers file (expected SNP F1 ≥ 0.999 on HG002 35× per Parabricks' published accuracy).
5. Exits non-zero if the run regresses below threshold.

## 10. Benchmarks

`bench/` runs the canonical workflow with `/usr/bin/time -v` and `nvidia-smi dmon` sampling, then writes a markdown report to `bench/results/<date>-<gpu>.md`: wall-clock, peak GPU memory, SKU detected, sample $/genome at a configurable hourly rate.

v1 commits five baseline results: **L40S, RTX6000 Ada, H200, B200, and B300**. Each is captured during implementation as part of the SKU verification matrix (see §11). Subsequent PRs adding new SKUs (or refreshing numbers when Parabricks is upgraded) are the ongoing contribution path.

## 11. Acceptance criteria

- A new customer can copy the Mode A snippets and successfully run all three NVIDIA step-by-step tutorials on Nebius, with each tutorial producing the outputs documented on NVIDIA's tutorial page.
- A customer can `docker build` the Mode B image, push it to their Nebius Container Registry, and submit a DeepVariant job on HG002 against their own S3 bucket within 30 minutes of starting (job run-time itself depends on GPU SKU and is reported in `bench/results/`; ~60–90 min on L40S, ~25–30 min on H200, faster on B200 / B300).
- The output VCF passes `qa/validate.py` against the GIAB truth set with SNP F1 ≥ 0.999.
- **The Mode B canonical DeepVariant job is verified end-to-end on all five target Nebius GPU SKUs: L40S, RTX6000 Ada, H200, B200, and B300.** Each run produces a VCF that passes the QA criterion and a benchmark entry committed to `bench/results/<date>-<sku>.md`.
- Top-level cookbook `README.md` has a new row under "Life Science" linking to the recipe.
- The recipe folder follows the same layout, frontmatter conventions, and README structure as `life-science/openmm-simulation/`.

## 12. Risks and verification items for implementation

- **NGC image self-sufficiency for Mode A.** NVIDIA's tutorial commands assume `wget`, `tar`, etc. inside the container. Verify on first job submission; if anything is missing, document a one-line `apt install` prefix in the `--args` rather than building a wrapper image.
- **NGC inline credential exposure.** Default Mode A flow passes the NGC API key as a `--registry-password` CLI argument. Document the trade-off explicitly in the README and link to the MysteryBox-secret alternative for production use.
- **`nebius ai job create --args` quoting** for multi-line shell. May need a `bash -c "<single quoted block>"` pattern; lock down the convention in `scripts/run_nvidia_tutorial.sh`.
- **Nebius Container Registry push docs** must be linked clearly so Mode B does not get blocked on registry confusion. The README cross-links to the official CR quickstart rather than duplicating instructions.
- **Public reference URL stability.** Broad's GRCh38 bucket and NIH's GIAB bucket have been stable for years but are third-party. If a URL ever breaks, `stage_demo_data.sh` and `qa/validate.py` need alternative sources; flagged as small ongoing risk.
- **Ephemeral-disk size.** A 30× HG002 FASTQ pair is ~50 GB, intermediate BAM another ~80 GB. The job preset's ephemeral disk must hold both plus outputs. Document a recommended preset (≥ 256 GB ephemeral) in the README; verify exact preset names against current Nebius offerings during implementation.
- **Per-SKU platform names.** `nebius ai job create --help` documents `gpu-h100-sxm` / `gpu-h200-sxm` defaults; exact `--platform` and `--preset` strings for L40S / RTX6000 Ada / B200 / B300 must be confirmed via `nebius compute platform list --parent-id <project>` during the implementation kickoff before bench scripts reference them.

## 13. Phasing

Single phase. The recipe is small enough (one folder, ~10 source files plus README) that splitting it adds overhead without value. The implementation plan (next step) breaks it into ordered tasks: confirm CLI platform/preset names → Mode A scripts + README sections → pipeline image (Dockerfile + `pipeline/` wrapper) → Mode B scripts + README sections → QA image + `validate.py` → bench harness → run end-to-end on all five target SKUs and commit `bench/results/` → top-level cookbook README link.

## 14. Out of scope follow-ups (separate tickets)

- Additional `pbrun` recipes as siblings (`life-science/parabricks-fq2bam/`, `parabricks-haplotypecaller/`) once v1 is proven.
- Somatic / Mutect2 recipe.
- A Nebius-published prebuilt image for Mode B.
- Promotion of any of the above to the public Nebius Applications marketplace.
- Solutions-library Terraform/Helm tracks.
