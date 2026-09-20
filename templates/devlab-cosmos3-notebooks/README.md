# Cosmos 3 Notebooks (DevLab)

<!-- factory:deploy -->

<a href="https://console.nebius.com/serverless/devlab/create?image=quay.io%2Fjupyter%2Fminimal-notebook%3Anotebook-7.5.6&amp;command=bash%20-c%20%22wget%20-qO%20%2Ftmp%2Fbootstrap.sh%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftemplates%2Fdevlab-cosmos3-notebooks%2Fsrc%2Fbootstrap.sh%20%26%26%20bash%20%2Ftmp%2Fbootstrap.sh%22&amp;targetPort=8888&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;env=JUPYTER_TOKEN%3DREPLACE_WITH_16_CHARS&amp;env=COSMOS3_REASONER_URL%3D&amp;env=COSMOS3_REASONER_TOKEN%3D&amp;env=COSMOS3_GENERATOR_URL%3D&amp;env=COSMOS3_GENERATOR_TOKEN%3D"><img src="../assets/create-devlab.svg" alt="Create DevLab" width="138" height="20"></a>

<!-- /factory:deploy -->

<!-- factory:intro -->

A JupyterLab DevLab with NVIDIA's Cosmos 3 cookbooks cloned in and a quickstart notebook wired to your Cosmos 3 Reasoner and Generator endpoints — run all of NVIDIA's Reasoner examples against Nebius endpoints from a small CPU machine.

