"""Bounded extraction coverage is not evidence of clinical completeness."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from clinical_report import document_transcript
from document import extraction_coverage, render, render_review


TEXT = 'Pain today. Rest two days.'
SEGMENTS = [{'id': 'S1', 'text': 'Pain today.', 'start': 0, 'end': 11},
            {'id': 'S2', 'text': ' Rest two days.', 'start': 11, 'end': len(TEXT)}]


def selected(identifier, quote):
    return {'section': 'history', 'source_ids': [identifier],
            'source_phrases': [{'source_id': identifier, 'quote': quote}],
            'uncertain': False, 'medication_or_dose': False, 'source_anchors': []}


class Reporter:
    def __init__(self, gap_result=True, excluded=False):
        self.gap_result, self.excluded = gap_result, excluded
        self.calls = []

    def complete(self, stage, prompt, data):
        self.calls.append((stage, data))
        if stage.startswith('extract'):
            gap = stage.startswith('extract-gap')
            if gap:
                assert [s['id'] for s in data['segments']] == ['S2']
            return {'kind': 'consultation', 'facts':
                    [selected('S2', 'Rest two days.')] if gap and self.gap_result else
                    [] if gap else [selected('S1', 'Pain today.')],
                    'uncertainties': [], 'excluded_segments':
                    [{'source_id': 'S2', 'reason': 'context_only'}] if self.excluded and not gap else []}
        if stage.startswith('review'):
            return {'decisions': [{'id': data['facts'][0]['id'], 'verdict': 'supported',
                                  'reason': 'Exact test source', 'medication_or_dose': False,
                                  'source_anchors': []}]}
        if stage == 'questions':
            return {'questions': []}
        raise AssertionError(stage)


class SourceCoverageTests(unittest.TestCase):
    def run_case(self, reporter):
        with tempfile.TemporaryDirectory() as folder, patch('clinical_report.source_segments', return_value=SEGMENTS):
            output = Path(folder)
            document = document_transcript(TEXT, 'en', reporter, output)
            self.assertEqual(json.loads((output/'coverage.json').read_text()), document['source_coverage'])
            return document, (output/'report.md').read_text()

    def test_one_followup_only_missing_segment_keeps_initial_omission(self):
        reporter = Reporter()
        document, _ = self.run_case(reporter)
        self.assertEqual(len(document['facts']), 2)
        receipt = document['source_coverage'][0]
        self.assertEqual(receipt['initial'][1]['assessment'], 'unassessed')
        self.assertEqual(receipt['followup_requested'], ['S2'])
        self.assertEqual(receipt['final'][1]['assessment'], 'validated_phrase')
        self.assertEqual([s for s, _ in reporter.calls if s.startswith('extract')],
                         ['extract-000', 'extract-gap-000'])

    def test_gap_still_missing_is_reported_not_retried_forever(self):
        reporter = Reporter(gap_result=False)
        document, report = self.run_case(reporter)
        self.assertEqual(document['source_coverage'][0]['final'][1]['assessment'], 'unassessed')
        self.assertIn('Limited extraction coverage: 1 source segments', report)
        self.assertEqual(sum(s.startswith('extract') for s, _ in reporter.calls), 2)

    def test_model_exclusion_cannot_suppress_followup_of_unvalidated_source(self):
        reporter = Reporter(excluded=True)
        document, _ = self.run_case(reporter)
        self.assertEqual(sum(s.startswith('extract') for s, _ in reporter.calls), 2)
        self.assertEqual(document['source_coverage'][0]['initial'][1]['assessment'], 'model_excluded')
        self.assertEqual(document['source_coverage'][0]['final'][1]['assessment'], 'validated_phrase')
        self.assertIn('not proof', document['source_coverage'][0]['interpretation'])

    def test_exclusion_ids_and_duplicate_records_are_validated(self):
        for excluded in [[{'source_id': 'S99', 'reason': 'non_clinical'}],
                         [{'source_id': 'S1', 'reason': 'non_clinical'}] * 2]:
            with self.assertRaises(ValueError):
                extraction_coverage({'excluded_segments': excluded}, SEGMENTS)

    def test_identical_source_quotes_deduplicate_without_changing_source(self):
        class DuplicateReporter(Reporter):
            def complete(self, stage, prompt, data):
                value = super().complete(stage, prompt, data)
                if stage == 'extract-000':
                    value['facts'] *= 2
                return value
        document, _ = self.run_case(DuplicateReporter(gap_result=False, excluded=True))
        self.assertEqual(len(document['facts']), 1)
        self.assertEqual(document['facts'][0]['source_phrases'][0]['quote'], 'Pain today.')

    def test_question_synthesis_does_not_receive_speculative_uncertainty_description(self):
        class UncertaintyReporter(Reporter):
            def complete(self, stage, prompt, data):
                if stage == 'questions':
                    assert 'Dioralyte' not in json.dumps(data)
                value = super().complete(stage, prompt, data)
                if stage == 'extract-000':
                    value['uncertainties'] = [{'description': 'Likely Dioralyte.', 'source_ids': ['S2']}]
                return value
        document, _ = self.run_case(UncertaintyReporter())
        self.assertEqual(document['uncertainties'][0]['model_description_for_review'], 'Likely Dioralyte.')
        self.assertNotIn('Dioralyte', document['uncertainties'][0]['description'])

    def test_referenced_invalid_quote_is_not_validated_coverage(self):
        value = {'facts': [selected('S1', 'Invented normalized name')], 'excluded_segments': []}
        row = extraction_coverage(value, SEGMENTS)[0]
        self.assertTrue(row['model_referenced'])
        self.assertEqual(row['assessment'], 'rejected_selection')

    def test_speculative_uncertainty_and_question_rationale_stay_review_only(self):
        document = {'kind': 'consultation', 'facts': [], 'rejected': [],
                    'uncertainties': [{'kind': 'source_uncertainty',
                                      'description': 'Source wording requires clarification.',
                                      'model_description_for_review': 'Likely Dioralyte.',
                                      'evidence': [{'quote': 'unclear dire light', 'spans': []}]}],
                    'questions': [{'question': 'What did the unclear name mean?', 'reason': 'Probably Dioralyte.',
                                   'fact_ids': ['F0001'], 'basis': 'unclear_source'}]}
        for language in ('en', 'de'):
            report, followup = render(document, language)
            self.assertNotIn('Dioralyte', report + followup)
            self.assertIn('dire light', followup)
            self.assertIn('Dioralyte', render_review(document, language))

    def test_full_source_conditions_are_adjacent_to_each_selected_plan_phrase(self):
        contexts = ['If feeling feverish and weak, taking paracetamol two tablets up to four times a day.',
                    'Take two to three days off work and rest; if symptoms have not improved in three to four days, return.']
        selected = ['taking paracetamol two tablets up to four times a day.',
                    'Take two to three days off work and rest']
        facts = [{'id': f'F{i+1:04}', 'section': 'plan', 'statement': phrase, 'uncertain': False,
                  'evidence': [{'quote': context, 'spans': [{'start': 0, 'end': len(context)}]}]}
                 for i, (phrase, context) in enumerate(zip(selected, contexts))]
        document = {'kind': 'consultation', 'facts': facts, 'rejected': [],
                    'uncertainties': [], 'questions': []}
        for language in ('en', 'de'):
            report, _ = render(document, language)
            first, second = report.index('[F0001]'), report.index('[F0002]')
            self.assertIn(contexts[0], report[first:second])
            # The context is in the same plan entry, before the later evidence appendix.
            appendix = report.index('## Quellen' if language == 'de' else '## Evidence')
            self.assertIn(contexts[1], report[second:appendix])


if __name__ == '__main__':
    unittest.main()
