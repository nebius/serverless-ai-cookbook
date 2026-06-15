"""GPU-deployable BioNeMo-compatible demo service for the cookbook recipe."""

import hashlib
import os
import shutil
import subprocess
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from bionemo_agent.catalog import CAPABILITIES, SAFETY_NOTICE, SERVICE_PATHS, route_request

app = FastAPI(
    title="Self-hosted BioNeMo-compatible Demo Service",
    version="0.1.0",
)


class TextRequest(BaseModel):
    text: str = Field(default="public EGFR kinase assay abstract")


class SequenceRequest(BaseModel):
    sequence: str = Field(default="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP")


class RetrievalRequest(BaseModel):
    query: str = Field(default="public benchmark biomedical retrieval")
    top_k: int = Field(default=3, ge=1, le=10)


class MolecularDynamicsRequest(BaseModel):
    system_name: str = Field(default="public-toy-water-box")
    steps: int = Field(default=250, ge=1, le=100_000)


class GenomicsRequest(BaseModel):
    prompt: str = Field(default="ATGCGT")
    length: int = Field(default=48, ge=1, le=512)


class ChatCompletionRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    input_message: str | None = None


def _require_api_key(request: Request) -> None:
    expected = os.getenv("BIONEMO_SERVICE_API_KEY")
    if not expected:
        return

    header = request.headers.get("authorization", "")
    if header != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def _gpu_status() -> dict[str, Any]:
    visible_devices = os.getenv("NVIDIA_VISIBLE_DEVICES") or os.getenv("CUDA_VISIBLE_DEVICES")
    status: dict[str, Any] = {
        "platform": "gpu-ready",
        "visible_devices": visible_devices,
        "nvidia_smi": None,
    }

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            output = subprocess.check_output(
                [
                    nvidia_smi,
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ],
                text=True,
                timeout=5,
            )
            status["nvidia_smi"] = [line.strip() for line in output.splitlines() if line.strip()]
        except (OSError, subprocess.SubprocessError) as exc:
            status["nvidia_smi_error"] = str(exc)

    return status


def _embedding(sequence: str, size: int = 16) -> list[float]:
    digest = hashlib.sha256(sequence.encode("utf-8")).digest()
    return [round((digest[index] / 255.0) * 2.0 - 1.0, 6) for index in range(size)]


def _message_text(request: ChatCompletionRequest) -> str:
    if request.input_message:
        return request.input_message
    for message in reversed(request.messages):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    return "Route a safe nonclinical BioNeMo research request."


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "self-hosted-bionemo-compatible-demo",
        "gpu": _gpu_status(),
    }


@app.get("/v1/capabilities")
def capabilities(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    return {
        "safety_notice": SAFETY_NOTICE,
        "service_paths": SERVICE_PATHS,
        "capabilities": CAPABILITIES,
    }


@app.post("/v1/chat/completions")
def chat(request: ChatCompletionRequest, _: None = Depends(_require_api_key)) -> dict[str, Any]:
    prompt = _message_text(request)
    routed = route_request(prompt)
    content = (
        "Self-hosted BioNeMo-compatible demo response. "
        "This is research-only and deterministic. Routing evidence: "
        f"{routed}"
    )
    return {
        "id": "bionemo-demo-chat",
        "object": "chat.completion",
        "model": "self-hosted-bionemo-demo",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }


@app.post("/v1/embeddings/protein")
def protein_embedding(
    request: SequenceRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    return {
        "model": "facebook-esm-2-650m-protein-embedding-demo",
        "sequence_length": len(request.sequence),
        "embedding": _embedding(request.sequence),
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/structure/boltz2")
def structure_prediction(
    request: SequenceRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    digest = hashlib.sha1(request.sequence.encode("utf-8")).hexdigest()[:12]
    return {
        "model": "boltz2-compatible-demo",
        "sequence_length": len(request.sequence),
        "artifact": {
            "pdb_id": f"demo-{digest}",
            "format": "pdb",
            "confidence": 0.72,
        },
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/retrieval/literature")
def literature_retrieval(
    request: RetrievalRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    documents = [
        {
            "rank": index + 1,
            "title": f"Public biomedical retrieval demo document {index + 1}",
            "score": round(0.91 - index * 0.07, 3),
            "snippet": f"Deterministic nonclinical result for query: {request.query}",
        }
        for index in range(request.top_k)
    ]
    return {
        "model": "nvidia-nv-embedqa-e5-v5-compatible-demo",
        "query": request.query,
        "documents": documents,
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/md/openmm")
def molecular_dynamics(
    request: MolecularDynamicsRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    ns_per_day = round(15.0 + min(request.steps, 10_000) / 1000.0, 3)
    return {
        "model": "openmm-md-8-5-1-compatible-demo",
        "system_name": request.system_name,
        "steps": request.steps,
        "timing": {"estimated_ns_per_day": ns_per_day, "gpu": _gpu_status()},
        "artifacts": ["energy.csv", "trajectory.dcd"],
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/genomics/carbon")
def genomics_generation(
    request: GenomicsRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    alphabet = "ACGT"
    seed = hashlib.sha256(request.prompt.encode("utf-8")).digest()
    generated = "".join(alphabet[byte % len(alphabet)] for byte in seed)
    while len(generated) < request.length:
        generated += generated
    return {
        "model": "carbon-3b-compatible-demo",
        "prompt": request.prompt,
        "generated_sequence": generated[: request.length],
        "safety_notice": SAFETY_NOTICE,
    }
