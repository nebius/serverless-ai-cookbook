from fastapi.testclient import TestClient

from bionemo_agent.self_hosted_service import app
from bionemo_agent.service_smoke import _run as run_service_smoke


def test_health_reports_gpu_status_shape():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "gpu" in payload


def test_capabilities_include_all_named_service_skills():
    client = TestClient(app)

    response = client.get("/v1/capabilities")

    assert response.status_code == 200
    skills = {capability["service_skill"] for capability in response.json()["capabilities"]}
    assert {
        "chat",
        "genomics_generation",
        "literature_retrieval",
        "molecular_dynamics",
        "protein_embedding",
        "structure_prediction",
    } <= skills


def test_protein_embedding_is_deterministic():
    client = TestClient(app)
    payload = {"sequence": "MKTAYIAK"}

    first = client.post("/v1/embeddings/protein", json=payload)
    second = client.post("/v1/embeddings/protein", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["embedding"] == second.json()["embedding"]
    assert first.json()["sequence_length"] == len(payload["sequence"])


def test_service_auth_is_optional_but_enforced_when_configured(monkeypatch):
    monkeypatch.setenv("BIONEMO_SERVICE_API_KEY", "secret")
    client = TestClient(app)

    rejected = client.post("/v1/embeddings/protein", json={"sequence": "MKTAYIAK"})
    accepted = client.post(
        "/v1/embeddings/protein",
        json={"sequence": "MKTAYIAK"},
        headers={"Authorization": "Bearer secret"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200


def test_service_smoke_exercises_all_skills(monkeypatch):
    monkeypatch.delenv("BIONEMO_SERVICE_API_KEY", raising=False)

    result = run_service_smoke(
        sequence="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP",
        query="public benchmark biomedical retrieval",
    )

    assert result["ok"] is True
    assert result["skills"] == [
        "chat",
        "genomics_generation",
        "literature_retrieval",
        "molecular_dynamics",
        "protein_embedding",
        "structure_prediction",
    ]
    assert result["protein_embedding_model"].endswith("-demo")
