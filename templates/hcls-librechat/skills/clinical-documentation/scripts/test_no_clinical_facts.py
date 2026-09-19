"""Retained v39 German no-report outcome: offline, no model or clinical claims."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

import clinical_report as workflow


# Original public non-consultation MultiMed ASR fragment, unchanged (162 UTF-8 bytes).
TEXT = ('nur HV sein, Maßnahmen ergreift, um den Ausbruch einer Erkrankung zu verhindern '
        'oder ich sage es etwas zurückhaltende, ihren Verlauf abzumildern. Das machen Sie')


class NoFactsReporter:
    def __init__(self, kind):
        self.kind, self.calls, self.closed = kind, [], False

    def complete(self, stage, _prompt, data):
        self.calls.append(stage)
        assert stage.startswith('extract'), 'No review/question generation for absent facts'
        return {'kind': self.kind, 'facts': [], 'uncertainties': [],
                'excluded_segments': [{'source_id': s['id'], 'reason': 'non_clinical'}
                                      for s in data['segments']]}

    def close(self):
        self.closed = True


class NoClinicalFactsTests(unittest.TestCase):
    def arguments(self, root):
        source = root/'source.txt'
        source.write_text(TEXT)
        return workflow.parser().parse_args([
            '--transcript', str(source), '--language', 'de', '--report-provider',
            'https://api.tokenfactory.nebius.com/v1', '--report-model',
            'Qwen/Qwen3-235B-A22B-Instruct-2507', '--output', str(root/'output')])

    def test_original_negative_and_insufficient_source_retain_precise_no_report_outcome(self):
        self.assertEqual(len(TEXT.encode()), 162)
        self.assertEqual(workflow.digest(TEXT),
                         'ecf9a586ece9c373ba38d721cc9301ddc05e66e8d4b3aa28179dadc63f0c267f')
        for kind in ('non_patient', 'insufficient', 'consultation'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                args = self.arguments(Path(directory))
                reporter = NoFactsReporter(kind)
                with patch.object(workflow, 'Platform') as platform, patch.object(workflow, 'Reporter', return_value=reporter):
                    with self.assertRaises(workflow.NoSupportedClinicalFacts):
                        workflow.run(args, key='offline-platform-fixture')
                manifest = workflow.read(args.output/'run.json')
                self.assertEqual(manifest['status'], 'incomplete')
                self.assertEqual(manifest['error_code'], 'no_supported_clinical_facts')
                self.assertEqual(manifest['error_detail'], workflow.NoSupportedClinicalFacts.detail)
                self.assertEqual((args.output/'transcript.txt').read_bytes(), args.transcript.read_bytes())
                self.assertEqual(workflow.read(args.output/'review.json')['kinds'], [kind])
                self.assertFalse((args.output/'report.md').exists())
                self.assertFalse((args.output/'document.json').exists())
                self.assertEqual(reporter.calls, ['extract-000', 'extract-gap-000'])
                self.assertTrue(reporter.closed)
                platform.return_value.require_models.assert_called_once_with([])
                platform.return_value.operation.assert_not_called()

    def test_cli_emits_recognized_code_for_actual_workflow_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.arguments(Path(directory))
            stdout = io.StringIO()
            with patch.object(workflow, 'parser') as parser, patch.object(workflow, 'Platform'), \
                    patch.object(workflow, 'credential', return_value='offline-fixture'), \
                    patch.object(workflow, 'Reporter', return_value=NoFactsReporter('non_patient')):
                parser.return_value.parse_args.return_value = args
                with contextlib.redirect_stdout(stdout), self.assertRaises(SystemExit) as stopped:
                    workflow.main()
            self.assertEqual(stopped.exception.code, 1)
            emitted = json.loads(stdout.getvalue())
            self.assertEqual(emitted['status'], 'incomplete')
            self.assertEqual(emitted['error_code'], workflow.NoSupportedClinicalFacts.code)
            self.assertEqual(emitted['reason'], workflow.NoSupportedClinicalFacts.detail)

    def test_unrelated_value_error_does_not_inherit_no_facts_explanation(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.arguments(Path(directory))
            with patch.object(workflow, 'Platform'), patch.object(workflow, 'Reporter') as reporter:
                reporter.return_value.complete.side_effect = ValueError('unrelated private fixture failure')
                with self.assertRaises(ValueError):
                    workflow.run(args, key='offline-fixture')
            manifest = workflow.read(args.output/'run.json')
            self.assertEqual(manifest['error'], 'ValueError')
            self.assertNotIn('error_code', manifest)
            self.assertNotIn('error_detail', manifest)

    def test_worker_static_public_copy_matches_recognized_python_outcome(self):
        worker = Path(__file__).resolve().parents[3]/'demos/worker.cjs'
        source = worker.read_text()
        self.assertEqual(re.search(r"const NO_FACTS_CODE = '([^']+)';", source)[1],
                         workflow.NoSupportedClinicalFacts.code)
        self.assertEqual(re.search(r"const NO_FACTS_DETAIL = '([^']+)';", source)[1],
                         workflow.NoSupportedClinicalFacts.detail)


if __name__ == '__main__':
    unittest.main()
