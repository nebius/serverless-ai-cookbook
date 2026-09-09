"""A deliberately small, single-GPU BioIR Boltz-2 HTTP adapter.

BioIR is a Python library, not an HTTP service. This adapter makes the library
workflow explicit: it creates the documented ``build_processor`` pipeline once,
warms it, and serializes one request per allocated GPU.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator

LOGGER = logging.getLogger("bioir.tutorial")
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())

MODEL_NAME = "boltz-2"
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/var/lib/bioir/output")).resolve()
SAMPLING_STEPS = int(os.environ.get("BIOIR_SAMPLING_STEPS", "50"))
MAX_SEQUENCE_LENGTH = int(os.environ.get("MAX_SEQUENCE_LENGTH", "1024"))
AMINO_ACIDS = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYXBZUO]+$")

# This is NVIDIA's public quickstart sequence. A query-only inline MSA keeps
# the warmup self-contained. Production use should supply a real MSA.
WARMUP_SEQUENCE = (
    "ACKIENIKYKGKEVESKLGSQLIDIFNDLDRAKEEYDKLSSPEFIAKFGDWINDEVERNVN"
    "EDGEPLLIQDVRQDSSKHYFFILKNGERFDLLTR"
)


class FoldRequest(BaseModel):
    """One protein chain and an optional inline A3M alignment."""

    sequence: str = Field(description="Protein sequence in one-letter notation.")
    msa_a3m: str | None = Field(
        default=None,
        description="Optional A3M alignment. A query-only alignment is used when omitted.",
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, value: str) -> str:
        sequence = "".join(value.upper().split())
        if not sequence or len(sequence) > MAX_SEQUENCE_LENGTH or not AMINO_ACIDS.fullmatch(sequence):
            raise ValueError(
                f"sequence must contain 1..{MAX_SEQUENCE_LENGTH} supported amino-acid letters"
            )
        return sequence

    @field_validator("msa_a3m")
    @classmethod
    def validate_msa(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 1_048_576:
            raise ValueError("msa_a3m must be at most 1 MiB")
        return value


class FoldResponse(BaseModel):
    request_id: str
    model: str
    cif: str
    scores: dict[str, Any]
    model_inference_time_seconds: float
    total_time_seconds: float


class BioIRRuntime:
    """Owns the one resident model pipeline and its bounded work queue."""

    def __init__(self) -> None:
        self.processor: Any | None = None
        self.ready = False
        self.load_error: str | None = None
        self.busy = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bioir")
        self.metrics = {"accepted": 0, "completed": 0, "failed": 0, "rejected": 0, "load_seconds": 0.0}

    def load(self) -> None:
        """Create and warm the pipeline before advertising readiness."""
        started = time.monotonic()
        try:
            from bionemo_ir.data.schemas import InputRequest, MSARecord, Polymer
            from bionemo_ir.pipeline.processor.engine_proc import EngineProcessorConfig, build_processor
            from bionemo_ir.pipeline.stages.configs import FeatureGeneratorStageConfig, WriterStageConfig

            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            self.processor = build_processor(
                EngineProcessorConfig(
                    model_source=MODEL_NAME,
                    runtime_args={"num_sampling_steps": SAMPLING_STEPS},
                    feature_generator_stage=FeatureGeneratorStageConfig(
                        init_context={"random_seed": 42}
                    ),
                    writer_stage=WriterStageConfig(output_path=str(OUTPUT_DIR), format="cif"),
                    engine_kwargs={"profile_inference": True},
                )
            )
            request = InputRequest(
                input_id="warmup",
                polymers=[
                    Polymer(
                        chain_id=["A1"],
                        sequence=WARMUP_SEQUENCE,
                        msas=[MSARecord(content=f">warmup\\n{WARMUP_SEQUENCE}\\n")],
                    )
                ],
            )
            self._run(request, "warmup")
            self.ready = True
            LOGGER.info("BioIR %s is ready after %.2fs", MODEL_NAME, time.monotonic() - started)
        except Exception as exc:  # Keep health alive while readiness reports the failure.
            self.processor = None
            self.ready = False
            self.load_error = type(exc).__name__
            LOGGER.exception("BioIR initialization failed")
        finally:
            self.metrics["load_seconds"] = time.monotonic() - started

    @staticmethod
    def _make_request(request_id: str, sequence: str, msa_a3m: str) -> Any:
        from bionemo_ir.data.schemas import InputRequest, MSARecord, Polymer

        return InputRequest(
            input_id=request_id,
            polymers=[Polymer(chain_id=["A1"], sequence=sequence, msas=[MSARecord(content=msa_a3m)])],
        )

    def _run(self, request: Any, request_id: str) -> tuple[str, dict[str, Any], float]:
        if self.processor is None:
            raise RuntimeError("BioIR pipeline is not initialized")

        rows = self.processor([{"record": request, "__record_id": request_id}])
        row = rows[0]
        inference_error = row.get("__inference_error__") or {}
        if isinstance(inference_error, dict) and inference_error.get("error_msg"):
            raise RuntimeError("BioIR reported an inference error")

        output_path = Path(row["output_path"]).resolve()
        if OUTPUT_DIR not in output_path.parents or not output_path.is_file():
            raise RuntimeError("BioIR did not produce an output inside the configured output directory")
        cif = output_path.read_text(encoding="utf-8")
        if not cif.lstrip().startswith("data_"):
            raise RuntimeError("BioIR output is not a valid-looking mmCIF document")

        try:
            scores = json.loads(row["scores"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("BioIR output did not contain a JSON score payload") from exc
        finally:
            # The writer places one structure per request under OUTPUT_DIR.
            # Never delete the shared output directory while another request is
            # being prepared; the adapter itself admits only one at a time.
            output_path.unlink(missing_ok=True)

        return cif, scores, float(row.get("model_inference_time", 0.0))

    def predict(self, request: FoldRequest, request_id: str) -> FoldResponse:
        started = time.monotonic()
        msa = request.msa_a3m or f">query\\n{request.sequence}\\n"
        cif, scores, model_time = self._run(self._make_request(request_id, request.sequence, msa), request_id)
        return FoldResponse(
            request_id=request_id,
            model=MODEL_NAME,
            cif=cif,
            scores=scores,
            model_inference_time_seconds=model_time,
            total_time_seconds=time.monotonic() - started,
        )

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)


runtime = BioIRRuntime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop = asyncio.get_running_loop()
    task = loop.run_in_executor(None, runtime.load)
    try:
        yield
    finally:
        await asyncio.shield(task)
        runtime.close()


app = FastAPI(title="BioIR Boltz-2 tutorial service", version="1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> Response:
    if runtime.ready:
        return JSONResponse({"status": "ready", "model": MODEL_NAME})
    status = "failed" if runtime.load_error else "loading"
    return JSONResponse({"status": status}, status_code=503)


@app.post("/v1/fold", response_model=FoldResponse)
async def fold(payload: FoldRequest, response: Response) -> FoldResponse:
    if not runtime.ready:
        raise HTTPException(status_code=503, detail="model is not ready")
    if runtime.busy:
        runtime.metrics["rejected"] += 1
        raise HTTPException(status_code=429, detail="one GPU request is already in progress")

    runtime.busy = True
    request_id = uuid.uuid4().hex
    runtime.metrics["accepted"] += 1
    try:
        result = await asyncio.get_running_loop().run_in_executor(runtime.executor, runtime.predict, payload, request_id)
        runtime.metrics["completed"] += 1
        response.headers["X-Backend-Id"] = os.environ.get("HOSTNAME", "bioir-worker")
        return result
    except Exception as exc:
        runtime.metrics["failed"] += 1
        LOGGER.exception("prediction failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="prediction failed") from exc
    finally:
        runtime.busy = False


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    return "\n".join(
        [
            "# TYPE bioir_model_ready gauge",
            f"bioir_model_ready {int(runtime.ready)}",
            "# TYPE bioir_requests_total counter",
            *(f'bioir_requests_total{{status="{status}"}} {count}' for status, count in runtime.metrics.items() if status != "load_seconds"),
            "# TYPE bioir_model_load_seconds gauge",
            f'bioir_model_load_seconds {runtime.metrics["load_seconds"]:.6f}',
            "",
        ]
    )
