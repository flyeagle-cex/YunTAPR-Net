"""Read only new E6-E9 evidence; inherit verified E1-E5 and real B7 endpoints."""
import argparse,json,re,subprocess
from datetime import datetime,timezone
from pathlib import Path
from close_static_pair import canonical,close,load,query,sha,values

COMMIT='7d4970d726aba1316f27fc7eea25817db6eca305'
PROPOSAL='ebd2391e0d6e95b1aa0a573df21416822f5173e1a6a11a8eafd6b74679e1f0d6'
CONTROL='B7_PERP_GRADIENT'
PUBLIC=Path('docs/research_readiness/20261025/evidence')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--private',type=Path,required=True);parser.add_argument('--frozen-code',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    assert not a.output.exists(),'Never overwrite historical closeout'
    root=Path(__file__).resolve().parents[2];v=load(a.private);out=Path(v['output_root']);folder=out/'B7_s2029';parent=Path(v['parent'])/'B7_s2029'
    p=load(root/PUBLIC/'dote_physical_recovery_proposal_20261031.json');stop=load(root/PUBLIC/'dote_physical_control_failure_20261031.json');baseline=load(root/PUBLIC/'b7_b8_terminal_20261028.json')
    assert canonical({k:x for k,x in p.items() if k!='proposal_sha256'})==p['proposal_sha256']==PROPOSAL
    binding=load(out/'authorization_binding.json');grant=binding['approval'];terminal=load(out/'completion.json');task=load(folder/'completion.json')
    assert binding['code_commit']==grant['code_commit']==p['execution_code_commit']==COMMIT and grant['proposal_sha256']==PROPOSAL
    assert grant['approved_replay_updates']==480 and grant['budget']==p['budget'] and grant['scientific_choices']==p['scientific_choices']
    assert subprocess.check_output(['git','-C',str(a.frozen_code),'rev-parse','HEAD'],text=True).strip()==COMMIT
    assert not subprocess.check_output(['git','-C',str(a.frozen_code),'status','--porcelain'],text=True).strip()
    for n,h in p['code_sha256'].items():assert sha(a.frozen_code/n)==h,n
    assert not (out/'failure.json').exists() and not (folder/'failure.json').exists()
    assert (terminal['status'],terminal['epochs'],terminal['optimizer_updates'],terminal['segment_updates'],terminal['replay_updates'],terminal['cumulative_attempt_updates'],terminal['control_id'],terminal['code_commit'])==('COMPLETE_TRAIN_AND_DEV_EVALUATION',9,4320,1920,480,4800,CONTROL,COMMIT)
    assert terminal['checkpoints']==task['checkpoints'] and len(terminal['checkpoints'])==9
    assert query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')==[('B7','RETURNED',1920,2401,4320)]
    assert 0<terminal['wall_seconds']<=10800 and 0<terminal['monotonic_seconds']<=10800
    for n,h in p['parent_pins'].items():assert sha(Path(v['parent'])/n)==h,n
    for n in ('paired_initial_identity.json','paired_orders.json'):assert load(folder/n)==load(parent/n)
    sources={}
    def record(path,alias,digest=None):sources[alias]=dict(sha256=digest or sha(path),bytes=path.stat().st_size,visibility='LOCAL_ONLY')
    for name in ('authorization_binding.json','completion.json','physical_control_paired_summary.json'):record(out/name,'RECOVERY/'+name)
    for name in ('updates.sqlite','paired_initial_identity.json','paired_orders.json','completion.json'):record(folder/name,'CONTROL/'+name)
    epochs=[e for e in stop['training']['epochs'] if e['epoch']<=5];assert len(epochs)==5
    reference=baseline['endpoint_groups']['B7'];orders=load(folder/'paired_orders.json');weather_bytes=weather_files=0
    original=load(root/PUBLIC/'dote_physical_control_training_proposal_20261030.json')
    for e in range(6,10):
        train=load(folder/f'B7_train_{e:02d}.json');dev=load(folder/f'B7_development_{e:02d}.json');tail=load(folder/f'B7_tail_{e:02d}.json');seal=load(folder/f'B7_LAST_epoch_{e:02d}.receipt.json')
        assert (train['scenes'],train['batches'],train['updates'],train['loss_arm'])==(959,480,480*e,'E0')
        assert train['train_order_sha256']==orders[str(e)]['sha256']==canonical(orders[str(e)]['ids'])
        assert seal==terminal['checkpoints'][e-1] and seal['code_commit']==COMMIT and seal['validation_receipt_sha256']==canonical(dev)
        assert seal['population_sha256']==p['data']['population_sha256'] and dev['source_identity']==p['data']
        assert set(dev['groups'])==set(reference)
        for group,item in dev['groups'].items():
            assert item['ids_sha']==reference[group]['ids_sha256']
            for count in ('scenes','n_valid','n_rain'):assert item['summary'][count]==reference[group]['summary'][count]
        s=dev['groups']['all']['summary'];assert (s['scenes'],s['n_valid'],s['n_rain'])==(963,3303090,407820)
        assert len(s['tau'])==32 and s['tau'][-1]==.984375
        close(s['brier_sum']/s['n_valid'],s['brier']);close(s['s_qr']/s['n_rain'],s['conditional_pinball']);close(s['covered'][-1]/s['n_rain'],s['coverage'][-1])
        assert len(tail['scene_sufficient_statistics'])==963 and tail['nominal_q32']==.984375
        assert sum(t['n_rain'] for t in tail['strata'])==s['n_rain'] and sum(t['q32_covered'] for t in tail['strata'])==s['covered'][-1]
        close(sum(t['n_rain']*t['conditional_pinball'] for t in tail['strata'])/s['n_rain'],s['conditional_pinball'])
        bins=tail['elevation_diagnostics']['bins'];assert sum(b['n_valid'] for b in bins.values())==s['n_valid'] and sum(b['n_rain'] for b in bins.values())==s['n_rain']
        close(sum(b['brier_sum'] for b in bins.values()),s['brier_sum'])
        epochs.append(dict(epoch=e,train=train,development=s,checkpoint=seal,elevation_diagnostics=tail['elevation_diagnostics']))
        for name in ('train','development','tail'):record(folder/f'B7_{name}_{e:02d}.json',f'CONTROL/{name}_{e:02d}.json')
        record(folder/f'B7_LAST_epoch_{e:02d}.receipt.json',f'CONTROL/LAST_epoch_{e:02d}.receipt.json')
        for role in ('train','dev'):
            sub=folder/f'B7_{role}_reads_{e:02d}';r=load(sub/'pass_receipt.json');n=r['actual_reads'];scope=original['source_scope_summary']['Train' if role=='train' else 'Development']
            assert not r['during_failure'] and r['source_manifest_sha256']==scope['source_manifest_sha256']
            assert n['opened_files']==r['expected_files']==scope['file_count'] and n['delivered_bytes']==n['reserved_bytes']==r['expected_bytes']==scope['bytes_per_pass']
            assert query(sub/'reads.sqlite','SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes) FROM file_io GROUP BY state')==[('READ_COMPLETE',n['opened_files'],n['delivered_bytes'],n['reserved_bytes'])]
            assert query(sub/'reads.sqlite','SELECT state,COUNT(*) FROM jobs GROUP BY state')==[('COMPLETE',n['opened_files'])]
            weather_bytes+=n['delivered_bytes'];weather_files+=n['opened_files']
            record(sub/'pass_receipt.json',f'CONTROL/{role}_{e:02d}/pass_receipt.json');record(sub/'reads.sqlite',f'CONTROL/{role}_{e:02d}/reads.sqlite')
        if e==9:
            groups={g:dict(summary=item['summary'],ids_sha256=item['ids_sha'],exact_score_table_sha256=item['exact_score_table_sha256']) for g,item in dev['groups'].items()}
            tails={k:tail[k] for k in ('scope','nominal_q32','independent_event_count','strata','elevation_diagnostics')}
    assert (weather_bytes,weather_files)==(212254062672,63472)
    for path,n,size in [(out/'B7_PERP_GRADIENT_static_source.sqlite',1,312828),(out/'failed_source_verification/source_verification.sqlite',1,4705249)]:
        assert query(path,'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes) FROM file_io GROUP BY state')==[('READ_COMPLETE',n,size,size)]
        assert query(path,'SELECT state,COUNT(*) FROM jobs GROUP BY state')==[('COMPLETE',1)]
        record(path,'RECOVERY/'+path.name)
    assert query(out/'failed_source_verification/source_verification.sqlite','SELECT sha256 FROM file_io')==[(p['source_verification']['expected_sha256'],)]
    assert query(out/'B7_PERP_GRADIENT_static_source.sqlite','SELECT sha256 FROM file_io')==[(original['static_source_sha256']['B7'],)]
    weight=folder/'B7_LAST_epoch_09.pt';cache=root/'docs/research_readiness/.local/perp_recovery_E9_hash_20261031.json';stat=weight.stat()
    if cache.exists():
        cached=load(cache);assert (cached['bytes'],cached['mtime_ns'])==(stat.st_size,stat.st_mtime_ns);actual_sha=cached['sha256']
    else:
        actual_sha=sha(weight)
        with cache.open('x',encoding='utf-8') as f:json.dump(dict(bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=actual_sha),f)
    assert actual_sha==seal['checkpoint_sha256'];record(weight,'CONTROL/LAST_epoch_09.pt',actual_sha)
    headline={'B7':values(reference['all']['summary']),CONTROL:values(groups['all']['summary'])}
    deltas={g:{k:values(reference[g]['summary'])[k]-values(item['summary'])[k] for k in headline['B7']} for g,item in groups.items()}
    tail_pairs={}
    for section in ('strata','elevation'):
        aa=baseline['tail_diagnostics']['B7']['strata'] if section=='strata' else baseline['tail_diagnostics']['B7']['elevation_diagnostics']['bins']
        bb=tails['strata'] if section=='strata' else tails['elevation_diagnostics']['bins'];tail_pairs[section]={}
        for key in (range(len(aa)) if section=='strata' else aa):
            for count in ('n_valid','n_rain'):
                if count in aa[key]:assert aa[key][count]==bb[key][count]
            ms=[k for k in ('brier','conditional_pinball','q32_coverage') if k in aa[key] and k in bb[key]]
            tail_pairs[section][str(key)]=dict(B7=aa[key],B7_PERP_GRADIENT=bb[key],real_minus_perp={k:aa[key][k]-bb[key][k] for k in ms})
    result=dict(status='VERIFIED_COMPLETE_PHYSICAL_CONTROL_TRAIN_AND_DEV',model=CONTROL,seed=2029,verified_at=datetime.now(timezone.utc).isoformat(),
        training_commit=COMMIT,proposal_sha256=PROPOSAL,data_version=p['data'],protocol=p['protocol'],scientific_choices=p['scientific_choices'],
        endpoint='FIXED_EPOCH_9_LAST',endpoint_sha256=actual_sha,epochs=epochs,endpoint_groups={'B7':reference,CONTROL:groups},
        tail_diagnostics={'B7':baseline['tail_diagnostics']['B7'],CONTROL:tails},
        summary=dict(values=headline,difference_direction='B7_REAL_MINUS_B7_PERP_GRADIENT',group_deltas=deltas,tail_pairs=tail_pairs),
        lineage=dict(inherited_epochs=[1,2,3,4,5],inherited_commit=p['checkpoint']['parent_commit'],recovery_epochs=[6,7,8,9],recovery_commit=COMMIT,original_proposal_sha256=p['original_proposal_sha256'],
            failure_evidence=(PUBLIC/'dote_physical_control_failure_20261031.json').as_posix(),failure_evidence_sha256=sha(root/PUBLIC/'dote_physical_control_failure_20261031.json')),
        budget_closure=dict(segment_updates=1920,effective_updates=4320,cumulative_attempts=4800,replayed_updates=480,additional_retry=0,
            new_weather_bytes=weather_bytes,new_weather_instances=weather_files,new_static_bytes=312828,new_verification_bytes=4705249,
            new_source_bytes=212259080749,new_source_instances=63474,cumulative_delivered_bytes=509171050013,cumulative_reserved_bytes=509175755262,
            cumulative_source_instances=152398,retained_prior_uncertain_reservation_bytes=4705249,
            new_wall_seconds=terminal['wall_seconds'],new_monotonic_seconds=terminal['monotonic_seconds'],new_time_cap_seconds=10800,new_time_acceptance='PASS',
            old_wall_seconds=stop['time_accounting']['wall_span_seconds'],old_time_acceptance='NOT_VERIFIED_NOT_RETROACTIVELY_PASSED'),
        checks=dict(new_train_epochs=4,new_dev_epochs=4,inherited_epochs=5,new_weather_ledgers=8,new_static_ledgers=1,new_verification_ledgers=1,E9_actual_hashes=1,all_nine_orders_match=True,same_supervision_and_groups=True),
        evaluation_script=baseline['evaluation_script'],evaluation_script_sha256=baseline['evaluation_script_sha256'],code_sha256=p['code_sha256'],sources=sources,
        scientific_acceptance='COMPLETE_WITH_LIMITATIONS_SINGLE_SEED_DIRECTIONAL_REPRESENTATION_PROBE',
        limitations=['Same GFS/DEM inputs; perpendicular-gradient probe changes scalar distributions and spatial/climate associations.',
            'Single training seed and one Dev year; no storm independence, causality, significant effect or final-year claim.',
            'Old failed segment,480 replay updates,uncertain source reservation and unverified original wall-time acceptance remain in evidence.'],
        activity=dict(raw_weather_reads=0,checkpoint_deserializations=0,model_inference=0,optimizer_updates=0,weight_files_hashed=1,final_2025='FROZEN_NO_ACCESS'),closeout_script_sha256=sha(__file__))
    text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n';assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/',text)
    with a.output.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
    print(json.dumps(dict(status=result['status'],E9_sha256=actual_sha,values=headline,real_minus_perp=deltas['all'],recovery_wall_seconds=terminal['wall_seconds'])))

if __name__=='__main__':main()
