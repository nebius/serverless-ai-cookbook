from copy import deepcopy
import json
import os

import pytest

from clinical_asr.balanced import calibrate, parse_fractions, prepare_inputs


def test_sampling_is_opt_in_and_fresh_english_only():
    assert parse_fractions(None,model_family='nemotron35') is None
    value='{"short":0.5,"long":0.5}'
    assert parse_fractions(value,model_family='english_specialist')=={'short':.5,'long':.5}
    for family,pointer in [('nemotron35',None),('english_specialist','any-resume')]:
        with pytest.raises(ValueError,match='fresh_english'):
            parse_fractions(value,model_family=family,resume_pointer=pointer)


@pytest.mark.parametrize('value',['[]','{}','{"one":1}','{"one":true,"two":0}',
    '{"one":NaN,"two":0.5}','{"../path":0.5,"other":0.5}'])
def test_bad_fraction_cli_values_fail(value):
    with pytest.raises(ValueError):parse_fractions(value,model_family='english_specialist')


def rows():
    return [{'id': name, 'training_corpus': name, 'split': 'train', 'duration': duration,
        'text': 'A reference with no changes.', 'target_lang': 'en-US', 'audio_sha256': 'a'*64,
        'audio_filepath': '/unchanged/' + name + '.wav'}
        for name,duration in [('short',1),('medium',2),('long',4)]]


def test_inverse_duration_weights():
    _, stats = calibrate(rows(), dict.fromkeys(['short','medium','long'],1/3))
    probabilities = [stats[key]['cut_selection_probability'] for key in ['short','medium','long']]
    assert probabilities == pytest.approx([4/7,2/7,1/7])
    shares = [stats[key]['mean_duration_seconds']*stats[key]['cut_selection_probability'] for key in stats]
    assert len(set(round(value,12) for value in shares)) == 1


@pytest.mark.parametrize('change', ['test_split','duplicate','nan_duration','missing_hash','unknown_corpus'])
def test_invalid_training_sources_fail(change):
    data=rows()
    if change=='test_split':data[0]['split']='test'
    if change=='duplicate':data.append(deepcopy(data[0]))
    if change=='nan_duration':data[0]['duration']=float('nan')
    if change=='missing_hash':del data[0]['audio_sha256']
    if change=='unknown_corpus':data[0]['training_corpus']='other'
    with pytest.raises(ValueError):calibrate(data,dict.fromkeys(['short','medium','long'],1/3))


@pytest.mark.parametrize('fractions',[{'short':1},{'short':-.1,'medium':.6,'long':.5},
    {'short':.2,'medium':.2,'long':.2},{'short':float('nan'),'medium':.5,'long':.5}])
def test_invalid_target_fractions_fail(fractions):
    with pytest.raises(ValueError):calibrate(rows(),fractions)


def test_exact_references_and_renewable_configuration(tmp_path):
    original=rows()
    cfg,receipt=prepare_inputs(original,dict.fromkeys(['short','medium','long'],1/3),tmp_path/'balanced',seed=19)
    reread=[json.loads(line) for item in receipt['manifests'] for line in open(item['path'])]
    assert sorted(reread,key=lambda x:x['id'])==sorted(original,key=lambda x:x['id'])
    assert cfg['force_finite'] is False and cfg['metadata_only'] is False and cfg['max_open_streams'] is None
    assert cfg['manifest_filepath'] is None and cfg['reweight_temperature']==1
    assert receipt['sampling_probability_is_duration_guarantee'] is False


@pytest.mark.skipif(os.getenv('RUN_NATIVE_NEMO_TESTS')!='1',reason='pinned upstream template required')
def test_actual_training_template_cap_and_validation_unchanged(tmp_path):
    from types import SimpleNamespace
    from omegaconf import OmegaConf
    from clinical_asr.train import dataset_configs
    args=SimpleNamespace(model_family='english_specialist',train_manifest='/train.jsonl',
                         dev_manifest='/dev.jsonl',seed=20260926,batch_duration=120)
    cfg,_=prepare_inputs(rows(),dict.fromkeys(['short','medium','long'],1/3),tmp_path/'native',seed=args.seed)
    base_train,base_dev=dataset_configs(OmegaConf.create({'sample_rate':16000}),args)
    train,dev=dataset_configs(OmegaConf.create({'sample_rate':16000}),args,sampling_override=cfg)
    assert train.batch_size==base_train.batch_size==16
    assert train.batch_duration==base_train.batch_duration==120
    assert train.max_duration==base_train.max_duration==30
    assert OmegaConf.to_container(base_dev,resolve=True)==OmegaConf.to_container(dev,resolve=True)
    assert 'input_cfg' not in base_train and len(train.input_cfg)==3


@pytest.mark.skipif(os.getenv('RUN_NATIVE_NEMO_TESTS')!='1',reason='requires exact pinned NeMo image; CPU only')
@pytest.mark.parametrize('bucketed',[False,True])
@pytest.mark.parametrize('heterogeneous',[False,True])
def test_actual_pinned_nemo_renewable_sampler(tmp_path,bucketed,heterogeneous):
    from collections import Counter
    from itertools import islice
    import wave
    from omegaconf import OmegaConf
    from nemo.collections.common.data.lhotse.dataloader import get_lhotse_dataloader_from_config
    from nemo.collections.common.data.lhotse.cutset import read_cutset_from_config

    data=rows()
    if heterogeneous:
        data=[dict(row,id=f'{row["id"]}-{index}',duration=row['duration']*factor)
              for row in data for index,factor in enumerate([.5,1,1.5])]
    for row in data:
        path=tmp_path/(row['id']+'.wav')
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
            wav.writeframes(b'\0\0'*int(row['duration']*16000))
        row['audio_filepath']=str(path)
    cfg,_=prepare_inputs(data,dict.fromkeys(['short','medium','long'],1/3),tmp_path/'native',seed=20260926)
    cfg.update(sample_rate=16000,use_lhotse=True,is_tarred=False,num_workers=0,
        pin_memory=False,text_field='text',lang_field='target_lang',shuffle=True,
        batch_duration=120,use_bucketing=bucketed,num_buckets=10,min_duration=.5,max_duration=30)
    class MetadataOnlyDataset:
        def __getitem__(self,cuts):return cuts
    raw,_=read_cutset_from_config(OmegaConf.create(cfg))
    raw_counts=Counter(cut.training_corpus for cut in islice(raw,30000))
    print('RAW_MUX_COUNTS',json.dumps(dict(raw_counts)))
    def sampled():
        loader=get_lhotse_dataloader_from_config(OmegaConf.create(cfg),0,1,MetadataOnlyDataset())
        totals=Counter();counts=Counter();order=[]
        for batch in islice(loader,300):
            for cut in batch:
                name=cut.training_corpus
                totals[name]+=cut.duration;counts[name]+=1
                order.append((name,cut.id,cut.duration))
        return totals,counts,order
    totals,counts,order=sampled()
    print('NATIVE_SAMPLE',json.dumps({'seconds':dict(totals),'cuts':dict(counts),
        'fractions':{key:value/sum(totals.values()) for key,value in totals.items()}}))
    assert min(counts.values())>100 # finite three-row inputs actually repeat
    assert len(order)>5000
    assert all(abs(value/sum(totals.values())-1/3)<.06 for value in totals.values()),dict(totals)
    assert sampled()==(totals,counts,order) # exact pinned seed reproducibility, no GPU
