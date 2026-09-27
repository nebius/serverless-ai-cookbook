import pytest

from fs2_speech.events import TranscriptEvents


def test_partials_replace_and_finals_seal_segments():
    events = TranscriptEvents("test-session")
    a = events.update(partial="The cat")
    b = events.update(partial="The cap")
    assert a[0].segment_id == b[0].segment_id == 0
    assert b[0].revision == 2 and b[0].sequence == 2
    assert not events.update(partial="The cap")
    final, next_partial = events.update(final="The cap.", partial="Next")
    assert final.segment_id == 0 and final.revision == 3
    assert next_partial.segment_id == 1 and next_partial.revision == 1
    tail = events.update(final="Next sentence.", last=True)
    assert tail[0].type == "transcript.final"
    with pytest.raises(ValueError, match="after_completion"):
        events.update(partial="more")


def test_retraction_is_an_empty_replacement():
    events = TranscriptEvents("test")
    events.update(partial="Wrong")
    assert events.update(partial="")[0].text == ""


def test_unflushed_tail_cannot_become_fake_success():
    events = TranscriptEvents("test")
    with pytest.raises(ValueError, match="did_not_finalize"):
        events.update(partial="unfinished", last=True)


def test_empty_audio_transcript_is_not_hallucinated():
    assert TranscriptEvents("silence").update(last=True) == []
