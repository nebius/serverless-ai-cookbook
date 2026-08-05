const port = Number(process.env.PORT || process.env.OPENCLAW_GATEWAY_PORT || 18789);
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 4_000);
try {
  const response = await fetch(`http://127.0.0.1:${port}/healthz`, { signal: controller.signal });
  if (!response.ok) process.exitCode = 1;
} catch {
  process.exitCode = 1;
} finally {
  clearTimeout(timer);
}
