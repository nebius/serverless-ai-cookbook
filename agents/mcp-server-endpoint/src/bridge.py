import sys
import json
import httpx

url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"

def out(obj):
    print(json.dumps(obj), flush=True)

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    mid = msg.get("id")
    method = msg.get("method", "")

    if method == "initialize":
        out({"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "mcp-endpoint", "version": "1.0"}
        }})
    elif method == "notifications/initialized":
        pass
    elif method == "tools/list":
        r = httpx.get(f"{url}/tools")
        out({"jsonrpc": "2.0", "id": mid, "result": r.json()})
    elif method == "tools/call":
        p = msg["params"]
        r = httpx.post(f"{url}/call", json={
            "name": p["name"],
            "arguments": p.get("arguments", {})
        })
        out({"jsonrpc": "2.0", "id": mid, "result": r.json()})
