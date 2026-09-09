import { spawn } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { capabilities, configureOpenClaw, normalizedEnvironment, validatedRemoteUrl } from "./runtime-config.mjs";
import { pinAndVerifyExampleSessions, seedExampleSessions } from "./example-sessions.mjs";
import { startMcpSchemaAdapter } from "./mcp-schema-adapter.mjs";
import { prepareClients } from "./prepare-clients.mjs";
import { startSetupServer } from "./setup-server.mjs";

export const CLOUDFLARED_URL_PATTERN = /https:\/\/[a-z0-9-]+\.trycloudflare\.com/iu;
const EXPOSURE_MODES = new Set(["cloudflare", "nebius", "external", "local"]);

function requireEnvironment(env) {
  const missing = [];
  if (!(env.AUTH_TOKEN || env.OPENCLAW_GATEWAY_TOKEN)) missing.push("AUTH_TOKEN (or OPENCLAW_GATEWAY_TOKEN)");
  if (missing.length) throw new Error(`Missing required MysteryBox-backed environment values: ${missing.join(", ")}`);
  const gatewayToken = env.OPENCLAW_GATEWAY_TOKEN || env.AUTH_TOKEN;
  if (gatewayToken.length < 24) throw new Error("Gateway token must contain at least 24 characters");
  return gatewayToken;
}

function parseBoolean(value, fallback = true, name = "BIONEMO_ENABLE_HTTPS_TUNNEL") {
  if (value === undefined || value === "") return fallback;
  if (["1", "true", "yes", "on"].includes(String(value).toLowerCase())) return true;
  if (["0", "false", "no", "off"].includes(String(value).toLowerCase())) return false;
  throw new Error(`${name} must be true or false`);
}

function safeOrigin(value) {
  const url = new URL(value);
  if (!["https:", "http:"].includes(url.protocol) || url.username || url.password || url.pathname !== "/" || url.search || url.hash) {
    throw new Error("BIONEMO_PUBLIC_ORIGIN must be an http(s) origin without credentials, path, query, or fragment");
  }
  return url.origin;
}

function exposureMode(env) {
  const explicit = String(env.BIONEMO_HTTPS_MODE || "").trim().toLowerCase();
  if (explicit) {
    if (!EXPOSURE_MODES.has(explicit)) throw new Error("BIONEMO_HTTPS_MODE must be cloudflare, nebius, external, or local");
    if (explicit === "external" && !env.BIONEMO_PUBLIC_ORIGIN) throw new Error("BIONEMO_HTTPS_MODE=external requires BIONEMO_PUBLIC_ORIGIN");
    return explicit;
  }
  if (parseBoolean(env.BIONEMO_ENABLE_HTTPS_TUNNEL, true)) return "cloudflare";
  return env.BIONEMO_PUBLIC_ORIGIN ? "external" : "local";
}

function nebiusManagedOrigin(value, port) {
  const origin = safeOrigin(value);
  const url = new URL(origin);
  const escapedPort = String(port).replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
  const hostnamePattern = new RegExp(`^port${escapedPort}-[a-z0-9]{8,64}\\.tunnel\\.applications\\.[a-z0-9-]{3,40}\\.nebius\\.cloud$`, "u");
  if (url.protocol !== "https:" || url.port || !hostnamePattern.test(url.hostname)) {
    throw new Error(`Nebius managed origin must match https://port${port}-<id>.tunnel.applications.<region>.nebius.cloud`);
  }
  return origin;
}

