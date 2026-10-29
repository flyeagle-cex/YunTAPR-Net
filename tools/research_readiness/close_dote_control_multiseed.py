"""Read-only seal of the two new ZERO_DOTE controls and saved three-seed stats.

Only new Train/Dev receipts, ledgers and two E9 weight hashes are inspected.
No model import, checkpoint deserialization, inference or weather payload read.
"""
import argparse
import copy
import json
import re
import statistics
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from close_static_pair import canonical, close, load, query, sha, stamp, values

COMMIT='8a4668377dbd40013245b54550c0963d10c286fb'
PROPOSAL='a53d38293e9b783b787e84baca7c9c0f1502cbae051828e4578a24051733a6c6'
PUBLIC=Path('docs/research_readiness/20261025/evidence')
CONTROL='B7_ZERO_DOTE'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--frozen-code',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert not args.output.exists(), 'Never overwrite a closeout'
    root=Path(__file__).resolve().parents[2]
    private=load(args.private);out=Path(private['output_root'])
    p=load(root/PUBLIC/'dote_control_multiseed_proposal_20261029.json')
    original=load(root/PUBLIC/'dote_control_completion_20261029.json')
    real=load(root/PUBLIC/'b7_b8_three_seed_completion_20261029.json')
    assert canonical({k:v for k,v in p.items() if k!='proposal_sha256'})==private['proposal_sha256']==PROPOSAL
    assert canonical({k:v for k,v in private.items() if k!='proposal_sha256'})==p['private_locator_sha256']
    assert subprocess.check_output(['git','-C',str(args.frozen_code),'rev-parse','HEAD'],text=True).strip()==COMMIT
    assert not subprocess.check_output(['git','-C',str(args.frozen_code),'status','--porcelain'],text=True).strip()
    assert all(sha(args.frozen_code/n)==h for n,h in p['code_sha256'].items())
    assert all(sha(root/n)==h for n,h in p['inherited_evidence_sha256'].items())
    binding=load(out/'authorization_binding.json');a=binding['approval']
    assert a['approved_by_researcher'] is True and a['code_commit']==COMMIT and a['proposal_sha256']==PROPOSAL
    assert a['tasks']==p['tasks'] and a['scientific_choices']==p['scientific_choices'] and a['budget']==p['budget']
    assert a['approved_replay_updates']==0 and binding['control']=='ZERO_NUMERIC_RETAIN_REAL_MASKS_TWO_SEEDS'
    assert not (out/'failure.json').exists()
    assert load(out/'completion.json')==dict(status='COMPLETE_TWO_CONTROLS_THREE_SEED_DOTE_SUMMARY',updates=8640,
        logical_source_bytes=955143907680,logical_source_files=285626,code_commit=COMMIT,proposal_sha256=PROPOSAL,replay=0)
    raw_summary=load(out/'three_seed_dote_control_summary.json')
    assert raw_summary['difference']=='B7_REAL_MINUS_B7_ZERO_DOTE' and raw_summary['seeds']==[2029,2030,2031]
    assert raw_summary['descriptive_only'] and raw_summary['significance']=='NOT_CLAIMED'
    sources={}
    def record(path,alias):
        sources[alias]=dict(sha256=sha(path),bytes=path.stat().st_size,visibility='LOCAL_ONLY')
    for name in ('authorization_binding.json','completion.json','source_admission.json','three_seed_dote_control_summary.json'):
        record(out/name,'PACKAGE/'+name)
    # Reuse all old formal results; this one small metadata read binds unchanged
    # event/partition definitions to the new Dev receipts, not a source audit.
    refpath=Path(private['real_B7']['2030'])/'B7_development_09.json'
    assert sha(refpath)==real['sources']['B7_s2030/development_09.json']['sha256']
    refmeta=load(refpath);record(refpath,'INHERITED_REAL_B7_s2030/development_09.json')
    groups={'2029':original['endpoint_groups']}
    tails={'2029':original['tail_diagnostics']}
    tasks=[];epochs=[];initializations={}
    for index,seed in enumerate((2030,2031),1):
        folder=out/f'B7_s{seed}';alias=f'{CONTROL}_s{seed}'
        assert not (folder/'failure.json').exists()
        task=load(folder/'completion.json')
        assert load(out/f'{alias}_complete.json')==dict(task,control_id=CONTROL)
        assert (task['status'],task['model'],task['seed'],task['epochs'],task['optimizer_updates'],task['replay'],task['code_commit'],task['endpoint'])==(
            'COMPLETE_TRAIN_AND_DEV_EVALUATION','B7',seed,9,4320,0,COMMIT,'FIXED_EPOCH_9_LAST')
        assert query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')==[('B7','RETURNED',4320,1,4320)]
        orders=load(folder/'paired_orders.json');initial=load(folder/'paired_initial_identity.json')
        for name,h in p['baseline_metadata_sha256'][str(seed)].items():assert sha(folder/name)==h
        assert initial==real['initializations'][f'B7_s{seed}']['initial']
        assert initial['B7']==p['seed_initialization'][str(seed)]['initialization']
        initializations[str(seed)]=dict(initial=initial,order_sha256=sha(folder/'paired_orders.json'),epoch_order_sha256={k:v['sha256'] for k,v in orders.items()})
        for name in ('completion.json','updates.sqlite','paired_orders.json','paired_initial_identity.json'):
            record(folder/name,alias+'/'+name)
        record(out/f'{alias}_complete.json',alias+'/control_completion.json')
        total=count=0
        for epoch in range(1,10):
            train=load(folder/f'B7_train_{epoch:02d}.json');dev=load(folder/f'B7_development_{epoch:02d}.json')
            tail=load(folder/f'B7_tail_{epoch:02d}.json');seal=load(folder/f'B7_LAST_epoch_{epoch:02d}.receipt.json')
            assert (train['scenes'],train['batches'],train['updates'],train['loss_arm'])==(959,480,epoch*480,'E0')
            assert train['train_order_sha256']==orders[str(epoch)]['sha256']==canonical(orders[str(epoch)]['ids'])
            assert seal==task['checkpoints'][epoch-1] and seal['code_commit']==COMMIT and seal['validation_receipt_sha256']==canonical(dev)
            assert seal['population_sha256']==p['data']['population_sha256'] and dev['source_identity']==p['data']
            for key in ('population_ids_sha256','partition_sha256','occurrence_event'):assert dev[key]==refmeta[key]
            reference=real['endpoint_groups'][str(seed)]['B7']
            assert set(dev['groups'])==set(reference)
            for g,item in dev['groups'].items():
                assert item['ids_sha']==reference[g]['ids_sha256']
                assert all(item['summary'][k]==reference[g]['summary'][k] for k in ('scenes','n_valid','n_rain'))
            s=dev['groups']['all']['summary']
            assert (s['scenes'],s['n_valid'],s['n_rain'])==(963,3303090,407820)
            assert len(s['tau'])==32 and s['tau'][-1]==.984375
            close(s['brier_sum']/s['n_valid'],s['brier']);close(s['s_qr']/s['n_rain'],s['conditional_pinball'])
            close(s['covered'][-1]/s['n_rain'],s['coverage'][-1])
            assert len(tail['scene_sufficient_statistics'])==963 and tail['nominal_q32']==.984375
            assert sum(x['n_rain'] for x in tail['strata'])==s['n_rain']
            assert sum(x['q32_covered'] for x in tail['strata'])==s['covered'][-1]
            close(sum(x['conditional_pinball']*x['n_rain'] for x in tail['strata'])/s['n_rain'],s['conditional_pinball'])
            bins=tail['elevation_diagnostics']['bins']
            assert sum(x['n_valid'] for x in bins.values())==s['n_valid'] and sum(x['n_rain'] for x in bins.values())==s['n_rain']
            close(sum(x['brier_sum'] for x in bins.values()),s['brier_sum'])
            epochs.append(dict(model=CONTROL,seed=seed,epoch=epoch,train=train,development=s,checkpoint=seal,elevation_diagnostics=tail['elevation_diagnostics']))
            for name in ('train','development','tail'):record(folder/f'B7_{name}_{epoch:02d}.json',f'{alias}/{name}_{epoch:02d}.json')
            record(folder/f'B7_LAST_epoch_{epoch:02d}.receipt.json',f'{alias}/LAST_epoch_{epoch:02d}.receipt.json')
            assert (folder/f'B7_LAST_epoch_{epoch:02d}.pt').stat().st_size>0
            for role in ('train','dev'):
                sub=folder/f'B7_{role}_reads_{epoch:02d}';receipt=load(sub/'pass_receipt.json');n=receipt['actual_reads']
                scope=p['source_scope_summary']['Train' if role=='train' else 'Development']
                assert not receipt['during_failure'] and receipt['source_manifest_sha256']==scope['source_manifest_sha256']
                assert n['opened_files']==receipt['expected_files']==scope['file_count']
                assert n['delivered_bytes']==n['reserved_bytes']==receipt['expected_bytes']==scope['bytes_per_pass']
                assert query(sub/'reads.sqlite','SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',n['opened_files'],n['delivered_bytes'],n['reserved_bytes'],0)]
                assert all(state=='COMPLETE' for state,_ in query(sub/'reads.sqlite','SELECT state,COUNT(*) FROM jobs GROUP BY state'))
                total+=n['delivered_bytes'];count+=n['opened_files']
                for name in ('pass_receipt.json','reads.sqlite'):record(sub/name,f'{alias}/{role}_{epoch:02d}/{name}')
            if epoch==9:
                groups[str(seed)]={'B7':reference,CONTROL:{g:dict(summary=x['summary'],ids_sha256=x['ids_sha'],exact_score_table_sha256=x['exact_score_table_sha256']) for g,x in dev['groups'].items()}}
                tails[str(seed)]={'B7':real['tail_diagnostics'][str(seed)]['B7'],CONTROL:{k:tail[k] for k in ('scope','nominal_q32','independent_event_count','strata','elevation_diagnostics')}}
        assert (total,count)==(task['logical_source_bytes'],task['logical_source_files'])==(477571641012,142812)
        static=out/f'{alias}_static_source.sqlite'
        assert query(static,'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',1,312828,312828,0)]
        assert query(static,'SELECT state,COUNT(*) FROM jobs GROUP BY state')==[('COMPLETE',1)]
        assert query(static,'SELECT sha256 FROM file_io')==[(p['static_source_sha256']['B7'],)]
        record(static,alias+'/static_source.sqlite');record(folder/'B7_LAST_epoch_09.pt',alias+'/LAST_epoch_09.pt')
        assert sources[alias+'/LAST_epoch_09.pt']['sha256']==seal['checkpoint_sha256']
        assert (task['total_logical_source_bytes'],task['total_logical_source_files'])==(477571953840,142813)
        elapsed=(folder/'completion.json').stat().st_mtime-(out/f'task_{index}_claim.json').stat().st_mtime
        assert 0<elapsed<=21600
        tasks.append(dict(model=CONTROL,seed=seed,status=task['status'],epochs=9,optimizer_updates=4320,replay_updates=0,
            code_commit=COMMIT,fixed_E9_sha256=seal['checkpoint_sha256'],source_bytes=477571953840,source_files=142813,
            completed_at=stamp(folder/'completion.json'),wall_seconds_mtime_proxy=elapsed,wall_seconds_cap=21600))
    def check_stats(ds,raw,metric):
        assert raw['by_seed']==ds
        close(statistics.mean(ds.values()),raw['mean']);close(statistics.stdev(ds.values()),raw['sample_sd'])
        assert raw['negative_seeds']==sum(x<0 for x in ds.values()) and raw['positive_seeds']==sum(x>0 for x in ds.values())
        if metric in ('brier','conditional_pinball','q32_absolute_error'):assert raw['improvement_seeds']==sum(x<0 for x in ds.values())
        if metric in ('auroc','average_precision'):assert raw['improvement_seeds']==sum(x>0 for x in ds.values())
    for group,metrics in raw_summary['groups'].items():
        for metric,result in metrics.items():
            ds={}
            for seed in ('2029','2030','2031'):
                pair={k:values(x[group]['summary']) for k,x in groups[seed].items()}
                assert pair==raw_summary['group_endpoints'][seed][group]
                ds[seed]=pair['B7'][metric]-pair[CONTROL][metric]
            check_stats(ds,result,metric)
        for metric in ('q32_coverage','q32_signed_bias'):
            assert metrics[metric]['improvement_seeds']==metrics['q32_absolute_error']['improvement_seeds']
    for section,items in raw_summary['tail_comparisons'].items():
        for key,metrics in items.items():
            for metric,result in metrics.items():
                ds={}
                for seed in ('2029','2030','2031'):
                    aa,bb=(tails[seed][k]['strata'][int(key)] if section=='strata' else tails[seed][k]['elevation_diagnostics']['bins'][key] for k in ('B7',CONTROL))
                    assert aa['n_rain']==bb['n_rain']
                    ds[seed]=aa[metric]-bb[metric]
                check_stats(ds,result,metric)
    summary=copy.deepcopy(raw_summary)
    # Reporting-only clarification of the generic saved helper's label. Values
    # and the original summary bytes remain unchanged; no new calibration target.
    for item in summary['tail_comparisons']['strata'].values():
        item['q32_coverage']['improvement_direction']='DESCRIPTIVE_OUTCOME_CONDITIONED_NO_PER_STRATUM_NOMINAL_TARGET'
    elapsed=(out/'completion.json').stat().st_mtime-(out/'authorization_binding.json').stat().st_mtime
    assert 0<elapsed<=43200
    result=dict(status='VERIFIED_COMPLETE_THREE_SEED_DOTE_NUMERIC_CONTROL_TRAIN_AND_DEV',verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
        completed_at=stamp(out/'completion.json'),training_commit=COMMIT,proposal_sha256=PROPOSAL,data_version=p['data'],protocol=p['protocol'],
        scientific_choices=p['scientific_choices'],endpoint='FIXED_EPOCH_9_LAST',tasks=tasks,epochs=epochs,endpoint_groups=groups,tail_diagnostics=tails,
        initializations=initializations,summary=summary,budget_closure=dict(optimizer_updates=8640,replay_updates=0,additional_retry=0,
        weather_source_bytes=955143282024,weather_source_files=285624,static_source_bytes=625656,static_source_files=2,
        total_source_bytes=955143907680,total_source_files=285626,wall_seconds_mtime_proxy=elapsed,wall_seconds_cap=43200,
        wall_definition='Completion minus authorization-binding file mtime; per-task completion minus claim; not GPU billing'),
        evaluation_script=original['evaluation_script'],evaluation_script_sha256=original['evaluation_script_sha256'],code_sha256=p['code_sha256'],sources=sources,
        inherited_evidence_sha256=p['inherited_evidence_sha256'],checks=dict(new_train_epochs=18,new_dev_epochs=18,new_weather_ledgers=36,new_static_ledgers=2,
        actual_E9_hashes=2,all_optimizer_returns=True,full_initialization_and_all_nine_orders_match_real_B7=True,population_and_partition_match=True,all_summary_arithmetic='PASS'),
        closeout_activity=dict(raw_weather_reads=0,checkpoint_deserializations=0,model_inference=0,optimizer_updates=0,weight_files_hashed=2,
        weight_payload_bytes_hashed=sum(sources[f'{CONTROL}_s{s}/LAST_epoch_09.pt']['bytes'] for s in (2030,2031)),historical_full_checks_repeated=False,final_2025='FROZEN_NO_ACCESS'),
        summary_descriptor_clarification='Only rain-stratum q32 generic direction label clarified as descriptive; source summary bytes and all numerical values unchanged',
        scientific_acceptance='COMPLETE_WITH_LIMITATIONS_THREE_SEED_PREDICTIVE_REPLICATION_NOT_PHYSICAL_CAUSALITY',
        limitations=summary['limitations'],closeout_script_sha256=sha(__file__))
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/',text)
    args.output.write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=result['status'],completed_at=result['completed_at'],tasks=tasks,budget=result['budget_closure'],metrics=summary['groups']['all']),ensure_ascii=False))


if __name__=='__main__':main()
