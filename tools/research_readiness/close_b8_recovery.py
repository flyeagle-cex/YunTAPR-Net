"""Seal only the three new B8 epochs; inherit all previously closed evidence."""
import argparse,json,re,subprocess
from pathlib import Path
from datetime import datetime,timedelta,timezone
from close_static_pair import load,sha,query,canonical,values,close,stamp

COMMIT='ef11531a7cdeb35b767caebdb61e0e81c6123187'
PUBLIC=Path('docs/research_readiness/20261025/evidence')

def main():
 p=argparse.ArgumentParser();p.add_argument('--private',type=Path,required=True);p.add_argument('--frozen-code',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists(),'Never overwrite an experimental receipt'
 root=Path(__file__).resolve().parents[2];v=load(a.private);out=Path(v['output_root']);folder=out/'B8_s2029'
 proposal=load(root/PUBLIC/'b8_recovery_proposal_20261028.json');stop=load(root/PUBLIC/'b7_b8_terminal_20261028.json');launched=load(root/PUBLIC/'b8_recovery_approved_launch_20261028.json')
 original=load(root/PUBLIC/'b7_b8_training_proposal.json');caps=proposal['budget']
 assert canonical({k:x for k,x in proposal.items() if k!='proposal_sha256'})==v['proposal_sha256']==proposal['proposal_sha256']
 assert sha(root/PUBLIC/'b7_b8_terminal_20261028.json')==proposal['stop_receipt_sha256']
 binding=load(out/'authorization_binding.json');grant=binding['approval']
 assert grant['approved_by_researcher'] is True and grant['code_commit']==COMMIT and grant['proposal_sha256']==proposal['proposal_sha256']
 assert grant['approved_replay_updates']==62 and grant['budget']==caps and grant['approved_checkpoint_sha256']==proposal['checkpoint']['sha256']
 assert sha(out/'authorization_binding.json')==launched['sources']['authorization_binding_sha256']
 assert subprocess.check_output(['git','-C',str(a.frozen_code),'rev-parse','HEAD'],text=True).strip()==COMMIT
 assert not subprocess.check_output(['git','-C',str(a.frozen_code),'status','--porcelain'],text=True).strip()
 assert not (out/'failure.json').exists() and not (folder/'failure.json').exists()
 completion=load(out/'completion.json');task=load(folder/'completion.json');summary=load(out/'innovation_paired_summary.json')
 assert (completion['status'],completion['code_commit'],completion['segment_updates'],completion['replayed_updates'])==('COMPLETE_TRAIN_AND_DEV_EVALUATION',COMMIT,1440,62)
 assert (task['status'],task['epochs'],task['optimizer_updates'],task['segment_updates'],task['replay_updates'],task['cumulative_attempt_updates'])==('COMPLETE_TRAIN_AND_DEV_EVALUATION',9,4320,1440,62,4382)
 assert completion['budget']==caps and completion['proposal_sha256']==proposal['proposal_sha256']
 assert query(folder/'updates.sqlite','SELECT model,state,COUNT(*),MIN(u),MAX(u) FROM updates GROUP BY model,state')==[('B8','RETURNED',1440,2881,4320)]
 assert query(folder/'updates.sqlite','SELECT COUNT(*) FROM updates WHERE u<=2942')==[(62,)]
 inherited=[e for e in stop['epochs'] if e['model']=='B8'];assert len(inherited)==6 and task['checkpoints'][:6]==[e['checkpoint'] for e in inherited]
 assert sha(folder/'paired_orders.json')==stop['sources']['B8/paired_orders.json']['sha256']
 assert sha(folder/'paired_initial_identity.json')==stop['sources']['B8/paired_initial_identity.json']['sha256']
 orders=load(folder/'paired_orders.json');old=Path(v['parent']);reference=load(old/'B7_s2029/B7_development_09.json')
 sources={};epochs=[];total=files=0;groups=dict(stop['endpoint_groups']);tail=None
 def record(path,alias):sources[alias]=dict(sha256=sha(path),bytes=path.stat().st_size,visibility='LOCAL_ONLY')
 for name in ('authorization_binding.json','completion.json','innovation_paired_summary.json'):record(out/name,'RECOVERY_PACKAGE/'+name)
 for name in ('completion.json','updates.sqlite','paired_initial_identity.json','paired_orders.json'):record(folder/name,'RECOVERY_B8/'+name)
 for epoch in (7,8,9):
  train=load(folder/f'B8_train_{epoch:02d}.json');dev=load(folder/f'B8_development_{epoch:02d}.json');seal=load(folder/f'B8_LAST_epoch_{epoch:02d}.receipt.json');tail=load(folder/f'B8_tail_{epoch:02d}.json')
  assert (train['scenes'],train['batches'],train['updates'],train['loss_arm'])==(959,480,epoch*480,'E0')
  assert train['train_order_sha256']==orders[str(epoch)]['sha256']==canonical(orders[str(epoch)]['ids'])
  assert (seal['model'],seal['epoch'],seal['updates'],seal['code_commit'])==('B8',epoch,epoch*480,COMMIT)
  assert seal==task['checkpoints'][epoch-1] and seal['population_sha256']==proposal['data']['population_sha256'] and seal['validation_receipt_sha256']==canonical(dev)
  assert dev['source_identity']==proposal['data'] and dev['partition_sha256']==reference['partition_sha256'] and dev['population_ids_sha256']==reference['population_ids_sha256'] and dev['occurrence_event']==reference['occurrence_event']
  s=dev['groups']['all']['summary'];assert (s['scenes'],s['n_valid'],s['n_rain'])==(963,3303090,407820)
  close(s['brier_sum']/s['n_valid'],s['brier']);close(s['s_qr']/s['n_rain'],s['conditional_pinball']);close(s['covered'][-1]/s['n_rain'],s['coverage'][-1])
  assert len(tail['scene_sufficient_statistics'])==963 and sum(t['n_rain'] for t in tail['strata'])==s['n_rain'] and sum(t['q32_covered'] for t in tail['strata'])==s['covered'][-1]
  close(sum(t['n_rain']*t['conditional_pinball'] for t in tail['strata'] if t['n_rain'])/s['n_rain'],s['conditional_pinball'])
  bins=tail['elevation_diagnostics']['bins'];assert sum(t['n_valid'] for t in bins.values())==s['n_valid'] and sum(t['n_rain'] for t in bins.values())==s['n_rain'];close(sum(t['brier_sum'] for t in bins.values()),s['brier_sum'])
  assert sum(t['q32_covered'] for t in bins.values())==s['covered'][-1]
  epochs.append(dict(model='B8',seed=2029,epoch=epoch,train=train,development=s,checkpoint=seal,elevation_diagnostics=tail['elevation_diagnostics'],code_commit=COMMIT))
  for suffix in ('train','development','tail'):record(folder/f'B8_{suffix}_{epoch:02d}.json',f'RECOVERY_B8/{suffix}_{epoch:02d}.json')
  record(folder/f'B8_LAST_epoch_{epoch:02d}.receipt.json',f'RECOVERY_B8/LAST_epoch_{epoch:02d}.receipt.json')
  for role in ('train','dev'):
   sub=folder/f'B8_{role}_reads_{epoch:02d}';r=load(sub/'pass_receipt.json');n=r['actual_reads'];scope=original['source_scope_summary']['Train' if role=='train' else 'Development']
   assert not r['during_failure'] and r['source_manifest_sha256']==scope['source_manifest_sha256']
   assert n['opened_files']==r['expected_files']==scope['file_count'] and n['delivered_bytes']==n['reserved_bytes']==r['expected_bytes']==scope['bytes_per_pass']
   assert query(sub/'reads.sqlite','SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',n['opened_files'],n['delivered_bytes'],n['reserved_bytes'],0)]
   assert all(state=='COMPLETE' for state,count in query(sub/'reads.sqlite','SELECT state,COUNT(*) FROM jobs GROUP BY state'))
   total+=n['delivered_bytes'];files+=n['opened_files'];record(sub/'pass_receipt.json',f'RECOVERY_B8/{role}_{epoch:02d}/pass_receipt.json');record(sub/'reads.sqlite',f'RECOVERY_B8/{role}_{epoch:02d}/reads.sqlite')
  if epoch==9:
   groups['B8']={}
   for name,item in dev['groups'].items():
    ref=reference['groups'][name];assert item['ids_sha']==ref['ids_sha'] and item['summary']['n_valid']==ref['summary']['n_valid'] and item['summary']['n_rain']==ref['summary']['n_rain']
    groups['B8'][name]=dict(summary=item['summary'],ids_sha256=item['ids_sha'],exact_score_table_sha256=item['exact_score_table_sha256'])
 static=out/'B8_static_source.sqlite'
 assert query(static,'SELECT state,COUNT(*),SUM(actual_bytes),SUM(expected_bytes),SUM(sha256 IS NULL) FROM file_io GROUP BY state')==[('READ_COMPLETE',1,312828,312828,0)]
 assert query(static,'SELECT sha256 FROM file_io')==[(original['static_source_sha256']['B8'],)]
 record(static,'RECOVERY_B8/static_source.sqlite')
 assert (total,files)==(caps['new_training_source_bytes'],caps['new_training_source_files'])
 assert (total+312828,files+1)==(task['segment_source_bytes'],task['segment_source_files'])==(caps['new_source_bytes'],caps['new_source_files'])
 weight=folder/'B8_LAST_epoch_09.pt';record(weight,'RECOVERY_B8/LAST_epoch_09.pt');assert sources['RECOVERY_B8/LAST_epoch_09.pt']['sha256']==seal['checkpoint_sha256']
 elapsed=(out/'completion.json').stat().st_mtime-(out/'authorization_binding.json').stat().st_mtime;assert 0<elapsed<=caps['max_wall_seconds']
 endpoints={m:values(g['all']['summary']) for m,g in groups.items()};deltas={}
 assert summary['values']==endpoints
 for target,base in (('B7','B6'),('B8','B4'),('B8','B5'),('B8','B6'),('B8','B7')):
  name=target+'_minus_'+base;deltas[name]={k:endpoints[target][k]-endpoints[base][k] for k in endpoints[base]}
  if name in summary['differences']:
   for k,x in deltas[name].items():close(x,summary['differences'][name][k])
 result=dict(status='VERIFIED_COMPLETE_B7_B8_FIXED_E9_TRAIN_AND_DEV',verified_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),completed_at=stamp(out/'completion.json'),
             training_commit=COMMIT,inherited_training_commit=stop['training_commit'],proposal_sha256=proposal['proposal_sha256'],data_version=proposal['data'],endpoint='FIXED_EPOCH_9_LAST',
             B7_fixed_E9_sha256=stop['tasks'][0]['fixed_E9_sha256'],B8_fixed_E9_sha256=seal['checkpoint_sha256'],epochs=epochs,endpoint_groups=groups,
             tail_diagnostics=dict(B8={k:tail[k] for k in ('scope','nominal_q32','independent_event_count','strata','elevation_diagnostics')}),
             summary=dict(values=endpoints,differences=deltas,descriptive_only=True,significance='NOT_CLAIMED'),
             budget_closure=dict(new_returned_updates=1440,replayed_updates=62,uncertain_updates=0,effective_B8_updates=4320,cumulative_B8_attempts=4382,cumulative_package_attempts=8702,
                 new_source_bytes=total+312828,new_source_files=files+1,diagnostic_source_bytes=4096,diagnostic_source_files=1,
                 cumulative_source_bytes=stop['budget_closure']['actual_source_bytes']+total+312828+4096,cumulative_source_files=stop['budget_closure']['actual_source_files']+files+1+1,
                 recovery_wall_seconds_mtime_proxy=elapsed,recovery_wall_cap=8316,prior_B8_wall_seconds_ceil=caps['prior_B8_wall_seconds_ceil'],combined_B8_wall_seconds_proxy=caps['prior_B8_wall_seconds_ceil']+elapsed,
                 extra_retries=0,wall_definition='File mtime intervals, not GPU billing/compute time'),
             checks=dict(new_epoch_seals=3,new_weather_read_ledgers=6,new_static_read_ledgers=1,new_actual_weight_hashes=1,prior_B7_and_B8_E1_E6='INHERITED_NOT_REAUDITED',nine_orders_and_initial_identity_match=True),
             sources=sources,inherited_terminal_evidence=dict(path='b7_b8_terminal_20261028.json',sha256=proposal['stop_receipt_sha256']),
             evaluation_script=stop['evaluation_script'],evaluation_script_sha256=stop['evaluation_script_sha256'],
             activity=dict(raw_weather_payload_reads=0,checkpoint_deserializations=0,new_optimizer_updates=0,inference=0,actual_E9_weight_hashes=1,old_full_audits_rerun=False,final_2025='FROZEN_NO_ACCESS'),
             scientific_acceptance='COMPLETE_WITH_LIMITATIONS_SINGLE_SEED; DTFM_GAIN_MIXED; no significance, causality or final generalization claim',closeout_script_sha256=sha(__file__))
 assert result['budget_closure']['cumulative_source_bytes']==caps['cumulative_source_bytes'] and result['budget_closure']['cumulative_source_files']==caps['cumulative_source_files']
 text=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n';assert not re.search(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/Users/|/home/',text)
 with a.output.open('x',encoding='utf-8') as f:f.write(text)
 print(json.dumps(dict(status=result['status'],completed_at=result['completed_at'],B8_E9_sha256=result['B8_fixed_E9_sha256'],budget=result['budget_closure'],B8_minus_B7=deltas['B8_minus_B7']),ensure_ascii=False))
if __name__=='__main__':main()
