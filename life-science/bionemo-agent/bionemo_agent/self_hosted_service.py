"""GPU-deployable BioNeMo-compatible demo service for the cookbook recipe."""

import hashlib
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from typing import Any
from urllib import error
from urllib import request as urllib_request

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from bionemo_agent.catalog import (
    CAPABILITIES,
    MODEL_SERVICE_SKILLS,
    SAFETY_NOTICE,
    SERVICE_PATHS,
    route_request,
)

app = FastAPI(
    title="BioNeMo-compatible Model Service",
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


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _gpu_is_available(gpu_status: dict[str, Any]) -> bool:
    return bool(gpu_status.get("nvidia_smi"))


def _service_mode() -> str:
    return os.getenv("BIONEMO_MODEL_SERVICE_MODE", "demo").strip().lower()


def _skill_env_prefix(skill: str) -> str:
    return f"BIONEMO_MODEL_{skill.upper()}"


def _real_backend_url(skill: str) -> str | None:
    value = os.getenv(f"{_skill_env_prefix(skill)}_URL")
    return value.strip() if value and value.strip() else None


def _backend_mode(skill: str) -> str:
    return "real_http" if _real_backend_url(skill) else "demo"


def _call_real_backend(skill: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    url = _real_backend_url(skill)
    if not url:
        if _service_mode() == "real":
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Real model backend for {skill} is not configured. "
                    f"Set {_skill_env_prefix(skill)}_URL."
                ),
            )
        return None

    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    api_key = os.getenv(f"{_skill_env_prefix(skill)}_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib_request.Request(
        url=url,
        data=json_bytes(payload),
        headers=headers,
        method="POST",
    )
    timeout = float(os.getenv("BIONEMO_MODEL_BACKEND_TIMEOUT", "30"))
    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "skill": skill,
                "backend_status": exc.code,
                "backend_body": exc.read().decode("utf-8", errors="replace")[:2000],
            },
        ) from exc
    except error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail={"skill": skill, "backend_error": str(exc.reason)},
        ) from exc

    if not body:
        return {"status": "ok", "backend": "real_http"}
    try:
        parsed = json_loads(body)
    except ValueError:
        parsed = {"body": body}
    if isinstance(parsed, dict):
        parsed.setdefault("backend", "real_http")
        return parsed
    return {"body": parsed, "backend": "real_http"}


def json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload).encode("utf-8")


def json_loads(payload: str) -> Any:
    import json

    return json.loads(payload)


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
    payload = _service_health_payload()
    if payload["status"] != "healthy" and _env_flag("BIONEMO_HEALTH_STRICT"):
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/health/models")
def health_models() -> dict[str, Any]:
    return _model_health_payload()


@app.get("/v1/models/health")
def v1_model_health(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    return _model_health_payload()


@app.get("/v1/capabilities")
def capabilities(_: None = Depends(_require_api_key)) -> dict[str, Any]:
    return {
        "safety_notice": SAFETY_NOTICE,
        "service_paths": SERVICE_PATHS,
        "capabilities": CAPABILITIES,
    }


@app.post("/v1/chat/completions")
def chat(request: ChatCompletionRequest, _: None = Depends(_require_api_key)) -> dict[str, Any]:
    real = _call_real_backend("chat", request.model_dump(exclude_none=True))
    if real is not None:
        return real

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
        "backend": "demo",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }


