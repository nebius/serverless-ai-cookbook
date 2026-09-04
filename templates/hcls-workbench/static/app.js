const state = { csrf: null, capabilities: null, pollTimer: null };
const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body) headers["Content-Type"] = "application/json";
  if (state.csrf && options.method && options.method !== "GET") headers["X-CSRF-Token"] = state.csrf;
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({ detail: "Unexpected non-JSON response" }));
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail));
  return payload;
}

function setText(id, value) { $(id).textContent = value || ""; }
function show(id, visible) { $(id).classList.toggle("hidden", !visible); }

function authenticated(session) {
  state.csrf = session.csrf_token;
  show("login-panel", false);
  show("workspace", true);
  show("logout-button", true);
  const select = $("endpoint-select");
  select.replaceChildren(new Option("Custom endpoint", ""));
  (session.default_endpoints || []).forEach((item) => select.add(new Option(item.name, item.url)));
  if (session.connected && session.capabilities) connected(session.endpoint_url, session.capabilities);
}

function connected(endpointUrl, capabilities) {
  state.capabilities = capabilities;
  $("endpoint-url").value = endpointUrl;
  show("connect-card", false);
  show("work-grid", true);
  $("connection-status").textContent = capabilities.service;
  $("connection-status").classList.add("connected");
  document.querySelectorAll(".step").forEach((node) => node.classList.add("active"));
  const engine = capabilities.engine || {};
  const accelerator = capabilities.accelerator || {};
  const summary = $("engine-summary");
  summary.replaceChildren();
  const title = document.createElement("strong");
  title.textContent = `${engine.name || capabilities.service} ${engine.version || ""}`.trim();
  const description = document.createElement("p");
  description.textContent = capabilities.disclaimer || "Research compute endpoint";
  const badges = document.createElement("div");
  badges.className = "engine-badges";
  [capabilities.workload, accelerator.kind, engine.scoring_semantics].filter(Boolean).forEach((value) => {
    const badge = document.createElement("span"); badge.textContent = value; badges.appendChild(badge);
  });
  summary.append(title, description, badges);
  resetExample();
}

function resetExample() {
  const example = state.capabilities?.examples?.[0]?.input || {};
  $("run-input").value = JSON.stringify(example, null, 2);
}

function renderRun(run) {
  const status = run.status || "unknown";
  $("run-state").textContent = status;
  $("run-state").className = `run-state ${status}`;
  show("empty-result", false);
  show("result-content", true);
  const metadata = $("run-metadata");
  metadata.replaceChildren();
  [["Run ID", run.run_id], ["Service", run.service], ["Started", run.started_at || "Waiting"], ["Finished", run.finished_at || "In progress"]].forEach(([key, value]) => {
    const wrapper = document.createElement("div");
    const dt = document.createElement("dt"); dt.textContent = key;
    const dd = document.createElement("dd"); dd.textContent = value;
    wrapper.append(dt, dd); metadata.appendChild(wrapper);
  });
  $("result-json").textContent = JSON.stringify(run.result || run.error || { status }, null, 2);
  const artifacts = $("artifacts"); artifacts.replaceChildren();
  (run.artifacts || []).forEach((artifact) => {
    const row = document.createElement("div"); row.className = "artifact";
    const name = document.createElement("span"); name.textContent = `${artifact.name} · ${artifact.bytes} B`;
    const link = document.createElement("a");
    link.textContent = "Download";
    link.href = `/api/runs/${encodeURIComponent(run.run_id)}/artifacts/${artifact.name.split("/").map(encodeURIComponent).join("/")}`;
    row.append(name, link); artifacts.appendChild(row);
  });
}

async function pollRun(runId) {
  clearTimeout(state.pollTimer);
  try {
    const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
    renderRun(run);
    if (!["succeeded", "failed", "cancelled"].includes(run.status)) state.pollTimer = setTimeout(() => pollRun(runId), 1500);
    else $("run-button").disabled = false;
  } catch (error) {
    setText("run-error", error.message);
    $("run-button").disabled = false;
  }
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setText("login-error", "");
  try {
    const result = await api("/api/login", { method: "POST", body: JSON.stringify({ access_key: $("access-key").value }) });
    const session = await api("/api/session");
    authenticated({ ...session, csrf_token: result.csrf_token });
    $("access-key").value = "";
  } catch (error) { setText("login-error", error.message); }
});

$("logout-button").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" }).catch(() => {});
  window.location.reload();
});

$("endpoint-select").addEventListener("change", () => {
  if ($("endpoint-select").value) $("endpoint-url").value = $("endpoint-select").value;
});

$("connect-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setText("connect-error", "");
  try {
    const result = await api("/api/connect", { method: "POST", body: JSON.stringify({ endpoint_url: $("endpoint-url").value, token: $("endpoint-token").value }) });
    $("endpoint-token").value = "";
    connected(result.endpoint_url, result.capabilities);
  } catch (error) { setText("connect-error", error.message); }
});

$("change-endpoint").addEventListener("click", () => {
  clearTimeout(state.pollTimer);
  show("connect-card", true); show("work-grid", false);
  $("connection-status").textContent = "Not connected";
  $("connection-status").classList.remove("connected");
});
$("reset-example").addEventListener("click", resetExample);

$("run-form").addEventListener("submit", async (event) => {
  event.preventDefault(); setText("run-error", "");
  let input;
  try { input = JSON.parse($("run-input").value); }
  catch (error) { setText("run-error", `Input is not valid JSON: ${error.message}`); return; }
  $("run-button").disabled = true;
  try {
    const run = await api("/api/runs", { method: "POST", body: JSON.stringify({ input }) });
    renderRun(run); pollRun(run.run_id);
  } catch (error) { setText("run-error", error.message); $("run-button").disabled = false; }
});

(async () => {
  try {
    const session = await api("/api/session");
    if (session.authenticated) authenticated(session);
  } catch (error) { setText("login-error", error.message); }
})();
