import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('report_assembly', Path(__file__).with_name('report-assembly.py'))
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def test_assembly_preserves_numeric_strings_unicode_and_actual_column_width(tmp_path):
    markdown = tmp_path / 'method.md'; markdown.write_bytes('Méthode — Å\r\nOriginal paragraph.\r\n'.encode())
    csv = tmp_path / 'rows.csv'; csv.write_text('run,top_rank,best_overlap,notes\na,1,false,"two|pipes\nand newline"\nb,1,true,1.21090000000\n')
    report, provenance = assembly.assemble('Research result', [
        {'title': 'Method', 'format': 'markdown', 'file': str(markdown)},
        {'title': 'Exact table', 'format': 'csv', 'file': str(csv)}])
    assert markdown.read_bytes() in report
    assert b'| a | 1 | false | two\\|pipes<br>and newline |' in report
    assert b'1.21090000000' in report
    assert provenance['sections'][1]['column_count'] == 4
    assert provenance['sections'][1]['row_count'] == 2
    assert provenance['report_size_bytes'] == len(report) != len(report.decode())
    assert provenance['sections'][0]['source_sha256'] == assembly.digest(markdown.read_bytes())
    assert not provenance['scientific_claims_validated']
    assert not provenance['inference_submitted']


def test_malformed_table_is_not_relabelled_as_success(tmp_path):
    source = tmp_path / 'broken.csv'; source.write_text('run,top_rank,best_overlap\nrun-a,false\n')
    with pytest.raises(ValueError, match='row width'):
        assembly.assemble('Report', [{'title': 'Rows', 'format': 'csv', 'file': str(source)}])