@app.post("/v1/embeddings/protein")
def protein_embedding(
    request: SequenceRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    real = _call_real_backend("protein_embedding", request.model_dump())
    if real is not None:
        return real

    return {
        "model": "facebook-esm-2-650m-protein-embedding-demo",
        "backend": "demo",
        "sequence_length": len(request.sequence),
        "embedding": _embedding(request.sequence),
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/structure/boltz2")
def structure_prediction(
    request: SequenceRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    real = _call_real_backend("structure_prediction", request.model_dump())
    if real is not None:
        return real

    digest = hashlib.sha1(request.sequence.encode("utf-8")).hexdigest()[:12]
    return {
        "model": "boltz2-compatible-demo",
        "backend": "demo",
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
    real = _call_real_backend("literature_retrieval", request.model_dump())
    if real is not None:
        return real

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
        "backend": "demo",
        "query": request.query,
        "documents": documents,
        "safety_notice": SAFETY_NOTICE,
    }


@app.post("/v1/md/openmm")
def molecular_dynamics(
    request: MolecularDynamicsRequest, _: None = Depends(_require_api_key)
) -> dict[str, Any]:
    real = _call_real_backend("molecular_dynamics", request.model_dump())
    if real is not None:
        return real

    ns_per_day = round(15.0 + min(request.steps, 10_000) / 1000.0, 3)
    return {
        "model": "openmm-md-8-5-1-compatible-demo",
        "backend": "demo",
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
    real = _call_real_backend("genomics_generation", request.model_dump())
    if real is not None:
        return real

    alphabet = "ACGT"
    seed = hashlib.sha256(request.prompt.encode("utf-8")).digest()
    generated = "".join(alphabet[byte % len(alphabet)] for byte in seed)
    while len(generated) < request.length:
        generated += generated
    return {
        "model": "carbon-3b-compatible-demo",
        "backend": "demo",
        "prompt": request.prompt,
        "generated_sequence": generated[: request.length],
        "safety_notice": SAFETY_NOTICE,
    }


def _model_checkers() -> dict[str, Callable[[], dict[str, Any]]]:
    sequence = SequenceRequest(sequence="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP")
    return {
        "chat": lambda: chat(
            ChatCompletionRequest(
                messages=[
                    {
                        "role": "user",
                        "content": "Health check every BioNeMo model service path.",
                    }
                ]
            )
        ),
        "protein_embedding": lambda: protein_embedding(sequence),
        "structure_prediction": lambda: structure_prediction(sequence),
        "literature_retrieval": lambda: literature_retrieval(
            RetrievalRequest(query="public benchmark biomedical retrieval", top_k=2)
        ),
        "molecular_dynamics": lambda: molecular_dynamics(
            MolecularDynamicsRequest(system_name="public-toy-water-box", steps=250)
        ),
        "genomics_generation": lambda: genomics_generation(
            GenomicsRequest(prompt="ATGCGT", length=48)
        ),
    }


def _model_health_payload() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checkers = _model_checkers()

    for capability in MODEL_SERVICE_SKILLS:
        skill = str(capability["service_skill"])
        started = time.perf_counter()
        try:
            result = checkers[skill]()
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            checks.append(
                {
                    "skill": skill,
                    "slug": capability["slug"],
                    "name": capability["name"],
                    "path": capability["service_path"],
                    "status": "healthy",
                    "backend": _backend_mode(skill),
                    "latency_ms": elapsed_ms,
                    "model": result.get("model"),
                }
            )
        except Exception as exc:  # noqa: BLE001 - health checks must isolate each model.
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            checks.append(
                {
                    "skill": skill,
                    "slug": capability["slug"],
                    "name": capability["name"],
                    "path": capability["service_path"],
                    "status": "unhealthy",
                    "backend": _backend_mode(skill),
                    "latency_ms": elapsed_ms,
                    "error": str(exc),
                }
            )

    healthy_count = sum(1 for check in checks if check["status"] == "healthy")
    status = "healthy" if healthy_count == len(checks) else "unhealthy"
    return {
        "status": status,
        "checked_models": len(checks),
        "healthy_models": healthy_count,
        "models": checks,
    }


def _service_health_payload() -> dict[str, Any]:
    gpu = _gpu_status()
    models = _model_health_payload()
    require_gpu = _env_flag("BIONEMO_REQUIRE_GPU")
    gpu_ok = not require_gpu or _gpu_is_available(gpu)
    status = "healthy" if gpu_ok and models["status"] == "healthy" else "unhealthy"
    return {
        "status": status,
        "service": "bionemo-compatible-model-service",
        "mode": _service_mode(),
        "gpu_required": require_gpu,
        "gpu": gpu,
        "model_health": {
            "status": models["status"],
            "checked_models": models["checked_models"],
            "healthy_models": models["healthy_models"],
        },
    }
