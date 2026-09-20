#!/usr/bin/env python3
"""Offline lexical ASR comparison. No clinical verdicts or inference calls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import unicodedata


def historical_metrics():
    path = Path(__file__).resolve().parents[2] / 'clinical-documentation/scripts/study_report.py'
    spec = importlib.util.spec_from_file_location('clinical_study_metrics', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def distance(left, right):
    """Exact unit-cost Levenshtein via bit vectors; avoids a character DP matrix."""
    if left == right:
        return 0
    if len(left) > len(right):
        left, right = right, left
    if not left:
        return len(right)
    masks = {}
    for i, char in enumerate(left):
        masks[char] = masks.get(char, 0) | (1 << i)
    positive, negative, score = ~0, 0, len(left)
    last = 1 << (len(left) - 1)
    for char in right:
        equal = masks.get(char, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        up = negative | ~(horizontal | positive)
        down = positive & horizontal
        score += bool(up & last) - bool(down & last)
        up = (up << 1) | 1
        down <<= 1
        positive = down | ~(vertical | up)
        negative = up & vertical
    return score


def normalized(text):
    # Do not collapse numerals, units, negation, accents or compound words.
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def phrase_present(phrase, text):
    needle, haystack = phrase.split(), text.split()
    return any(haystack[i:i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def evaluate(reference, hypothesis, language, keywords=()):
    if language not in {'en', 'de'}:
        raise ValueError('This evaluation release supports declared en or de only')
    metrics = historical_metrics()
    wer = metrics.word_error(reference, hypothesis)
    ref, hyp = normalized(reference), normalized(hypothesis)
    if not isinstance(keywords, (list, tuple)) or any(not isinstance(k, str) for k in keywords):
        raise ValueError('keywords must be an array of literal phrases')
    terms = [normalized(k) for k in keywords]
    if any(not k or not phrase_present(k, ref) for k in terms):
        raise ValueError('Every keyword must be a nonempty contiguous phrase in the reference')
    if len(terms) != len(set(terms)):
        raise ValueError('Duplicate normalized keywords would bias the denominator')
    rows = [{'phrase': k, 'present': phrase_present(k, hyp)} for k in terms]
    edits = distance(ref, hyp)
    return {
        'schema': 'scientific-ai/clinical-asr-lexical/v1', 'language': language,
        'reference_sha256': hashlib.sha256(reference.encode()).hexdigest(),
        'hypothesis_sha256': hashlib.sha256(hypothesis.encode()).hexdigest(),
        'wer_normalization': metrics.NORMALIZATION, 'wer': wer,
        'cer_normalization': 'unicode-nfc-casefold-whitespace-v1; includes spaces and punctuation',
        'cer': {'reference_characters': len(ref), 'edit_distance': edits, 'rate': edits / len(ref)},
        'keyword_method': 'distinct-contiguous-whitespace-token-phrases/v1; punctuation retained',
        'keywords': rows,
        'keyword_error_rate': sum(not r['present'] for r in rows) / len(rows) if rows else None,
        'clinical_correctness': 'not_assessed',
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--reference', type=Path, required=True)
    cli.add_argument('--hypothesis', type=Path, required=True)
    cli.add_argument('--language', choices=['en', 'de'], required=True)
    cli.add_argument('--keywords', type=Path)
    cli.add_argument('--output', type=Path, required=True)
    args = cli.parse_args()
    # Decode raw bytes without newline conversion so hashes bind original files.
    reference = args.reference.read_bytes().decode('utf-8')
    hypothesis = args.hypothesis.read_bytes().decode('utf-8')
    terms = json.loads(args.keywords.read_text()) if args.keywords else []
    result = evaluate(reference, hypothesis, args.language, terms)
    output = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n'
    with args.output.open('x', encoding='utf-8') as handle:
        handle.write(output)
    if args.output.read_text(encoding='utf-8') != output:
        raise RuntimeError('Output readback mismatch')
    print(json.dumps({'output': str(args.output), 'schema': result['schema']}))


if __name__ == '__main__':
    main()
