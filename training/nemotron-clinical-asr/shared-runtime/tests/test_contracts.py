import pytest
from pydantic import ValidationError

from fs2_speech.contracts import (
    ADAPTATION_LOCALES,
    ENGLISH_ID,
    MODELS,
    MULTILINGUAL_ID,
    READY_LOCALES,
    AudioFormat,
    RuntimeProfile,
    SpeechOptions,
    StreamStart,
)


def test_models_are_exact_pins_and_separate_apps():
    assert len(MODELS) == 2
    for model in MODELS.values():
        assert len(model.revision) == 40
        assert model.revision != "main"
        assert model.license_id


@pytest.mark.parametrize("language", READY_LOCALES)
def test_every_ready_locale_is_preserved(language):
    options = SpeechOptions(model=MULTILINGUAL_ID, language=language)
    assert options.resolved_language == language


def test_locale_tiers_are_disjoint_and_correct_size():
    assert len(set(READY_LOCALES)) == 32
    assert len(set(ADAPTATION_LOCALES)) == 8
    assert not set(READY_LOCALES) & set(ADAPTATION_LOCALES)


@pytest.mark.parametrize("language", ADAPTATION_LOCALES)
def test_adaptation_is_not_advertised_as_enabled(language):
    with pytest.raises(ValidationError, match="adapted checkpoint"):
        SpeechOptions(model=MULTILINGUAL_ID, language=language)


@pytest.mark.parametrize("model", [ENGLISH_ID, MULTILINGUAL_ID])
def test_model_specific_attention_context(model):
    for chunk in MODELS[model].chunk_sizes_ms:
        options = SpeechOptions(model=model, chunk_size_ms=chunk)
        assert options.attention_context == (MODELS[model].left_context, chunk // 80 - 1)


def test_no_silent_english_detection_or_extra_320ms_mode():
    with pytest.raises(ValidationError):
        SpeechOptions(model=ENGLISH_ID, language="auto")
    with pytest.raises(ValidationError):
        SpeechOptions(model=ENGLISH_ID, chunk_size_ms=320)


@pytest.mark.parametrize("language,expected", [("en", "en-US"), ("de", "de-DE"), ("pt", "pt-BR"), ("fr", "fr-FR")])
def test_librechat_bare_language_mapping(language, expected):
    assert SpeechOptions(model=MULTILINGUAL_ID, language=language).resolved_language == expected


def test_defaults():
    assert SpeechOptions(model=ENGLISH_ID).resolved_language == "en-US"
    assert SpeechOptions(model=MULTILINGUAL_ID).resolved_language == "auto"


@pytest.mark.parametrize("payload", [{"sample_rate_hz": 48000}, {"channels": 2}, {"encoding": "mp3"}])
def test_live_format_negotiation_is_explicit(payload):
    with pytest.raises(ValidationError):
        AudioFormat(**payload)


def test_unknown_or_coerced_options_do_not_silently_pass():
    with pytest.raises(ValidationError):
        SpeechOptions(model=ENGLISH_ID, prompt="an unsupported Whisper prompt")
    with pytest.raises(ValidationError):
        SpeechOptions(model=ENGLISH_ID, chunk_size_ms="80")
    with pytest.raises(ValidationError):
        SpeechOptions(model=ENGLISH_ID, strip_language_tags="false")


def test_start_message_and_profile_match():
    start = StreamStart.model_validate({"options": {"model": ENGLISH_ID}})
    RuntimeProfile(model=ENGLISH_ID).require_match(start.options)
    with pytest.raises(ValueError, match="runtime_profile_mismatch"):
        RuntimeProfile(model=ENGLISH_ID, chunk_size_ms=80).require_match(start.options)


def test_ignored_decoder_settings_are_rejected():
    with pytest.raises(ValidationError, match="beam_size"):
        RuntimeProfile(model=ENGLISH_ID, beam_size=8)
    RuntimeProfile(model=ENGLISH_ID, decoding="malsd_batch", beam_size=8)
