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
    assert '--env-secret "NEBIUS_API_KEY=' in deploy
    assert '--env-secret "AUTH_TOKEN=' in deploy


def test_token_factory_and_gromacs_are_preconfigured() -> None:
    renderer = (ROOT / "render-config.mjs").read_text(encoding="utf-8")
    assert "https://api.tokenfactory.nebius.com/v1" in renderer
    assert "type: streamable-http" in renderer
    assert "url: '\\${GROMACS_MCP_URL}'" in renderer
    assert "Authorization: 'Bearer \\${AUTH_TOKEN}'" in renderer
    assert "Authorization: 'Bearer {{GROMACS_MCP_TOKEN}}'" in renderer


def test_scientific_placeholders_are_seeded_and_catalog_aware() -> None:
    seeder = (ROOT / "seed-workbench.js").read_text(encoding="utf-8")
    assert "agent_audio_transcription_tutorial" in seeder
    assert "agent_medical_image_analysis_tutorial" in seeder
    assert "matchingSkillPaths" in seeder
    assert "https://api.tokenfactory.nebius.com/v1/models" in seeder
    assert "do not provide a diagnosis" in seeder


def test_client_branding_is_baked_into_the_wrapper() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    brand_client = (ROOT / "brand-client.mjs").read_text(encoding="utf-8")
    assert "nebius-logo.svg" in dockerfile
    assert "/app/client/dist/assets/logo.svg" in dockerfile
    assert 'APP_TITLE="Nebius Scientific AI Agent"' in dockerfile
    assert "Nebius Scientific AI Agent" in brand_client
