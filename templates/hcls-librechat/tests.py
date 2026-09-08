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
