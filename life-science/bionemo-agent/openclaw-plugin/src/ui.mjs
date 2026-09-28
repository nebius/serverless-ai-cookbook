import { randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import { PUBLIC_CATALOG } from "./catalog.mjs";
import { VIEWER_ROUTE_PREFIX } from "./artifacts.mjs";
import { publicError, redactSecrets } from "./errors.mjs";
import { createNotebookHandler, NOTEBOOK_CATALOG, publicNotebookCatalog } from "./notebooks.mjs";
import { capabilities } from "../../runtime/runtime-config.mjs";

export const CANONICAL_CHAT_PATH = "/chat?session=agent%3Abionemo%3Amain";

export const DEMO_STARTERS = Object.freeze(NOTEBOOK_CATALOG.map((entry) => Object.freeze({
  id: entry.slug,
  label: entry.title,
  description: entry.description,
  steps: entry.steps,
  prompt: entry.prompt,
})));

function sendJson(res, status, value) {
  const body = Buffer.from(`${JSON.stringify(redactSecrets(value))}\n`, "utf8");
  res.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
  });
  res.end(body);
}

function dashboardHtml(nonce) {
  const catalog = JSON.stringify(PUBLIC_CATALOG).replace(/</gu, "\\u003c");
  const demos = JSON.stringify(DEMO_STARTERS).replace(/</gu, "\\u003c");
  const notebooks = JSON.stringify(publicNotebookCatalog()).replace(/</gu, "\\u003c");
  const canonicalChatPath = JSON.stringify(CANONICAL_CHAT_PATH);
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>BioNeMo Research Agent</title>
<style nonce="${nonce}">
:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#07110d;color:#e9fff3}*{box-sizing:border-box}body{margin:0;padding:24px;background:radial-gradient(circle at top right,#153b28,#07110d 55%);min-height:100vh}main{max-width:1100px;margin:auto}.hero,.panel{border:1px solid #2c5f43;background:#0d1c15e8;border-radius:16px;padding:20px;box-shadow:0 18px 55px #0007}.hero{display:grid;gap:12px;margin-bottom:18px}h1,h2,h3,p{margin:0}h1{font-size:clamp(28px,5vw,48px);letter-spacing:-.035em}h2{font-size:19px}.accent{color:#71f2a8}.muted{color:#9fc8af}.warning{color:#ffd888}.auth,.viewer-head,.demo-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;align-items:center}.viewer-head h2{flex:1}input,button,.action{font:inherit;border-radius:9px;padding:10px 12px}input{flex:1;min-width:240px;border:1px solid #47705a;background:#07110d;color:#fff}button,.action{border:0;background:#71f2a8;color:#052010;font-weight:700;cursor:pointer}.action{text-decoration:none;display:inline-block}button.secondary{background:#1b3b2b;color:#d9fbe7}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:12px;margin:12px 0}.card{border:1px solid #294b38;background:#0a1711;padding:14px;border-radius:12px;display:grid;gap:7px}.demo-card{border-color:#3d7b58}.pill{display:inline-block;width:max-content;padding:3px 8px;border-radius:999px;background:#183d2a;color:#88f2b3;font-size:12px}.steps{font-size:12px;color:#a8d4b8}.prompt{white-space:pre-wrap;overflow-wrap:anywhere;margin:5px 0 0;padding:10px;border:1px solid #294b38;border-radius:8px;background:#07110d;color:#d9fbe7;font:12px/1.45 ui-monospace,monospace}.runs{display:grid;gap:10px;margin-top:12px}.run{border-left:4px solid #4cd78b;background:#09150f;padding:12px;border-radius:8px}.run.failed{border-color:#ff7777}.progress{display:grid;gap:4px;margin:9px 0 0;padding:0;list-style:none}.progress li{font-size:12px;color:#a8d4b8}.progress li::before{content:'○';color:#ffd35c;margin-right:7px}.progress li.completed::before{content:'✓';color:#71f2a8}.progress li.failed::before{content:'×';color:#ff7777}.files{display:flex;gap:7px;flex-wrap:wrap;margin-top:8px}.files button{font-size:12px;padding:6px 8px}.status{min-height:22px}.research{border-left:4px solid #ffd35c;padding-left:12px;margin-top:12px}.spaced{margin-top:18px}.viewer{width:100%;height:min(70vh,650px);min-height:420px;margin-top:12px;border:1px solid #294b38;border-radius:12px;overflow:hidden;background:#07110d}.hidden{display:none}code{font-family:ui-monospace,monospace;color:#b5f7cf}
</style></head><body><main>
<section class="hero"><span class="pill">BioNeMo Agent Workbench 3.3.2</span><h1>Research workflows, <span class="accent">bounded by design.</span></h1><p class="muted">BioNeMo MCP models plus ten direct NVIDIA-hosted NIM skills and ${PUBLIC_CATALOG.workflows.length} composed workflows. Codex and Claude Code are also installed for explicitly secured terminal use.</p><div class="research"><strong>Research only.</strong> Outputs are computational hypotheses, not clinical advice. Review model confidence and validate experimentally before scientific use.</div><form id="auth" class="auth"><input id="token" type="password" autocomplete="off" placeholder="Gateway token (kept only in this page's memory)" aria-label="Gateway token"><button id="connect" type="submit">Load authenticated activity</button><button id="refresh" class="secondary" type="button">Refresh</button></form><p id="status" class="status muted" role="status">The notebook catalog is public; authenticated activity and generated-artifact downloads require the gateway token.</p></section>
<section class="panel"><h2>4 open demo notebooks</h2><p class="muted">Four image-baked, read-only workbooks are visible without another login or a notebook server. Inspect the cells, download the real .ipynb, or launch its reviewed prompt in BioNeMo chat.</p><div id="notebooks" class="grid"></div></section>
<section class="panel spaced"><h2>Start an end-to-end demo</h2><p class="muted">These reviewed prompts run the same four typed workflows as the notebooks. The EGFR research workflow can begin with cited Tavily evidence; the other three work without Tavily. Copy a prompt or open it in the canonical BioNeMo chat.</p><div id="demos" class="grid"></div></section>
<section class="panel spaced"><h2>Hosted NIM skills</h2><div id="skills" class="grid"></div><h2>Composed workflows</h2><div id="workflows" class="grid"></div></section>
<section class="panel spaced"><h2>Requests and artifacts</h2><div id="runs" class="runs"><p class="muted">Authenticate to load recent requests.</p></div></section>
<section id="viewer-panel" class="panel spaced hidden"><div class="viewer-head"><h2 id="viewer-title">Structure viewer</h2><button id="viewer-close" class="secondary" type="button">Close viewer</button></div><p class="muted">Interactive cartoon view. Drag to rotate, scroll to zoom, and right-drag to translate.</p><div id="viewer" class="viewer"></div></section></main>
<script nonce="${nonce}" src="/plugins/bionemo/assets/3dmol.min.js"></script><script nonce="${nonce}">
const catalog=${catalog},demos=${demos},notebooks=${notebooks},canonicalChatPath=${canonicalChatPath};let bearer="",refreshTimer;const q=(s)=>document.querySelector(s);const esc=(v)=>String(v??"").replace(/[&<>"']/g,c=>'&#'+c.charCodeAt(0)+';');
function card(x,kind){return '<article class="card"><span class="pill">'+kind+'</span><h3>'+esc(x.label)+'</h3><p class="muted">'+esc(x.description)+'</p>'+(x.steps?'<p class="steps">'+x.steps.map(esc).join(' → ')+'</p>':'')+'<code>'+esc(x.tool)+'</code></article>'}q('#skills').innerHTML=catalog.skills.map(x=>card(x,'NIM')).join('');q('#workflows').innerHTML=catalog.workflows.map(x=>card(x,'Workflow')).join('');
function demoCard(x,index){const href=canonicalChatPath+'&draft='+encodeURIComponent(x.prompt);return '<article class="card demo-card"><span class="pill">End-to-end</span><h3>'+esc(x.label)+'</h3><p class="muted">'+esc(x.description)+'</p><p class="steps">'+x.steps.map(esc).join(' → ')+'</p><pre class="prompt">'+esc(x.prompt)+'</pre><div class="demo-actions"><button class="secondary" type="button" data-copy-demo="'+index+'">Copy prompt</button><a class="action" target="_top" rel="noopener" href="'+esc(href)+'">Open in BioNeMo chat</a></div></article>'}q('#demos').innerHTML=demos.map(demoCard).join('');q('#demos').querySelectorAll('button[data-copy-demo]').forEach(button=>button.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(demos[Number(button.dataset.copyDemo)].prompt);button.textContent='Copied';setTimeout(()=>{button.textContent='Copy prompt'},1600)}catch{q('#status').textContent='Copy is unavailable; select the visible prompt text instead.'}}));
function notebookCard(x){return '<article class="card demo-card"><span class="pill">Guided notebook</span><h3>'+esc(x.title)+'</h3><p class="muted">'+esc(x.description)+'</p><p class="steps">'+x.steps.map(esc).join(' → ')+'</p><div class="demo-actions"><a class="action" href="'+esc(x.viewPath)+'">Open notebook</a><a class="action secondary" target="_top" rel="noopener" href="'+esc(x.chatPath)+'">Run in chat</a><a class="action secondary" href="'+esc(x.downloadPath)+'" download="'+esc(x.file)+'">Download .ipynb</a></div></article>'}q('#notebooks').innerHTML=notebooks.map(notebookCard).join('');
async function api(path,options={}){if(!bearer)throw new Error('Enter the gateway token first.');const response=await fetch(path,{...options,headers:{...(options.headers||{}),Authorization:'Bearer '+bearer}});if(!response.ok){let detail={};try{detail=await response.json()}catch{}throw new Error(detail.message||('HTTP '+response.status));}return response}
async function download(runId,name){try{const response=await api('/plugins/bionemo/api/artifacts/'+encodeURIComponent(runId)+'/'+encodeURIComponent(name));const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(error){q('#status').textContent=error.message}}
let structureViewer;async function viewStructure(runId,name){try{q('#status').textContent='Loading '+name+'…';const response=await api('/plugins/bionemo/api/artifacts/'+encodeURIComponent(runId)+'/'+encodeURIComponent(name));const structure=await response.text();if(!globalThis.$3Dmol)throw new Error('The bundled 3D viewer did not load.');q('#viewer-panel').classList.remove('hidden');q('#viewer-title').textContent=name;structureViewer?.clear();structureViewer=globalThis.$3Dmol.createViewer(q('#viewer'),{backgroundColor:'#07110d'});structureViewer.addModel(structure,/\.pdb$/i.test(name)?'pdb':'cif');structureViewer.setStyle({},{cartoon:{color:'spectrum'}});structureViewer.addStyle({hetflag:true},{stick:{radius:.18}});structureViewer.zoomTo();structureViewer.render();q('#viewer-panel').scrollIntoView({behavior:'smooth'});q('#status').textContent='Viewing '+name}catch(error){q('#status').textContent=error.message}}
function renderRuns(runs){if(!runs.length){q('#runs').innerHTML='<p class="muted">No requests yet.</p>';return}q('#runs').innerHTML=runs.map(run=>'<article class="run '+(run.status==='failed'?'failed':'')+'"><strong>'+esc(run.id)+'</strong> · '+esc(run.status)+'<br><span class="muted">'+esc(run.createdAt)+'</span>'+(run.steps?.length?'<ol class="progress">'+run.steps.map(step=>'<li class="'+esc(step.status)+'">'+esc(step.label)+' · '+esc(step.status)+(step.elapsedMs?' · '+esc(step.elapsedMs)+' ms':'')+'</li>').join('')+'</ol>':'')+(run.error?'<p class="warning">'+esc(run.error.message)+'</p>':'')+'<div class="files">'+(run.artifacts||[]).map(file=>'<button data-action="download" data-run="'+esc(run.runId)+'" data-file="'+esc(file.name)+'">Download '+esc(file.name)+' ('+esc(file.bytes)+' B)</button>'+(/\.(?:pdb|cif|mmcif)$/i.test(file.name)?'<button class="secondary" data-action="view" data-run="'+esc(run.runId)+'" data-file="'+esc(file.name)+'">View 3D</button>':'')).join('')+'</div></article>').join('');q('#runs').querySelectorAll('button[data-action]').forEach(button=>button.addEventListener('click',()=>button.dataset.action==='view'?viewStructure(button.dataset.run,button.dataset.file):download(button.dataset.run,button.dataset.file)))}
async function refresh(){try{q('#status').textContent='Loading authenticated activity…';const response=await api('/plugins/bionemo/api/status');const data=await response.json();renderRuns(data.runs||[]);q('#status').textContent=(data.status==='ready'?'Ready':'Setup required')+' · reasoning '+esc(data.configured.reasoningProvider)+' · model tools '+esc(data.configured.modelBackend)+' · Tavily '+(data.configured.tavily?'configured':'not configured')}catch(error){q('#status').textContent=error.message}}
q('#auth').addEventListener('submit',(event)=>{event.preventDefault();bearer=q('#token').value;q('#token').value='';clearInterval(refreshTimer);refresh();refreshTimer=setInterval(refresh,5000)});q('#refresh').addEventListener('click',refresh);
q('#viewer-close').addEventListener('click',()=>{structureViewer?.clear();q('#viewer-panel').classList.add('hidden')});
</script></body></html>`;
}

function structureViewerHtml(nonce, name, structure) {
  const safeName = JSON.stringify(name).replace(/</gu, "\\u003c");
  const safeStructure = JSON.stringify(structure).replace(/</gu, "\\u003c").replace(/\u2028/gu, "\\u2028").replace(/\u2029/gu, "\\u2029");
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BioNeMo 3D structure</title><style nonce="${nonce}">:root{color-scheme:dark;font-family:Inter,ui-sans-serif,system-ui,sans-serif;background:#07110d;color:#e9fff3}*{box-sizing:border-box}body{margin:0;padding:18px;background:#07110d}main{max-width:1200px;margin:auto}h1,p{margin:0 0 9px}.muted{color:#9fc8af}#viewer{width:100%;height:calc(100vh - 100px);min-height:480px;border:1px solid #2c5f43;border-radius:14px;overflow:hidden}</style></head><body><main><h1 id="title"></h1><p class="muted">Drag to rotate, scroll to zoom, and right-drag to translate. Research use only.</p><div id="viewer"></div></main><script nonce="${nonce}" src="/plugins/bionemo/assets/3dmol.min.js"></script><script nonce="${nonce}">const name=${safeName},structure=${safeStructure};document.querySelector('#title').textContent=name;if(!globalThis.$3Dmol)throw new Error('Bundled 3D viewer unavailable');const viewer=globalThis.$3Dmol.createViewer(document.querySelector('#viewer'),{backgroundColor:'#07110d'});viewer.addModel(structure,/\\.pdb$/i.test(name)?'pdb':'cif');viewer.setStyle({},{cartoon:{color:'spectrum'}});viewer.addStyle({hetflag:true},{stick:{radius:.18}});viewer.zoomTo();viewer.render();</script></body></html>`;
}

