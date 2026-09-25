"""Stable segment/revision semantics independent of an ASR vendor transport."""

from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class TranscriptEvent:
    type: Literal["transcript.partial", "transcript.final"]
    session_id: str
    sequence: int
    segment_id: int
    revision: int
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


class TranscriptEvents:
    """Partial text replaces the current segment; finals seal it exactly once.

    Clients must not append partial text to previous partials. These are segment
    identifiers, not claimed acoustic timestamps. A final may revise a partial.
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.sequence = 0
        self.segment_id = 0
        self.revision = 0
        self._partial = ""
        self._finished = False

    def update(self, *, final: str = "", partial: str = "", last: bool = False) -> list[TranscriptEvent]:
        if self._finished:
            raise ValueError("transcript_after_completion")
        result = []
        if final:
            result.append(self._event("transcript.final", final))
            self.segment_id += 1
            self.revision = 0
            self._partial = ""
        if last:
            # Runtime must have actually finalized its tail. Never promote a
            # stale provisional transcript into a successful final ourselves.
            if partial:
                raise ValueError("runtime_did_not_finalize_tail")
            self._finished = True
        elif partial != self._partial:
            # Empty replacement is meaningful: the runtime retracted a partial.
            result.append(self._event("transcript.partial", partial))
            self._partial = partial
        return result

    def _event(self, kind: Literal["transcript.partial", "transcript.final"], text: str) -> TranscriptEvent:
        self.sequence += 1
        self.revision += 1
        return TranscriptEvent(kind, self.session_id, self.sequence, self.segment_id, self.revision, text)