async function startQuickTunnel(port, { spawnImpl = spawn, timeoutMs = 45_000 } = {}) {
  const child = spawnImpl("/usr/local/bin/cloudflared", [
    "tunnel",
    "--no-autoupdate",
    "--protocol", "http2",
    "--url", `http://127.0.0.1:${port}`,
  ], {
    stdio: ["ignore", "ignore", "pipe"],
    env: {
      HOME: "/tmp/cloudflared",
      PATH: "/usr/local/bin:/usr/bin:/bin",
      SSL_CERT_DIR: "/etc/ssl/certs",
    },
  });

  const origin = await new Promise((resolve, reject) => {
    let buffer = "";
    const timer = setTimeout(() => reject(new Error("Cloudflare quick tunnel did not publish an HTTPS URL within 45 seconds")), timeoutMs);
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.once("exit", (code) => { clearTimeout(timer); reject(new Error(`cloudflared exited before startup (code ${code})`)); });
    child.stderr.on("data", (chunk) => {
      buffer = `${buffer}${chunk.toString("utf8")}`.slice(-32_768);
      const match = buffer.match(CLOUDFLARED_URL_PATTERN);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
  });
  return { child, origin };
}

async function writeRuntimeFiles({ templatePath, configPath, stateDir, origins, env = process.env, setupPort = 18790 }) {
  const config = JSON.parse(await readFile(templatePath, "utf8"));
  const dynamicNebiusOrigin = exposureMode(env) === "nebius" && !env.BIONEMO_PUBLIC_ORIGIN;
  config.gateway.controlUi.allowedOrigins = dynamicNebiusOrigin ? ["*"] : [...new Set(origins)];
  config.gateway.controlUi.dangerouslyAllowHostHeaderOriginFallback = false;
  const devicePairingRequired = parseBoolean(env.BIONEMO_REQUIRE_DEVICE_PAIRING, false, "BIONEMO_REQUIRE_DEVICE_PAIRING");
  config.gateway.controlUi.dangerouslyDisableDeviceAuth = !devicePairingRequired;
  const capabilityState = configureOpenClaw(config, env, setupPort);
  await mkdir(path.dirname(configPath), { recursive: true, mode: 0o700 });
  await mkdir(stateDir, { recursive: true, mode: 0o700 });
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await chmod(configPath, 0o600);
  const approvals = {
    version: 1,
    defaults: { security: "full", ask: "off", askFallback: "full", autoAllowSkills: true },
    agents: { bionemo: { security: "full", ask: "off", askFallback: "full", autoAllowSkills: true, allowlist: [] } },
  };
  const approvalsPath = path.join(stateDir, "exec-approvals.json");
  await writeFile(approvalsPath, `${JSON.stringify(approvals, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await chmod(approvalsPath, 0o600);
  return capabilityState;
}

function configureMcpAdapterEnvironment(runtimeEnv, { upstreamUrl, adapterUrl, processEnv = process.env }) {
  const upstream = validatedRemoteUrl(upstreamUrl, runtimeEnv);
  const adapter = new URL(adapterUrl);
  if (adapter.protocol !== "http:" || adapter.hostname !== "127.0.0.1" || !adapter.port || adapter.pathname !== "/mcp" || adapter.username || adapter.password || adapter.search || adapter.hash) {
    throw new Error("MCP schema adapter URL must be an exact loopback HTTP /mcp endpoint");
  }
  if (adapter.toString() === upstream) throw new Error("MCP upstream and schema adapter URLs must be distinct");
  runtimeEnv.BIONEMO_MCP_UPSTREAM_URL = upstream;
  runtimeEnv.BIONEMO_MCP_URL = adapter.toString();
  runtimeEnv.BIONEMO_ALLOW_INSECURE_MCP = "true";
  processEnv.BIONEMO_MCP_UPSTREAM_URL = upstream;
  processEnv.BIONEMO_MCP_URL = adapter.toString();
  processEnv.BIONEMO_ALLOW_INSECURE_MCP = "true";
  return runtimeEnv;
}

function gatewayChildEnvironment(runtimeEnv, gatewayToken, { port, stateDir, configPath }) {
  const childEnv = {
    ...runtimeEnv,
    OPENCLAW_GATEWAY_TOKEN: gatewayToken,
    OPENCLAW_GATEWAY_PORT: String(port),
    OPENCLAW_STATE_DIR: stateDir,
    OPENCLAW_CONFIG_PATH: configPath,
  };
  delete childEnv.AUTH_TOKEN;
  // OpenClaw treats TAVILY_API_KEY as an opt-in to its separately packaged
  // official plugin and otherwise attempts an npm install during startup.
  // Keep the injected public env name for Codex/Claude preparation, but give
  // the hardened browser child only a private alias used by our remote MCP
  // transport and composed workflow client.
  if (childEnv.TAVILY_API_KEY) childEnv.BIONEMO_TAVILY_API_KEY = childEnv.TAVILY_API_KEY;
  delete childEnv.TAVILY_API_KEY;
  return childEnv;
}

async function main() {
  const runtimeEnv = normalizedEnvironment(process.env);
  const gatewayToken = requireEnvironment(runtimeEnv);
  const port = Number(runtimeEnv.PORT || runtimeEnv.OPENCLAW_GATEWAY_PORT || 18789);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("PORT must be an integer between 1024 and 65535");
  const stateDir = runtimeEnv.OPENCLAW_STATE_DIR || "/workspace/state";
  const configPath = runtimeEnv.OPENCLAW_CONFIG_PATH || path.join(stateDir, "openclaw.json");
  process.env.OPENCLAW_STATE_DIR = stateDir;
  process.env.OPENCLAW_CONFIG_PATH = configPath;
  const templatePath = runtimeEnv.BIONEMO_CONFIG_TEMPLATE || "/opt/bionemo/config/openclaw.template.json";
  const setupPort = Number(runtimeEnv.BIONEMO_SETUP_PORT || 18790);
  const mcpAdapterPort = Number(runtimeEnv.BIONEMO_MCP_ADAPTER_PORT || 18791);
  if (!Number.isInteger(setupPort) || setupPort < 1024 || setupPort > 65535) throw new Error("BIONEMO_SETUP_PORT must be an integer between 1024 and 65535");
  if (!Number.isInteger(mcpAdapterPort) || mcpAdapterPort < 1024 || mcpAdapterPort > 65535) throw new Error("BIONEMO_MCP_ADAPTER_PORT must be an integer between 1024 and 65535");
  if (new Set([port, setupPort, mcpAdapterPort]).size !== 3) throw new Error("Gateway, setup, and MCP adapter ports must be distinct");
  const mode = exposureMode(runtimeEnv);
  let tunnel = null;
  let mcpAdapter = null;
  let publicOrigin = null;
  const origins = [`http://127.0.0.1:${port}`, `http://localhost:${port}`];

  if (mode === "cloudflare") {
    if (runtimeEnv.BIONEMO_PUBLIC_ORIGIN) origins.push(safeOrigin(runtimeEnv.BIONEMO_PUBLIC_ORIGIN));
    tunnel = await startQuickTunnel(port);
    publicOrigin = tunnel.origin;
    process.stdout.write(`BioNeMo authenticated HTTPS browser URL: ${publicOrigin}\n`);
    process.stdout.write("Open the URL and enter the MysteryBox AUTH_TOKEN in OpenClaw; the token is never placed in the URL.\n");
  } else if (mode === "nebius") {
    if (runtimeEnv.BIONEMO_PUBLIC_ORIGIN) publicOrigin = nebiusManagedOrigin(runtimeEnv.BIONEMO_PUBLIC_ORIGIN, port);
    if (publicOrigin) process.stdout.write(`BioNeMo native Nebius HTTPS browser URL: ${publicOrigin}\n`);
    else process.stdout.write("BioNeMo native Nebius HTTPS mode: use the managed https:// URL from the endpoint's public_endpoints status. The event Control UI accepts that post-create browser origin and still requires the rate-limited OpenClaw gateway token. This mode requires no public VM IP and no Serverless bearer-auth layer.\n");
  } else if (mode === "external") {
    publicOrigin = safeOrigin(runtimeEnv.BIONEMO_PUBLIC_ORIGIN);
  } else {
    process.stdout.write("External HTTPS exposure disabled; only local browser origins are configured.\n");
  }
  if (publicOrigin) origins.push(publicOrigin);

  const initialCapabilities = capabilities(runtimeEnv);
  if (initialCapabilities.mcp) {
    mcpAdapter = await startMcpSchemaAdapter({
      upstreamUrl: initialCapabilities.mcpUrl,
      apiKey: runtimeEnv.BIONEMO_MCP_API_KEY,
      port: mcpAdapterPort,
    });
    // OpenClaw, Codex, and Claude consume the flattened loopback MCP contract.
    // The adapter owns credential forwarding for those adapted client calls.
    // Composed plugin workflows keep the validated raw upstream URL and use the
    // same injected credential through their native typed gateway client.
    mcpAdapter.server.unref();
    configureMcpAdapterEnvironment(runtimeEnv, {
      upstreamUrl: initialCapabilities.mcpUrl,
      adapterUrl: mcpAdapter.url,
    });
    process.stdout.write("BioNeMo MCP schema adapter: active on loopback; remote request envelopes are normalized locally.\n");
  }

  const capabilityState = await writeRuntimeFiles({ templatePath, configPath, stateDir, origins, env: runtimeEnv, setupPort });
  const seededSessions = await seedExampleSessions({ configPath });
  process.stdout.write(`BioNeMo ready example sessions: ${seededSessions.length} native static starters seeded; no workflow was started.\n`);
  const devicePairingRequired = parseBoolean(runtimeEnv.BIONEMO_REQUIRE_DEVICE_PAIRING, false, "BIONEMO_REQUIRE_DEVICE_PAIRING");
  process.stdout.write(`BioNeMo browser authentication: gateway token${devicePairingRequired ? " plus one-time device approval" : " only; per-browser device approval disabled"}.\n`);
  await prepareClients(runtimeEnv);
  const setupServer = await startSetupServer(setupPort);
  process.stdout.write(`BioNeMo capability mode: reasoning=${capabilityState.reasoningProvider}, models=${capabilityState.modelBackend}, mcp=${capabilityState.mcp ? "configured" : "not configured"}, tavily=${capabilityState.tavily ? "configured" : "not configured"}\n`);
  if (!capabilityState.reasoning || capabilityState.modelBackend === "unavailable") {
    process.stdout.write("BioNeMo setup is incomplete; the browser remains available and will explain which optional credential is missing.\n");
  }
  const childEnv = gatewayChildEnvironment(runtimeEnv, gatewayToken, { port, stateDir, configPath });
  if (publicOrigin) childEnv.BIONEMO_PUBLIC_URL = publicOrigin;
  const gateway = spawn("node", ["/app/openclaw.mjs", "gateway", "run", "--port", String(port), "--bind", "lan"], {
    stdio: "inherit",
    env: childEnv,
  });
  const gatewayExit = new Promise((resolve) => gateway.once("exit", (code, signal) => resolve(code ?? (signal ? 128 : 1))));

  let stopping = false;
  const stop = (signal = "SIGTERM") => {
    if (stopping) return;
    stopping = true;
    if (!gateway.killed) gateway.kill(signal);
    if (tunnel && !tunnel.child.killed) tunnel.child.kill(signal);
    mcpAdapter?.server.close();
    setupServer?.close();
  };
  process.on("SIGTERM", () => stop("SIGTERM"));
  process.on("SIGINT", () => stop("SIGINT"));
  gateway.once("error", (error) => { process.stderr.write(`OpenClaw gateway failed to start: ${error.message}\n`); stop(); });
  tunnel?.child.once("exit", (code) => {
    if (!stopping) { process.stderr.write(`HTTPS tunnel stopped unexpectedly (code ${code}); shutting down gateway.\n`); stop(); }
  });
  try {
    await pinAndVerifyExampleSessions({ port, token: gatewayToken });
    process.stdout.write(`BioNeMo ready example sessions: ${seededSessions.length} visible and pinned in the Sessions sidebar.\n`);
  } catch (error) {
    stop();
    throw error;
  }
  const exitCode = await gatewayExit;
  stop();
  process.exitCode = exitCode;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => {
    process.stderr.write(`BioNeMo launcher error: ${error.message}\n`);
    process.exitCode = 78;
  });
}

export const __test = { CLOUDFLARED_URL_PATTERN, requireEnvironment, parseBoolean, safeOrigin, exposureMode, nebiusManagedOrigin, startQuickTunnel, writeRuntimeFiles, configureMcpAdapterEnvironment, gatewayChildEnvironment };
