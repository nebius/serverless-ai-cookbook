"""Pass the exact native contract without editing scientific input or hiding rejection."""
import argparse
import asyncio
import copy
import json

import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow
import test_scientific_study as study_tests
from test_scientific_workflow import workflow

mounted = study_tests.mounted


def plan(root, selected=True):
    source = root / 'native.json'
    source.write_text('{"unchanged_input":true}\n')
    step = {'id':'native','kind':'native','model':'example-model','input':str(source),
            'idempotency_key':'native-selector-test'}
    if selected:
        step['tool_name'] = 'example_model_specific_native'
    return {'schema':study.SCHEMA,'title':'Exact native selector','steps':[step],
        'deliverables':[{'name':'result.json','role':'report','source':{'step':'native','file':'result.json'}}]}


@pytest.mark.parametrize('selected',[False,True])
def test_exact_selector_reaches_native_client_and_is_in_immutable_plan(mounted, selected):
    value = plan(mounted, selected)
    assert study.validate(value)
    started = study.submit(value, mounted/'output')
    saved = json.loads((study.directory(started['id'])/'plan.json').read_bytes())
    assert saved == value
    frozen = copy.deepcopy(value)
    calls=[]
    async def execute(args):
        calls.append(vars(args).copy())
        assert getattr(args,'tool',None) == value['steps'][0].get('tool_name')
        assert args.input.read_text() == '{"unchanged_input":true}\n'
        return {'state':'succeeded','operation_id':'retained-test-operation'}
    transported={'schema':'scientific-workflow/v1','steps':[
        {**value['steps'][0],'output':str(mounted/'operation')}]}
    result=asyncio.run(workflow.run(transported,mounted/'workflow',native_run_step=execute))
    assert result['state']=='completed' and len(calls)==1 and value==frozen
    transported['steps'][0]['tool_name']='other_tool'
    with pytest.raises(ValueError,match='plan changed'):
        asyncio.run(workflow.run(transported,mounted/'workflow',native_run_step=execute))
    assert len(calls)==1


@pytest.mark.parametrize('selector',[None,False,4,'',{}])
def test_invalid_selector_rejected_before_study_admission(mounted,selector):
    value=plan(mounted)
    value['steps'][0]['tool_name']=selector
    with pytest.raises(ValueError):
        study.submit(value,mounted/'output')
    assert study.list_studies()==[]


def test_discovery_exposes_optional_exact_tool_name():
    schema=describe_workflow(['native'])['phases']['native']['step_schema']
    assert 'tool_name' in schema['properties'] and 'tool_name' not in schema['required']
    assert 'uniquely matching native schema' in schema['properties']['tool_name']['description']


@pytest.mark.parametrize('kind',['local_input_validation','local_contract_selection'])
def test_saved_no_admission_rejection_survives_exceptiongroup_without_sensitive_text(tmp_path,kind):
    args=argparse.Namespace(output_dir=tmp_path)
    async def failed(_):
        workflow.save(tmp_path/'receipt.json',{'state':'input_rejected','last_rejection':{
            'type':kind,'durable_admission':False,'validator':'required',
            'input_pointer':'/','schema_pointer':'/required','code':'ambiguous_native_contract',
            'candidate_tools':['example_specific','example_generic'],
            'message':'sensitive raw input must not be exposed','arguments':{'secret':'do-not-print'}}})
        raise ExceptionGroup('sensitive transport text',[ValueError('sensitive raw input')])
    with pytest.raises(workflow.NativePreflightRejected) as error:
        asyncio.run(workflow.run_native_step(args,failed))
    assert kind in str(error.value) and 'schema_pointer' in str(error.value)
    assert 'example_specific' in str(error.value) and 'no retry' in str(error.value)
    assert 'sensitive' not in str(error.value) and 'do-not-print' not in str(error.value)


@pytest.mark.parametrize('override',[{'state':'admission_unknown'}, {'operation_id':'known-operation'},
    {'last_rejection':{'type':'unrecognized','durable_admission':False}},
    {'last_rejection':{'type':'local_input_validation','durable_admission':True}}])
def test_ambiguous_or_unrecognized_errors_remain_unchanged(tmp_path,override):
    async def failed(_):
        workflow.save(tmp_path/'receipt.json',{'state':'input_rejected',
            'last_rejection':{'type':'local_input_validation','durable_admission':False},**override})
        raise ExceptionGroup('original retained failure',[ValueError('original')])
    with pytest.raises(ExceptionGroup,match='original retained failure'):
        asyncio.run(workflow.run_native_step(argparse.Namespace(output_dir=tmp_path),failed))
