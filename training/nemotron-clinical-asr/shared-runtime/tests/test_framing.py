import random

import pytest

from fs2_speech.framing import PCMFramer


@pytest.mark.parametrize("samples", [1, 7, 8, 9, 16, 17, 128, 301])
def test_no_lost_or_duplicated_boundary_samples(samples):
    original = b"".join(value.to_bytes(2, "little") for value in range(samples))
    framer = PCMFramer(8)
    frames = []
    rng = random.Random(samples)
    offset = 0
    while offset < len(original):
        count = rng.randrange(1, 13) * 2
        frames.extend(framer.push(original[offset:offset + count]))
        offset += count
        assert framer.buffered_bytes <= 16
    frames.append(framer.finish())
    assert b"".join(frame.pcm[:frame.valid_samples * 2] for frame in frames) == original
    assert sum(frame.first for frame in frames) == 1
    assert sum(frame.last for frame in frames) == 1
    assert frames[-1].last
    assert framer.total_samples == samples
    assert all(len(frame.pcm) == 16 for frame in frames)


def test_exact_boundary_is_explicitly_flushed():
    framer = PCMFramer(2)
    assert framer.push(b"\1\0\2\0") == []
    final = framer.finish()
    assert final.first and final.last and final.valid_samples == 2


@pytest.mark.parametrize("data", [b"", b"\0", b"\0" * 10])
def test_bad_messages_do_not_change_accounting(data):
    framer = PCMFramer(2, max_message_bytes=8)
    with pytest.raises(ValueError):
        framer.push(data)
    assert framer.total_samples == 0 and framer.buffered_bytes == 0


def test_empty_and_double_finish_fail():
    with pytest.raises(ValueError, match="empty_audio"):
        PCMFramer(8).finish()
    framer = PCMFramer(8)
    framer.push(b"\0\0")
    framer.finish()
    with pytest.raises(ValueError, match="already_finished"):
        framer.finish()
    with pytest.raises(ValueError, match="audio_after_finish"):
        framer.push(b"\0\0")
