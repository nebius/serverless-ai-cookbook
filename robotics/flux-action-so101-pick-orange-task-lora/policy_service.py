"""Synchronous FLUX policy service for the separate Isaac Sim evaluation process."""

import base64
import json
import os
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import snapshot_download
from peft import PeftConfig, PeftModel
from lerobot.policies.factory import make_pre_post_processors
from lerobot.policies.flux3 import Flux3Policy
from lerobot.policies.flux3.configuration_flux3 import Flux3Config

from calibration import ID as CALIBRATION_ID, to_motor, to_policy
from publish import verify_adapter

RECIPE = json.loads((Path(__file__).parent / "recipe.json").read_text())


def load_policy():
    base = Path("/workspace/work/models/so101")
    encoders = Path("/workspace/work/models/base")
    snapshot_download(RECIPE["policy"]["repo_id"], revision=RECIPE["policy"]["revision"],
                      local_dir=base, ignore_patterns=["variants/*"])
    snapshot_download(RECIPE["encoders"]["repo_id"], revision=RECIPE["encoders"]["revision"],
                      local_dir=encoders, allow_patterns=["video_vae.safetensors", "text_encoder/*"])
    variant = os.environ.get("MODEL_VARIANT")
    if variant == "base":
        path = base
    elif variant == "adapter":
        path = Path(os.environ["CHECKPOINT_DIR"])
        marker = path.parent / "COMPLETE.json"
        published = json.loads(marker.read_text())
        if published.get("calibration_id") != CALIBRATION_ID:
            raise ValueError("adapter was trained with a different or unrecorded SO-101 calibration")
        actual = verify_adapter(path, published)
    else:
        raise ValueError("MODEL_VARIANT must be base or adapter")
    config = Flux3Config.from_pretrained(path)
    config.pretrained_path = str(path)
    config.device = "cuda"
    config.video_vae_id = str(encoders / "video_vae.safetensors")
    config.text_encoder_id = str(encoders / "text_encoder")
    if variant == "adapter":
        config.use_peft = True
    if (config.action_dim, config.fps, config.camera_order) != (
        6, 30, ["observation.images.scene", "observation.images.wrist"]
    ):
        raise ValueError("checkpoint does not match SO-101 observation/action contract")
    if variant == "adapter":
        peft_config = PeftConfig.from_pretrained(str(path))
        if Path(peft_config.base_model_name_or_path) != base:
            raise ValueError("adapter does not reference the pinned SO-101 base path")
        policy = Flux3Policy.from_pretrained(base, config=config)
        policy = PeftModel.from_pretrained(
            policy, str(path), config=peft_config, is_trainable=False
        )
    else:
        policy = Flux3Policy.from_pretrained(base, config=config)
    policy = policy.to("cuda").eval()
    pre, post = make_pre_post_processors(config, pretrained_path=path)
    return policy, pre, post, actual if variant == "adapter" else None


def decode_image(payload: dict) -> torch.Tensor:
    shape = payload["shape"]
    if len(shape) != 3 or shape[2] != 3 or shape[0] > 1080 or shape[1] > 1920:
        raise ValueError(f"invalid image shape: {shape}")
    raw = zlib.decompress(base64.b64decode(payload["data"]))
    if len(raw) != int(np.prod(shape)):
        raise ValueError("image byte count mismatch")
    image = np.frombuffer(raw, dtype=np.uint8).reshape(shape).copy()
    return torch.from_numpy(image).permute(2, 0, 1).float().unsqueeze(0) / 255.0


def make_handler(policy, pre, post, model: str, checkpoint: str, adapter_sha256: str | None):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/health":
                return self.respond(404, {"error": "unknown path"})
            self.respond(200, {"ready": True, "model": model, "checkpoint": checkpoint,
                               "adapter_sha256": adapter_sha256, "calibration_id": CALIBRATION_ID})

        def do_POST(self):
            if self.path not in {"/reset", "/act"}:
                return self.respond(404, {"error": "unknown path"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 8_000_000:
                    raise ValueError("invalid request length")
                request = json.loads(self.rfile.read(size))
                if self.path == "/reset":
                    policy.reset()
                    pre.reset()
                    post.reset()
                    return self.respond(200, {"reset": True})
                state = torch.tensor(to_policy(request["state"]), dtype=torch.float32).reshape(1, 6)
                if not torch.isfinite(state).all():
                    raise ValueError("non-finite state")
                observation = {
                    "observation.images.scene": decode_image(request["front"]),
                    "observation.images.wrist": decode_image(request["wrist"]),
                    "observation.state": state,
                    "task": [RECIPE["instruction"]],
                }
                with torch.inference_mode():
                    command = post(policy.select_action(pre(observation)))
                command = command.detach().cpu().reshape(-1)
                if command.numel() != 6 or not torch.isfinite(command).all():
                    raise ValueError("policy produced invalid SO-101 command")
                self.respond(200, {"action": to_motor(command.tolist())})
            except Exception as error:
                self.respond(500, {"error": str(error)})
                print(f"policy request failed: {error}", flush=True)

    return Handler


def main() -> None:
    policy, pre, post, adapter_sha256 = load_policy()
    host = os.environ.get("SERVICE_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVICE_PORT", "8765"))
    model = os.environ["MODEL_VARIANT"]
    checkpoint = os.environ.get("CHECKPOINT_DIR", RECIPE["policy"]["repo_id"])
    HTTPServer((host, port), make_handler(policy, pre, post, model, checkpoint, adapter_sha256)).serve_forever()


if __name__ == "__main__":
    main()
