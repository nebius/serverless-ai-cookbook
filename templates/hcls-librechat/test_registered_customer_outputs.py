"""Only exact producer-selected customer files supplement declared deliverables."""
import copy
import pytest

import scientific_study as study
import test_scientific_study as study_tests

mounted = study_tests.mounted


def fixture(root):
    files = {}
    for name, content in {'report.md': 'Existing draft, not clinical validation.\n',
                          'transcript.txt': 'Unchanged uncertain words.\n',
                          'outcome.md': 'Measured outcome and explicit limitations.\n',
                          'private-state.json': '{"internal":true}\n'}.items():
        path = root / name
        path.write_text(content)
        files[name] = study.measure(path)
    record = {'steps': {'clinical-en': {'state': 'completed', 'files': files,
        'customer_artifacts': {name: {**files[name], 'role': role}
                               for name, role in [('report.md','report'), ('transcript.txt','data')]}}}}
    plan = {'steps': [{'id': 'clinical-en', 'kind': 'clinical'}], 'deliverables': [
        {'name': 'summary.md', 'role': 'report', 'source': {'step': 'clinical-en', 'file': 'outcome.md'}}]}
    return plan, record


def test_selected_actual_outputs_are_discoverable_without_llm_aliases(mounted):
    plan, record = fixture(mounted)
    original = copy.deepcopy(record)
    result = study.publication_artifacts(plan, record)
    assert [item['name'] for item in result] == [
        'summary.md', 'steps/clinical-en/report.md', 'steps/clinical-en/transcript.txt']
    assert [item['path'] for item in result] == [str(mounted / name) for name in (
        'outcome.md','report.md','transcript.txt')]
    assert all(item['sha256'] == study.measure(study.Path(item['path']))['sha256'] for item in result)
    assert record == original
    assert 'private-state.json' not in str(result)


def test_explicit_missing_promise_not_replaced_by_registered_files(mounted):
    plan, record = fixture(mounted)
    plan['deliverables'][0]['source']['file'] = 'invented.md'
    with pytest.raises(ValueError, match='not verified and complete'):
        study.publication_artifacts(plan, record)


def test_explicit_selected_same_path_is_not_duplicated(mounted):
    plan, record = fixture(mounted)
    plan['deliverables'].append({'name': 'my-draft.md', 'role': 'report',
                                'source': {'step':'clinical-en','file':'report.md'}})
    result = study.publication_artifacts(plan, record)
    assert len(result) == 3 and sum(item['path'] == str(mounted / 'report.md') for item in result) == 1
    assert result[1]['name'] == 'my-draft.md'


@pytest.mark.parametrize('defect', ['state','path','size_bytes','sha256','role','not_registered'])
def test_unverified_or_substituted_selection_fails_closed(mounted, defect):
    plan, record = fixture(mounted)
    step = record['steps']['clinical-en']
    if defect == 'state':
        step['state'] = 'failed'
        plan['deliverables'][0]['source'] = str(mounted / 'outcome.md')
    elif defect == 'not_registered':
        del step['files']['report.md']
    else:
        step['customer_artifacts']['report.md'][defect] = 'different'
    with pytest.raises(ValueError, match='exact verified completed-step file'):
        study.publication_artifacts(plan, record)


def test_changed_bytes_do_not_publish(mounted):
    plan, record = fixture(mounted)
    (mounted / 'report.md').write_text('Changed after verification.')
    with pytest.raises(RuntimeError, match='differ'):
        study.publication_artifacts(plan, record)


def test_duplicate_name_different_path_fails_instead_of_guessing_alias(mounted):
    plan, record = fixture(mounted)
    plan['deliverables'][0]['name'] = 'steps/clinical-en/report.md'
    with pytest.raises(ValueError, match='names conflict'):
        study.publication_artifacts(plan, record)


def test_no_registration_does_not_publish_whole_step_directory(mounted):
    plan, record = fixture(mounted)
    del record['steps']['clinical-en']['customer_artifacts']
    assert len(study.publication_artifacts(plan, record)) == 1
