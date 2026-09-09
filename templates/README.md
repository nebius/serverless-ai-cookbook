# Nebius Serverless Templates

<!-- catalog:generated — HTML tables with fixed column widths; do not auto-format -->

Templates are quick-start configurations to help you serve models and run jobs in a few clicks. Click a **Deploy** link (Create Endpoint / Create Job) to open the Nebius Console create form with fields pre-filled. You can manually adjust fields if needed.

**License policy:** Apache-2.0, MIT, BSD, [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/).

---

## Endpoints

### 🎨 Text-to-Image

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen-Image" align="absmiddle">&nbsp;<a href="endpoint-qwen-image/README.md"><strong>Qwen-Image</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Qwen%2FQwen-Image%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen-Image is an Apache-2.0 multimodal image generation model with strong text rendering, served on preemptible H100 via vLLM-Omni.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/62b4b5beb25cb80fcf278354/SIddx3hYu5rWXA4-O3Oaj.jpeg" width="20" height="20" alt="Sana" align="absmiddle">&nbsp;<a href="endpoint-sana/README.md"><strong>Sana</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fsana-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Sana 1.6B is a fast Apache-2.0 1024px text-to-image model (~9GB weights) for single-L40S Diffusers serving.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/64379d79fac5ea753f1c10f3/fxHO6QoYjdv9_LTyiUD3g.jpeg" width="20" height="20" alt="Z-Image-Turbo" align="absmiddle">&nbsp;<a href="endpoint-z-image-turbo/README.md"><strong>Z-Image-Turbo</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Tongyi-MAI%2FZ-Image-Turbo%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Z-Image-Turbo is a 6B Apache-2.0 text-to-image model distilled for 8-step generation, served on preemptible H100 via vLLM-Omni.</td>
</tr>
</tbody>
</table>

### 🖼️ Image-to-Image

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen-Image-Edit-2511" align="absmiddle">&nbsp;<a href="endpoint-qwen-image-edit-2511/README.md"><strong>Qwen-Image-Edit-2511</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Qwen%2FQwen-Image-Edit-2511%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen-Image-Edit-2511 is an Apache-2.0 image-to-image editor for instruction-based edits, served on preemptible H100 via vLLM-Omni.</td>
</tr>
</tbody>
</table>

### 🎬 Text-to-Video

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/67b610677ea7952def8b29c6/N6jQbbeaa_FcUY-wI1dgG.png" width="20" height="20" alt="Wan2.1-T2V-1.3B" align="absmiddle">&nbsp;<a href="endpoint-wan21-t2v-1-3b/README.md"><strong>Wan2.1-T2V-1.3B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.1-T2V-1.3B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Wan2.1-T2V-1.3B is a compact Apache-2.0 text-to-video Diffusers checkpoint for short clips on preemptible H100 via vLLM-Omni.</td>
</tr>
</tbody>
</table>

### 🎥 Image-to-Video

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/67b610677ea7952def8b29c6/N6jQbbeaa_FcUY-wI1dgG.png" width="20" height="20" alt="Wan2.2-I2V-A14B" align="absmiddle">&nbsp;<a href="endpoint-wan22-i2v-a14b/README.md"><strong>Wan2.2-I2V-A14B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.2-I2V-A14B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Wan2.2-I2V-A14B is a flagship Apache-2.0 image-to-video model (~35GB) for 480p clips on preemptible H100 via vLLM-Omni.</td>
</tr>
</tbody>
</table>

### 🗣️ Text-to-Speech

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6000a0456a2a91af974298cf/qmxSbcVBCwUtVez918IkQ.png" width="20" height="20" alt="Chatterbox" align="absmiddle">&nbsp;<a href="endpoint-chatterbox/README.md"><strong>Chatterbox</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fchatterbox-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Chatterbox is a MIT expressive English TTS model with bundled preset voices and an OpenAI-compatible speech API on preemptible H100.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6629552c96f529a39bac7c89/EaoEz4WH2VoE5twl2oJie.png" width="20" height="20" alt="Kokoro-82M" align="absmiddle">&nbsp;<a href="endpoint-kokoro-82m/README.md"><strong>Kokoro-82M</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fkokoro-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Kokoro-82M is an 82M-parameter Apache-2.0 text-to-speech model with an OpenAI-compatible speech API on a single L40S.</td>
</tr>
</tbody>
</table>

### 🎵 Text-to-Audio

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6209bb6ede1c3ff3ec37620c/xk4TNYgu3UPz74tAgzTrA.jpeg" width="20" height="20" alt="ACE-Step 1.5" align="absmiddle">&nbsp;<a href="endpoint-ace-step-1-5/README.md"><strong>ACE-Step 1.5</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Facestep-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">ACE-Step 1.5 is an MIT text-to-audio (music) model with a sync OpenAI-shaped generation API on preemptible H100.</td>
</tr>
</tbody>
</table>

### 💬 Large Language Models

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen3-0.6B" align="absmiddle">&nbsp;<a href="endpoint-vllm-qwen3-0-6b/README.md"><strong>Qwen3-0.6B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-0.6B%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen3-0.6B is a compact Apache-2.0 chat LLM served OpenAI-compatibly via vLLM on a single L40S.</td>
</tr>
</tbody>
</table>

### 🧲 Multimodal Embeddings

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen3-VL-Embedding-8B" align="absmiddle">&nbsp;<a href="endpoint-qwen3-vl-embedding/README.md"><strong>Qwen3-VL-Embedding-8B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-VL-Embedding-8B%20--runner%20pooling%20--trust-remote-code%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen3-VL-Embedding-8B is an Apache-2.0 multimodal embedding model for text, image, and video, served OpenAI-compatibly via vLLM.</td>
</tr>
</tbody>
</table>

### 🧪 Molecular Docking

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle">🧪&nbsp;<a href="endpoint-autodock-gpu/README.md"><strong>AutoDock-GPU REST + MCP</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fhcls%2Fautodock-gpu-api%3A20260909-rest-mcp-sm80-sm90&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true&amp;volumeMountPath=%2Fmnt%2Fhcls&amp;volumeSize=32"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Run source-built AutoDock-GPU v1.6 through REST or MCP on SM80/86/89/90 GPUs; Blackwell is explicitly unsupported by this image.</td>
</tr>
</tbody>
</table>

## Jobs

### 🏋️ Fine-tuning

<table width="960" border="1" cellpadding="8" cellspacing="0" style="table-layout:fixed;width:960px;min-width:960px;border-collapse:collapse;">
<colgroup>
  <col width="220">
  <col width="160">
  <col width="580">
</colgroup>
<thead>
<tr>
  <th width="220" align="left">Template</th>
  <th width="160" align="center">Deploy</th>
  <th width="580" align="left">Description</th>
</tr>
</thead>
<tbody>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Axolotl" align="absmiddle">&nbsp;<a href="job-axolotl-finetune/README.md"><strong>Axolotl</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=docker.io%2Faxolotlai%2Faxolotl%3Amain-20260309-py3.11-cu128-2.9.1&amp;command=curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftraining%2Faxolotl-finetuning%2Fsrc%2Fconfig.yaml%20-o%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20export%20RUN_ID%3Drun-%24%28date%20%2B%25Y%25m%25d-%25H%25M%25S%29%20%26%26%20axolotl%20train%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20mkdir%20-p%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID%20%26%26%20cp%20-r%20%2Fworkspace%2Foutput%2F.%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;volume=%2Fworkspace%2Fdata&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Axolotl finetunes Qwen2.5-0.5B (Apache-2.0) on a preemptible H100 using the cookbook train config.</td>
</tr>
</tbody>
</table>
