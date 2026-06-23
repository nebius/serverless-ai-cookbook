from fastapi.testclient import TestClient

from bionemo_agent.catalog import MODEL_SERVICE_SKILLS
from bionemo_agent.self_hosted_service import app
from bionemo_agent.service_smoke import _run as run_service_smoke


def test_health_reports_gpu_status_shape():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "gpu" in payload
    assert payload["model_health"]["checked_models"] == len(MODEL_SERVICE_SKILLS)


def test_model_health_checks_required_default_models():
    client = TestClient(app)

    response = client.get("/health/models")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checked_models"] == len(MODEL_SERVICE_SKILLS)
    assert {item["skill"] for item in payload["models"]} == {
        capability["service_skill"] for capability in MODEL_SERVICE_SKILLS
    }
    assert {item["backend"] for item in payload["models"]} == {"demo"}


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


def test_real_mode_requires_configured_model_backends(monkeypatch):
    monkeypatch.setenv("BIONEMO_MODEL_SERVICE_MODE", "real")
    monkeypatch.setenv("BIONEMO_HEALTH_STRICT", "true")
    monkeypatch.delenv("BIONEMO_MODEL_PROTEIN_EMBEDDING_URL", raising=False)
    client = TestClient(app)

    model_health = client.get("/health/models")
    service_health = client.get("/health")
    handler = client.post("/v1/embeddings/protein", json={"sequence": "MKTAYIAK"})

    assert model_health.status_code == 200
    assert model_health.json()["status"] == "unhealthy"
    assert service_health.status_code == 503
    assert handler.status_code == 503


def test_service_smoke_exercises_all_skills(monkeypatch):
    monkeypatch.delenv("BIONEMO_SERVICE_API_KEY", raising=False)

    result = run_service_smoke(
        sequence="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP",
        query="public benchmark biomedical retrieval",
    )

    assert result["ok"] is True
    assert result["skills"] == [
        "chat",
        "literature_retrieval",
        "molecular_dynamics",
        "protein_embedding",
        "structure_prediction",
    ]
    assert "genomics_generation" in result["catalog_skills"]
    assert result["protein_embedding_model"].endswith("-demo")
