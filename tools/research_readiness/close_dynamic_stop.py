"""Read-only B7 complete / B8 stopped closeout. Never reads raw observations.

Reuse the existing numerical receipt helpers. Only new15 epoch seals and new
read ledgers are audited; historical B0--B6 closure is inherited. No model or
optimizer is imported, and no checkpoint is deserialized.
"""
import argparse,json,re,subprocess
from pathlib import Path
from datetime import datetime,timedelta,timezone
from close_static_pair import load,sha,query,canonical,values,close,stamp

COMMIT='b1f072e45fdd17b80106a774083995c350b28f04'
PROPOSAL='64e8d0f3c4b458b56e7cfaa1b81459eb4f61db0d947aceff62aa6e2ec579f5c8'
PUBLIC=Path('docs/research_readiness/20261025/evidence')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation',type=Path,required=True)
    parser.add_argument('--frozen-code',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    assert not args.output.exists(),'Never overwrite a stop/closure receipt'
    private=load(args.preparation);out=Path(private['output_root'])
    p=load(root/PUBLIC/'b7_b8_training_proposal.json')
    assert p['proposal_sha256']==private['proposal_sha256']==PROPOSAL
    assert sha(root/PUBLIC/'b7_b8_training_proposal.json')=='1e3eb1f34df503344984532d0f9cc5416373bf74504ff3368e6ab9c28c56bc0e'
    binding=load(out/'authorization_binding.json');a=binding['approval']
    assert a['approved_by_researcher'] and a['code_commit']==COMMIT and a['proposal_sha256']==PROPOSAL
    assert a['budget']==p['budget'] and a['scientific_choices']==p['scientific_choices']
    assert (out/'failure.json').is_file() and not (out/'completion.json').exists()
    assert not (out/'innovation_paired_summary.json').exists(),'No final two-model summary should exist'
    assert subprocess.check_output(['git','-C',str(args.frozen_code),'rev-parse','HEAD'],text=True).strip()==COMMIT
    assert not subprocess.check_output(['git','-C',str(args.frozen_code),'status','--porcelain'],text=True).strip()
    relevant=('src/yuntapr/experimental/research_readiness/dynamic_terrain.py',
              'src/yuntapr/experimental/research_readiness/dynamic_training.py',
              'src/yuntapr/experimental/core_innovation/stage4/engine.py',
              'src/yuntapr/experimental/core_innovation/stage4/data.py',
              'src/yuntapr/experimental/core_innovation/stage4/launch.py',
              'src/yuntapr/experimental/core_innovation/stage4/evaluation.py',
              'src/yuntapr/experimental/core_innovation/stage2/fusion.py',
              'src/yuntapr/experimental/core_innovation/dtfm.py')
    for name in relevant:assert sha(args.frozen_code/name)==p['code_sha256'][name]
    inherited=load(root/PUBLIC/'b5_b6_completion_and_paired_evidence.json')
    assert inherited['data_version']==p['data']
    baseline_path=Path(private['baseline_paths']['B6'])
    assert sha(baseline_path)==p['baseline_E9_sha256']['B6']==inherited['sources']['B6/development_09.json']['sha256']
    baseline=load(baseline_path)
    base_initial=load(Path(private['historical_pair'])/'paired_initial_identity.json')
    base_orders=load(Path(private['historical_pair'])/'paired_orders.json')
    groups={k:v for k,v in inherited['endpoint_groups'].items()}
    sources={};tasks=[];epochs=[];tails={};partial_passes=[];initializations={};total_bytes=total_files=0
    def record(path,alias):sources[alias]=dict(sha256=sha(path),bytes=Path(path).stat().st_size,visibility='LOCAL_ONLY')
    record(out/'authorization_binding.json','PACKAGE/authorization_binding.json')
    record(out/'failure.json','PACKAGE/failure.json')
    record(out/'B8_console.log','B8/console.log')
    log=(out/'B8_console.log').read_text(encoding='utf-8',errors='replace')
    assert '[WinError 121]' in log and 'read_seven_band' in log and 'resolve(strict=True)' in log
    for index,(model,n_epochs,n_updates) in enumerate((('B7',9,4320),('B8',6,2942)),1):
        folder=out/f'{model}_s2029';orders=load(folder/'paired_orders.json');initial=load(folder/'paired_initial_identity.json')
        assert orders==base_orders and initial['B6']==base_initial['B6']
        assert initial[model]['common_sha256']==base_initial['B6']['common_sha256']
        initializations[model]=initial
        assert query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')==[(model,'RETURNED',n_updates,1,n_updates)]
        record(folder/'updates.sqlite',f'{model}/updates.sqlite')
        record(folder/'paired_orders.json',f'{model}/paired_orders.json')
        record(folder/'paired_initial_identity.json',f'{model}/paired_initial_identity.json')
        if model=='B7':
            completion=load(folder/'completion.json')
            assert (completion['status'],completion['epochs'],completion['optimizer_updates'],completion['replay'],completion['code_commit'])==('COMPLETE_TRAIN_AND_DEV_EVALUATION',9,4320,0,COMMIT)
            record(folder/'completion.json',f'{model}/completion.json')
        else:
            assert not (folder/'completion.json').exists()
            assert load(folder/'failure.json')['status']=='STOP_NO_AUTOMATIC_RETRY'
            record(folder/'failure.json','B8/failure.json')
            for epoch in range(7,10):
                assert not (folder/f'B8_LAST_epoch_{epoch:02d}.receipt.json').exists()
                assert not (folder/f'B8_development_{epoch:02d}.json').exists()
        weather_bytes=weather_files=0
        for epoch in range(1,n_epochs+1):
            train=load(folder/f'{model}_train_{epoch:02d}.json')
            dev=load(folder/f'{model}_development_{epoch:02d}.json')
            seal=load(folder/f'{model}_LAST_epoch_{epoch:02d}.receipt.json')
            assert (train['scenes'],train['batches'],train['updates'],train['loss_arm'])==(959,480,480*epoch,'E0')
            assert train['train_order_sha256']==orders[str(epoch)]['sha256']==canonical(orders[str(epoch)]['ids'])
            assert (seal['model'],seal['epoch'],seal['updates'],seal['code_commit'])==(model,epoch,epoch*480,COMMIT)
            assert seal['population_sha256']==p['data']['population_sha256'] and seal['validation_receipt_sha256']==canonical(dev)
            assert dev['source_identity']==p['data'] and dev['partition_sha256']==baseline['partition_sha256']
            assert dev['population_ids_sha256']==baseline['population_ids_sha256'] and dev['occurrence_event']==baseline['occurrence_event']
            s=dev['groups']['all']['summary'];assert (s['scenes'],s['n_valid'],s['n_rain'])==(963,3303090,407820)
            close(s['brier_sum']/s['n_valid'],s['brier']);close(s['s_qr']/s['n_rain'],s['conditional_pinball'])
            close(s['covered'][-1]/s['n_rain'],s['coverage'][-1])
            tail=load(folder/f'{model}_tail_{epoch:02d}.json')
            assert len(tail['scene_sufficient_statistics'])==963
            assert sum(t['n_rain'] for t in tail['strata'])==s['n_rain']
            assert sum(t['q32_covered'] for t in tail['strata'])==s['covered'][-1]
            close(sum(t['n_rain']*t['conditional_pinball'] for t in tail['strata'] if t['n_rain'])/s['n_rain'],s['conditional_pinball'])
            bins=tail['elevation_diagnostics']['bins']
            assert sum(z['n_valid'] for z in bins.values())==s['n_valid'] and sum(z['n_rain'] for z in bins.values())==s['n_rain']
            close(sum(z['brier_sum'] for z in bins.values()),s['brier_sum'])
            assert sum(z['q32_covered'] for z in bins.values())==s['covered'][-1]
            for suffix in ('train','development','tail'):
                record(folder/f'{model}_{suffix}_{epoch:02d}.json',f'{model}/{suffix}_{epoch:02d}.json')
            record(folder/f'{model}_LAST_epoch_{epoch:02d}.receipt.json',f'{model}/LAST_epoch_{epoch:02d}.receipt.json')
            assert (folder/f'{model}_LAST_epoch_{epoch:02d}.pt').stat().st_size>0
            for role in ('train','dev'):
                sub=folder/f'{model}_{role}_reads_{epoch:02d}';r=load(sub/'pass_receipt.json');actual=r['actual_reads']
                expected=p['source_scope_summary']['Train' if role=='train' else 'Development']
                assert not r['during_failure'] and r['source_manifest_sha256']==expected['source_manifest_sha256']
                assert actual['opened_files']==r['expected_files']==expected['file_count']
                assert actual['delivered_bytes']==actual['reserved_bytes']==r['expected_bytes']==expected['bytes_per_pass']
                assert query(sub/'reads.sqlite','SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',actual['opened_files'],actual['delivered_bytes'],actual['reserved_bytes'],0)]
                weather_bytes+=actual['delivered_bytes'];weather_files+=actual['opened_files']
                record(sub/'pass_receipt.json',f'{model}/{role}_{epoch:02d}/pass_receipt.json')
                record(sub/'reads.sqlite',f'{model}/{role}_{epoch:02d}/reads.sqlite')
            epochs.append(dict(model=model,seed=2029,epoch=epoch,train=train,development=s,checkpoint=seal,
                               elevation_diagnostics=tail['elevation_diagnostics'],fixed_E9_endpoint=(model=='B7' and epoch==9)))
            if model=='B7' and epoch==9:
                assert completion['checkpoints'][-1]==seal
                groups['B7']={}
                for group,item in dev['groups'].items():
                    ref=baseline['groups'][group]
                    assert item['ids_sha']==ref['ids_sha'] and item['summary']['n_valid']==ref['summary']['n_valid'] and item['summary']['n_rain']==ref['summary']['n_rain']
                    groups['B7'][group]=dict(summary=item['summary'],ids_sha256=item['ids_sha'],exact_score_table_sha256=item['exact_score_table_sha256'])
                tails['B7']={k:tail[k] for k in ('scope','nominal_q32','independent_event_count','strata','elevation_diagnostics')}
        sealed_bytes=weather_bytes;sealed_files=weather_files
        if model=='B8':
            sub=folder/'B8_train_reads_07';r=load(sub/'pass_receipt.json');actual=r['actual_reads']
            assert r['during_failure'] and actual['opened_files']<r['expected_files']
            assert actual['delivered_bytes']==actual['reserved_bytes'] and actual['states']=={'READ_COMPLETE':actual['opened_files']}
            assert query(sub/'reads.sqlite','SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',actual['opened_files'],actual['delivered_bytes'],actual['reserved_bytes'],0)]
            jobs=dict(query(sub/'reads.sqlite','SELECT state,COUNT(*) FROM jobs GROUP BY state'))
            partial_passes.append(dict(model='B8',role='Train',epoch=7,receipt=r,job_states=jobs))
            weather_bytes+=actual['delivered_bytes'];weather_files+=actual['opened_files']
            record(sub/'pass_receipt.json','B8/train_07/partial_pass_receipt.json');record(sub/'reads.sqlite','B8/train_07/reads.sqlite')
        static_db=out/f'{model}_static_source.sqlite'
        assert query(static_db,'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',1,312828,312828,0)]
        assert query(static_db,'SELECT sha256 FROM file_io')[0][0]==p['static_source_sha256'][model]
        record(static_db,f'{model}/static_source.sqlite')
        weight=folder/f'{model}_LAST_epoch_{n_epochs:02d}.pt';record(weight,f'{model}/LAST_epoch_{n_epochs:02d}.pt')
        assert sources[f'{model}/LAST_epoch_{n_epochs:02d}.pt']['sha256']==seal['checkpoint_sha256']
        if model=='B7':
            assert (weather_bytes,weather_files)==(completion['logical_source_bytes'],completion['logical_source_files'])
            assert weather_bytes+312828==completion['total_logical_source_bytes']==p['budget']['total_source_bytes_per_model']['B7']
        task_bytes=weather_bytes+312828;task_files=weather_files+1
        stop=folder/'completion.json' if model=='B7' else out/'failure.json'
        elapsed=stop.stat().st_mtime-(out/f'task_{index}_claim.json').stat().st_mtime
        assert 0<elapsed<=p['budget']['max_model_seconds']
        assert task_bytes<=p['budget']['total_source_bytes_per_model'][model]
        tasks.append(dict(model=model,seed=2029,status='COMPLETE_TRAIN_AND_DEV_EVALUATION' if model=='B7' else 'FAILED_INCOMPLETE_NO_FIXED_E9',
                          sealed_train_dev_epochs=n_epochs,returned_updates=n_updates,uncertain_updates=0,
                          saved_epoch=n_epochs,saved_updates=n_epochs*480,unsaved_returned_updates=n_updates-n_epochs*480,
                          last_saved_sha256=seal['checkpoint_sha256'],fixed_E9_sha256=seal['checkpoint_sha256'] if model=='B7' else None,
                          sealed_weather_source_bytes=sealed_bytes,sealed_weather_source_files=sealed_files,
                          actual_weather_source_bytes=weather_bytes,actual_weather_source_files=weather_files,
                          static_source_bytes=312828,static_source_files=1,total_source_bytes=task_bytes,total_source_files=task_files,
                          completed_or_stopped_at=stamp(stop),wall_seconds_mtime_proxy=elapsed,code_commit=COMMIT))
        total_bytes+=task_bytes;total_files+=task_files
    endpoint_values={m:values(g['all']['summary']) for m,g in groups.items()}
    deltas={f'B7_minus_{m}':{k:endpoint_values['B7'][k]-endpoint_values[m][k] for k in endpoint_values[m]} for m in ('B4','B5','B6')}
    elapsed=(out/'failure.json').stat().st_mtime-(out/'authorization_binding.json').stat().st_mtime
    assert elapsed<p['budget']['max_package_seconds'] and total_bytes<=p['budget']['total_source_bytes'] and total_files<=p['budget']['total_source_files']
    failure=dict(kind='SOURCE_PATH_RESOLUTION_OS_ERROR',exception='OSError',winerror=121,
                 reason='SEMAPHORE_TIMEOUT_DURING_SATELLITE_PATH_RESOLVE',stage='B8_EPOCH7_TRAIN_BATCH_LOADING_BEFORE_NEXT_OPTIMIZER_INTENT',
                 source_modality='HIMAWARI_2023_TRAIN',source_basename='NC_H09_20231025_2300_R21_FLDK.06001_06001.nc',
                 underlying_storage_or_connection_cause='NOT_VERIFIED_NO_SOURCE_RETRY_OR_PROBE',
                 scientific_or_model_performance_failure=False)
    result=dict(status='VERIFIED_B7_COMPLETE_B8_FAILED_PARTIAL_PACKAGE',verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                package_stopped_at=stamp(out/'failure.json'),training_commit=COMMIT,proposal_sha256=PROPOSAL,data_version=p['data'],
                endpoint='FIXED_EPOCH_9_LAST',tasks=tasks,epochs=epochs,partial_passes=partial_passes,failure=failure,
                endpoint_groups=groups,tail_diagnostics=tails,initializations=initializations,
                summary=dict(values=endpoint_values,differences=deltas,descriptive_only=True,significance='NOT_CLAIMED',B8='NOT_AVAILABLE_FIXED_E9'),
                evaluation_script='src/yuntapr/experimental/core_innovation/stage4/evaluation.py',
                evaluation_script_sha256=p['code_sha256']['src/yuntapr/experimental/core_innovation/stage4/evaluation.py'],
                budget_closure=dict(returned_updates=7262,uncertain_updates=0,update_cap=8640,
                                    actual_source_bytes=total_bytes,reserved_source_bytes=total_bytes,source_byte_cap=p['budget']['total_source_bytes'],
                                    actual_source_files=total_files,source_file_cap=p['budget']['total_source_files'],
                                    optimizer_replay_updates=0,automatic_retries=0,unsaved_B8_updates_after_E6=62,
                                    max_package_seconds=43200,wall_seconds_mtime_proxy=elapsed,
                                    wall_clock_definition='File mtime intervals, not GPU billing/compute time'),
                checks=dict(B7_new_epoch_seals=9,B8_partial_epoch_seals=6,completed_weather_read_ledgers=30,
                            partial_weather_read_ledgers=1,static_read_ledgers=2,actual_weight_hashes=2,
                            paired_orders_all_nine_epochs=True,B6_common_initialization_matches=True,
                            all_saved_population_partitions_match=True,B8_no_E7_E9_seals=True),sources=sources,
                inherited_baseline_evidence='b5_b6_completion_and_paired_evidence.json',
                activity=dict(raw_weather_payload_reads=0,checkpoint_deserializations=0,optimizer_updates=0,model_inference=0,
                              new_B7_B8_weight_hashes=2,old_full_audits_rerun=False,original_source_retry_or_probe=0,final_2025='FROZEN_NO_ACCESS'),
                scientific_acceptance=dict(B7='COMPLETE_WITH_LIMITATIONS_SINGLE_SEED',B8='NOT_VERIFIED_MISSING_FIXED_E9',
                                           DTFM_vs_concat='NOT_VERIFIED_NO_VALID_ENDPOINT_PAIR',physical_mechanism='NOT_PROVEN',
                                           significance='NOT_CLAIMED',final_generalization='NOT_VERIFIED',new_recovery='NOT_AUTHORIZED'),
                closeout_script_sha256=sha(__file__))
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    assert not re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/',text)
    args.output.write_text(text,encoding='utf-8')
    print(json.dumps(dict(status=result['status'],stopped_at=result['package_stopped_at'],tasks=tasks,budget_closure=result['budget_closure'],B7_deltas=deltas),ensure_ascii=False))

if __name__=='__main__':main()
