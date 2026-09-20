"""Release regressions for reusable, non-event onboarding."""
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).parent


@pytest.mark.parametrize("legacy_flag", ["true", "false", ""])
def test_retired_event_flag_cannot_restore_event_providers(tmp_path, legacy_flag):
    output = tmp_path / "config.json"
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("SCIENTIFIC_", "NEBIUS_"))}
    env.update(SCIENTIFIC_DISCOVER_CHAT_MODELS="false",
               SCIENTIFIC_DEDICATED_CHAT_ENABLED=legacy_flag,
               SCIENTIFIC_AGENT_INSTRUCTIONS_PATH=str(
                   ROOT.parents[1] / "life-science/bionemo-librechat/scientific-agent-instructions.md"))
    subprocess.run(["node", str(ROOT / "render-config.mjs"), str(output)],
                   env=env, capture_output=True, check=True)
    raw = output.read_text()
    config = json.loads(raw)
    assert [row["name"] for row in config["endpoints"]["custom"]] == ["Nebius Token Factory"]
    assert "Dedicated" not in config["endpoints"]["agents"]["allowedProviders"]
    assert "LongevityHack2026" not in raw
    assert "Stockholm" not in raw
    assert "us-central1" not in raw
    evaluation = next(row for row in config["modelSpecs"]["list"] if row["name"] == "mindeval-workshop")
    assert evaluation["label"] == "Conversation Evaluation"
    assert evaluation["preset"]["agent_id"] == "agent_mindeval_workshop"


def test_onboarding_is_baked_into_both_entry_paths():
    landing = (ROOT / "ScientificLanding.tsx").read_text()
    guide = (ROOT / "ScientificGettingStarted.tsx").read_text()
    panels = (ROOT / "demos/Demos.tsx").read_text()
    image = (ROOT / "Dockerfile").read_text()
    assert "workspaceTourPrompt" in landing
    assert "ScientificGettingStarted.tsx /app/client/src/components/ScientificGettingStarted.tsx" in image
    assert "tab === 'getting-started'" in panels
    assert "<GettingStarted />" in panels
    for model in ["OpenFold2", "GenMol", "PhenoAge", "SAM 2"]:
        assert model in guide
    for phrase in ["Do not run inference yet", "/workspace/examples/v1", "reference transcript",
                   "original run ID", "does not automatically upload", "Clipboard unavailable"]:
        assert phrase in guide
    assert "fetch(" not in guide and "axios" not in guide


def test_runtime_copy_has_no_event_destination_or_campaign_banner():
    for name in ["render-config.mjs", "ScientificLanding.tsx", "ScientificGettingStarted.tsx",
                 "demos/Demos.tsx", "demos/seed.cjs", "scripts/deploy.sh"]:
        text = (ROOT / name).read_text().lower()
        assert not any(word in text for word in ["stockholm", "longevityhack2026", "sword ai summit", "porto"])
    # Persisted IDs / tools are retained for compatibility, not deleted histories.
    assert "agent_mindeval_workshop" in (ROOT / "demos/seed.cjs").read_text()
    assert "SCIENTIFIC_DEDICATED_CHAT_ENABLED" not in (ROOT / "scripts/deploy.sh").read_text()
