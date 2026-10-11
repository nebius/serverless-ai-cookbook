import os
import subprocess

import pytest


IMAGE = os.environ.get("BIOIR_TEST_IMAGE")


@pytest.mark.skipif(
    not IMAGE, reason="Set BIOIR_TEST_IMAGE to validate a built image with Docker"
)
def test_baked_runtime_and_non_root_cache():
    code = """
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import nbformat
from bionemo_ir.pipeline.processor.engine_proc import EngineProcessorConfig, build_processor

assert os.getuid() == 10001
assert importlib.metadata.version("bionemo-ir") == "0.1.0"
subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
cache = Path.home() / ".cache" / "hf"
cache.mkdir(parents=True, exist_ok=True)
probe = cache / "cookbook-write-probe"
probe.write_text("ok")
probe.unlink()
notebook = nbformat.read("/workspace/notebooks/bir_boltz2_tutorial.ipynb", as_version=4)
assert all("id" in cell for cell in notebook.cells)
nbformat.validate(notebook)
"""
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "/opt/bioir/venv/bin/python",
            IMAGE,
            "-c",
            code,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
