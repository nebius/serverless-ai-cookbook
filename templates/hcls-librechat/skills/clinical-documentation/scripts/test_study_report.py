"""Offline methodology regressions; synthetic text is not clinical validation."""
import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

import study_report as report


def test_standalone_hyphen_and_annotation_policy_are_explicit():
    result = report.word_error('hello -- <UNSURE>world</UNSURE> <UNIN/>', 'hello world')
    assert result == {'reference_tokens': 2, 'hypothesis_tokens': 2, 'substitutions': 0,
                      'deletions': 0, 'insertions': 0, 'correct': 2, 'edit_distance': 0, 'wer': 0.0}
    assert report.METHOD['id'] == 'casefold-annotation-edge-punctuation/v1'
    assert '-' in report.METHOD['edge_punctuation']


def test_german_casefold_and_internal_punctuation_are_not_fuzzy_correction():
    assert report.words('Straße, A-B 1,5 "zwei"') == ['strasse', 'a-b', '1,5', 'zwei']
    result = report.word_error('Nicht nur HIV; zwei Tabletten.', 'nur HV zwei Tabletten')
    assert (result['reference_tokens'], result['deletions'], result['substitutions']) == (5, 1, 1)
    assert result['wer'] == 0.4


def test_contractions_numbers_and_uncertain_inner_words_are_not_normalized_away():
    value = report.word_error("don't <UNSURE>two</UNSURE>", 'do not 2')
    assert value['reference_tokens'] == 2
    assert value['edit_distance'] == 3


def test_empty_reference_is_not_zero_wer():
    with pytest.raises(ValueError, match='undefined'):
        report.word_error('-- <UNIN/>', 'words')
    assert report.word_error('some words', '')['wer'] == 1


def test_tied_alignment_has_stable_counts_and_denominators():
    for _ in range(3):
        value = report.word_error('a b', 'b a')
        assert value['substitutions'] == 2
        assert value['deletions'] == value['insertions'] == 0
        assert value['correct'] + value['substitutions'] + value['deletions'] == value['reference_tokens']
        assert value['correct'] + value['substitutions'] + value['insertions'] == value['hypothesis_tokens']


@pytest.fixture
def source_document():
    text = 'If symptoms persist, further tests may be considered. No fever now.'
    cut = text.index(' No fever')
    end_phrase = text.index(',')
    context = {'quote': text[:cut], 'spans': [{'start': 0, 'end': cut}]}
    phrase = {'quote': text[:end_phrase], 'spans': [{'start': 0, 'end': end_phrase}]}
    document = {'schema': 'clinical-documentation/v11', 'transcript_sha256': report.digest(text.encode()),
                'facts': [{'statement': phrase['quote'], 'source_phrases': [phrase], 'evidence': [context]}],
                'source_excerpts': [{'quote': text[cut:], 'spans': [{'start': cut, 'end': len(text)}]}],
                'rejected': [{'candidate': {'statement': 'Fever absent for all time'}}],
                'source_coverage': [{'final': [{'start': 0, 'end': cut, 'assessment': 'validated_phrase'},
                                             {'start': cut, 'end': len(text), 'assessment': 'validated_phrase'}]}]}
    return text, document


def test_keyword_in_context_or_review_is_not_an_accepted_fact(source_document):
    text, document = source_document
    probes = []
    for quote in ('If symptoms persist', 'further tests', 'No fever now.'):
        start = text.index(quote)
        probes.append({'start': start, 'end': start + len(quote), 'quote': quote})
    value = report.selection_report(document, text, probes)
    assert [p['location'] for p in value['source_span_probes']] == [
        'selected_phrase', 'cited_context_only', 'review_excerpt_only']
    assert value['segments_with_selected_phrase'] == 1  # Ignore model's two positive labels.
    assert value['clinical_completeness'] == 'not_established'
    assert value['declared_segment_character_gaps'] == []


def test_all_probe_hits_still_do_not_prove_completeness(source_document):
    text, document = source_document
    phrase = document['facts'][0]['source_phrases'][0]
    value = report.selection_report(document, text, [{**phrase['spans'][0], 'quote': phrase['quote']}])
    assert value['source_span_probes'][0]['location'] == 'selected_phrase'
    assert value['clinical_completeness'] == 'not_established'
    rendered = report.markdown({'kind': 'coverage', 'helper_sha256': '0'*64, 'measurement': value})
    assert 'not established' in rendered
    assert 'meaning not assessed' in rendered
    assert 'no important omission' not in rendered.lower()


def test_rejected_proposal_is_not_a_selected_fact(source_document):
    text, document = source_document
    quote = 'No fever now.'
    start = text.index(quote)
    # A false proposal in the review queue must not become a selected fact.
    document['rejected'][0]['candidate']['statement'] = quote
    value = report.selection_report(document, text, [{'start': start, 'end': len(text), 'quote': quote}])
    assert value['source_span_probes'][0]['location'] == 'review_excerpt_only'


