"""Source labels are explicit classifications, not new medical facts or calls."""
import copy

import pytest

from clinical_report import document_transcript
from document import (SOURCE_ATTRIBUTIONS, apply_review, completion_schema,
                      render, validate_extraction)


def extracted(text, phrase, label='patient_reported', uncertain=False):
    candidate = {'section': 'findings', 'source_ids': ['S1'],
                 'source_phrases': [{'source_id': 'S1', 'quote': phrase}],
                 'source_attribution': label, 'uncertain': uncertain,
                 'medication_or_dose': False, 'source_anchors': []}
    data = {'kind': 'consultation', 'facts': [candidate], 'uncertainties': []}
    chunk = {'text': text, 'start': 0,
             'segments': [{'id': 'S1', 'text': text, 'start': 0, 'end': len(text)}]}
    facts, _, rejected, _ = validate_extraction(data, chunk)
    assert not rejected
    return facts


def reviewed(facts, label='patient_reported'):
    return apply_review(facts, {'decisions': [{'id': facts[0]['id'],
        'verdict': 'supported', 'reason': 'Test source classification, not a clinical verdict.',
        'source_attribution': label, 'medication_or_dose': False, 'source_anchors': []}]})


def document(facts):
    return {'kind': 'consultation', 'facts': facts, 'rejected': [],
            'uncertainties': [], 'questions': []}


@pytest.mark.parametrize('text,phrase,language', [
    # Exact short passages from the retained public acted v60/08 cases. Labels
    # below are explicit mocked extraction/review inputs, not inferred by regex.
    ('Ja, haben Sie mal gemessen. Ja hundertsechzig Schläge pro Minute.',
     'hundertsechzig Schläge pro Minute', 'de'),
    ('ich schwitze auch absurd viel nachts. Ich kann mein T Shirt morgens ausbringen',
     'ich schwitze auch absurd viel nachts', 'de'),
    ('Es sind vier Kilo weg in den letzten sechs Wochen, obwohl sie viel Appetit',
     'Es sind vier Kilo weg in den letzten sechs Wochen', 'de'),
    ('has it been affecting your life uh sorry I need to stay close to the toilet cause I go quite frequently during the these past three days',
     'I need to stay close to the toilet cause I go quite frequently during the these past three days', 'en'),
])
def test_retained_reported_passages_never_render_as_objective_findings(text, phrase, language):
    facts = extracted(text, phrase)
    before = copy.deepcopy(facts[0]['source_phrases'])
    kept, rejected = reviewed(facts)
    assert not rejected and kept[0]['source_attribution'] == 'patient_reported'
    assert kept[0]['statement'] == phrase and kept[0]['source_phrases'] == before
    report, _ = render(document(kept), language)
    assert SOURCE_ATTRIBUTIONS['patient_reported'][language == 'en'] in report
    assert '\n## Findings\n' not in report and '\n## Befunde\n' not in report
    assert phrase in report and text in report


@pytest.mark.parametrize('label,text', [
    ('clinician_observed', 'Clinician: I measured a pulse of 80 during this examination.'),
    ('clinician_statement', 'Clinician: We will examine you after this conversation.'),
    ('teaching_narration', 'Narrator: You are playing the role of the patient.'),
    ('unclear', 'A pulse of 80 was mentioned; the speaker is unclear.'),
])
def test_agreed_classifications_render_separately_without_rewriting(label, text):
    kept, rejected = reviewed(extracted(text, text, label), label)
    assert not rejected
    report, _ = render(document(kept), 'en')
    assert SOURCE_ATTRIBUTIONS[label][1] in report and text in report
    assert kept[0]['statement'] == text


@pytest.mark.parametrize('extraction,review', [
    ('patient_reported', 'clinician_observed'),
    ('clinician_observed', 'patient_reported'),
    ('unclear', 'clinician_observed'),
    ('clinician_observed', 'unclear'),
])
def test_disagreement_remains_unclear_not_upgraded_or_dropped(extraction, review):
    text = 'Pulse mentioned in the conversation.'
    kept, rejected = reviewed(extracted(text, text, extraction), review)
    assert not rejected and kept[0]['source_attribution'] == 'unclear'
    assert kept[0]['source_attribution_extraction'] == extraction
    assert kept[0]['source_attribution_review'] == review
    report, _ = render(document(kept), 'en')
    assert SOURCE_ATTRIBUTIONS['unclear'][1] in report
    assert SOURCE_ATTRIBUTIONS['clinician_observed'][1] not in report
    assert kept[0]['statement'] == text


@pytest.mark.parametrize('language', ['en', 'de'])
def test_legacy_section_and_number_do_not_infer_speaker_or_observation(language):
    text = 'hundertsechzig Schläge pro Minute'
    fact = extracted(text, text)[0]
    fact.pop('source_attribution')
    retained = document([fact])
    before = copy.deepcopy(retained)
    report, _ = render(retained, language)
    assert SOURCE_ATTRIBUTIONS['unclear'][language == 'en'] in report
    assert retained == before
    assert text in report


