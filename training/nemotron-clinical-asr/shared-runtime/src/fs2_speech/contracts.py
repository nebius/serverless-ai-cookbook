"""Model-specific, strict speech contracts shared by file and streaming adapters.

These are upstream capabilities, NOT a declaration of platform qualification.
Runtime profile matching below prevents options from being silently ignored.
"""

from dataclasses import dataclass
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SpeechModelId = Literal["nemotron-speech-en-0.6b", "nemotron-speech-multilingual-0.6b"]
ENGLISH_ID: SpeechModelId = "nemotron-speech-en-0.6b"
MULTILINGUAL_ID: SpeechModelId = "nemotron-speech-multilingual-0.6b"
NEMO_REVISION = "3b08b2acacc13ec1268e53653346266202b2335f"

TRANSCRIPTION_LOCALES = (
    "en-US", "en-GB", "es-US", "es-ES", "fr-FR", "fr-CA", "it-IT", "pt-BR", "pt-PT",
    "nl-NL", "de-DE", "tr-TR", "ru-RU", "ar-AR", "hi-IN", "ja-JP", "ko-KR", "vi-VN", "uk-UA",
)
BROAD_COVERAGE_LOCALES = (
    "pl-PL", "sv-SE", "cs-CZ", "nb-NO", "da-DK", "bg-BG", "fi-FI", "hr-HR", "sk-SK",
    "zh-CN", "hu-HU", "ro-RO", "et-EE",
)
ADAPTATION_LOCALES = ("el-GR", "lt-LT", "lv-LV", "mt-MT", "sl-SI", "he-IL", "th-TH", "nn-NO")
READY_LOCALES = TRANSCRIPTION_LOCALES + BROAD_COVERAGE_LOCALES
# LibreChat sends ISO-639-1, losing the locale. These defaults are part of the
# compatibility contract; the native API preserves an explicit complete locale.
LANGUAGE_ALIASES = {locale.split("-")[0]: locale for locale in reversed(READY_LOCALES)}


@dataclass(frozen=True)
class ModelSpec:
    id: SpeechModelId
    repository: str
    revision: str
    filename: str
    license_id: str
    left_context: int
    chunk_sizes_ms: tuple[int, ...]
    default_language: str


MODELS = {
    ENGLISH_ID: ModelSpec(
        ENGLISH_ID, "nvidia/nemotron-speech-streaming-en-0.6b",
        "ebe59e5a817142986528bbbee5dba8db7b38ed50", "nemotron-speech-streaming-en-0.6b.nemo",
        "nvidia-open-model-license", 70, (80, 160, 560, 1120), "en-US",
    ),
    MULTILINGUAL_ID: ModelSpec(
        MULTILINGUAL_ID, "nvidia/nemotron-3.5-asr-streaming-0.6b",
        "ea30d66debe3740a08b573244286791d423d6b3e", "nemotron-3.5-asr-streaming-0.6b.nemo",
        "openmdw-1.1", 56, (80, 160, 320, 560, 1120), "auto",
    ),
}


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class AudioFormat(StrictContract):
    """Native streaming wire format; file decoding explicitly converts to this."""

    encoding: Literal["pcm_s16le"] = "pcm_s16le"
    sample_rate_hz: Literal[16000] = 16000
    channels: Literal[1] = 1


class SpeechOptions(StrictContract):
    model: SpeechModelId
    language: str | None = Field(default=None, min_length=2, max_length=16)
    chunk_size_ms: int = Field(default=560, ge=80, le=1120)
    strip_language_tags: bool = True
    output_granularity: Literal["segment", "word"] = "segment"
    stop_history_eou_ms: int = Field(default=800, ge=0, le=10000)

    @model_validator(mode="after")
    def validate_model_options(self) -> Self:
        spec = MODELS[self.model]
        if self.chunk_size_ms not in spec.chunk_sizes_ms:
            raise ValueError(f"{self.model} chunk_size_ms must be one of {spec.chunk_sizes_ms}")
        language = self.language or spec.default_language
        language = LANGUAGE_ALIASES.get(language, language)
        if language in ADAPTATION_LOCALES or language in {item[:2] for item in ADAPTATION_LOCALES}:
            raise ValueError(f"{language} requires an adapted checkpoint; it is not an enabled transcription locale")
        if self.model == ENGLISH_ID and language != "en-US":
            raise ValueError("English App accepts en-US/en; use the multilingual App for other locales or auto")
        if self.model == MULTILINGUAL_ID and language not in (*READY_LOCALES, "auto"):
            raise ValueError(f"Unknown transcription locale: {language}")
        return self

    @property
    def resolved_language(self) -> str:
        language = self.language or MODELS[self.model].default_language
        return LANGUAGE_ALIASES.get(language, language)

    @property
    def attention_context(self) -> tuple[int, int]:
        return MODELS[self.model].left_context, self.chunk_size_ms // 80 - 1


class StreamStart(StrictContract):
    type: Literal["session.start"] = "session.start"
    options: SpeechOptions
    audio: AudioFormat = Field(default_factory=AudioFormat)


class RuntimeProfile(StrictContract):
    """Immutable model-wide settings: never mutate them under active sessions.

    A future profile router may select among workers; a mismatched request must
    fail explicitly until its matching worker is available.
    """

    model: SpeechModelId
    chunk_size_ms: int = 560
    strip_language_tags: bool = True
    decoding: Literal["greedy_batch", "malsd_batch"] = "greedy_batch"
    beam_size: int = Field(default=4, ge=1, le=32)
    precision: Literal["float32", "float16", "bfloat16"] = "float32"
    confidence: bool = False
    cuda_graphs: bool = False

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        SpeechOptions(model=self.model, chunk_size_ms=self.chunk_size_ms)
        if self.decoding == "greedy_batch" and self.beam_size != 4:
            raise ValueError("beam_size is configurable only for malsd_batch decoding")
        return self

    def require_match(self, options: SpeechOptions) -> None:
        for field in ("model", "chunk_size_ms", "strip_language_tags"):
            if getattr(self, field) != getattr(options, field):
                raise ValueError(f"runtime_profile_mismatch: request {field} differs from the loaded worker")