function sendHtml(res) {
  const nonce = randomBytes(18).toString("base64");
  const body = Buffer.from(dashboardHtml(nonce), "utf8");
  res.writeHead(200, {
    "Cache-Control": "no-store",
    "Content-Security-Policy": `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'`,
    "Content-Type": "text/html; charset=utf-8",
    "Content-Length": body.length,
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
  });
  res.end(body);
}

export function createUiHandlers({ store, env = process.env, runtimeVersion }) {
  const notebooks = createNotebookHandler({ root: env.BIONEMO_NOTEBOOK_ROOT || "/workspace/agent/notebooks" });
  return {
    dashboard(_req, res) { sendHtml(res); return true; },
    notebooks,
    async viewerAsset(_req, res) {
      try {
        const body = await readFile(env.BIONEMO_3DMOL_PATH || "/opt/bionemo/assets/3Dmol-min.js");
        res.writeHead(200, { "Cache-Control": "public, max-age=31536000, immutable", "Content-Type": "text/javascript; charset=utf-8", "Content-Length": body.length, "X-Content-Type-Options": "nosniff" });
        res.end(body);
      } catch { sendJson(res, 503, { code: "viewer_unavailable", message: "Bundled 3D viewer asset is unavailable" }); }
      return true;
    },
    async viewer(req, res) {
      try {
        const url = new URL(req.url || "/", "http://localhost");
        const escapedPrefix = VIEWER_ROUTE_PREFIX.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
        const match = url.pathname.match(new RegExp(`^${escapedPrefix}/([a-f0-9-]{36})/([A-Za-z0-9][A-Za-z0-9._-]{0,127})$`, "u"));
        if (req.method !== "GET" || !match) { sendJson(res, 404, { code: "not_found", message: "Unknown BioNeMo viewer route" }); return true; }
        const artifact = await store.openViewerArtifact(match[1], match[2], url.searchParams.get("access"));
        let structure;
        try { structure = (await artifact.handle.readFile()).toString("utf8"); } finally { await artifact.handle.close(); }
        const nonce = randomBytes(18).toString("base64");
        const body = Buffer.from(structureViewerHtml(nonce, match[2], structure), "utf8");
        res.writeHead(200, {
          "Cache-Control": "no-store",
          "Content-Security-Policy": `default-src 'none'; script-src 'nonce-${nonce}'; style-src 'nonce-${nonce}'; connect-src 'none'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'`,
          "Content-Type": "text/html; charset=utf-8", "Content-Length": body.length,
          "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()", "Referrer-Policy": "no-referrer",
          "X-Content-Type-Options": "nosniff", "X-Frame-Options": "SAMEORIGIN",
        });
        res.end(body);
      } catch { sendJson(res, 403, { code: "viewer_access_denied", message: "This structure viewer link is invalid or unavailable" }); }
      return true;
    },
    health(_req, res) {
      sendJson(res, 200, { status: "healthy", service: "bionemo-agent", runtimeVersion });
      return true;
    },
    async readiness(_req, res) {
      const state = capabilities(env);
      const configured = { reasoning: state.reasoning, reasoningProvider: state.reasoningProvider, modelBackend: state.modelBackend, nvidia: state.nvidia, nebius: state.nebius, openai: state.openai, anthropic: state.anthropic, mcp: state.mcp, tavily: state.tavily, gateway: Boolean(env.OPENCLAW_GATEWAY_TOKEN) };
      try { await store.initialize(); } catch (error) {
        sendJson(res, 503, { status: "not_ready", configured, artifactWorkspace: false, message: publicError(error).message });
        return true;
      }
      const ready = configured.reasoning && configured.modelBackend !== "unavailable";
      sendJson(res, 200, { status: ready ? "ready" : "setup_required", configured, artifactWorkspace: true });
      return true;
    },
    async api(req, res) {
      try {
        const url = new URL(req.url || "/", "http://localhost");
        if (req.method === "GET" && url.pathname === "/plugins/bionemo/api/status") {
          const state = capabilities(env);
          sendJson(res, 200, {
            status: state.reasoning && state.modelBackend !== "unavailable" ? "ready" : "setup_required",
            catalog: PUBLIC_CATALOG,
            configured: {
              reasoning: state.reasoning,
              reasoningProvider: state.reasoningProvider,
              modelBackend: state.modelBackend,
              nvidia: state.nvidia,
              nebius: state.nebius,
              openai: state.openai,
              anthropic: state.anthropic,
              mcp: state.mcp,
              tavily: state.tavily,
            },
            runs: await store.listRuns(),
          });
          return true;
        }
        const match = url.pathname.match(/^\/plugins\/bionemo\/api\/artifacts\/([a-f0-9-]{36})\/([A-Za-z0-9][A-Za-z0-9._-]{0,127})$/u);
        if (req.method === "GET" && match) {
          const artifact = await store.openArtifact(match[1], match[2]);
          res.writeHead(200, {
            "Cache-Control": "no-store",
            "Content-Disposition": `attachment; filename="${match[2]}"`,
            "Content-Length": artifact.size,
            "Content-Type": artifact.type,
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
          });
          artifact.handle.createReadStream({ autoClose: true }).pipe(res);
          return true;
        }
        sendJson(res, 404, { code: "not_found", message: "Unknown BioNeMo API route" });
        return true;
      } catch (error) {
        const safe = publicError(error);
        sendJson(res, safe.status >= 400 && safe.status < 600 ? safe.status : 500, safe);
        return true;
      }
    },
  };
}

export const __test = { dashboardHtml, structureViewerHtml, sendJson };
