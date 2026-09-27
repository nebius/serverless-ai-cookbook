import copy

import pytest

from fs2_speech.events import assemble_transcript


@pytest.mark.parametrize("parts,expected", [
    ([{"text": " Hello, hi"}, {"text": "shall we stop?", "separator_before": " "}], "Hello, hi shall we stop?"),
    ([{"text": "I am sor"}, {"text": "ry to hear"}], "I am sorry to hear"),
    ([{"text": "I am sor"}, {"text": "ry to hear", "separator_before": ""}], "I am sorry to hear"),
    ([{"text": "你好"}, {"text": "世界"}], "你好世界"),
    ([{"text": "こんにちは"}, {"text": "世界"}], "こんにちは世界"),
    ([{"text": "Hello"}, {"text": ", world."}], "Hello, world."),
    ([{"text": "Hello."}, {"text": "Next.", "separator_before": " "}], "Hello. Next."),
    ([{"text": "Hello "}, {"text": "world", "separator_before": " "}], "Hello world"),
    ([{"text": "Hello"}, {"text": " world", "separator_before": " "}], "Hello world"),
    ([{"text": "", "separator_before": " "}, {"text": "Hello", "separator_before": " "}], "Hello"),
])
def test_explicit_separator_only_preserves_raw_evidence(parts, expected):
    before = copy.deepcopy(parts)
    assert assemble_transcript(parts) == expected
    assert parts == before


@pytest.mark.parametrize("hint", [None, False, True, 0, [], {}, "\n", "  "])
def test_invalid_join_hint_rejected(hint):
    with pytest.raises(ValueError, match="join_contract"):
        assemble_transcript([{"text": "word", "separator_before": hint}])
