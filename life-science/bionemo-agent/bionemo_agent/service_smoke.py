"""Container smoke checks for the self-hosted BioNeMo-compatible service."""

from __future__ import annotations

import argparse
import json

from bionemo_agent.catalog import MODEL_SERVICE_SKILLS, SERVICE_PATHS
from bionemo_agent.self_hosted_service import (
    ChatCompletionRequest,
    MolecularDynamicsRequest,
    RetrievalRequest,
    SequenceRequest,
    capabilities,
    chat,
    health,
    health_models,
    literature_retrieval,
    molecular_dynamics,
    protein_embedding,
    structure_prediction,
)


def _run(sequence: str, query: str) -> dict[str, object]:
    health_result = health()
    model_health_result = health_models()
    catalog_result = capabilities()
    chat_result = chat(
        ChatCompletionRequest(
            messages=[
                {
                    "role": "user",
                    "content": "Route a public protein sequence embedding request.",
                }
            ]
        )
    )
    embedding_result = protein_embedding(SequenceRequest(sequence=sequence))
    structure_result = structure_prediction(SequenceRequest(sequence=sequence))
    retrieval_result = literature_retrieval(RetrievalRequest(query=query, top_k=2))
    md_result = molecular_dynamics(
        MolecularDynamicsRequest(system_name="public-toy-water-box", steps=250)
    )
    expected_capability_skills = {
        "chat",
        "protein_embedding",
        "structure_prediction",
        "literature_retrieval",
        "molecular_dynamics",
        "genomics_generation",
    }
    expected_required_skills = {item["service_skill"] for item in MODEL_SERVICE_SKILLS}
    expected_service_paths = expected_capability_skills | {"capabilities"}
    observed_skills = {item["service_skill"] for item in catalog_result["capabilities"]}

    if observed_skills != expected_capability_skills:
        raise RuntimeError(f"unexpected service skills: {sorted(observed_skills)}")
    if set(SERVICE_PATHS) != expected_service_paths:
        raise RuntimeError(f"unexpected service paths: {sorted(SERVICE_PATHS)}")
    if model_health_result["status"] != "healthy":
        raise RuntimeError(f"model health failed: {model_health_result}")
    if model_health_result["checked_models"] != len(expected_required_skills):
        raise RuntimeError(
            "model health did not check every required service skill: "
            f"{model_health_result['checked_models']} checks"
        )
    if len(embedding_result["embedding"]) != 16:
        raise RuntimeError("protein embedding smoke check returned the wrong vector size")
    if not structure_result["artifact"]["pdb_id"].startswith("demo-"):
        raise RuntimeError("structure prediction smoke check did not return a demo artifact")
    if len(retrieval_result["documents"]) != 2:
        raise RuntimeError("literature retrieval smoke check returned the wrong document count")
    if not md_result["artifacts"]:
        raise RuntimeError("molecular dynamics smoke check returned no artifacts")

    return {
        "ok": True,
        "service": health_result["service"],
        "gpu": health_result["gpu"],
        "model_health": model_health_result,
        "skills": sorted(expected_required_skills),
        "catalog_skills": sorted(observed_skills),
        "chat_model": chat_result["model"],
        "protein_embedding_model": embedding_result["model"],
        "structure_model": structure_result["model"],
        "retrieval_model": retrieval_result["model"],
        "md_model": md_result["model"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a self-hosted BioNeMo-compatible service container smoke check."
    )
    parser.add_argument(
        "--sequence",
        default="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP",
        help="Public or synthetic protein sequence for deterministic demo checks.",
    )
    parser.add_argument(
        "--query",
        default="public benchmark biomedical retrieval",
        help="Research-only retrieval query for deterministic demo checks.",
    )
    args = parser.parse_args()
    print(json.dumps(_run(sequence=args.sequence, query=args.query), indent=2))


if __name__ == "__main__":
    main()
