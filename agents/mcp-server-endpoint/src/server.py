import os
import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

API_KEY = os.environ["NEBIUS_API_KEY"]
BASE_URL = "https://api.ai.nebius.cloud/v1"
MODEL = "Qwen/Qwen3-Embedding-8B"

TOOLS = [{
    "name": "embed",
    "description": "Return embedding vector for a text input",
    "inputSchema": {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"]
    }
}]

class Call(BaseModel):
    name: str
    arguments: dict

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tools")
def tools():
    return {"tools": TOOLS}

@app.post("/call")
async def call(req: Call):
    if req.name != "embed":
        return {"error": f"unknown tool {req.name}"}
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE_URL}/embeddings",
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": MODEL, "input": req.arguments["text"]},
            timeout=30,
        )
    vec = r.json()["data"][0]["embedding"]
    return {"content": [{"type": "text", "text": str(vec[:8]) + " ..."}]}
