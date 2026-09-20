"""Compatibility entry point for the portable authoritative skills tests."""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
globals().update({name: value for name, value in runpy.run_path(
    str(ROOT / 'skills/scientific-ai/tests/test_bundle.py')).items()
    if name.startswith('test_')})
