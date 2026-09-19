"""Literal grounding regressions, not clinical validation or drug recognition."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clinical_report import document_transcript, run
from document import (VERSION, apply_review, completion_schema, render_review,
                      validate_extraction)


def anchor(surface, quote=None, kind='medication', uncertain=False):
    return {'kind': kind, 'surface': surface, 'quote': quote or surface,
            'source_id': 'S1', 'uncertain': uncertain}


def fact(statement, anchors, flagged=None):
    return {'section': 'plan', 'statement': statement, 'uncertain': False,
            'source_ids': ['S1'], 'medication_or_dose': bool(anchors) if flagged is None else flagged,
            'source_anchors': anchors}


def extract(text, candidate):
    return validate_extraction({'kind': 'consultation', 'facts': [candidate], 'uncertainties': []},
                               {'text': text, 'start': 0, 'segments': [
                                   {'id': 'S1', 'text': text, 'start': 0, 'end': len(text)}]})


def review(candidate, anchors=None, verdict='supported', flagged=None):
    return {'decisions': [{'id': candidate['id'], 'verdict': verdict,
                          'reason': 'Model claims support; literal gate must be independent.',
                          'medication_or_dose': candidate['medication_or_dose'] if flagged is None else flagged,
                          'source_anchors': candidate['source_anchors'] if anchors is None else anchors}]}


class SourceAnchorTests(unittest.TestCase):
    def test_en_de_normalizations_rejected_with_context(self):
        for text, statement, source, normalized in [
            ('Try the unclear name dire light.', 'Try Dioralyte.', 'dire light', 'Dioralyte'),
            ('Sie nennt etwas wie meta pro lol.', 'Sie nimmt Metoprolol.', 'meta pro lol', 'Metoprolol'),
        ]:
            with self.subTest(text=text):
                facts, _, rejected, _ = extract(text, fact(statement, [anchor(normalized, source)]))
                self.assertEqual(facts, [])
                self.assertEqual(rejected[0]['candidate']['statement'], statement)
                self.assertEqual(rejected[0]['candidate']['evidence'][0]['quote'], text)
                self.assertIn('differs from literal source', rejected[0]['reason'])

    def test_invented_source_quote_rejected(self):
        facts, _, rejected, _ = extract('The name sounds like med a sin.',
                                       fact('Take Medicin.', [anchor('Medicin')]))
        self.assertEqual(facts, [])
        self.assertIn('not a literal span', rejected[0]['reason'])

    def test_en_de_unclear_names_retained_literally_and_flagged(self):
        for text, name in [('It sounded like med a sin.', 'med a sin'),
                           ('Der Name war wohl beta block a.', 'beta block a')]:
            with self.subTest(name=name):
                facts, _, rejected, _ = extract(text, fact(text, [anchor(name, uncertain=True)]))
                self.assertEqual(rejected, [])
                accepted, rejected = apply_review(facts, review(facts[0]))
                self.assertEqual(rejected, [])
                self.assertEqual(accepted[0]['statement'], text)
                self.assertTrue(accepted[0]['uncertain'])

    def test_literal_names_and_doses_allowed_en_de(self):
        for text, name, dose in [('Take aspirin 5 mg.', 'aspirin', '5 mg'),
                                 ('Kein Metoprolol 25 mg einnehmen.', 'Metoprolol', '25 mg')]:
            with self.subTest(text=text):
                facts, _, rejected, _ = extract(text, fact(text, [anchor(name), anchor(dose, kind='dose')]))
                self.assertEqual(rejected, [])
                accepted, rejected = apply_review(facts, review(facts[0]))
                self.assertEqual(rejected, [])
                self.assertEqual(accepted[0]['statement'], text)
                for a in accepted[0]['source_anchors']:
                    for span in a['spans']:
                        self.assertEqual(text[span['start']:span['end']], a['quote'])

    def test_case_and_unicode_render_exact_source_bytes(self):
        text = 'Not prescribed: cafémed 5 mg.'
        statement = 'Not prescribed: CAFE\u0301MED 5 mg.'
        facts, _, rejected, _ = extract(text, fact(statement, [anchor('CAFE\u0301MED', 'cafémed'),
                                                              anchor('5 mg', kind='dose')]))
        self.assertEqual(rejected, [])
        accepted, _ = apply_review(facts, review(facts[0]))
        self.assertEqual(accepted[0]['statement'], text)
        self.assertEqual(accepted[0]['original_statement'], statement)

    def test_dose_unit_and_number_conversion_not_silently_normalized(self):
        for source, surface in [('five milligrams', '5 mg'), ('5 mg', '5 g'), ('zweimal täglich', '2x täglich')]:
            with self.subTest(source=source):
                facts, _, rejected, _ = extract(source, fact(surface, [anchor(surface, source, kind='dose')]))
                self.assertEqual(facts, [])
                self.assertTrue(rejected)

    def test_substring_not_complete_surface_rejected(self):
        facts, _, rejected, _ = extract('Take 15 mg.', fact('Take 15 mg.', [anchor('5 mg', kind='dose')]))
        self.assertEqual(facts, [])
        self.assertTrue(rejected)

    def test_source_id_must_be_cited_not_merely_known(self):
        item = anchor('aspirin')
        item['source_id'] = 'S2'
        facts, _, rejected, _ = extract('aspirin', fact('aspirin', [item]))
        self.assertEqual(facts, [])
        self.assertTrue(rejected)

    def test_supported_reviewer_cannot_override_bad_anchor(self):
        facts, _, _, _ = extract('The name is unclear: med a sin.',
                                 fact('The name is unclear: med a sin.', [anchor('med a sin')]))
        accepted, rejected = apply_review(facts, review(facts[0], [anchor('Medicin', 'med a sin')]))
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]['verdict'], 'source_anchor_mismatch')
        self.assertEqual(rejected[0]['review']['verdict'], 'supported')

    def test_review_independently_catches_extraction_omission(self):
        facts, _, _, _ = extract('Discuss aspirin.', fact('Discuss aspirin.', [], flagged=False))
        accepted, rejected = apply_review(facts, review(facts[0], [anchor('aspirin')], flagged=True))
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]['verdict'], 'source_anchor_mismatch')

    def test_both_models_omitting_classification_remains_explicit_limitation(self):
        facts, _, _, _ = extract('med a sin', fact('Medicin', [], flagged=False))
        accepted, _ = apply_review(facts, review(facts[0]))
        self.assertEqual(len(accepted), 1)  # No false guarantee of entity recognition.

    def test_negation_requires_contextual_review_even_with_valid_anchor(self):
        facts, _, _, _ = extract('Do not take aspirin.', fact('Take aspirin.', [anchor('aspirin')]))
        accepted, rejected = apply_review(facts, review(facts[0], verdict='unsupported'))
        self.assertEqual(accepted, [])
        self.assertEqual(rejected[0]['verdict'], 'unsupported')

    def test_declared_medication_without_anchor_rejected(self):
        facts, _, rejected, _ = extract('Take aspirin.', fact('Take aspirin.', [], flagged=True))
        self.assertEqual(facts, [])
        self.assertTrue(rejected)

    def test_old_extraction_fields_are_not_silently_accepted(self):
        candidate = fact('Symptoms improved.', [])
        del candidate['medication_or_dose']
        del candidate['source_anchors']
        facts, _, rejected, _ = extract('Symptoms improved.', candidate)
        self.assertEqual(facts, [])
        self.assertIn('source-anchor declaration', rejected[0]['reason'])

    def test_schemas_require_independent_extraction_and_review_declarations(self):
        extracted = completion_schema('extract-000', {'segments': [{'id': 'S1'}]})
        facts, _, _, _ = extract('Take aspirin.', fact('Take aspirin.', [anchor('aspirin')]))
        reviewed = completion_schema('review-000', {'facts': facts})
        for schema, field in [(extracted, 'facts'), (reviewed, 'decisions')]:
            for branch in schema['properties'][field]['items']['anyOf']:
                self.assertIn('source_anchors', branch['required'])
                self.assertIn('medication_or_dose', branch['required'])
                flagged = branch['properties']['medication_or_dose']['enum'][0]
                self.assertEqual(branch['properties']['source_anchors']['minItems'], 1 if flagged else 0)
                self.assertEqual(branch['properties']['source_anchors']['maxItems'], 12 if flagged else 0)
        self.assertEqual(reviewed['properties']['decisions']['minItems'], 1)
        self.assertEqual(reviewed['properties']['decisions']['maxItems'], 1)

    def test_duplicate_review_decisions_still_fail_instead_of_being_collapsed(self):
        facts, _, _, _ = extract('No aspirin.', fact('No aspirin.', [anchor('aspirin')]))
        verdict = review(facts[0])
        verdict['decisions'] *= 2
        with self.assertRaisesRegex(ValueError, 'exactly once'):
            apply_review(facts, verdict)

    def test_mismatch_cannot_be_rescued_by_citation_repair(self):
        class Reporter:
            def complete(self, stage, prompt, data):
                if stage.startswith('extract'):
                    return {'kind': 'consultation', 'uncertainties': [], 'facts': [
                        fact('Symptoms improved.', []), fact('Discuss med a sin.', [anchor('med a sin')])]}
                if stage.startswith('review'):
                    item = data['facts'][0]
                    return review(item, [anchor('Medicin', 'med a sin')] if item['source_anchors'] else [])
                if stage == 'questions':
                    return {'questions': []}
                raise AssertionError('No relocation is allowed after anchor mismatch')
        with tempfile.TemporaryDirectory() as folder:
            result = document_transcript('Symptoms improved. Discuss med a sin.', 'en', Reporter(), Path(folder))
            self.assertEqual(len(result['facts']), 1)
            self.assertEqual(result['rejected'][0]['verdict'], 'source_anchor_mismatch')
            self.assertIn('Discuss med a sin.', render_review(result, 'en'))

    def test_v4_output_is_untouched_and_requires_new_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'input.txt'
            source.write_text('Symptoms improved.')
            output = root / 'existing'
            output.mkdir()
            manifest = output / 'run.json'
            original = json.dumps({'config': {'schema': 'clinical-documentation/v4'}, 'status': 'completed'})
            manifest.write_text(original)
            args = SimpleNamespace(report_model='unchanged', audio=None, transcript=source,
                                   artifact=None, asr_model=None, language='en', report_provider='unchanged',
                                   base_url='http://unused', output=output)
            with patch('clinical_report.Platform') as platform:
                with self.assertRaisesRegex(ValueError, 'document version'):
                    run(args)
                platform.assert_not_called()
            self.assertEqual(manifest.read_text(), original)
            self.assertEqual(VERSION, 'clinical-documentation/v5')


if __name__ == '__main__':
    unittest.main()
