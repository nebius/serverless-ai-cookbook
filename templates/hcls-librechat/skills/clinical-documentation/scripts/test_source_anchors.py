"""Literal grounding regressions, not clinical validation or drug recognition."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from clinical_report import document_transcript, run
from document import (VERSION, apply_review, completion_schema, introduced_fact_tokens, render, render_review,
                      source_excerpt_fallbacks, validate_extraction)


def anchor(surface, quote=None, kind='medication', uncertain=False):
    return {'kind': kind, 'surface': surface, 'quote': quote or surface,
            'source_id': 'S1', 'uncertain': uncertain}


def fact(statement, anchors, flagged=None):
    return {'section': 'plan', 'statement': statement, 'uncertain': False,
            'source_phrases': [{'source_id': 'S1', 'quote': statement}],
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
                self.assertIn('not an exact literal span', rejected[0]['reason'])

    def test_invented_source_quote_rejected(self):
        facts, _, rejected, _ = extract('The name sounds like med a sin.',
                                       fact('Take Medicin.', [anchor('Medicin')]))
        self.assertEqual(facts, [])
        self.assertIn('not an exact literal span', rejected[0]['reason'])

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

    def test_exact_phrases_preserve_source_case_unicode_not_normalized_proposal(self):
        text = 'Not prescribed: cafémed 5 mg.'
        statement = 'Not prescribed: CAFE\u0301MED 5 mg.'
        facts, _, rejected, _ = extract(text, fact(statement, [anchor('CAFE\u0301MED', 'cafémed'),
                                                              anchor('5 mg', kind='dose')]))
        self.assertEqual(facts, [])
        self.assertTrue(rejected)
        item = fact(text, [anchor('cafémed'), anchor('5 mg', kind='dose')])
        item['statement'] = statement  # Unrecognized free prose cannot replace selected source bytes.
        facts, _, rejected, _ = extract(text, item)
        self.assertEqual(rejected, [])
        accepted, _ = apply_review(facts, review(facts[0]))
        self.assertEqual(accepted[0]['statement'], text)
        self.assertEqual(accepted[0]['original_statement'], text)

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

    def test_both_false_flags_and_empty_anchors_cannot_authorize_normalized_names(self):
        for text, statement in [
            ('There are things like dire light from the pharmacy.', 'Consider Dioralyte.'),
            ('There are things like dire light from the pharmacy.', 'consider dioralyte.'),
            ('Sie nennt meta pro lol.', 'Sie nennt Metoprolol.'),
            ('Der Name war med a sin.', 'Der Name war medicin.'),
        ]:
            with self.subTest(statement=statement):
                facts, _, rejected, _ = extract(text, fact(statement, [], flagged=False))
                self.assertEqual(facts, [])
                self.assertIn('not an exact literal span', rejected[0]['reason'])
                self.assertEqual(rejected[0]['candidate']['evidence'][0]['quote'], text)
                # Even a preconstructed fact and a supported second-model verdict
                # cannot skip the independent check at review/citation repair.
                candidate = dict(rejected[0]['candidate'], id='F0001')
                accepted, dropped = apply_review([candidate], review(candidate))
                self.assertEqual(accepted, [])
                self.assertEqual(dropped[0]['verdict'], 'source_vocabulary_mismatch')
                self.assertEqual(dropped[0]['review']['medication_or_dose'], False)

    def test_literal_unclear_words_survive_false_classification_without_replacement(self):
        for text in ['The name is unclear: dire light.', 'Der Name ist unklar: meta pro lol.']:
            facts, _, rejected, _ = extract(text, fact(text, [], flagged=False))
            self.assertEqual(rejected, [])
            accepted, dropped = apply_review(facts, review(facts[0]))
            self.assertEqual(dropped, [])
            self.assertEqual(accepted[0]['statement'], text)

    def test_retained_public_f0027_false_classification_cannot_bypass_extraction(self):
        source = ('making sure you\'re well hydrated so drinking fluids um there are '
                  'things like dire light you can get from the pharmacy')
        statement = ('The patient should maintain hydration and consider using oral '
                     'rehydration solutions like Dioralyte.')
        facts, _, rejected, _ = extract(source, fact(statement, [], flagged=False))
        self.assertEqual(facts, [])
        self.assertIn('not an exact literal span', rejected[0]['reason'])
        self.assertEqual(rejected[0]['candidate']['statement'], statement)
        self.assertIn('dire light', rejected[0]['candidate']['evidence'][0]['quote'])
        self.assertNotIn('Dioralyte', rejected[0]['candidate']['evidence'][0]['quote'])

    def test_source_excerpt_fallback_deduplicates_quotes_never_renders_rejected_normalization(self):
        for text, proposed in [('things like dire light from the pharmacy', 'Dioralyte'),
                               ('der Name ist meta pro lol', 'Metoprolol')]:
            with self.subTest(text=text):
                _, _, rejected, _ = extract(text, fact(proposed, [], flagged=False))
                second = {**rejected[0], 'id': 'F0002'}
                excerpts = source_excerpt_fallbacks(rejected + [second])
                self.assertEqual(len(excerpts), 1)
                self.assertEqual(excerpts[0]['quote'], text)
                self.assertEqual(excerpts[0]['candidate_ids'], ['F0001', 'F0002'])
                for span in excerpts[0]['spans']:
                    self.assertEqual(text[span['start']:span['end']], excerpts[0]['quote'])
                document = {'kind': 'consultation', 'facts': [], 'rejected': rejected,
                            'source_excerpts': excerpts, 'uncertainties': [], 'questions': []}
                for language in ('en', 'de'):
                    report, _ = render(document, language)
                    self.assertIn(text, report)
                    self.assertNotIn(proposed, report)
                    self.assertIn(proposed, render_review(document, language))
                self.assertEqual(document['facts'], [])  # Excerpts never become accepted clinical facts.

    def test_all_withheld_facts_produce_explicit_source_only_review_not_empty_note(self):
        class Reporter:
            def complete(self, stage, prompt, data):
                if stage.startswith('extract'):
                    return {'kind': 'consultation', 'facts': [fact('Dioralyte', [], flagged=False)],
                            'uncertainties': []}
                raise AssertionError('No speculative review or questions without accepted facts')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            result = document_transcript('The unclear name is dire light.', 'en', Reporter(), root)
            self.assertEqual(result['facts'], [])
            self.assertEqual(result['draft_mode'], 'source_review_only_no_accepted_facts')
            report = (root / 'report.md').read_text()
            self.assertIn('No facts accepted.', report)
            self.assertIn('dire light', report)
            self.assertNotIn('Dioralyte', report)
            self.assertIn('Dioralyte', (root / 'review.md').read_text())

    def test_conservative_wording_scope_and_known_false_rejections(self):
        for source, statement in [
            ('The symptoms have improved.', 'symptoms have improved.'),
            ('Die Schmerzen sind besser.', 'Schmerzen sind besser.'),
        ]:
            facts, _, rejected, _ = extract(source, fact(statement, []))
            self.assertEqual(rejected, [])
            self.assertEqual(len(apply_review(facts, review(facts[0]))[0]), 1)
        # Supported linguistic equivalents are intentionally not silently inferred.
        for source, statement in [('Symptoms improve.', 'Symptoms improved.'),
                                  ('fünf Milligramm', '5 Milligramm'),
                                  ('five milligrams', '5 milligrams'),
                                  ('no fever', 'kein Fieber'),
                                  ('mit starken Schmerzen', 'starke Schmerzen'),
                                  ('0.5 mg', '5.0 mg')]:
            with self.subTest(statement=statement):
                facts, _, rejected, _ = extract(source, fact(statement, [], flagged=False))
                self.assertEqual(facts, [])
                self.assertTrue(rejected)
        # Presence is not entailment: a separate contextual reviewer must catch negation.
        self.assertEqual(introduced_fact_tokens('Take aspirin.', [{'quote': 'Do not take aspirin.'}]), [])

    def test_negation_requires_contextual_review_even_with_valid_anchor(self):
        facts, _, _, _ = extract('Do not take aspirin.', fact('take aspirin.', [anchor('aspirin')]))
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
        for branch in extracted['properties']['facts']['items']['anyOf']:
            self.assertIn('source_phrases', branch['required'])
            self.assertNotIn('statement', branch['properties'])

    def test_multiple_exact_fact_passages_keep_offsets_and_context(self):
        text = 'Any blood? No blood. Name unclear: dire light.'
        item = fact('ignored invented brand', [], flagged=False)
        item['source_phrases'] = [{'source_id': 'S1', 'quote': 'Any blood?'},
                                  {'source_id': 'S1', 'quote': 'No blood.'}]
        facts, _, rejected, _ = extract(text, item)
        self.assertEqual(rejected, [])
        self.assertEqual(facts[0]['statement'], 'Any blood? … No blood.')
        for phrase in facts[0]['source_phrases']:
            for span in phrase['spans']:
                self.assertEqual(text[span['start']:span['end']], phrase['quote'])
        self.assertEqual(facts[0]['evidence'][0]['quote'], text)
        del item['source_phrases']
        facts, _, rejected, _ = extract(text, item)
        self.assertEqual(facts, [])
        self.assertIn('no free-form factual statement', rejected[0]['reason'])

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

    def test_old_completed_outputs_are_untouched_and_require_new_directory(self):
        for version in ('v4', 'v5', 'v6', 'v7', 'v8', 'v9'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                source = root / 'input.txt'
                source.write_text('Symptoms improved.')
                output = root / 'existing'
                output.mkdir()
                manifest = output / 'run.json'
                original = json.dumps({'config': {'schema': 'clinical-documentation/' + version}, 'status': 'completed'})
                manifest.write_text(original)
                args = SimpleNamespace(report_model='unchanged', audio=None, transcript=source,
                                       artifact=None, asr_model=None, language='en', report_provider='unchanged',
                                       base_url='http://unused', output=output)
                with patch('clinical_report.Platform') as platform:
                    with self.assertRaisesRegex(ValueError, 'document version'):
                        run(args)
                    platform.assert_not_called()
                self.assertEqual(manifest.read_text(), original)
                self.assertEqual(VERSION, 'clinical-documentation/v10')


if __name__ == '__main__':
    unittest.main()
