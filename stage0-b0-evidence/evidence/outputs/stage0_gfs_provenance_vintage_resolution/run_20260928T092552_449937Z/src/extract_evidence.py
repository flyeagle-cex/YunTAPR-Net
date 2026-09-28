"""Primary local evidence extraction. Reads logs/manifests and prior tables, never raw datasets."""
import json,re,csv,collections
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd
from config import *
from common import write_csv,write_json,sha256,dumps
from compat_rules import source_evidence

def read(p): return pd.read_csv(p,keep_default_na=False)
def logical_key(p):
 s=str(p).replace('\\','/');m=re.search(r'/raw/(GFS(?:_thermo)?)/(.+)$',s,re.I)
 return (m.group(1).lower()+'/'+m.group(2).lower()) if m else ''
def case_key(p):
 m=re.search(r'gfs_(?:thermo_)?0p25_(\d{10})_f(\d{3})',str(p));return f'{m[1]}_f{m[2]}' if m else ''
def timestamp(r):return next((str(r[k]) for k in ['recorded_utc','recorded_at','timestamp','downloaded_at','completed_at'] if r.get(k)), '')
def offset_known(s):return bool(re.search(r'(Z|[+-]\d{2}:\d{2})$',s))

def run():
 inv=read(OUT/'PROVENANCE/local_artifact_inventory.csv')
 extra=[]
 for name in ['gfs_predictor_whitelist.json','gfs_vintage_index_summary.json','gfs_vintage_index_2023_2025_march_october.csv']:
  p=DATA/'processed'/name;s=p.stat();extra.append(dict(path=str(p),file_type=p.suffix,matched_keyword='gfs;vintage;availability',mtime=datetime.fromtimestamp(s.st_mtime,timezone.utc).isoformat(),mtime_ns=s.st_mtime_ns,size=s.st_size,evidence_relevance='LEGACY_DERIVED_ARTIFACT_NOT_APPROVAL',content_search_scope='FULL_TARGETED_REFERENCE',sha256_before=sha256(p)))
 inv=pd.concat([inv,pd.DataFrame(extra)],ignore_index=True).drop_duplicates('path')
 inv.to_csv(OUT/'PROVENANCE/local_artifact_inventory.csv',index=False,encoding='utf-8-sig')
 write_json(OUT/'logs/targeted_search_extension.json',{'reason':'completion manifest explicitly references GFS vintage index; only 3 named GFS processed artifacts opened','paths':[x['path'] for x in extra],'raw_recursive_search':False})
 selected=read(OUT/'logs/selected_raw_manifest_before.csv');selected_ids=set(selected.case_id)
 rawby={(r.case_id,r.branch):r for r in selected.itertuples()}
 events=[];summaries=[];errors=[];headers=[]
 for ip in inv.itertuples():
  p=Path(ip.path)
  if p.parent!=DATA/'manifests' or p.suffix!='.jsonl' or not p.name.startswith('gfs'):continue
  statuses=collections.Counter();count=0;times=[];urls=0
  with p.open(encoding='utf-8-sig') as f:
   for ln,line in enumerate(f,1):
    if not line.strip():continue
    try:r=json.loads(line)
    except Exception as e:errors.append(dict(path=str(p),line=ln,error=str(e)));continue
    count+=1;statuses[str(r.get('status','UNKNOWN'))]+=1;t=timestamp(r)
    if t:times.append(t)
    path=r.get('path','');cid=case_key(path);branch='thermo' if 'thermo' in str(path).lower() else 'main';url=r.get('url',r.get('original_url',r.get('requested_url','')));urls+=bool(url)
    for k,v in r.items():
     if k.lower().replace('_','-') in ['last-modified','response-date','http-date'] or k.lower()=='headers':headers.append(dict(path=str(p),line=ln,field=k,value=dumps(v)))
    if cid in selected_ids:
     current=rawby.get((cid,branch));size=r.get('bytes',r.get('size_bytes'))
     events.append(dict(case_id=cid,branch=branch,evidence_path=str(p),line=ln,status=r.get('status','UNKNOWN'),local_timestamp=t,timezone_explicit=offset_known(t),requested_url=url,recorded_path=path,logical_key=logical_key(path),current_path=current.path if current else '',current_size=current.size_bytes if current else '',recorded_size=size,size_matches_current=(int(size)==int(current.size_bytes)) if current and size is not None else '',same_literal_path=str(path).casefold()==str(current.path).casefold() if current else False,physical_root_identity='NOT_ESTABLISHED' if 'yunnan_extreme_precip_data' in str(path) else 'EXACT_LITERAL_PATH' if current and str(path).casefold()==str(current.path).casefold() else 'NOT_ESTABLISHED',content_hash_link='NOT_ESTABLISHED',remote_last_modified=r.get('last_modified',''),response_date=r.get('response_date',''),error=r.get('error',''),raw_record=dumps(r)))
  summaries.append(dict(path=str(p),records=count,status_counts=dumps(statuses),timestamp_min=min(times) if times else '',timestamp_max=max(times) if times else '',requested_url_records=urls,timestamp_interpretation='local manifest event; not official publication; skipped is not completion'))
 write_csv(OUT/'TIME_AVAILABILITY/download_manifest_case_events.csv',events)
 write_csv(OUT/'TIME_AVAILABILITY/download_manifest_summary.csv',summaries)
 write_csv(OUT/'TIME_AVAILABILITY/saved_http_header_evidence.csv',headers,columns=['path','line','field','value'])
 write_csv(OUT/'logs/manifest_parse_errors.csv',errors,columns=['path','line','error'])
 # Read complete relevant small historical text logs; preserve raw timestamps, no assumed timezone.
 logrows=[];logstats=[];templates=[];scriptrefs=[]
 for ip in inv.itertuples():
  p=Path(ip.path)
  if p.parent!=DATA/'logs' or p.suffix!='.log' or not any(x in p.name.lower() for x in ['gfs','download_','full_pipeline']):continue
  n=0;requests=0;completions=0
  with p.open(encoding='utf-8-sig',errors='replace') as f:
   for ln,line in enumerate(f,1):
    n+=1;line=line.strip()
    if not re.search('gfs|thermo|NCAR|d084001',line,re.I):continue
    requests+=bool(re.search(r'Request|Downloading|GET ',line));completions+=bool(re.search('Completed|downloaded|Saved',line,re.I))
    if 'AWS templates' in line:templates.append(dict(evidence_path=str(p),line=ln,raw_event=line,evidence_class='DIRECT_EVIDENCE',causal_attribute_assignment='NOT_ESTABLISHED'))
    if re.search(r'\.py\b|wgrib2|cfgrib|netcdf-java|last-modified|response.?date',line,re.I):scriptrefs.append(dict(evidence_path=str(p),line=ln,raw_event=line))
    hit=next((cid for cid in selected_ids if cid.split('_')[0] in line or datetime.strptime(cid.split('_')[0],'%Y%m%d%H').strftime('%Y-%m-%d %H') in line),None)
    if hit or re.search(r'https?://',line) or re.search('last-modified|response.?date',line,re.I):
     url=re.findall(r'https?://[^\s\"<>]+',line);m=re.match(r'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[,.]\d+)?)',line)
     logrows.append(dict(candidate_case_id=hit or '',evidence_path=str(p),line=ln,local_timestamp_raw=m[1] if m else '',timezone='UNKNOWN_UNLESS_EXPLICIT_IN_RAW_EVENT',requested_url=dumps(url),event_type='COMPLETION' if re.search('Completed|downloaded|Saved',line,re.I) else 'REQUEST' if re.search('Request|Downloading|GET ',line) else 'OTHER',remote_last_modified='NOT_RECORDED_IN_EVENT',response_date='NOT_RECORDED_IN_EVENT',raw_event=line))
  logstats.append(dict(path=str(p),lines=n,gfs_request_lines=requests,gfs_completion_lines=completions))
 write_csv(OUT/'TIME_AVAILABILITY/download_log_events.csv',logrows)
 write_csv(OUT/'TIME_AVAILABILITY/download_log_summary.csv',logstats)
 write_csv(OUT/'TIME_LINEAGE/template_log_evidence.csv',templates)
 write_csv(OUT/'PROVENANCE/tool_or_script_log_references.csv',scriptrefs,columns=['evidence_path','line','raw_event'])
 # Compare legacy derived index to existing inventories only. No raw reopen.
 old=read(DATA/'processed/gfs_vintage_index_2023_2025_march_october.csv')
 mi=read(BASE_MAIN/'GFS/gfs_inventory.csv');ti=read(BASE_THERMO/'THERMO/gfs_thermo_inventory.csv')
 maps={b:{str(r.relative_path).replace('\\','/').lower():int(r.size_bytes) for r in d.itertuples()} for b,d in [('main',mi),('thermo',ti)]}
 comps=[]
 for r in old.to_dict('records'):
  for b,pre in [('main','core'),('thermo','thermo')]:
   rel=r[pre+'_relative_path'].replace('\\','/');rel=re.sub(r'^(raw/)?GFS(?:_thermo)?/','',rel,flags=re.I);sz=maps[b].get(rel.lower())
   comps.append(dict(init_time=r['init_time_utc'],lead=r['lead_hours'],branch=b,relative_path=rel,legacy_size=r[pre+'_size_bytes'],current_inventory_size=sz if sz is not None else '',size_match=sz==int(r[pre+'_size_bytes']) if sz is not None else False,legacy_source=r[pre+'_source'],legacy_conservative_available_time=r['conservative_available_time_utc'],legacy_index_is_release_evidence=False,content_identity='NOT_ESTABLISHED'))
 write_csv(OUT/'PROVENANCE/legacy_vintage_index_comparison.csv',comps)
 # Original tokens from metadata fields already recorded in old source lineage, not NC filenames.
 lin=read(BASE_THERMO/'COMPATIBILITY/source_lineage_fields.csv');tokens=[];fields=[]
 for r in lin.to_dict('records'):
  a=json.loads(r['main_evidence']);b=json.loads(r['thermo_evidence']);tokens.append(dict(init_time=r['init_time'],lead=r['lead_time'],main_source_tokens=dumps(a['direct_tokens']),main_history_tokens=dumps(a['history_tokens']),thermo_source_tokens=dumps(b['direct_tokens']),thermo_history_tokens=dumps(b['history_tokens']),main_current_source_token_match=a['current_token_match'],thermo_current_source_token_match=b['current_token_match'],both_current_token_match=a['current_token_match'] and b['current_token_match'],same_declared_gfs_family=a['gfs_product_evidence'] and b['gfs_product_evidence'],direct_token_conflict=a['direct_token_conflict'] or b['direct_token_conflict'],main_stale_history=a['stale_history'],evidence_path=str(BASE_THERMO/'COMPATIBILITY/source_lineage_fields.csv'),independent_grib_identity='NOT_ESTABLISHED'))
 write_csv(OUT/'PROVENANCE/original_filename_token_comparison.csv',tokens)
 raw=json.loads((OUT/'PROVENANCE/selected_case_raw_metadata.json').read_text(encoding='utf-8'))
 roles={'source':'declared archive/retrieval source, not necessarily generating center','history':'conversion/creation narrative','institution':'declared institution','references':'reference, not download receipt','title':'product/subset description','originating':'generating center or process','process':'generating process','original':'upstream filename/URL token','archive':'declared archive or retrieval route'}
 for item in raw:
  if item['branch']!='main':continue
  for k,v in item['global_attrs'].items():
   hits=[x for x in roles if x in k.lower()]
   if hits:fields.append(dict(case_id=item['case_id'],field=k,value=str(v),likely_role=roles[hits[0]],evidence=item['path']+' global attribute '+k,confidence='DIRECT',interpretation_caveat='DIRECT means attribute observed; upstream truth and byte identity are not independently proved'))
 write_csv(OUT/'PROVENANCE/main_source_fields_interpretation.csv',fields)
 ev=pd.DataFrame(events);tok=pd.DataFrame(tokens);co=pd.DataFrame(comps)
 summary=dict(artifact_count=len(inv),primary_artifact_count=int(sum(inv.evidence_relevance=='PRIMARY_LOCAL_LOG_OR_MANIFEST')),targeted_legacy_artifacts=3,selected_cases=len(selected_ids),selected_raw_files=len(selected),manifest_files=len(summaries),manifest_records=sum(x['records'] for x in summaries),manifest_parse_errors=len(errors),selected_manifest_events=len(events),manifest_status_counts=ev.status.value_counts().to_dict(),selected_events_size_match=int(sum(ev.size_matches_current==True)),selected_events_size_mismatch=int(sum(ev.size_matches_current==False)),selected_events_exact_path=int(sum(ev.same_literal_path)),saved_http_header_records=len(headers),log_files=len(logstats),log_lines=sum(x['lines'] for x in logstats),template_events=len(templates),script_or_tool_log_references=len(scriptrefs),legacy_index_rows=len(old),legacy_size_match_by_branch=co.groupby('branch').size_match.agg(['count','sum']).to_dict('index'),token_rows=len(tok),both_token_match=int(tok.both_current_token_match.sum()),direct_token_conflicts=int(tok.direct_token_conflict.sum()),stale_history_in_matched_pairs=int(tok.main_stale_history.sum()),model_family_match=int(tok.same_declared_gfs_family.sum()),acquisition_conversion_scripts_located=0,operational_release_status='NOT_ESTABLISHED')
 write_json(OUT/'logs/evidence_extraction_summary.json',summary);print(dumps(summary))
if __name__=='__main__':run()
