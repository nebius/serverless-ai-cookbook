"""Saved-media integrity regressions; no inference or physical-quality claim."""
import asyncio
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import scientific_study as study
from scientific_study_schema import describe_workflow, known_output_files

spec = importlib.util.spec_from_file_location('robotics_analysis', Path(__file__).with_name('robotics-analysis.py'))
robotics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(robotics)


def video(path, color='red'):
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=16x16:r=4',
                    '-frames:v','4','-c:v','libx264','-pix_fmt','yuv420p',str(path)], check=True)


def dataset(path, selected_color='red', timestamp=0.0):
    (path/'meta/episodes').mkdir(parents=True)
    (path/'data').mkdir()
    cameras=['observation.images.high','observation.images.wrist']
    info={'fps':4,'features':{key:{'dtype':'video'} for key in cameras},
          'video_path':'videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4'}
    (path/'meta/info.json').write_text(json.dumps(info))
    data=pa.table({'index':pa.array([0,1,2,3],type=pa.int64()),
                   'timestamp':pa.array([timestamp,.25,.5,.75],type=pa.float32()),
                   'done':pa.array([False,False,False,True]),
                   'action':pa.array([[1.,2.]]*4,type=pa.list_(pa.float32(),2))})
    pq.write_table(data,path/'data/file.parquet')
    episode={'episode_index':[0],'length':[4],
             'videos/observation.images.high/from_timestamp':[0.],
             'videos/observation.images.high/to_timestamp':[1.],
             'videos/observation.images.wrist/from_timestamp':[0.],
             'videos/observation.images.wrist/to_timestamp':[1.]}
    for camera in cameras:
        episode[f'videos/{camera}/chunk_index']=[0]
        episode[f'videos/{camera}/file_index']=[0]
    pq.write_table(pa.table(episode),path/'meta/episodes/file.parquet')
    for camera in cameras:
        video(path/'videos'/camera/'chunk-000/file-000.mp4',selected_color if camera.endswith('high') else 'green')


def bundle(source,target):
    raw=target.with_suffix('.tar')
    with tarfile.open(raw,'w') as archive:
        archive.add(source,arcname='dataset')
    with target.open('wb') as stream:
        subprocess.run(['zstd','-q','-c',str(raw)],stdout=stream,check=True)


@pytest.fixture
def saved(tmp_path):
    source,generated=tmp_path/'source',tmp_path/'generated'
    dataset(source);dataset(generated,'blue')
    original=tmp_path/'source.tar.zst';bundle(source,original)
    operation=tmp_path/'operation';operation.mkdir()
    native=operation/'result.mp4';video(native,'blue')
    metadata={'schema':'scientific-native-file/v1','content_type':'video/mp4',
              'file':{'path':str(native),**robotics.identity(native)}}
    (operation/'result.json').write_text(json.dumps(metadata))
    returned=operation/'output-00.artifact';bundle(generated,returned)
    manifest={'schema':'fs2-serve.nebius.ai/scientific-artifact-manifest/v1','entries':[
        {'name':'variant-00','semantic_type':'lerobot-v3-augmented-bundle/v1','artifact':{
            **robotics.identity(returned),'compression':'zstd','media_type':'application/x-tar'}}]}
    (operation/'output-manifest.json').write_text(json.dumps(manifest))
    return {'source_video':str(source/'videos/observation.images.high/chunk-000/file-000.mp4'),
            'source_archive':str(original),'native_result':str(operation/'result.json'),
            'manifest_file':str(operation/'output-manifest.json'),
            'selected_cameras':['observation.images.high']}


def test_saved_manifest_media_and_all_values_are_measured(saved,tmp_path):
    result=robotics.analyze(saved,tmp_path/'report')
    data=result['dataset']
    assert data['source_rows']==4 and data['scalar_values']==20
    assert data['all_nonvideo_values_and_types_exact']
    assert data['episode_identities_and_timestamps_equal']
    assert data['all_unselected_media_bytes_and_pixels_equal']
    assert next(row for row in data['media'] if row['selected'])['changed_frames']==4
    assert not result['geometry_preservation_verified']
    assert not result['physical_action_alignment_verified']
    assert (tmp_path/'report/native-output.mp4').read_bytes()==(Path(saved['native_result']).parent/'result.mp4').read_bytes()
    assert set(p.name for p in (tmp_path/'report').iterdir())=={
        'metrics.json','report.md','native-output.mp4','augmented-dataset.tar.zst','completion-manifest.json'}


