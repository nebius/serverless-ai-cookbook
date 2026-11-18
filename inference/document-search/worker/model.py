"""Pinned local Qwen encoder following the upstream last-token pooling example."""
from __future__ import annotations

import importlib.metadata
import time


class LocalEncoder:
    def __init__(self, settings: dict, *, device: str = "cuda"):
        # Lazy imports keep offline integrity checks independent of GPU packages.
        import torch
        from transformers import AutoModel, AutoTokenizer

        start = time.perf_counter()
        self.torch, self.settings, self.device = torch, settings, device
        encoder = settings["encoder_settings"]
        for package in ("torch", "transformers"):
            actual = importlib.metadata.version(package).split("+")[0]
            if actual != encoder[package]:
                raise ValueError(f"Install worker/requirements.txt: expected {package} {encoder[package]}, got {actual}")
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable. Use a GPU Job, or explicitly select --device cpu for a CPU run.")
        dtype = {"float16": torch.float16, "float32": torch.float32}[encoder["dtype"]]
        if device == "cpu" and dtype != torch.float32:
            raise ValueError("CPU runs require a separate config with encoder_settings.dtype=float32; do not mix indexes.")
        self.tokenizer = AutoTokenizer.from_pretrained(
            settings["model"], revision=settings["model_revision"], padding_side="left")
        self.model = AutoModel.from_pretrained(
            settings["model"], revision=settings["model_revision"], torch_dtype=dtype,
            attn_implementation="sdpa", trust_remote_code=False).to(device).eval()
        if device == "cuda":
            torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - start
        self.hardware = {"device": device, "gpu": torch.cuda.get_device_name(0) if device == "cuda" else None,
                         "torch": torch.__version__, "transformers": importlib.metadata.version("transformers"),
                         "cuda_runtime": torch.version.cuda,
                         "model_load_seconds": self.load_seconds,
                         "gpu_memory_bytes": torch.cuda.get_device_properties(0).total_memory if device == "cuda" else None}

    def __call__(self, texts: list[str]) -> list[list[float]]:
        torch = self.torch
        encoded = self.tokenizer(texts, padding=True, truncation=False, return_tensors="pt")
        if encoded["input_ids"].shape[1] > self.settings["encoder_settings"]["max_length"]:
            raise ValueError("A chunk exceeds the token limit; use a new run prefix with smaller chunks. No silent truncation.")
        encoded = {key: value.to(self.device) for key, value in encoded.items()}
        with torch.inference_mode():
            output = self.model(**encoded)
            # Left padding means the last column is the last real token for every row.
            vectors = torch.nn.functional.normalize(output.last_hidden_state[:, -1], p=2, dim=1)
        if self.device == "cuda":
            torch.cuda.synchronize()
        return vectors.float().cpu().tolist()
