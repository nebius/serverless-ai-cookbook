"""The retained v56 C-versus-A/B selection mismatch must remain visible."""
import copy
import csv
import json

from test_design_artifact_analysis import module


def retained_shape():
    return {'schema':'scientific-ai/protein-design-artifact-analysis/v1',
        'verified_artifacts':2,'coordinate_outputs':1,'linked_designs':None,
        'requested_constraints':{'binder_chain':'C','binder_length_min':60,'binder_length_max':80},
        'explicit_binder_unique_sequences':0,'limitations':['No biological efficacy validation.'],
        'structures':[{'artifact_name':'structure.pdl1-face','member':None,
            'role':'unassigned_without_explicit_provenance','target_sequence_exact_unique':True,
            'target_sequence_matching_chains':['B'],'geometry':{'constraint_pass':False,
                'candidate_binder_chains':[], 'chains':[
                    {'chain':name,'residues':count,'sequence_sha256':name*64,
                     'adjacent_ca_median_angstrom':3.8,'ca_step_outside_2_5_to_4_5_fraction':0.0,
                     'within_requested_length':within} for name,count,within in [('A',60,True),('B',127,False)]]}}],
        'metadata_unmodified_values':[{'artifact_name':'ranking.pdl1-face','content':{'csv_rows':[
            {'design_to_target_iptm':'0.41095','design_ptm':'0.80473','filter_rmsd':'1.18888',
             'pass_filters':'True','quality_score':'1.0','id':'pdl1-face_06'}]}}]}


def test_actual_missing_requested_chain_visible_in_report_and_inventory_without_remap(tmp_path):
    value=retained_shape()
    before=copy.deepcopy(value)
    module.publish(value,tmp_path)
    report=(tmp_path/'report.md').read_text()
    assert 'Requested binder chain C absent; no remapping was performed' in report
    assert '["A", "B"]' in report and '| false | true |' in report
    assert 'analysis-selection mismatch, not a platform admission failure' in report
    rows=list(csv.DictReader((tmp_path/'inventory.csv').open()))
    assert len(rows)==2 and {row['chain'] for row in rows}=={'A','B'}
    assert all(row['constraint_pass']=='False' and row['requested_binder_chain']=='C' for row in rows)
    assert all('chain C absent' in row['constraint_reason'] for row in rows)
    assert json.loads((tmp_path/'measurements.json').read_text())==before==value


def test_exact_score_values_no_false_diversity_or_rejection_counts(tmp_path):
    module.publish(retained_shape(),tmp_path)
    report=(tmp_path/'report.md').read_text()
    assert '"design_to_target_iptm" | ["0.41095"]' in report
    assert '"pass_filters" | ["True"]' in report
    assert 'zero with an absent selected chain does not measure model-wide diversity' in report
    assert 'Missing rejection rows/reasons are unavailable, not zero' in report
    assert 'not the analysis constraint verdict' in report


def test_unknown_selection_and_no_scores_remain_explicit(tmp_path):
    value=retained_shape()
    value['requested_constraints']={}
    value['explicit_binder_unique_sequences']=None
    value['metadata_unmodified_values']=[]
    value['structures'][0]['geometry']['constraint_pass']=None
    value['structures'][0]['target_sequence_exact_unique']=None
    module.publish(value,tmp_path)
    report=(tmp_path/'report.md').read_text()
    assert 'Requested binder chain: null' in report
    assert 'No confidence inferred' in report and '| null | null | null |' in report
    assert 'Constraint verdict unavailable; no success inferred' in report


def test_provenance_linked_diversity_does_not_double_count_raw_and_refolded(tmp_path):
    value=retained_shape()
    value['linked_designs']={'design_count':3,'generated_geometry_pass_count':2,
        'self_refolded_geometry_pass_count':3,'predictions':[{'sequence_sha256':s} for s in ['one','two','one']]}
    module.publish(value,tmp_path)
    report=(tmp_path/'report.md').read_text()
    assert '2 unique / 3 design rows' in report
    assert 'raw-geometry screen: 2/3; refold screen: 3/3' in report