def test_changed_recorded_values_are_not_reported_exact(tmp_path):
    source,generated=tmp_path/'source',tmp_path/'generated'
    dataset(source);dataset(generated,timestamp=.125)
    result=robotics.compare_dataset(source,generated,['observation.images.high'])
    assert not result['all_nonvideo_values_and_types_exact']
    assert not next(row for row in result['nonvideo_fields'] if row['field']=='timestamp')['values_equal']


def test_unchanged_camera_can_move_to_declared_new_shard(tmp_path):
    source,generated=tmp_path/'source',tmp_path/'generated'
    dataset(source);dataset(generated,'blue')
    camera='observation.images.wrist'
    destination=generated/'videos'/camera/'chunk-001/file-000.mp4'
    destination.parent.mkdir()
    (generated/'videos'/camera/'chunk-000/file-000.mp4').rename(destination)
    path=generated/'meta/episodes/file.parquet'
    rows=pq.read_table(path).to_pylist()
    rows[0][f'videos/{camera}/chunk_index']=1
    pq.write_table(pa.Table.from_pylist(rows),path)
    result=robotics.compare_dataset(source,generated,['observation.images.high'])
    assert result['all_unselected_media_bytes_and_pixels_equal']
    assert result['episode_identities_and_timestamps_equal']
    wrist=next(row for row in result['media'] if not row['selected'])
    assert wrist['source_file']!=wrist['file'] and wrist['bytes_equal']


def test_manifest_hash_mismatch_cannot_publish_result(saved,tmp_path):
    (Path(saved['manifest_file']).parent/'output-00.artifact').write_bytes(b'not the declared bundle')
    with pytest.raises(RuntimeError,match='differ'):
        robotics.analyze(saved,tmp_path/'failed')
    assert not (tmp_path/'failed/report.md').exists()


def test_missing_native_media_contract_is_not_a_null_comparison(saved,tmp_path):
    Path(saved['native_result']).write_text('{}')
    with pytest.raises(ValueError,match='native-file'):
        robotics.analyze(saved,tmp_path/'failed')


def test_whole_study_runs_saved_analysis_and_publishes_media(saved,tmp_path,monkeypatch):
    monkeypatch.setenv('SCIENTIFIC_WORKSPACE',str(tmp_path))
    monkeypatch.setenv('SCIENTIFIC_MODELS_MCP_URL','https://platform.test/mcp')
    monkeypatch.setenv('SCIENTIFIC_MODELS_API_KEY','test-only')
    monkeypatch.setenv('SEED_DEFAULT_USER_EMAIL','robotics@example.test')
    monkeypatch.setenv('SCIENTIFIC_STUDY_OWNER_MODE','first-instance')
    monkeypatch.setattr(study,'workflow_module',lambda:pytest.fail('Saved analysis must never submit inference'))
    step={'id':'compare','kind':'analysis','method':'robotics-analysis','arguments':saved}
    plan={'schema':study.SCHEMA,'title':'Recorded evidence','steps':[step],
          'deliverables':[{'name':name,'role':'report' if name=='report.md' else 'data',
                           'source':{'step':'compare','file':name}} for name in
                          ['report.md','metrics.json','native-output.mp4','augmented-dataset.tar.zst']]}
    accepted=study.submit(plan,tmp_path/'complete')
    for _ in range(2):
        final=asyncio.run(study.advance(accepted['id']))
    assert final['state']=='completed',final
    published=final['steps']['compare']['files']
    contract=describe_workflow(['robotics-analysis'])['phases']['robotics-analysis']
    assert set(contract['always_on_success'])<=published.keys()
    assert set(published)==known_output_files(step)
    assert len(final['artifacts'])==4


def test_archive_invalid_paths_are_not_extracted(tmp_path):
    raw=tmp_path/'bad.tar'
    with tarfile.open(raw,'w') as archive:
        archive.addfile(tarfile.TarInfo('../invalid'))
    with pytest.raises(ValueError,match='relative regular'):
        robotics.unpack_bundle(raw,tmp_path/'unpacked')


def test_sequence_phase_has_explicit_operation_provenance_and_future_references():
    args={'reference_file':'/workspace/source.fa','cases':[{'id':'one','start_zero_based':0,
        'input_file':'/workspace/input.json','result_file':{'step':'generate','file':'result.json'},
        'operation_file':{'step':'generate','file':'operation.json'}}]}
    phase={'id':'compare','kind':'analysis','method':'evo2-continuation','arguments':args}
    study.validate_local_arguments('evo2-continuation',args)
    assert study.input_references(phase)==['/workspace/source.fa','/workspace/input.json',
        {'step':'generate','file':'result.json'},{'step':'generate','file':'operation.json'}]
    assert 'report.md' in known_output_files(phase)