**License:** [OpenMDW-1.1](https://openmdw.ai/license/1-1/) (Cosmos cookbooks) · **Source:** [NVIDIA Cosmos](https://github.com/nvidia/cosmos/tree/main/cookbooks/cosmos3)

<!-- /factory:intro -->

## What you get

A persistent JupyterLab workspace (`/home/jovyan/work`, kept across stop/start) on a 4-vCPU
CPU DevLab — no GPU here, the models run on your endpoints:

```text
work/
  00_cosmos3_on_nebius.ipynb        start here: endpoint check, a Reasoner caption, a Generator image + async video
  nebius_endpoints.json             the endpoint URLs/tokens the DevLab was created with
  cosmos/cookbooks/cosmos3/         NVIDIA's cookbooks (Reasoner + Generator notebooks, prompt guide, sample assets)
  cosmos/…/reasoner/run_with_vllm_nebius.ipynb   NVIDIA's full Reasoner tour, re-pointed at your endpoint (see below)
```

The bootstrap installs `openai`, `requests`, `pillow`, clones `nvidia/cosmos`, writes the two
Nebius notebooks (only if absent, so your edits survive restarts), self-tests the Reasoner
endpoint, and starts JupyterLab behind the DevLab's managed HTTPS route.

**What the `_nebius` copy changes** — NVIDIA's `run_with_vllm.ipynb` is left untouched; the copy
gets a new first cell that reads the endpoint URL and token from the environment, every
`base_url="http://localhost:800x/v1"` becomes the endpoint, `api_key="EMPTY"` becomes the bearer
token, and media references change from `file://` paths (which only a server on the same machine
could read) to the public GitHub URLs of the same sample assets. Prompts, sampling and model names
are unchanged.

## Before you click

You need at least one endpoint to talk to:

1. Deploy the [Cosmos 3 Reasoner](../endpoint-cosmos3-reasoner/README.md) (and optionally the
   [Cosmos 3 Generator](../endpoint-cosmos3-generator/README.md)) template. Wait until
   `/v1/models` answers.
2. Copy each endpoint's **HTTPS FQDN** (`https://port8000-<id>.tunnel.applications.<region>.nebius.cloud`)
   and its **bearer token**.

## How to run it

1. **Click Create DevLab.** In the form:
   - set `JUPYTER_TOKEN` to a random 16-character alphanumeric string (this is your JupyterLab sign-in token; keep it),
   - paste the endpoint FQDNs and tokens into `COSMOS3_REASONER_URL` / `COSMOS3_REASONER_TOKEN` (and the Generator pair if you have one),
   - create. First start takes ~3 minutes (pip install + clone).
2. **Open** the DevLab's managed URL — `https://port8888-<id>.tunnel.applications.<region>.nebius.cloud`
   (console → DevLab → Network → *Public Devlabs*, or `status.public_endpoints[0]` in the CLI) — and
   sign in with the Jupyter token. Without it the route answers `403`.
3. **Run `00_cosmos3_on_nebius.ipynb`** top to bottom, then open
   `cosmos/cookbooks/cosmos3/reasoner/run_with_vllm_nebius.ipynb` for NVIDIA's full tour.

**Which of NVIDIA's notebooks work here.** NVIDIA wrote them for one GPU machine: the *client*
notebooks (`run_with_vllm`, `run_with_vllm_omni`, `run_with_sglang`, `run_with_tensorrt_llm`,
`run_with_nim`) call a server on `localhost`, so they only need their base URL changed to your
endpoint — that is what this DevLab is for. The *in-process* notebooks (`run_with_diffusers`,
`run_with_transformers`, `run_with_cosmos_framework`) load the model onto the notebook's own GPU
and need a GPU DevLab with the Cosmos Framework installed; they are out of scope on this CPU DevLab.

Generator notebooks under `cosmos/cookbooks/cosmos3/generator/` shell out to `curl` against
`http://localhost:8000`; point them at your Generator FQDN and add
`-H "Authorization: Bearer $COSMOS3_GENERATOR_TOKEN"` (the quickstart notebook shows the
request shapes, including the async `/v1/videos` job flow).

> **Auth.** The DevLab route itself is open; JupyterLab's own token protects the UI (browsers
> cannot send a bearer header, so the platform's token auth is for API endpoints, not web UIs).
> Use a strong `JUPYTER_TOKEN`, and never commit `nebius_endpoints.json` — it holds endpoint tokens.

> 💸 **Billing.** The DevLab bills a 4-vCPU VM while running and only the disk while stopped
> (`nebius ai devlab stop`). Your GPU endpoints bill separately — delete them when done.

### Observed results

<!-- filled from the validation run -->

<!-- factory:cli -->

## CLI alternative

```bash
JUPYTER_TOKEN=$(openssl rand -hex 8)   # 16 alphanumeric chars — save it, it is your sign-in token

nebius ai devlab create \
  --name cosmos3-notebooks \
  --image quay.io/jupyter/minimal-notebook:notebook-7.5.6 \
  --primary-route-port 8888 \
  --workspace-path /home/jovyan/work \
  --platform cpu-d3 --preset 4vcpu-16gb \
  --env JUPYTER_TOKEN=$JUPYTER_TOKEN \
  --env COSMOS3_REASONER_URL=https://port8000-<id>.tunnel.applications.<region>.nebius.cloud \
  --env COSMOS3_REASONER_TOKEN=<reasoner-token> \
  --env COSMOS3_GENERATOR_URL=https://port8000-<id>.tunnel.applications.<region>.nebius.cloud \
  --env COSMOS3_GENERATOR_TOKEN=<generator-token> \
  --container-command bash \
  --args '-c "wget -qO /tmp/bootstrap.sh https://raw.githubusercontent.com/nebius/serverless-ai-cookbook/main/templates/devlab-cosmos3-notebooks/src/bootstrap.sh && bash /tmp/bootstrap.sh"'

nebius ai devlab get <devlab-id> --format jsonpath='{.status.public_endpoints[0]}'   # managed HTTPS URL
nebius ai devlab logs <devlab-id>     # look for "reasoner self-test OK"
```

Prefer `--env-secret COSMOS3_REASONER_TOKEN=<mysterybox-secret>` over plain `--env` for the
tokens in shared projects. Add `--platform gpu-l40s-a --preset 1gpu-8vcpu-32gb` if you also want
to run the Cosmos Framework locally in the DevLab (not needed for the endpoint notebooks).

<!-- /factory:cli -->

## Troubleshooting

- **Route opens but asks for a token** — that is JupyterLab; enter `JUPYTER_TOKEN`.
- **`reasoner self-test failed` in the DevLab log** — the endpoint was not ready or the URL/token is wrong; JupyterLab starts anyway. Fix the env and `nebius ai devlab restart`, or edit `nebius_endpoints.json`.
- **First cell prints `Reasoner 401`** — wrong or missing token in `COSMOS3_REASONER_TOKEN`.
- **NVIDIA's original notebooks fail on `localhost`** — they expect a local server; use the `_nebius` copy or replace the base URL as described above.
- **Changed the endpoint after creating the DevLab** — edit `nebius_endpoints.json` in the workspace; the notebooks read it when the env var is empty.
