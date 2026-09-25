"""Bounded PCM framing with an explicit last-frame flush (no dropped tail)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PCMFrame:
    pcm: bytes
    valid_samples: int
    first: bool
    last: bool


class PCMFramer:
    """Hold at most one frame so exact-boundary EOS can mark its last frame.

    Incoming messages are bounded separately. Transport backpressure must await
    inference/queue admission before receiving another message. Padding is never
    counted as customer audio duration.
    """

    def __init__(self, frame_samples: int, *, max_message_bytes: int = 65536) -> None:
        if frame_samples <= 0 or max_message_bytes <= 0 or max_message_bytes % 2:
            raise ValueError("positive frame size and even positive message limit required")
        self.frame_bytes = frame_samples * 2
        self.max_message_bytes = max_message_bytes
        self._pending = bytearray()
        self._frames = 0
        self._closed = False
        self.total_samples = 0

    @property
    def buffered_bytes(self) -> int:
        return len(self._pending)

    def push(self, data: bytes) -> list[PCMFrame]:
        if self._closed:
            raise ValueError("audio_after_finish")
        if not data or len(data) % 2:
            raise ValueError("PCM16 messages must contain a nonempty whole number of samples")
        if len(data) > self.max_message_bytes:
            raise ValueError("audio_message_too_large")
        self.total_samples += len(data) // 2
        self._pending.extend(data)
        result = []
        while len(self._pending) > self.frame_bytes:
            result.append(self._take(self.frame_bytes, last=False))
        return result

    def finish(self) -> PCMFrame:
        if self._closed:
            raise ValueError("already_finished")
        self._closed = True
        if not self._pending:
            raise ValueError("empty_audio")
        return self._take(len(self._pending), last=True)

    def _take(self, valid_bytes: int, *, last: bool) -> PCMFrame:
        pcm = bytes(self._pending[:valid_bytes])
        del self._pending[:valid_bytes]
        frame = PCMFrame(
            pcm=pcm.ljust(self.frame_bytes, b"\0"),
            valid_samples=valid_bytes // 2,
            first=self._frames == 0,
            last=last,
        )
        self._frames += 1
        return frame
