---
title: RFD4-Proteina public Hugging Face model
category: life-sciences
type: job
runtime: gpu-h100-sxm
frameworks: [pytorch, huggingface]
keywords: [protein-design, rfd4]
difficulty: intermediate
---

# RFD4-Proteina public Hugging Face model

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fmonomer-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fmonomer.cif+out_dir%3D%2Ftmp%2Frfd4-runs%2Fmonomer-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%0Amkdir+-p+%2Fdata%2Frfd4%2Fruns+%26%26+cp+-r+%2Ftmp%2Frfd4-runs%2Fmonomer-001+%2Fdata%2Frfd4%2Fruns%2Fmonomer-001%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="../assets/create-job.svg" alt="Create Job" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

Finite GPU job that installs the pinned public `rfd4-proteina` package into NVIDIA's
PyTorch image and writes protein designs into a mounted Object Storage bucket, then
exits. Follow the [recipe](../../life-science/rfd4-proteina/hugging-face/README.md) for
bucket setup, commands and expected outputs. The image is pulled directly from NVIDIA;
no mirror or rebuild is used.

**License:** [BSD-3-Clause](../../life-science/rfd4-proteina/licenses/RFD4-BSD-3-Clause.txt)
for RFD4; Apache-2.0 for the template code. NVIDIA's
[PyTorch image](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/pytorch) has its
own terms.

<!-- /factory:intro -->

[Validation status](../../life-science/rfd4-proteina/validation.md).

<!-- factory:cli -->

## CLI alternative

Upload the example input to your bucket first, as the
[recipe](../../life-science/rfd4-proteina/hugging-face/README.md) describes. The job
installs its dependencies at startup, so the first minutes of GPU time are setup.

```bash
export NEBIUS_PROJECT_ID='project-...'
export NEBIUS_SUBNET_ID='vpcsubnet-...'
# bucket in the same project and region; create with:
#   nebius storage bucket create --name rfd4-data --parent-id <project-id>
export BUCKET=$(nebius storage bucket get-by-name --name rfd4-data --format jsonpath='{.metadata.id}')

RFD4_CMD="set -e
apt-get update && apt-get install -y --no-install-recommends libxrender1 libx11-6 libxext6
unset PYTHONPATH
export LD_LIBRARY_PATH=/usr/local/nvidia/lib:/usr/local/nvidia/lib64
test ! -e /data/rfd4/runs/monomer-001
python -m pip install --no-cache-dir uv==0.13.4
uv venv --python 3.12 /tmp/rfd4
uv pip install --python /tmp/rfd4/bin/python --torch-backend cu130 torch==2.14.1 'atomworks[ml,openbabel]==3.0.4' cuequivariance==0.13.0 cuequivariance-torch==0.13.0 cuequivariance-ops-torch-cu13==0.13.0 cuequivariance-ops-cu13==0.13.0 'rfd4-proteina[all-cuda13]==0.0.2'
/tmp/rfd4/bin/rfd4-generate inputs=/data/rfd4/inputs/monomer.cif out_dir=/tmp/rfd4-runs/monomer-001 hf_ckpt_path=nvidia/RFD4-Proteina hf_ckpt_revision=a06e2509c7033b010fc43614e9fd840303588502 num_replicates=2 batch_size=1 seed=42 recycle_strategy=medium/front_loaded inference_backend=native compile_lengths=null prevalidate_inputs=true ~metrics
mkdir -p /data/rfd4/runs && cp -r /tmp/rfd4-runs/monomer-001 /data/rfd4/runs/monomer-001"

nebius ai job create \
  --parent-id "$NEBIUS_PROJECT_ID" \
  --name rfd4-proteina-monomer \
  --image nvcr.io/nvidia/pytorch@sha256:f71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d \
  --platform gpu-h100-sxm \
  --preset 1gpu-16vcpu-200gb \
  --disk-size 200Gi \
  --subnet-id "$NEBIUS_SUBNET_ID" \
  --volume "$BUCKET:/data:rw" \
  --container-command /bin/bash \
  --args "-lc \"$RFD4_CMD\""
```

The script is the one the button sets. Keep the output folder new for every attempt:
it refuses to start if the folder already exists, which protects earlier results.
Generation runs on the container disk and the last line copies the run folder into
the bucket: the mount is object storage (mountpoint-s3), which does not accept the
incremental writes the CIF writer makes, so an `out_dir` on the mount yields 0-byte
structures from a job that still reports success.

> This contribution has not had live end-to-end acceptance yet; see the
> [validation status](../../life-science/rfd4-proteina/validation.md).

<!-- /factory:cli -->
