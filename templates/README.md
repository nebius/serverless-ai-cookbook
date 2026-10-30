# Nebius Serverless Templates

<!-- catalog:generated — HTML tables with fixed column widths; do not auto-format -->

Templates are quick-start configurations to help you serve models and run jobs in a few clicks. Click a **Deploy** link (Create Endpoint / Create Job) to open the Nebius Console create form with fields pre-filled. You can manually adjust fields if needed.

**License policy:** Apache-2.0, MIT, BSD, LGPL-2.1, [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/), [OpenMDW-1.1](https://openmdw.ai/license/1-1/).
Template code in this repository is Apache-2.0. Some templates deploy third-party software under a copyleft license such as GPL-2.0; the template description says so.

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
  <td width="220" valign="middle"><a href="endpoint-flux2-klein-4b/README.md"><strong>FLUX.2 Klein 4B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0%40sha256%3A566d89d7eaba08dd313dab2464e67fe984825d281c77437582e3008a917bbf7c&amp;command=vllm+serve+black-forest-labs%2FFLUX.2-klein-4B+--omni+--host+0.0.0.0+--port+8000+--revision+e7b7dc27f91deacad38e78976d1f2b499d76a294&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-16vcpu-64gb&amp;diskSize=500GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Black Forest Labs' Apache-2.0 distilled 4B image generator and editor, served on one L40S via vLLM-Omni.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen-Image" align="absmiddle">&nbsp;<a href="endpoint-qwen-image/README.md"><strong>Qwen-Image</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Qwen%2FQwen-Image%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen-Image is an Apache-2.0 multimodal image generation model with strong text rendering, served on preemptible H100 via vLLM-Omni.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/62b4b5beb25cb80fcf278354/SIddx3hYu5rWXA4-O3Oaj.jpeg" width="20" height="20" alt="Sana" align="absmiddle">&nbsp;<a href="endpoint-sana/README.md"><strong>Sana</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fsana-serve%3A660347b&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Sana 1.6B is a fast Apache-2.0 1024px text-to-image model (~9GB weights) for single-L40S Diffusers serving.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/64379d79fac5ea753f1c10f3/fxHO6QoYjdv9_LTyiUD3g.jpeg" width="20" height="20" alt="Z-Image-Turbo" align="absmiddle">&nbsp;<a href="endpoint-z-image-turbo/README.md"><strong>Z-Image-Turbo</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Tongyi-MAI%2FZ-Image-Turbo%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="220" valign="middle"><a href="endpoint-flux2-klein-4b/README.md"><strong>FLUX.2 Klein 4B</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0%40sha256%3A566d89d7eaba08dd313dab2464e67fe984825d281c77437582e3008a917bbf7c&amp;command=vllm+serve+black-forest-labs%2FFLUX.2-klein-4B+--omni+--host+0.0.0.0+--port+8000+--revision+e7b7dc27f91deacad38e78976d1f2b499d76a294&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-16vcpu-64gb&amp;diskSize=500GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Black Forest Labs' Apache-2.0 distilled 4B image generator and editor, served on one L40S via vLLM-Omni.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Qwen-Image-Edit-2511" align="absmiddle">&nbsp;<a href="endpoint-qwen-image-edit-2511/README.md"><strong>Qwen-Image-Edit-2511</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Qwen%2FQwen-Image-Edit-2511%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.1-T2V-1.3B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Av0.24.0&amp;command=vllm%20serve%20Wan-AI%2FWan2.2-I2V-A14B-Diffusers%20--omni%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fchatterbox-serve%3A660347b&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Chatterbox is a MIT expressive English TTS model with bundled preset voices and an OpenAI-compatible speech API on preemptible H100.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6629552c96f529a39bac7c89/EaoEz4WH2VoE5twl2oJie.png" width="20" height="20" alt="Kokoro-82M" align="absmiddle">&nbsp;<a href="endpoint-kokoro-82m/README.md"><strong>Kokoro-82M</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Fkokoro-serve%3A660347b&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00gw2b7v3pxetvpy7%2Facestep-serve%3Ad315ae1&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-0.6B%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.19.1&amp;command=python3%20-m%20vllm.entrypoints.openai.api_server%20--model%20Qwen%2FQwen3-VL-Embedding-8B%20--runner%20pooling%20--trust-remote-code%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Qwen3-VL-Embedding-8B is an Apache-2.0 multimodal embedding model for text, image, and video, served OpenAI-compatibly via vLLM.</td>
</tr>
</tbody>
</table>

### 🌍 Physical AI

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
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/65df9200dc3292a8983e5017/Vs5FPVCH-VZBipV3qKTuy.png" width="20" height="20" alt="Cosmos 3 Reasoner" align="absmiddle">&nbsp;<a href="endpoint-cosmos3-reasoner/README.md"><strong>Cosmos 3 Reasoner</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-openai%3Av0.29.0&amp;command=vllm%20serve%20nvidia%2FCosmos3-Nano%20--tensor-parallel-size%201%20--mm-encoder-tp-mode%20data%20--async-scheduling%20--host%200.0.0.0%20--port%208000&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Cosmos3-Nano Reasoner is NVIDIA's OpenMDW-1.1 world model for video and image understanding in robotics and driving, served OpenAI-compatibly via vLLM on a single H100.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/65df9200dc3292a8983e5017/Vs5FPVCH-VZBipV3qKTuy.png" width="20" height="20" alt="Cosmos 3 Generator" align="absmiddle">&nbsp;<a href="endpoint-cosmos3-generator/README.md"><strong>Cosmos 3 Generator</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=vllm%2Fvllm-omni%3Acosmos3&amp;command=vllm%20serve%20nvidia%2FCosmos3-Nano%20--omni%20--model-class-name%20Cosmos3OmniDiffusersPipeline%20--no-guardrails%20--host%200.0.0.0%20--port%208000%20--init-timeout%201800&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=500GiB&amp;preemptible=true&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Cosmos3-Nano Generator is NVIDIA's OpenMDW-1.1 world model for text/image/video-to-video generation with optional sound, served via vLLM-Omni on a single H100 (async video jobs API).</td>
</tr>
</tbody>
</table>

### 🧬 Molecular Dynamics

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
  <td width="220" valign="middle">🧬&nbsp;<a href="endpoint-gromacs/README.md"><strong>GROMACS REST + MCP</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb21%40sha256%3Ac291e308591382e2114e7a43146b4e4af4e4c47326397f935059c5094d4932ba&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Run bounded GPU molecular dynamics through REST or MCP, with a self-contained CUDA engine and optional persistent storage.</td>
</tr>
<tr>
  <td width="220" valign="middle">🧬&nbsp;<a href="endpoint-openmm/README.md"><strong>OpenMM REST + MCP</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb24%40sha256%3A4a30409ff30ca0906743938363f0f92903a7ba4c49dd4f8dfc1ab2e9634d3184&amp;targetPort=8000&amp;platform=gpu-l40s-a&amp;preset=1gpu-8vcpu-32gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Run bounded synthetic molecular dynamics through REST or MCP with a pinned OpenMM CUDA engine and optional persistent storage. OpenMM is MIT + LGPL-3.0; the template code is Apache-2.0.</td>
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
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb22%40sha256%3A5c81e5455f526e19ec0dd6a34cf3dad51816898ebef2d7797e181e7879760f71&amp;targetPort=8000&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Run source-built AutoDock-GPU v1.6 through REST or MCP on SM80/86/89/90 GPUs; Blackwell is explicitly unsupported by this image. AutoDock-GPU is GPL-2.0; the template code is Apache-2.0.</td>
</tr>
<tr>
  <td width="220" valign="middle">🧪&nbsp;<a href="endpoint-autodock-vina/README.md"><strong>AutoDock Vina REST + MCP</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=cr.eu-north1.nebius.cloud%2Fe00jz93pkqx2m4vqj4%2Fcb23%40sha256%3Af80ba1d50f7bbbd6192f9695a71691bdd37390d3bfc0e6152d9cb0a80ef2f171&amp;targetPort=8000&amp;platform=cpu-d3&amp;preset=4vcpu-16gb&amp;diskSize=100GiB&amp;preemptible=false&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Run low-cost AutoDock Vina CPU redocking through REST or MCP with explicit boxes, bounded PDBQT inputs, and optional persistent storage.</td>
</tr>
</tbody>
</table>

### 🧬 Protein Design

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
  <td width="220" valign="middle">🧬&nbsp;<a href="endpoint-rfd4-proteina/README.md"><strong>RFD4-Proteina NVIDIA NIM</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/endpoint/create?image=nvcr.io%2Fnim%2Fipd%2Frfd4-proteina%40sha256%3Af4106e6b659aa53979d37c450c0c0cef620dcfce63934ef7e8e1268c5439b49a&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;diskSize=200GiB&amp;targetPort=8000&amp;auth=true"><img src="./assets/create-endpoint.svg" alt="Create Endpoint" width="138" height="20"></a></td>
  <td width="580" valign="middle">Serve NVIDIA's RFD4-Proteina NIM directly from NVCR and submit protein-design requests from a bucket. Needs an NGC API key as a registry credential; the NIM checkpoint differs from the public Hugging Face release.</td>
</tr>
</tbody>
</table>

## Jobs

### 🧬 Protein Design

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
  <td width="220" valign="middle">🧬&nbsp;<a href="job-rfd4-proteina/README.md"><strong>RFD4-Proteina (Hugging Face)</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fmonomer-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fmonomer.cif+out_dir%3D%2Fdata%2Frfd4%2Fruns%2Fmonomer-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Finite GPU job that installs the pinned public <code>rfd4-proteina</code> package in NVIDIA's PyTorch image and generates designs into a mounted bucket. RFD4 is BSD-3-Clause; the template code is Apache-2.0.</td>
</tr>
<tr>
  <td width="220" valign="middle">🧬&nbsp;<a href="job-pdl1-binder-design/README.md"><strong>PD-L1 Binder Design</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=nvcr.io%2Fnvidia%2Fpytorch%40sha256%3Af71fd67f6d71f685e0bd08ce6c8df48807624cc5d48886370d3471bc4f89d81d&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;preemptible=false&amp;command=%2Fbin%2Fbash+-lc+%27set+-e%0Aapt-get+update+%26%26+apt-get+install+-y+--no-install-recommends+libxrender1+libx11-6+libxext6%0Aunset+PYTHONPATH%0Aexport+LD_LIBRARY_PATH%3D%2Fusr%2Flocal%2Fnvidia%2Flib%3A%2Fusr%2Flocal%2Fnvidia%2Flib64%0Atest+%21+-e+%2Fdata%2Frfd4%2Fruns%2Fpdl1-001%0Apython+-m+pip+install+--no-cache-dir+uv%3D%3D0.13.4%0Auv+venv+--python+3.12+%2Ftmp%2Frfd4%0Auv+pip+install+--python+%2Ftmp%2Frfd4%2Fbin%2Fpython+--torch-backend+cu130+torch%3D%3D2.14.1+%27%22%27%22%27atomworks%5Bml%2Copenbabel%5D%3D%3D3.0.4%27%22%27%22%27+cuequivariance%3D%3D0.13.0+cuequivariance-torch%3D%3D0.13.0+cuequivariance-ops-torch-cu13%3D%3D0.13.0+cuequivariance-ops-cu13%3D%3D0.13.0+%27%22%27%22%27rfd4-proteina%5Ball-cuda13%5D%3D%3D0.0.2%27%22%27%22%27%0A%2Ftmp%2Frfd4%2Fbin%2Frfd4-generate+inputs%3D%2Fdata%2Frfd4%2Finputs%2Fpdl1.cif+out_dir%3D%2Fdata%2Frfd4%2Fruns%2Fpdl1-001+hf_ckpt_path%3Dnvidia%2FRFD4-Proteina+hf_ckpt_revision%3Da06e2509c7033b010fc43614e9fd840303588502+num_replicates%3D2+batch_size%3D1+seed%3D42+recycle_strategy%3Dmedium%2Ffront_loaded+inference_backend%3Dnative+compile_lengths%3Dnull+prevalidate_inputs%3Dtrue+~metrics%27&amp;diskSize=200GiB&amp;volume=%2Fdata"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Generate 80-residue PD-L1 binder candidates with the public model, then optionally predict the complexes with NVIDIA OpenFold3 NIM. Adapted from Arseniy Sokolov's PD-L1 contribution.</td>
</tr>
</tbody>
</table>

### 🎬 Synthetic Data

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
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/65df9200dc3292a8983e5017/Vs5FPVCH-VZBipV3qKTuy.png" width="20" height="20" alt="Cosmos 3 Synthetic Data" align="absmiddle">&nbsp;<a href="job-cosmos3-synthetic-data/README.md"><strong>Cosmos 3 Synthetic Data</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=vllm%2Fvllm-omni%3Acosmos3&amp;command=curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftemplates%2Fjob-cosmos3-synthetic-data%2Fsrc%2Frun.sh%20-o%20%2Ftmp%2Frun.sh%20%26%26%20bash%20%2Ftmp%2Frun.sh&amp;platform=gpu-rtx6000-a&amp;preset=1gpu-24vcpu-218gb&amp;volume=%2Fdata&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Batch image-to-video / text-to-video generation with Cosmos3-Nano (OpenMDW-1.1) into an Object Storage bucket on a preemptible RTX Pro 6000; resumable, shardable.</td>
</tr>
</tbody>
</table>

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
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/65df9200dc3292a8983e5017/Vs5FPVCH-VZBipV3qKTuy.png" width="20" height="20" alt="Cosmos 3 SFT" align="absmiddle">&nbsp;<a href="job-cosmos3-sft/README.md"><strong>Cosmos 3 SFT</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=nvidia%2Fcuda%3A13.0.2-cudnn-devel-ubuntu24.04&amp;command=bash%20-c%20%22apt-get%20update%20-qq%20%26%26%20apt-get%20install%20-y%20-qq%20curl%20ca-certificates%20%3E%2Fdev%2Fnull%20%26%26%20curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftemplates%2Fjob-cosmos3-sft%2Fsrc%2Frun.sh%20-o%20%2Ftmp%2Frun.sh%20%26%26%20bash%20%2Ftmp%2Frun.sh%22&amp;platform=gpu-h100-sxm&amp;preset=8gpu-128vcpu-1600gb&amp;volume=%2Fdata&amp;diskSize=500GiB&amp;preemptible=true&amp;env=MAX_ITER%3D20"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Post-trains the Cosmos3-Nano video generator (OpenMDW-1.1) with NVIDIA's Cosmos Framework SFT recipe on 8×H100 and exports a Diffusers pipeline to your bucket.</td>
</tr>
<tr>
  <td width="220" valign="middle"><img src="https://cdn-avatars.huggingface.co/v1/production/uploads/6215ca5692c0ecfba9186921/hrRM50-6XcdWgg2AKpENG.jpeg" width="20" height="20" alt="Axolotl" align="absmiddle">&nbsp;<a href="job-axolotl-finetune/README.md"><strong>Axolotl</strong></a></td>
  <td width="160" valign="middle" align="center"><a href="https://console.nebius.com/serverless/job/create?image=docker.io%2Faxolotlai%2Faxolotl%3Amain-20260309-py3.11-cu128-2.9.1&amp;command=curl%20-fsSL%20https%3A%2F%2Fraw.githubusercontent.com%2Fnebius%2Fserverless-ai-cookbook%2Fmain%2Ftraining%2Faxolotl-finetuning%2Fsrc%2Fconfig.yaml%20-o%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20export%20RUN_ID%3Drun-%24%28date%20%2B%25Y%25m%25d-%25H%25M%25S%29%20%26%26%20axolotl%20train%20%2Fworkspace%2Fdata%2Fconfig.yaml%20%26%26%20mkdir%20-p%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID%20%26%26%20cp%20-r%20%2Fworkspace%2Foutput%2F.%20%2Fworkspace%2Fdata%2Foutput%2F%24RUN_ID&amp;platform=gpu-h100-sxm&amp;preset=1gpu-16vcpu-200gb&amp;volume=%2Fworkspace%2Fdata&amp;diskSize=500GiB&amp;preemptible=true"><img src="./assets/create-job.svg" alt="Create Job" width="138" height="20"></a></td>
  <td width="580" valign="middle">Axolotl finetunes Qwen2.5-0.5B (Apache-2.0) on a preemptible H100 using the cookbook train config.</td>
</tr>
</tbody>
</table>