def test_one_phrase_with_multiple_occurrences_is_not_counted_as_multiple_phrases():
    text = 'word word.'
    document = {'schema': 'clinical-documentation/v11', 'transcript_sha256': report.digest(text.encode()),
                'facts': [{'statement': 'word', 'source_phrases': [{'quote': 'word',
                    'spans': [{'start': 0, 'end': 4}, {'start': 5, 'end': 9}]}],
                    'evidence': [{'quote': text, 'spans': [{'start': 0, 'end': len(text)}]}]}],
                'source_excerpts': [], 'rejected': [],
                'source_coverage': [{'final': [{'start': 0, 'end': len(text)}]}]}
    value = report.selection_report(document, text)
    assert value['selected_phrases'] == 1
    assert value['selected_span_occurrences'] == 2


def test_source_only_and_missing_declared_character_coverage_are_explicit(source_document):
    text, document = source_document
    document['source_excerpts'] = []
    second = document['source_coverage'][0]['final'].pop()
    value = report.selection_report(document, text, [{'start': second['start'], 'end': second['end'], 'quote': text[second['start']:]}])
    assert value['source_span_probes'][0]['location'] == 'source_only'
    assert value['declared_segment_character_gaps'] == [{'start': second['start'], 'end': second['end']}]


@pytest.mark.parametrize('mutation', ['source', 'offset', 'statement', 'version', 'outside_context', 'probe'])
def test_changed_or_contradictory_source_evidence_is_not_accepted(source_document, mutation):
    text, original = source_document
    document = copy.deepcopy(original)
    probes = []
    if mutation == 'source':
        text += ' changed'
    elif mutation == 'offset':
        document['facts'][0]['source_phrases'][0]['spans'][0]['start'] = 1
    elif mutation == 'statement':
        document['facts'][0]['statement'] = 'A diagnosis not stated'
    elif mutation == 'version':
        document['schema'] = 'unknown/v99'
    elif mutation == 'outside_context':
        start = text.index('No fever')
        document['facts'][0]['evidence'] = [{'quote': text[start:], 'spans': [{'start': start, 'end': len(text)}]}]
    else:
        probes = [{'start': 0, 'end': 2, 'quote': 'No'}]
    with pytest.raises(ValueError):
        report.selection_report(document, text, probes)
    assert original == source_document[1]


def test_cli_retains_exact_source_and_inputs_and_can_reproduce_json(tmp_path):
    reference, hypothesis = tmp_path/'reference.txt', tmp_path/'hypothesis.txt'
    reference.write_bytes('Äpfel -- <UNSURE>zwei</UNSURE>\r\n'.encode())
    hypothesis.write_bytes('äpfel zwei\n'.encode())
    output, replay = tmp_path/'first', tmp_path/'replay'
    command = [sys.executable, str(Path(report.__file__)), 'wer', '--reference', str(reference),
               '--hypothesis', str(hypothesis), '--output', str(output)]
    subprocess.run(command, check=True, capture_output=True)
    subprocess.run([sys.executable, str(output/'helper.py'), 'wer', '--reference', str(output/'reference.txt'),
                    '--hypothesis', str(output/'hypothesis.txt'), '--output', str(replay)], check=True, capture_output=True)
    assert (output/'measurement.json').read_bytes() == (replay/'measurement.json').read_bytes()
    assert (output/'report.md').read_bytes() == (replay/'report.md').read_bytes()
    assert (output/'reference.txt').read_bytes() == reference.read_bytes()
    result = json.loads((output/'measurement.json').read_text())
    assert result['helper_sha256'] == report.digest((output/'helper.py').read_bytes())
    assert result['measurement']['reference_tokens'] == 2
    assert result['clinical_validation'] is False
    assert subprocess.run(command, capture_output=True).returncode != 0  # Never rewrite first output.


def test_clinical_cli_renders_actual_counts_without_changing_document(tmp_path, source_document):
    text, document = source_document
    document_path, transcript_path = tmp_path/'document.json', tmp_path/'transcript.txt'
    document_path.write_text(json.dumps(document))
    transcript_path.write_text(text)
    before = document_path.read_bytes()
    output = tmp_path/'measurement'
    subprocess.run([sys.executable, str(Path(report.__file__)), 'coverage', '--document', str(document_path),
                    '--transcript', str(transcript_path), '--output', str(output)], check=True, capture_output=True)
    value = json.loads((output/'measurement.json').read_text())
    assert value['measurement']['segments_with_selected_phrase'] == 1
    assert '1/2' in (output/'report.md').read_text()
    assert document_path.read_bytes() == before == (output/'document.json').read_bytes()
