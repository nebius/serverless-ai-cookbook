"""Stable segment/revision semantics independent of an ASR vendor transport."""

from dataclasses import asdict, dataclass
from typing import Literal


def assemble_transcript(finals) -> str:
    """Join raw finalized segments using only an explicit native boundary hint.

    Legacy/no-hint output is concatenated verbatim, including split words and
    no-space scripts. Text, acoustic items and timestamps are never rewritten.
    """
    text = ""
    for final in finals:
        chunk = final["text"]
        separator = final.get("separator_before", "")
        if not isinstance(chunk, str) or separator not in ("", " "):
            raise ValueError("invalid_transcript_join_contract")
        if separator and text and chunk and not text[-1].isspace() and not chunk[0].isspace():
            text += separator
        text += chunk
    return text.strip()


class NativeSeparatorObserver:
    """Observe the pinned decoder's dropped-prefix-punctuation edge case only.

    This instance-local hook does not replace decoding or modify native state.
    English word output is the only corrected contract. All other locales,
    segment output and unknown upstream shapes remain byte-for-byte verbatim.
    Hints exist only within one serialized native batch, never across sessions.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.batch = {}
        self.hints = {}
        self.seen = set()
        self.decoder = getattr(pipeline, "bpe_decoder", None)
        self.original = getattr(self.decoder, "decode_bpe_tokens", None)
        self.enabled = (
            callable(self.original)
            and callable(getattr(self.decoder, "cached_ids_to_text", None))
            and isinstance(getattr(self.decoder, "start_of_word_cache", None), dict)
            and callable(getattr(pipeline, "get_state", None))
            and callable(getattr(pipeline, "get_sep", None))
        )
        if self.enabled:
            self.decoder.decode_bpe_tokens = self._decode

    def begin_batch(self, entries):
        self.end_batch()
        self.batch = {stream: options for stream, _frame, options in entries}

    def end_batch(self):
        self.batch.clear()
        self.hints.clear()
        self.seen.clear()

    def _candidate(self, state):
        streams = [stream for stream in self.batch if self.pipeline.get_state(stream) is state]
        if len(streams) != 1:
            return None
        stream = streams[0]
        options = self.batch[stream]
        if (stream in self.seen or options.resolved_language != "en-US"
                or options.output_granularity != "word" or self.pipeline.get_sep() != " "
                or not state.options.is_word_level_output() or state.words or state.final_segments):
            return None
        tokens = state.tokens
        starts = self.decoder.start_of_word_cache
        if not tokens or type(starts.get(tokens[0])) is not bool:
            return None
        # Bound observation; never copy/log an entire native token history.
        boundary = next((i for i in range(1, min(len(tokens), 128))
                         if starts.get(tokens[i]) is True), None)
        if boundary is None or starts[tokens[0]]:
            return stream, None
        prefix = self.decoder.cached_ids_to_text(tuple(tokens[:boundary]))
        if prefix not in {".", ",", "?"}:
            return stream, None
        return stream, " "

    def _decode(self, state):
        try:
            candidate = self._candidate(state)
        except (AttributeError, KeyError, TypeError, ValueError, IndexError):
            candidate = None  # Unsupported metadata is not permission to repair.
        result = self.original(state)  # Original native errors are never hidden.
        if candidate is not None and getattr(state, "words", None):
            stream, hint = candidate
            self.seen.add(stream)
            first = state.words[0].text
            if hint and isinstance(first, str) and first.strip() and first.strip() not in {".", ",", "?"}:
                self.hints[stream] = (hint, first.strip())
        return result

    def annotate(self, outputs):
        for output in outputs:
            hint = self.hints.get(output.stream_id)
            text = output.final_transcript
            segments = getattr(output, "final_segments", None)
            if (hint and isinstance(text, str) and text and not text[0].isspace()
                    and segments and segments[0].text.strip() == hint[1]
                    and text.startswith(hint[1])):
                output.separator_before = hint[0]


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