def test_extraction_only_label_cannot_masquerade_as_reviewed_attribution():
    facts = extracted('Pulse was recorded.', 'Pulse was recorded.', 'clinician_observed')
    report, _ = render(document(facts), 'en')
    assert SOURCE_ATTRIBUTIONS['unclear'][1] in report
    assert SOURCE_ATTRIBUTIONS['clinician_observed'][1] not in report


def test_uncertain_quote_stays_uncertain_even_when_source_type_agrees():
    kept, rejected = reviewed(extracted('I may have felt dizzy.', 'I may have felt dizzy.', uncertain=True))
    assert not rejected and kept[0]['uncertain']
    report, _ = render(document(kept), 'en')
    assert '[unclear – verify]' in report
    assert SOURCE_ATTRIBUTIONS['patient_reported'][1] in report


@pytest.mark.parametrize('stage,field', [('extract-000', 'facts'), ('review-000', 'decisions')])
def test_same_existing_structured_calls_require_independent_attribution(stage, field):
    facts = extracted('A statement.', 'A statement.')
    schema = completion_schema(stage, {'segments': [{'id': 'S1'}], 'facts': facts})
    for branch in schema['properties'][field]['items']['anyOf']:
        assert 'source_attribution' in branch['required']
        assert set(branch['properties']['source_attribution']['enum']) == set(SOURCE_ATTRIBUTIONS)


def test_existing_stage_count_and_quotes_unchanged_with_or_without_metadata(tmp_path):
    text = 'Patient: I measured my pulse at home.'
    class Reporter:
        def __init__(self, with_attribution):
            self.with_attribution, self.calls = with_attribution, []
        def complete(self, stage, prompt, data):
            self.calls.append(stage)
            if stage.startswith('extract'):
                fact = {'section':'findings', 'source_ids':['S1'],
                    'source_phrases':[{'source_id':'S1','quote':text}],
                    'uncertain':False,'medication_or_dose':False,'source_anchors':[]}
                if self.with_attribution:
                    fact['source_attribution'] = 'patient_reported'
                return {'kind':'consultation','facts':[fact],'uncertainties':[]}
            if stage.startswith('review'):
                item = {'id':data['facts'][0]['id'],'verdict':'supported','reason':'Literal source.',
                        'medication_or_dose':False,'source_anchors':[]}
                if self.with_attribution:
                    item['source_attribution'] = 'patient_reported'
                return {'decisions':[item]}
            if stage == 'questions':
                return {'questions':[]}
            raise AssertionError(stage)
    results, calls = [], []
    for flag in [False, True]:
        reporter = Reporter(flag)
        results.append(document_transcript(text,'en',reporter,tmp_path/str(flag)))
        calls.append(reporter.calls)
    assert calls[0] == calls[1] == ['extract-000','review-000-F0001','questions']
    assert results[0]['facts'][0]['source_attribution'] == 'unclear'
    assert results[1]['facts'][0]['source_attribution'] == 'patient_reported'
    assert results[0]['facts'][0]['source_phrases'] == results[1]['facts'][0]['source_phrases']
    assert results[0]['transcript_sha256'] == results[1]['transcript_sha256']


def test_identical_quote_duplicate_disagreement_preserves_both_classifications(tmp_path):
    text = 'Pulse mentioned in the conversation.'
    class Reporter:
        def complete(self, stage, prompt, data):
            if stage.startswith('extract'):
                facts = [{'section':'findings','source_ids':['S1'],
                          'source_phrases':[{'source_id':'S1','quote':text}],
                          'uncertain':False,'medication_or_dose':False,'source_anchors':[],
                          'source_attribution':label} for label in ['patient_reported','clinician_observed']]
                return {'kind':'consultation','facts':facts,'uncertainties':[]}
            if stage.startswith('review'):
                fact = data['facts'][0]
                return {'decisions':[{'id':fact['id'],'verdict':'supported','reason':'Test classification.',
                    'source_attribution':fact['source_attribution'],'medication_or_dose':False,'source_anchors':[]}]}
            if stage == 'questions':
                return {'questions':[]}
            raise AssertionError(stage)
    result = document_transcript(text, 'en', Reporter(), tmp_path)
    fact, = result['facts']
    assert fact['statement'] == text and fact['source_attribution'] == 'unclear'
    assert fact['source_attribution_conflicts'] == [
        {'fact_id':'F0001','extraction':'patient_reported','review':'patient_reported'},
        {'fact_id':'F0002','extraction':'clinician_observed','review':'clinician_observed'}]
    report, _ = render(result, 'en')
    assert SOURCE_ATTRIBUTIONS['unclear'][1] in report
    assert SOURCE_ATTRIBUTIONS['clinician_observed'][1] not in report
