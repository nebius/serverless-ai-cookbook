from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class AudioFormat(StrictContract):
    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate_hz: Literal[16000] = 16000
    channels: Literal[1] = 1


class SpeechOptions(StrictContract):
    model: Literal["nemotron-clinical-en", "nemotron35-base-en"]
    language: Literal["en", "en-US"] = "en-US"
    chunk_size_ms: Literal[80, 160, 320, 560, 1120] = 560
    strip_language_tags: Literal[True] = True
    output_granularity: Literal["segment", "word"] = "segment"
    stop_history_eou_ms: int = Field(default=800, ge=0, le=10000)

    @property
    def resolved_language(self):
        return "en-US"


class StreamStart(StrictContract):
    type: Literal["session.start"]
    options: SpeechOptions
    audio: AudioFormat = Field(default_factory=AudioFormat)


class TranscriptionRequest(StrictContract):
    audio_artifact: str = Field(pattern=r"^artifact:sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    options: SpeechOptions
