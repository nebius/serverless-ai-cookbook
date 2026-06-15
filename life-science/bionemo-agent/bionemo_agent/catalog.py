"""Shared catalog and routing for the BioNeMo cookbook agent."""

import json
from typing import Any

SAFETY_NOTICE = (
    "Research-only. Do not send PHI, patient records, confidential customer data, unpublished "
    "customer sequences, or proprietary molecule/protein inputs unless explicit approval exists. "
    "Do not use this agent for diagnosis, treatment recommendations, triage, patient-specific "
    "interpretation, or clinical decision support."
)

CAPABILITIES: list[dict[str, Any]] = [
    {
        "slug": "nvidia-nv-embedqa-e5-v5",
        "name": "NVIDIA NV-EmbedQA E5 v5",
        "task": "Biomedical retrieval and literature-search embeddings",
        "keywords": ["retrieval", "rag", "literature", "embedding", "pubmed", "semantic search"],
        "when_to_use": "Embed biomedical documents, abstracts, and research questions.",
        "sample_input": "Synthetic abstract: EGFR inhibitors in nonclinical kinase assays.",
        "serverless_fit": (
            "Endpoint for interactive RAG assistants; Job for batch embedding refreshes."
        ),
        "service_skill": "literature_retrieval",
        "service_path": "/v1/retrieval/literature",
    },
    {
        "slug": "stanfordcrfm-biomedlm-2-7b",
        "name": "BioMedLM 2.7B",
        "task": "Biomedical text generation and educational summarization",
        "keywords": ["summarization", "biomedical", "question answering", "education", "text"],
        "when_to_use": "Summarize public biomedical text or explain nonclinical research concepts.",
        "sample_input": "Public abstract text about kinase inhibition assays.",
        "serverless_fit": "Endpoint for chat-style assistance; Job for batch summaries.",
        "service_skill": "chat",
        "service_path": "/v1/chat/completions",
    },
    {
        "slug": "boltz2-nim",
        "name": "Boltz2 NIM",
        "task": "Protein structure and biomolecular complex prediction",
        "keywords": ["protein", "structure", "complex", "binding", "folding", "boltz"],
        "when_to_use": "Prepare structure-prediction requests from public or synthetic sequences.",
        "sample_input": "Public benchmark protein sequence or synthetic toy sequence.",
        "serverless_fit": (
            "Job for bounded prediction tasks; Endpoint only for interactive low-latency use."
        ),
        "service_skill": "structure_prediction",
        "service_path": "/v1/structure/boltz2",
    },
    {
        "slug": "facebook-esm-2-650m-protein-embedding",
        "name": "ESM-2 650M Protein Embedding",
        "task": "Protein sequence embeddings",
        "keywords": ["protein", "embedding", "sequence", "esm", "representation"],
        "when_to_use": "Embed public or synthetic protein sequences for similarity search.",
        "sample_input": "MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP.",
        "serverless_fit": (
            "Endpoint for interactive embedding demos; Job for larger sequence batches."
        ),
        "service_skill": "protein_embedding",
        "service_path": "/v1/embeddings/protein",
    },
    {
        "slug": "openmm-md-8-5-1-wrapper",
        "name": "OpenMM MD 8.5.1 Wrapper",
        "task": "Small molecular dynamics demo runs",
        "keywords": ["molecular dynamics", "simulation", "openmm", "trajectory", "energy"],
        "when_to_use": (
            "Run bounded, educational MD samples and return timing or artifact metadata."
        ),
        "sample_input": "Small public benchmark system with short run length.",
        "serverless_fit": "Job is preferred because MD runs are bounded batch workloads.",
        "service_skill": "molecular_dynamics",
        "service_path": "/v1/md/openmm",
    },
    {
        "slug": "huggingfacebio-carbon-3b-vllm-cuda13",
        "name": "Carbon 3B",
        "task": "Generative DNA/RNA sequence foundation model fallback",
        "keywords": ["genomics", "dna", "rna", "sequence", "carbon", "generative"],
        "when_to_use": (
            "Use as a conservative genomics demo path when larger models are unavailable."
        ),
        "sample_input": "Synthetic nonclinical DNA prompt.",
        "serverless_fit": "Endpoint for interactive sequence examples; Job for scripted batches.",
        "service_skill": "genomics_generation",
        "service_path": "/v1/genomics/carbon",
    },
]

SERVICE_PATHS = {
    "capabilities": "/v1/capabilities",
    "chat": "/v1/chat/completions",
    "protein_embedding": "/v1/embeddings/protein",
    "structure_prediction": "/v1/structure/boltz2",
    "literature_retrieval": "/v1/retrieval/literature",
    "molecular_dynamics": "/v1/md/openmm",
    "genomics_generation": "/v1/genomics/carbon",
}


def _tokenize(text: str) -> set[str]:
    return {
        token.strip(".,:;()[]{}").lower()
        for token in text.split()
        if token.strip(".,:;()[]{}")
    }


def _capability_score(capability: dict[str, Any], query_tokens: set[str]) -> int:
    haystack = _tokenize(
        " ".join(
            [
                str(capability["slug"]),
                str(capability["name"]),
                str(capability["task"]),
                str(capability["when_to_use"]),
                " ".join(capability["keywords"]),
            ]
        )
    )
    return len(query_tokens & haystack)


def get_matching_capabilities(query: str = "", limit: int | None = None) -> list[dict[str, Any]]:
    """Return BioNeMo capabilities ranked by keyword overlap."""
    query_tokens = _tokenize(query)

    if not query_tokens:
        matches = CAPABILITIES
    else:
        scored = [
            (capability, _capability_score(capability, query_tokens))
            for capability in CAPABILITIES
        ]
        matches = [
            capability
            for capability, score in sorted(scored, key=lambda item: item[1], reverse=True)
            if score
        ]
        if not matches:
            matches = CAPABILITIES

    if limit is not None:
        return matches[:limit]
    return matches


def list_capabilities(query: str = "") -> str:
    """List BioNeMo-oriented research capabilities."""
    return json.dumps(
        {
            "safety_notice": SAFETY_NOTICE,
            "capabilities": get_matching_capabilities(query=query),
        },
        indent=2,
    )


def route_request(request_text: str) -> str:
    """Recommend a BioNeMo capability and Nebius Serverless shape."""
    capabilities = get_matching_capabilities(query=request_text, limit=3)
    primary = capabilities[0]
    return json.dumps(
        {
            "safety_notice": SAFETY_NOTICE,
            "request": request_text,
            "recommended_capability": primary,
            "alternatives": capabilities[1:],
            "serverless_guidance": {
                "endpoint": (
                    "Use a Nebius Serverless Endpoint for an interactive assistant served by "
                    "NVIDIA NeMo Agent Toolkit."
                ),
                "job": (
                    "Use a Nebius Serverless Job for one-shot or bounded batch work such as "
                    "embedding refreshes, protein prediction, or molecular dynamics."
                ),
            },
        },
        indent=2,
    )
