---
title: Public RFD4-Proteina from Hugging Face
category: life-sciences
type: job
runtime: gpu-h100-sxm
frameworks: [pytorch, huggingface]
keywords: [protein-design, bionemo, object-storage, rfd4]
difficulty: intermediate
---

# Public RFD4-Proteina from Hugging Face

Run a finite Serverless GPU job with NVIDIA's PyTorch image. At startup, the job
installs the public RFD4 package in an isolated Python environment and downloads
the pinned Hugging Face bundle, including its matching autoencoder. It reads and
writes your private bucket. No image build, registry copy or Hugging Face token
is required.

This is the retrained public model from
[RosettaCommons](https://github.com/RosettaCommons/RFD4-Proteina), separate from the
[NVIDIA NIM checkpoint pair](../nim/README.md).

## Run a first protein design

1. Upload [monomer.cif](../inputs/hugging-face/monomer.cif) to
   `rfd4/inputs/monomer.cif` in your private bucket. It specifies a blank
   150-residue protein. From the console, or with the AWS CLI:

   ```bash
   aws s3 cp monomer.cif s3://<your-bucket>/rfd4/inputs/monomer.cif \
     --endpoint-url https://storage.eu-north1.nebius.cloud
   ```

2. Open **Create Job**:

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fmonomer-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fmonomer.cif+out_dir%3D%2Ftmp%2Frfd4-runs%2Fmonomer-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%0Amkdir+-p+%2Fdata%2Frfd4%2Fruns+%26%26+cp+-r+%2Ftmp%2Frfd4-runs%2Fmonomer-001+%2Fdata%2Frfd4%2Fruns%2Fmonomer-001%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

<!-- /factory:deploy -->

3. Select your project, one regular H100 (`gpu-h100-sxm`,
   `1gpu-16vcpu-200gb`), a **200 GiB disk** and a **one-hour timeout**.
4. Attach the bucket **read-write at `/data`**. Check the command below and
   create the job. The button supplies the same command; no script upload is
   needed.

```bash
set -e
apt-get update && apt-get install -y --no-install-recommends libxrender1 libx11-6 libxext6
unset PYTHONPATH
export LD_LIBRARY_PATH=/usr/local/nvidia/lib:/usr/local/nvidia/lib64
test ! -e /data/rfd4/runs/monomer-001
python -m pip install --no-cache-dir uv==0.13.4
uv venv --python 3.12 /tmp/rfd4
uv pip install --python /tmp/rfd4/bin/python --torch-backend cu130 torch==2.14.1 'atomworks[ml,openbabel]==3.0.4' cuequivariance==0.13.0 cuequivariance-torch==0.13.0 cuequivariance-ops-torch-cu13==0.13.0 cuequivariance-ops-cu13==0.13.0 'rfd4-proteina[all-cuda13]==0.0.2'
/tmp/rfd4/bin/rfd4-generate inputs=/data/rfd4/inputs/monomer.cif out_dir=/tmp/rfd4-runs/monomer-001 hf_ckpt_path=nvidia/RFD4-Proteina hf_ckpt_revision=a06e2509c7033b010fc43614e9fd840303588502 num_replicates=2 batch_size=1 seed=42 recycle_strategy=medium/front_loaded inference_backend=native compile_lengths=null prevalidate_inputs=true ~metrics
mkdir -p /data/rfd4/runs && cp -r /tmp/rfd4-runs/monomer-001 /data/rfd4/runs/monomer-001
```

The first commands install the model in `/tmp/rfd4`, separate from the base
image's Python packages. `rfd4-generate` then creates two proposals using the
native backend. A new output folder is required.

Generation writes to the container disk (`/tmp/rfd4-runs/…`) and the last line
copies the finished run into the bucket. Do not point `out_dir` at the mount:
it is object storage (mountpoint-s3), where whole files can be created or
replaced but **append, truncate and rename are not permitted**. The CIF writer
builds its files incrementally, so writing straight to the mount leaves 0-byte
structures while the job still reports success. `cp` writes each file in one
go, which the mount accepts.

When the job completes, open `rfd4/runs/monomer-001/inference_samples/` in the
bucket. Each proposal has a generated CIF containing sequence and coordinates.
Keep the job logs, configuration files and input alongside the structures.
Delete the completed job after collecting results; the bucket files remain.

## Other inputs

Upload the selected CIF to `rfd4/inputs/` and use its button. The endpoint and
JSON inputs from the NIM recipe are not used here.

| Input | What it asks for | Run |
|---|---|---|
| [pdl1.cif](../inputs/hugging-face/pdl1.cif) | Two 80-residue binder candidates against PD-L1 | <a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fpdl1.cif+out_dir%3D%2Ftmp%2Frfd4-runs%2Fpdl1-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%0Amkdir+-p+%2Fdata%2Frfd4%2Fruns+%26%26+cp+-r+%2Ftmp%2Frfd4-runs%2Fpdl1-001+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a> |
| [heme.cif](../inputs/hugging-face/heme.cif) | Two 150-residue proteins conditioned on heme B | <a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fheme-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fheme.cif+out_dir%3D%2Ftmp%2Frfd4-runs%2Fheme-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D1024+recycle_strategy%3Dmedium%2Fmidpeak+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%0Amkdir+-p+%2Fdata%2Frfd4%2Fruns+%26%26+cp+-r+%2Ftmp%2Frfd4-runs%2Fheme-001+%2Fdata%2Frfd4%2Fruns%2Fheme-001%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="../../../templates/assets/create-job.svg" alt="Create Job" width="138" height="20"></a> |

The heme example uses `medium/midpeak`; the protein examples use
`medium/front_loaded`. Change `num_replicates=2` or `seed=42` in the command for
another run. Input lengths and structural conditions live in the CIF; follow
the [input guide](https://rfd4-proteina.org/latest/how-to/input_prep/index.html)
to prepare a different problem.

The bundle revision in [images.json](../images.json) pins both model and
autoencoder. Keep them together. [Validation](../validation.md) records what
has been checked for this startup-installation recipe.

## Troubleshooting

If installation or checkpoint download fails, keep the job logs and check
network access to PyPI, PyTorch and Hugging Face. An existing output folder
stops the command; use a new run folder. If the generated CIFs arrive 0 bytes,
`out_dir` is pointing at the bucket mount: keep it on the container disk and
copy the run folder afterwards, as the command above does. Check the
[validation limits](../validation.md) before treating a completed install as a
validated design run.
