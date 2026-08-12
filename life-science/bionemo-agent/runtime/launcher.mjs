import { spawn } from "node:child_process";
import { chmod, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { configureOpenClaw, normalizedEnvironment } from "./runtime-config.mjs";
import { prepareClients } from "./prepare-clients.mjs";
import { startSetupServer } from "./setup-server.mjs";

export const CLOUDFLARED_URL_PATTERN = /https:\/\/[a-z0-9-]+\.trycloudflare\.com/iu;

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
  config.gateway.controlUi.allowedOrigins = [...new Set(origins)];
  const devicePairingRequired = parseBoolean(env.BIONEMO_REQUIRE_DEVICE_PAIRING, false, "BIONEMO_REQUIRE_DEVICE_PAIRING");
  config.gateway.controlUi.dangerouslyDisableDeviceAuth = !devicePairingRequired;
  const capabilityState = configureOpenClaw(config, env, setupPort);
  await mkdir(path.dirname(configPath), { recursive: true, mode: 0o700 });
  await mkdir(stateDir, { recursive: true, mode: 0o700 });
  await writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await chmod(configPath, 0o600);
  const approvals = {
    version: 1,
    defaults: { security: "deny", ask: "off", askFallback: "deny", autoAllowSkills: false },
    agents: { bionemo: { security: "deny", ask: "off", askFallback: "deny", autoAllowSkills: false, allowlist: [] } },
  };
  const approvalsPath = path.join(stateDir, "exec-approvals.json");
  await writeFile(approvalsPath, `${JSON.stringify(approvals, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await chmod(approvalsPath, 0o600);
  return capabilityState;
}

async function main() {
  const runtimeEnv = normalizedEnvironment(process.env);
  const gatewayToken = requireEnvironment(runtimeEnv);
  const port = Number(runtimeEnv.PORT || runtimeEnv.OPENCLAW_GATEWAY_PORT || 18789);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error("PORT must be an integer between 1024 and 65535");
  const stateDir = runtimeEnv.OPENCLAW_STATE_DIR || "/workspace/state";
  const configPath = runtimeEnv.OPENCLAW_CONFIG_PATH || path.join(stateDir, "openclaw.json");
  const templatePath = runtimeEnv.BIONEMO_CONFIG_TEMPLATE || "/opt/bionemo/config/openclaw.template.json";
  const setupPort = Number(runtimeEnv.BIONEMO_SETUP_PORT || 18790);
  const tunnelEnabled = parseBoolean(runtimeEnv.BIONEMO_ENABLE_HTTPS_TUNNEL, true);
  let tunnel = null;
  const origins = [`http://127.0.0.1:${port}`, `http://localhost:${port}`];
  if (runtimeEnv.BIONEMO_PUBLIC_ORIGIN) origins.push(safeOrigin(runtimeEnv.BIONEMO_PUBLIC_ORIGIN));

  if (tunnelEnabled) {
    tunnel = await startQuickTunnel(port);
    origins.push(tunnel.origin);
    process.stdout.write(`BioNeMo authenticated HTTPS browser URL: ${tunnel.origin}\n`);
    process.stdout.write("Open the URL and enter the MysteryBox AUTH_TOKEN in OpenClaw; the token is never placed in the URL.\n");
  } else if (!runtimeEnv.BIONEMO_PUBLIC_ORIGIN) {
    process.stdout.write("HTTPS tunnel disabled; only local browser origins are configured. Set BIONEMO_PUBLIC_ORIGIN for a supervised external HTTPS proxy.\n");
  }

  const capabilityState = await writeRuntimeFiles({ templatePath, configPath, stateDir, origins, env: runtimeEnv, setupPort });
  const devicePairingRequired = parseBoolean(runtimeEnv.BIONEMO_REQUIRE_DEVICE_PAIRING, false, "BIONEMO_REQUIRE_DEVICE_PAIRING");
  process.stdout.write(`BioNeMo browser authentication: gateway token${devicePairingRequired ? " plus one-time device approval" : " only; per-browser device approval disabled"}.\n`);
  await prepareClients(runtimeEnv);
  const setupServer = capabilityState.reasoningProvider === "setup" ? await startSetupServer(setupPort) : null;
  process.stdout.write(`BioNeMo capability mode: reasoning=${capabilityState.reasoningProvider}, models=${capabilityState.modelBackend}, mcp=${capabilityState.mcp ? "configured" : "not configured"}, tavily=${capabilityState.tavily ? "configured" : "not configured"}\n`);
  if (!capabilityState.reasoning || capabilityState.modelBackend === "unavailable") {
    process.stdout.write("BioNeMo setup is incomplete; the browser remains available and will explain which optional credential is missing.\n");
  }
  const childEnv = { ...runtimeEnv, OPENCLAW_GATEWAY_TOKEN: gatewayToken, OPENCLAW_GATEWAY_PORT: String(port), OPENCLAW_STATE_DIR: stateDir, OPENCLAW_CONFIG_PATH: configPath };
  delete childEnv.AUTH_TOKEN;
  if (tunnel?.origin) childEnv.BIONEMO_PUBLIC_URL = tunnel.origin;
  const gateway = spawn("node", ["/app/openclaw.mjs", "gateway", "run", "--port", String(port), "--bind", "lan"], {
    stdio: "inherit",
    env: childEnv,
  });

  let stopping = false;
  const stop = (signal = "SIGTERM") => {
    if (stopping) return;
    stopping = true;
    if (!gateway.killed) gateway.kill(signal);
    if (tunnel && !tunnel.child.killed) tunnel.child.kill(signal);
    setupServer?.close();
  };
  process.on("SIGTERM", () => stop("SIGTERM"));
  process.on("SIGINT", () => stop("SIGINT"));
  gateway.once("error", (error) => { process.stderr.write(`OpenClaw gateway failed to start: ${error.message}\n`); stop(); });
  tunnel?.child.once("exit", (code) => {
    if (!stopping) { process.stderr.write(`HTTPS tunnel stopped unexpectedly (code ${code}); shutting down gateway.\n`); stop(); }
  });
  const exitCode = await new Promise((resolve) => gateway.once("exit", (code, signal) => resolve(code ?? (signal ? 128 : 1))));
  stop();
  process.exitCode = exitCode;
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href) {
  main().catch((error) => {
    process.stderr.write(`BioNeMo launcher error: ${error.message}\n`);
    process.exitCode = 78;
  });
}

export const __test = { CLOUDFLARED_URL_PATTERN, requireEnvironment, parseBoolean, safeOrigin, startQuickTunnel, writeRuntimeFiles };
