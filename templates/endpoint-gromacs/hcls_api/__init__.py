"""Shared API surface for the Nebius HCLS Serverless templates."""

from .core import EngineAdapter, create_app

__all__ = ["EngineAdapter", "create_app"]
