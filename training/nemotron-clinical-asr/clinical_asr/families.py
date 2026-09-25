"""Explicit pinned model families; do not infer architecture from a filename.

English specialization is an opt-in candidate path, not a serving default swap.
Its non-prompt RNNT loader differs from the multilingual prompt RNNT loader.
"""
from dataclasses import dataclass

from . import BASE_FILENAME, BASE_REPOSITORY, BASE_REVISION


@dataclass(frozen=True)
class Family:
    repository: str
    revision: str
    filename: str
    sha256: str
    training_template: str
    model_class: str
    training_batch_fields: int
    left_context: int


FAMILIES = {
    "nemotron35": Family(
        BASE_REPOSITORY, BASE_REVISION, BASE_FILENAME,
        "210214ed94039bf6bfbb9a047c7fa289628db75b103e2bf6381fa78285436a74",
        "fastconformer_transducer_bpe_streaming_prompt.yaml",
        "EncDecRNNTBPEModelWithPrompt", 5, 56),
    "english_specialist": Family(
        "nvidia/nemotron-speech-streaming-en-0.6b",
        "ebe59e5a817142986528bbbee5dba8db7b38ed50",
        "nemotron-speech-streaming-en-0.6b.nemo",
        "283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd",
        "fastconformer_transducer_bpe_streaming.yaml",
        "EncDecRNNTBPEModel", 4, 70),
}


def family_spec(name):
    try:
        return FAMILIES[name]
    except KeyError as exc:
        raise ValueError("unknown_model_family") from exc


def training_batch_evidence(batch, family):
    """Return native reference tensors without assuming prompt/non-prompt parity."""
    if not isinstance(batch, (tuple, list)) or len(batch) != family_spec(family).training_batch_fields:
        raise ValueError("unexpected_native_training_batch_contract")
    return batch[1], batch[2], batch[3]


def assert_training_model(model, family):
    if type(model).__name__ != family_spec(family).model_class:
        raise ValueError("restored_model_family_class_mismatch")
