from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import os
import re

app = FastAPI(title="SIPA MLL Agent Router", version="1.0.0")

# Nebius Token Factory endpoint (OpenAI-compatible)
TF_BASE_URL = "https://api.studio.nebius.ai/v1"

# MLL Routing table: intent -> model
ROUTING_TABLE = {
    "crisis":   "NousResearch/Hermes-4-70B",
    "code":     "Qwen/Qwen3-32B",
    "research": "deepseek-ai/DeepSeek-V4-Pro",
    "writing":  "openai/gpt-oss-120b",
    "general":  "nvidia/Nemotron-3-Super-120b-a12b",
}

SYSTEM_PROMPTS = {
    "crisis": (
        "You are a warm, empathetic mental health support companion. "
        "Validate feelings, offer grounding techniques, and gently suggest "
        "professional resources when appropriate. Never dismiss emotions."
    ),
    "code": "You are an expert software engineer. Provide clean, well-commented code.",
    "research": "You are a research analyst. Be thorough, cite reasoning, and acknowledge uncertainty.",
    "writing": "You are a skilled writer. Adapt tone and style to the request.",
    "general": (
        "You are a helpful AI assistant designed for neurodivergent users. "
        "Be clear, structured, and patient."
    ),
}

# Keywords for intent classification
CRISIS_KEYWORDS = r"overwhelm|cannot cope|hopeless|worthless|suicide|self.harm|crisis|breakdown"
CODE_KEYWORDS = r"\bcode\b|function|debug|error|python|javascript|bash|sql|api|deploy"
RESEARCH_KEYWORDS = r"explain|research|analyz|summariz|why|how does|what is|compare"
WRITING_KEYWORDS = r"write|draft|letter|post|essay|email|story|article|blog"


def classify_intent(message: str) -> str:
    """Classify message intent using keyword matching (MLL L01 simplified)."""
    msg = message.lower()
    if re.search(CRISIS_KEYWORDS, msg):
        return "crisis"
    if re.search(CODE_KEYWORDS, msg):
        return "code"
    if re.search(WRITING_KEYWORDS, msg):
        return "writing"
    if re.search(RESEARCH_KEYWORDS, msg):
        return "research"
    return "general"


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    max_tokens: int = 512


class ChatResponse(BaseModel):
    session_id: str
    intent: str
    model_used: str
    response: str
    tokens_used: int


@app.get("/")
def root():
    return {
        "name": "SIPA MLL Agent Router",
        "version": "1.0.0",
        "description": "Multi-layer routing agent for neurodivergent AI support",
        "routes": list(ROUTING_TABLE.keys()),
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="NEBIUS_API_KEY not set")

    intent = classify_intent(req.message)
    model = ROUTING_TABLE[intent]
    system_prompt = SYSTEM_PROMPTS[intent]

    client = OpenAI(api_key=api_key, base_url=TF_BASE_URL)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message},
        ],
        max_tokens=req.max_tokens,
        temperature=0.7,
    )

    return ChatResponse(
        session_id=req.session_id,
        intent=intent,
        model_used=model,
        response=completion.choices[0].message.content,
        tokens_used=completion.usage.total_tokens if completion.usage else 0,
    )

