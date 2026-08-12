import http from "node:http";

function responseBody() {
  const message = [
    "BioNeMo Agent Workbench is running, but no reasoning-model credential is configured.",
    "Set NVIDIA_API_KEY for NVIDIA Build (recommended), or NEBIUS_API_KEY for Nebius Token Factory, then restart the endpoint.",
    "BioNeMo model tools additionally use BIONEMO_MCP_API_KEY for the default Cerebrium MCP gateway; an NVIDIA key alone enables the direct hosted-NIM adapters.",
    "Optional: set TAVILY_API_KEY for web search. No credential is stored in the image.",
  ].join(" ");
  return { id: "setup-required", object: "chat.completion", created: Math.floor(Date.now() / 1000), model: "setup-required", choices: [{ index: 0, message: { role: "assistant", content: message }, finish_reason: "stop" }], usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 } };
}

export function startSetupServer(port = 18790) {
  const server = http.createServer((req, res) => {
    if (req.method === "GET" && req.url === "/healthz") {
      res.writeHead(200, { "Content-Type": "application/json", "Cache-Control": "no-store" });
      res.end('{"status":"ok"}\n');
      return;
    }
    if (req.method === "POST" && req.url === "/v1/chat/completions") {
      let size = 0;
      req.on("data", (chunk) => { size += chunk.length; if (size > 1_000_000) req.destroy(); });
      req.on("end", () => {
        const body = Buffer.from(`${JSON.stringify(responseBody())}\n`);
        res.writeHead(200, { "Content-Type": "application/json", "Content-Length": body.length, "Cache-Control": "no-store" });
        res.end(body);
      });
      return;
    }
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end('{"error":{"message":"not found"}}\n');
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}
