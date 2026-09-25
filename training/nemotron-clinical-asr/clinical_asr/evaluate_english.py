"""Pinned original English specialist benchmark; no live endpoint or default swap."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from .assembly import TEXT_ASSEMBLY
from .common import read_jsonl, sha256_file, write_json
from .evaluate import transcribe_wav
from .runtime import NeMoRuntime

REPOSITORY = 'nvidia/nemotron-speech-streaming-en-0.6b'
REVISION = 'ebe59e5a817142986528bbbee5dba8db7b38ed50'
CHECKPOINT_SHA = '283638054c44f6794e74fe9af9048d78a6d9d6c058c12131856c7859a62ac9cd'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--manifest', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    from huggingface_hub import hf_hub_download
    checkpoint = hf_hub_download(REPOSITORY, 'nemotron-speech-streaming-en-0.6b.nemo', revision=REVISION)
    if sha256_file(checkpoint) != CHECKPOINT_SHA:
        raise ValueError('english_upstream_checkpoint_sha256_mismatch')
    runtime = NeMoRuntime(checkpoint=checkpoint, checkpoint_sha=CHECKPOINT_SHA,
        model_id='nemotron-en-base', model_family='english_specialist', fine_tuned=False)
    runtime.load()
    # CLI-only fixed profile, not a newly admitted public API model choice.
    options = SimpleNamespace(model='nemotron-en-base', chunk_size_ms=560, output_granularity='segment', stop_history_eou_ms=800)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(args.manifest)
    with output.open('x') as target:
        for row in rows:
            result = transcribe_wav(runtime, row['audio_filepath'], options)
            result.update(id=row['id'], input_sha256=sha256_file(row['audio_filepath']))
            result['collapse_warning'] = not result['text'].strip() or '<unk>' in result['text'].lower()
            target.write(json.dumps(result, ensure_ascii=False) + '\n')
            target.flush()
    write_json(output.with_suffix('.provenance.json'), {'runtime': runtime.identity, 'text_assembly': TEXT_ASSEMBLY,
        'manifest_sha256': sha256_file(args.manifest), 'predictions_sha256': sha256_file(output), 'rows': len(rows),
        'comparison_scope': 'Same audio and nominal560ms native greedy profile; model-specific pretrained left context70 versus56 for Nemotron3.5; not identical architecture'})
