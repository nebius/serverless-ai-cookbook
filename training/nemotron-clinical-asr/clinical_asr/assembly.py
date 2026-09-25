"""Exact native final-fragment assembly shared by batch and offline rescoring.

NeMo finals are text deltas, not independently whitespace-delimited sentences.
They may split a word (``naus`` + ``ea``) or already contain separators. Never
strip individual fragments, insert spaces, or infer punctuation from timing.
"""

TEXT_ASSEMBLY = "native_final_concat_v1"


def assemble_final_fragments(events):
    fragments = []
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("invalid_transcript_event")
        if event["type"] == "transcript.final":
            if not isinstance(event.get("text"), str):
                raise ValueError("invalid_final_fragment")
            fragments.append(event["text"])
    # Preserve all internal native whitespace and native boundary errors. Only
    # surrounding whitespace is trimmed, matching the existing live client.
    return "".join(fragments).strip()
