from pathlib import Path


ROOT = Path(__file__).parent


def test_no_credentials_are_baked_into_the_image_context() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "Dockerfile", ROOT / "entrypoint.sh", ROOT / "render-config.mjs")
    )
    assert "Bearer <" not in combined
    assert "NEBIUS_API_KEY=" not in combined
    assert "AUTH_TOKEN=" not in combined


def test_serverless_and_librechat_auth_are_separated() -> None:
    deploy = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")
    assert "--auth none" in deploy
    assert '--env-secret "KOPRA_API_KEY=' in deploy
    assert '--env-secret "NEBIUS_API_KEY=' in deploy
    assert '--env-secret "AUTH_TOKEN=' in deploy


def test_kopra_and_gromacs_are_preconfigured() -> None:
    renderer = (ROOT / "render-config.mjs").read_text(encoding="utf-8")
    assert "KOPRA_API_BASE_URL" in renderer
    assert "KOPRA_MCP_URL" in renderer
    assert "Kopra Scientific Model Gateway" in renderer
    assert "zai-org/GLM-5.3-Flash" in renderer
    assert "type: streamable-http" in renderer
    assert "url: '\\${KOPRA_MCP_URL}'" in renderer
    assert "url: '\\${GROMACS_MCP_URL}'" in renderer
    assert "Authorization: 'Bearer ${AUTH_TOKEN}'" in renderer
    assert "Authorization: 'Bearer ${KOPRA_API_KEY}'" in renderer
    assert "Authorization: 'Bearer {{GROMACS_MCP_TOKEN}}'" in renderer


def test_model_grouped_tutorials_are_seeded() -> None:
    seeder = (ROOT / "seed-workbench.js").read_text(encoding="utf-8")
    assert "agent_protein_structure" in seeder
    assert "agent_molecular_design" in seeder
    assert "agent_biomedical_imaging" in seeder
    assert "agent_genomics_aging" in seeder
    assert "agent_audio_transcription_tutorial" in seeder
    assert "list_models_mcp_kopra" in seeder
    assert "boltz2_predict_native_mcp_kopra" in seeder
    assert "segment_ct_native_mcp_kopra" in seeder
    assert "Do not give a diagnosis" in seeder


def test_client_branding_is_baked_into_the_wrapper() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    brand_client = (ROOT / "brand-client.mjs").read_text(encoding="utf-8")
    assert "kopra-scientific-logo.svg" in dockerfile
    assert "/app/client/dist/assets/logo.svg" in dockerfile
    assert 'APP_TITLE="Kopra Scientific AI"' in dockerfile
    assert "Kopra Scientific AI" in brand_client
