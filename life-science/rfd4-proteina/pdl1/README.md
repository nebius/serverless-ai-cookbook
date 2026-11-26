---
title: Design PD-L1 binders and check their structures
category: life-sciences
type: job
runtime: gpu-h100-sxm
frameworks: [nvidia-nim, pytorch, huggingface]
keywords: [protein-design, pdl1, openfold3, object-storage]
difficulty: intermediate
---

# Design PD-L1 binders and check their structures

Design two 80-residue candidates around a fixed PD-L1 target, then optionally
predict each sequence–target complex with OpenFold3. All jobs use your private
bucket. No local GPU, image build or registry copy is required.

This adapts the PD-L1 workflow contributed by
[Arseniy Sokolov](https://github.com/hazirliver) to the public model distributions.
It uses inputs from the public release.

## 1. Generate binder candidates

Choose one path and follow its setup. Both use the same supplied target and
contact annotations, but their model checkpoints differ.

| Model | Setup and input | Generate |
|---|---|---|
| NVIDIA NIM | [Create the RFD4 endpoint](../nim/README.md), upload [pdl1.json](../inputs/nim/pdl1.json), and configure the CPU request job | <a href="https://console.nebius.com/serverless/job/create?image=alpine%2Fcurl%40sha256%3Ac103daf2dbf75dbaee86c278f45be6c82acd86eef27e17521d0992bf90031d81&amp;platform=cpu-d3&amp;preset=2vcpu-8gb&amp;preemptible=false&amp;command=%2Fbin%2Fsh+-c+%27test+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%2Fresponse.json+%26%26+curl+--fail-with-body+--show-error+--silent+--max-time+1800+--create-dirs+-H+%22Authorization%3A+Bearer+%24AUTH_TOKEN%22+-H+%22Content-Type%3A+application%2Fjson%22+--data-binary+%40%2Fdata%2Frfd4%2Finputs%2Fpdl1.json+--output+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%2Fresponse.json+%22%24RFD4_URL%2Fbiology%2Fipd%2Frfd4-proteina%2Fgenerative%22%27&amp;diskSize=20GiB&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a> |
| Public Hugging Face | [Configure the GPU job](../hugging-face/README.md) and upload [pdl1.cif](../inputs/hugging-face/pdl1.cif) | <a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fpdl1.cif+out_dir%3D%2Ftmp%2Frfd4-runs%2Fpdl1-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%0Amkdir+-p+%2Fdata%2Frfd4%2Fruns+%26%26+cp+-r+%2Ftmp%2Frfd4-runs%2Fpdl1-001+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a> |

Upload the input from the console, or with the AWS CLI:

```bash
aws s3 cp pdl1.cif s3://<your-bucket>/rfd4/inputs/pdl1.cif \
  --endpoint-url https://storage.eu-north1.nebius.cloud
```

Keep every proposed structure. NIM writes a response JSON; the Hugging Face job
generates on the container disk and copies the finished run into the bucket —
the mount is object storage and refuses the incremental writes the CIF writer
makes, so a run with `out_dir` on the mount lands 0-byte structures; see the
[Hugging Face recipe](../hugging-face/README.md). Use a fresh run folder for
each attempt. These examples use seed 42. Choose seeds before generating
candidates and retain failures.

## 2. Prepare an optional OpenFold3 request

Use each distinct 80-residue binder sequence once. From a NIM response, inspect
`designs[].sequence` and its structure. For Hugging Face, take the designed
chain's sequence from the generated CIF's `_entity_poly` record. Keep chain A
(the 80-residue binder) separate from chain B (the 115-residue target):

```bash
# Hugging Face: chain A on one _entity_poly row of the generated CIF.
# The target (chain B) sits in a multi-line ";" block, so it is skipped.
BINDER_SEQUENCE=$(awk '$2 == "polypeptide(L)" && NF == 8 && $7 == "A" { print $5 }' \
  pdl1_rep0_generated.cif)
# NIM: BINDER_SEQUENCE=$(jq -r '.designs[0].sequence' response.json)
echo "${#BINDER_SEQUENCE} $BINDER_SEQUENCE"
```

Download [pdl1.template.json](../inputs/openfold3/pdl1.template.json) and
[pdl1-target.cif](../inputs/openfold3/pdl1-target.cif) to a local folder. The JSON
is a template: fill it with your binder sequence and the supplied target CIF
before uploading it. With `jq` installed, run:

```bash
jq --arg binder "$BINDER_SEQUENCE" --rawfile target pdl1-target.cif '
  if ($binder | test("^[ACDEFGHIKLMNPQRSTVWY]{80}$")) then
    .inputs[0].molecules[0].sequence = $binder |
    .inputs[0].molecules[0].msa.query.a3m.alignment = (">query\n" + $binder) |
    .inputs[0].molecules[1].structural_templates[0].structure = $target
  else error("Supply the 80-residue binder sequence") end
' pdl1.template.json > pdl1-refold.json
```

Upload `pdl1-refold.json` to `rfd4/inputs/pdl1-refold.json` in your bucket.
It requests one prediction, query-only MSAs and a template for the fixed target.
The designed binder has **no structural template**. No external MSA search runs.

## 3. Create the OpenFold3 endpoint and request job

Use NVIDIA's [OpenFold3 NIM](https://docs.nvidia.com/nim/bionemo/openfold3/1.6.0/getting-started.html),
referenced directly from NVCR. Its [container terms](https://catalog.ngc.nvidia.com/orgs/nim/openfold/containers/openfold3/-/governing-terms)
apply. This is a separate predictor, with its own checkpoint and runtime.

<a href="https://console.nebius.com/serverless/endpoint/create?image=nvcr.io%2Fnim%2Fopenfold%2Fopenfold3%40sha256%3Aac982329c9c38c7e6eb865d1bad0d925635912a0d81684da40bd78f9226ff5a3&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=200GiB&amp;preemptible=false&amp;auth=true"><img src="../../../templates/assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a>

Follow the [NIM secret and authentication setup](../nim/README.md#create-the-model-endpoint)
for this endpoint too. Check that your NGC key grants OpenFold3 access. Use one
regular H100, a 200 GiB disk, port 8000, the image's default command and at most
one replica. Add `NIM_INFERENCE_SEED=700001` and `NIM_MAX_QUEUED_REQUESTS=8`.
Wait for `/v1/health/ready` to succeed with the endpoint token.

<a href="https://console.nebius.com/serverless/job/create?image=alpine%2Fcurl%40sha256%3Ac103daf2dbf75dbaee86c278f45be6c82acd86eef27e17521d0992bf90031d81&amp;command=%2Fbin%2Fsh+-c+%27test+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fpdl1-refold-001%2Fresponse.json+%26%26+curl+--fail-with-body+--show-error+--silent+--max-time+1800+--create-dirs+-H+%22Authorization%3A+Bearer+%24AUTH_TOKEN%22+-H+%22Content-Type%3A+application%2Fjson%22+--data-binary+%40%2Fdata%2Frfd4%2Finputs%2Fpdl1-refold.json+--output+%2Fdata%2Frfd4%2Fruns%2Fpdl1-refold-001%2Fresponse.json+%22%24OF3_URL%2Fbiology%2Fopenfold%2Fopenfold3%2Fpredict%22%27&amp;platform=cpu-d3&amp;preset=2vcpu-8gb&amp;diskSize=20GiB&amp;preemptible=false&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

Use regular CPU compute (`cpu-d3`, `2vcpu-8gb`), a 20 GiB disk, a one-hour timeout
and the same bucket **read-write at `/data`**. Set `OF3_URL` to this endpoint's
HTTPS URL without a trailing slash and `AUTH_TOKEN` from its token secret.
The command sends the bucket JSON to `/biology/openfold/openfold3/predict` and
saves `rfd4/runs/pdl1-refold-001/response.json`. It refuses to overwrite that file
and does not retry a prediction automatically.

Repeat for the other distinct sequence with a new input ID and run folder.
Re-predicting the same sequence is not another designed binder. Stop the GPU
endpoints and delete completed jobs when finished; retain the bucket results.

## 4. Read the results

Keep the complete response. Save its predicted complex locally with:

```bash
jq -r '.outputs[0].structures_with_scores[0].structure' response.json > refolded.cif
```

The response includes complex pLDDT, pTM and interface pTM scores. It does not
compute target-aligned binder RMSD or an automated pass flag. Do not apply
thresholds from a different predictor without checking their definitions.

To compare poses, align the predicted and designed target backbones, then
measure binder RMSD in that alignment; do not align the binder independently.
Predeclare a rule before screening candidates and keep failures. Neither a
confident prediction nor a small RMSD measures binding or specificity.

These exact vendor-image paths remain [awaiting live acceptance](../validation.md).
There is no new success-rate or performance claim for this workflow.
