"""Mode-selection guidance must not equate prefix continuation with restyling."""
from pathlib import Path

ROOT = Path(__file__).parent


def test_recorded_motion_guidance_is_seeded_and_uses_live_contracts():
    seed = (ROOT / 'seed-workbench.js').read_text()
    assert 'whole-sequence transfer controls' in seed
    assert 'not video-to-video prefix/suffix continuation' in seed
    assert 'Numeric action equality does not establish' in seed
    skill = (ROOT.parents[1] / 'skills/scientific-ai/generative-media/SKILL.md').read_text()
    assert 'augmentation.mode: transfer' in skill
    assert 'augmentation.conditioning.controls' in skill
    assert 'do not copy the LeRobot parameter shape into the native request' in skill
    assert 'does **not** establish' in skill
    assert 'not yet live-tested' not in skill
