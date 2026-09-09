"""Stub heavy model-server dependencies so schema imports work locally."""

import os
import sys
import types

for key in (
    "BOLTZ_SOURCE_REVISION",
    "BOLTZ_MODEL_REPOSITORY",
    "BOLTZ_MODEL_REVISION",
    "BOLTZ_CONF_SHA256",
    "BOLTZ_AFF_SHA256",
    "BOLTZ_MOLS_SHA256",
):
    os.environ.setdefault(key, "test")

if "torch" not in sys.modules:
    torch = types.ModuleType("torch")
    cuda = types.ModuleType("torch.cuda")
    cuda.is_available = lambda: False
    cuda.get_device_capability = lambda *a, **k: (9, 0)
    torch.cuda = cuda
    sys.modules["torch"] = torch

class _FakeApp:
    def get(self, *args, **kwargs):
        return lambda fn: fn

    def post(self, *args, **kwargs):
        return lambda fn: fn

    def on_event(self, *args, **kwargs):
        return lambda fn: fn

    def add_middleware(self, *args, **kwargs):
        return None

    def include_router(self, *args, **kwargs):
        return None


for name in ("yaml", "fastapi", "fastapi.responses", "huggingface_hub"):
    if name not in sys.modules:
        module = types.ModuleType(name)
        if name == "fastapi":
            module.FastAPI = lambda *a, **k: _FakeApp()
            module.HTTPException = Exception
            module.responses = types.SimpleNamespace(PlainTextResponse=object)
        if name == "fastapi.responses":
            module.PlainTextResponse = object
        if name == "huggingface_hub":
            module.hf_hub_download = lambda *a, **k: ""
        sys.modules[name] = module
