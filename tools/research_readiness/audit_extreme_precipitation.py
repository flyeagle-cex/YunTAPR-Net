"""Read existing 2024 evidence only; never import a model or run inference.

Writes new audit artifacts. Private absolute paths stay in an ignored local copy;
the public copy has verified repository paths and external-source aliases.
"""
import argparse,csv,hashlib,io,json,math,re,sqlite3,statistics,subprocess,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
MODELS=('B4','B7','B8');SEEDS=(2029,2030,2031)
NOMINAL=.984375

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def div(a,b):return a/b if b else None
def close(a,b):return a is not None and b is not None and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12)
def rates(c):
    t,p,n,z=(c[k] for k in ('TP','FP','FN','TN'))
    return dict(CSI=div(t,t+p+n),POD=div(t,t+n),FAR=div(p,t+p),Precision=div(t,t+p))
def table(headers,rows):
    def val(v):
        if v is None or v=='':return '未建立'
        if isinstance(v,float):return f'{v:.8g}'
        return str(v).replace('|','\\|').replace('\n',' ')
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join(['---']*len(headers))+'|']+['|'+'|'.join(map(val,r))+'|' for r in rows])
def xlsx_rows(p):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(p) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            for s in ET.fromstring(z.read('xl/sharedStrings.xml')):strings.append(''.join(t.text or '' for t in s.iter('{'+ns['m']+'}t')))
        sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));out=[]
        for row in sheet.findall('m:sheetData/m:row',ns):
            if not 7<=int(row.get('r'))<=37:continue
            d={}
            for c in row:
                v=c.find('m:v',ns);t=c.get('t');a=re.sub(r'\d','',c.get('r'))
                if t=='inlineStr':d[a]=''.join(x.text or '' for x in c.findall('.//m:t',ns))
                elif v is not None:d[a]=strings[int(v.text)] if t=='s' else v.text
            if d.get('A') in MODELS and d.get('C')=='E0':out.append(d)
        return out

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for key in ('private','index','output','private-output'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--reuse-checkpoint-validation',type=Path,help='Reuse this same audit initial byte-hash pass, conditional on size and no later mtime')
    a=ap.parse_args()
    if a.output.exists() or a.private_output.exists():raise PermissionError('Audit output must be a new directory')
    files={};rows=[];anomalies=[];checked={};data={};tails={};scoped_dirs=set();prior_hashes={}
    if a.reuse_checkpoint_validation:
        with a.reuse_checkpoint_validation.open(encoding='utf-8-sig',newline='') as f:
            prior_hashes={r['source_path']:r for r in csv.DictReader(f) if r['record_type']=='FILE' and r['metric']=='FIXED_E9_CHECKPOINT_BYTES_ONLY' and r['status']=='PASS_SHA256'}
    base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    def file(p,kind,expected='',hash_file=True):
        p=Path(p).absolute();key=str(p)
        if key in files:return files[key]['id']
        ident=f'F{len(files)+1:03d}';item=dict(id=ident,path=key,kind=kind,exists=p.is_file(),expected_sha256=expected,sha256='',bytes='',status='MISSING')
        files[key]=item
        if item['exists']:
            try:
                item['bytes']=p.stat().st_size
                cached=prior_hashes.get(key)
                if cached and kind=='FIXED_E9_CHECKPOINT_BYTES_ONLY' and cached['file_sha256']==expected and int(cached['value'])==item['bytes'] and p.stat().st_mtime_ns<=a.reuse_checkpoint_validation.stat().st_mtime_ns:
                    item['sha256']=cached['file_sha256'];item['hash_validation']='REUSED_INITIAL_BYTE_HASH_PASS_THIS_AUDIT_SIZE_AND_MTIME_UNCHANGED'
                else:item['sha256']=sha(p) if hash_file else 'NOT_REHASHED_SCHEMA_OR_LOCATION_ONLY'
                item['status']='PASS_SHA256' if expected and item['sha256']==expected else 'SHA256_MISMATCH' if expected and hash_file else 'FOUND'
            except OSError as error:item['status']='READ_ERROR';item['error']=str(error)
        if item['status'] in ('SHA256_MISMATCH','READ_ERROR'):anomalies.append(f'{ident}: {item["status"]}')
        return ident
    def emit(kind,model='',seed='',**kw):
        r=dict(record_type=kind,model=model,seed=seed,loss='E0' if model else '',epoch=9 if model else '',split='2024_Development',independent_events='NOT_IDENTIFIED',status='VERIFIED_SAVED_STATISTIC')
        r.update(kw);rows.append(r);return r
    index_id=file(a.index,'EXPERIMENT_INDEX','8cd976aa6e458e6f55b17dada9e7546a945260eeede39038341c6cacb142af86')
    index={(r['A'],int(float(r['B']))):r for r in xlsx_rows(a.index)}
    if set(index)!={(m,s) for m in MODELS for s in SEEDS}:raise ValueError('Index does not identify the nine requested E0 configurations')
    private_id=file(a.private,'PRIVATE_EXISTING_RESULT_LOCATOR');private=read(a.private)
    if a.reuse_checkpoint_validation:file(a.reuse_checkpoint_validation,'INITIAL_BYTE_HASH_PASS_OF_THIS_AUDIT')
    reg_id=file(private['registry'],'EXISTING_EVALUATION_REGISTRY',private['registry_sha256']);registry=read(private['registry'])
    runs=[r for r in registry['runs'] if (r['model'],r['seed']) in index]
    matrix_id=file(ROOT/'EXPERIMENT_MATRIX.csv','CONFIGURATION_MATRIX')
    with (ROOT/'EXPERIMENT_MATRIX.csv').open(encoding='utf-8-sig',newline='') as f:
        matrix={(r['model_id'],int(r['seed'])):r for r in csv.DictReader(f) if r['model_id'] in MODELS and r['seed'] in map(str,SEEDS) and r['loss_arm']=='E0'}
    metrics_id=file(ROOT/'METRICS.csv','SAVED_MASTER_METRICS')
    master={}
    with (ROOT/'METRICS.csv').open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r['record_type']=='RAW_ENDPOINT' and r['model_id'] in MODELS and r['seed'] in map(str,SEEDS) and r['loss_arm']=='E0' and r['group']=='all' and r['metric'] in ('brier','auroc','average_precision','conditional_pinball'):
                master[(r['model_id'],int(r['seed']),r['metric'])]=float(r['value'])
    source_files=['tools/research_readiness/audit_extreme_precipitation.py','src/yuntapr/data/imerg_v07.py','src/yuntapr/experimental/core_innovation/stage4/data.py','src/yuntapr/experimental/core_innovation/stage4/evaluation.py','src/yuntapr/experimental/research_readiness/tail_diagnostics.py','config/science_v2/phase_a_protocol_frozen_v1.json','config/spatial/sp04_coordinate_manifest_v1.json','config/spatial/sp04_coordinate_axes_v1.csv','config/spatial/sp04_target_cell_membership_v1.csv']
    for p in source_files:file(ROOT/p,'READER_OR_FROZEN_SPATIAL_CONFIGURATION')
    for p in ['SCIENTIFIC_ANALYSIS.md','docs/research_readiness/20261025/evidence/dote_control_three_seed_completion_20261029.json','docs/research_readiness/20261025/evidence/dote_physical_control_completion_20261030.json','docs/research_readiness/20261025/evidence/b7_b8_three_seed_completion_20261029.json']:file(ROOT/p,'INHERITED_SCIENTIFIC_RESULTS_NOT_REANALYZED')
    infer=Path(private['registry']).parent/'infer_eval.py';infer_id=file(infer,'EXISTING_POINT_AND_MIXTURE_METRIC_IMPLEMENTATION')
    infer_text=infer.read_text(encoding='utf-8');assert 'above_support = idx >= 32' in infer_text and 'out = p * (1.0 - f)' in infer_text
    source_identities=[];population_ids=[];mask_refs=[];train_orders={};scope_weather=0;scope_files=0;historical_times=[]
    for run in sorted(runs,key=lambda x:(MODELS.index(x['model']),x['seed'])):
        rid=run['run_id'];m=run['model'];s=run['seed'];mr=matrix[(m,s)]
        result_path=Path(private['inherited'][rid]['result']);result_id=file(result_path,'SAVED_THRESHOLD_AND_CONTINUOUS_RESULTS',private['inherited'][rid]['sha256']);result=read(result_path)
        dev_path=Path(run['dev_report_path']);dev_id=file(dev_path,'FIXED_E9_DEVELOPMENT_REPORT',run['dev_report_sha256']);dev=read(dev_path)
        cp=Path(run['checkpoint_path']);cp_id=file(cp,'FIXED_E9_CHECKPOINT_BYTES_ONLY',run['checkpoint_sha256'])
        receipt_path=cp.with_suffix('.receipt.json');receipt_id=file(receipt_path,'CHECKPOINT_RECEIPT');receipt=read(receipt_path)
        train_path=dev_path.parent/(m+'_train_09.json');train_id=file(train_path,'E9_TRAIN_AND_LOSS_RECEIPT');train=read(train_path)
        file(dev_path.parent/'completion.json','TRAINING_COMPLETION_METADATA')
        source_identities.append(dev['source_identity']);population_ids.append(dev['population_ids_sha256']);train_orders[(m,s)]=train['train_order_sha256']
        cp_ok=files[str(cp.absolute())]['status']=='PASS_SHA256'
        assert run['arm']=='E0' and receipt['epoch']==9 and receipt['updates']==4320 and train['updates']==4320 and train['loss_arm']=='E0' and train['scenes']==959 and train['batches']==480
        assert receipt['checkpoint_sha256']==index[(m,s)]['AF']==mr['checkpoint_reference']==run['checkpoint_sha256']
        assert result['status']=='COMPLETE' and result['gate']['passed'] is True and result['scenes_planned']==963
        assert dev['scope']=='2024_DEVELOPMENT_FIXED_F006_RETROSPECTIVE' and dev['groups']['all']['complete']
        for key in ('brier','auroc','average_precision','conditional_pinball'):
            assert close(master[(m,s,key)],dev['groups']['all']['summary'][key])
            assert close(result['gate']['metrics'][key]['recomputed'],dev['groups']['all']['summary'][key])
        if mr['global_steps']!='4320':anomalies.append(f'{rid}: matrix global_steps={mr["global_steps"]} is cumulative/replay accounting; E9 receipt effective updates=4320. Historical replay is not another seed.')
        config_path=Path(run['code_root'])/'config/science_v2/phase_a_protocol_frozen_v1.json';config_id=file(config_path,'EXECUTION_COPY_FROZEN_PROTOCOL');conf=read(config_path);mask_refs.append(conf['identity']['yunnan_mask'])
        # Enumerate only this E9 output and result directories, not raw-data trees.
        dirs=[dev_path.parent,result_path.parent];evaluation_dir=dev_path.parent/(m+'_evaluation_09')
        if evaluation_dir.is_dir():dirs.append(evaluation_dir)
        discovered=[]
        for folder in dirs:
            scoped_dirs.add(str(folder.absolute()))
            for p in folder.iterdir():
                if not p.is_file():continue
                if p.suffix.lower() in ('.npy','.npz','.parquet','.arrow','.h5','.hdf5') or any(t in p.name.lower() for t in ('pixel','prediction','event_catalog')):discovered.append(p)
                if folder==result_path.parent and p.name=='compact_metrics.csv':file(p,'SAVED_COMPACT_METRICS')
        if not discovered:emit('MISSING',m,s,group='PIXEL_PREDICTIONS',status='NOT_FOUND_IN_SCOPED_E9_AND_RESULT_DIRECTORIES',note='No joint (scene,pixel,y,p,q) export; full-disk absence is not claimed',source_id=dev_id,source_path=str(dev_path))
        for p in discovered:file(p,'POTENTIAL_PREDICTION_EXPORT_LOCATION_ONLY',hash_file=False)
        db=evaluation_dir/'all.sqlite'
        if db.is_file():
            db_id=file(db,'OCCURRENCE_SCORE_COUNTS_NOT_PIXEL_PREDICTIONS',hash_file=False)
            con=sqlite3.connect(db.absolute().as_uri()+'?mode=ro&immutable=1',uri=True)
            schema=con.execute("SELECT sql FROM sqlite_master WHERE type='table'").fetchall();con.close()
            emit('SOURCE_SCHEMA',m,s,group='EXACT_OCCURRENCE_SCORES',status='AGGREGATE_SCORE_COUNTS_NO_JOINT_RAIN_RATE_OR_COORDINATES',source_id=db_id,source_path=str(db),note=json.dumps(schema,ensure_ascii=False))
        tail_path=next((p for p in dev_path.parent.iterdir() if p.is_file() and p.name==m+'_tail_09.json'),None)
        if tail_path:
            tid=file(tail_path,'PER_SCENE_RAIN_STRATUM_SUFFICIENT_STATISTICS');tails[(m,s)]=(read(tail_path),tid,str(tail_path))
        else:emit('MISSING',m,s,group='PER_SCENE_TAIL',status='NO_E9_TAIL_FILE_FOUND',note='Aggregate rain strata exist in the Dev report; per-scene tail file absent',source_id=dev_id,source_path=str(dev_path))
        checked[(m,s)]=dict(checkpoint=cp_id,actual_sha256=files[str(cp.absolute())]['sha256'],checkpoint_ok=cp_ok,dev=dev_id,result=result_id,receipt=receipt_id,train=train_id,config=config_id,run=run)
        emit('CHECKPOINT_CONFIG',m,s,status='PASS' if cp_ok else 'CHECKPOINT_NOT_CURRENTLY_VERIFIED',source_id=';'.join((cp_id,receipt_id,train_id,config_id)),source_path=str(cp),checkpoint_sha256=run['checkpoint_sha256'],population_sha256=dev['source_identity']['population_sha256'],n_scenes=963,n_total=3303090,n_positive=407820,metric='effective_updates',value=4320,note=f'{mr["config"]};{mr["input_spec"]};parameters={mr["parameter_count"]};Train2/Dev8;seed={s};train_order_E9={train["train_order_sha256"]};execution={run["executed_commit"]}')
        data[(m,s)]=dict(run=run,dev=dev,result=result,dev_id=dev_id,result_id=result_id)
        scope_weather+=run['read_scope']['dev_pass_bytes'];scope_files+=run['read_scope']['dev_pass_files'];historical_times.append(result['elapsed_seconds'])
    assert len(set(json.dumps(x,sort_keys=True) for x in source_identities))==1 and len(set(population_ids))==1
    identity=source_identities[0]
    assert identity['train']==959 and identity['dev']==963 and identity['lead']==6 and identity['mode']=='retrospective'
    for s in SEEDS:assert len({train_orders[(m,s)] for m in MODELS})==1
    assert len(set(json.dumps(x,sort_keys=True) for x in mask_refs))==1
    mask_ref=mask_refs[0];mask_id=file(mask_ref['path'],'FROZEN_YUNNAN_ADMINISTRATIVE_MASK',mask_ref['sha256'])
    import netCDF4,numpy as np
    with netCDF4.Dataset(mask_ref['path']) as nc:mask=np.asarray(nc['yunnan_mask'][:],dtype=bool)[10:110,20:120]
    assert mask.shape==(100,100) and int(mask.sum())==3430
    first=next(iter(data.values()))['run'];prepared=read(first['private_preparation']['path'])['prepared'];dev_ids=prepared['roles']['Development']['ids'];train_ids=prepared['roles']['Train']['ids']
    file(first['private_preparation']['path'],'FROZEN_POPULATION_AND_PROTOCOL_PREPARATION')
    assert len(dev_ids)==963 and len(train_ids)==959 and all(x.startswith('2024-') for x in dev_ids)
    for d in data.values():assert [p[0] for p in d['dev']['groups']['all']['scene_blocks']]==dev_ids
    analyses=[datetime.fromisoformat(x)+timedelta(minutes=30) for x in dev_ids];assert set(t.hour for t in analyses)=={0,6,12,18}
    qc_path=ROOT/'docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv';qc_id=file(qc_path,'EXISTING_2023_2024_TARGET_QC',identity['target_QC_sha256'])
    with qc_path.open(encoding='utf-8-sig',newline='') as f:qc={r['window_start']:r for r in csv.DictReader(f) if r['window_start'] in set(dev_ids)|set(train_ids)}
    assert sum(int(qc[x]['imerg_valid_yunnan_count']) for x in dev_ids)==3303090
    qc_scenes={f'{op}{r}':sum((float(qc[x]['imerg_max_yunnan_mmhr'])>r if op=='>' else float(qc[x]['imerg_max_yunnan_mmhr'])>=r) for x in dev_ids) for r in (5,10,20,50) for op in ('>','>=')}
    assert qc_scenes['>=20']==208
    train_positive=sum(int(qc[x]['imerg_valid_yunnan_count'])-int(qc[x]['imerg_zero_yunnan_count']) for x in train_ids)
    train_rain=sum(int(qc[x]['imerg_rain_yunnan_count']) for x in train_ids)
    peak_truth=max(float(qc[x]['imerg_max_yunnan_mmhr']) for x in dev_ids)
    train_stats_path=Path(first['private_preparation']['stage3_run'])/'train_statistics.json';train_stats_id=file(train_stats_path,'EXISTING_2023_TRAIN_NORMALIZATION',identity['statistics_sha256']);train_stats=read(train_stats_path)
    assert train_stats['fit_years']==[2023] and train_stats['fit_role']=='Train'
    for t in (95,99):emit('MISSING',group='TRAIN_POSITIVE_RAIN_THRESHOLD',metric=f'P{t}_mm_h',status='NO_POOLED_TRAIN_POSITIVE_LABEL_VALUES_OR_QUANTILE_FOUND',source_id=train_stats_id,source_path=str(train_stats_path),note=f'Proposal only: quantile of all2023 Train valid&region R>0;N_positive={train_positive};R>0.1 sensitivity N={train_rain};no Dev/2025 threshold selection')
    raw=[]
    for (m,s),pack in data.items():
        result=pack['result'];dev=pack['dev'];nm=result['new_metrics'];rid=pack['run']['run_id'];cp_sha=pack['run']['checkpoint_sha256'];sid=pack['result_id'];path=str(Path(private['inherited'][rid]['result']))
        for item in nm['point_estimates']:
            row=emit('CONTINUOUS',m,s,group='ALL_SUPERVISED',method=item['candidate'],n_total=nm['N_valid'],n_positive=nm['N_rain'],n_scenes=963,MAE_mm_h=item['MAE_mm_h'],RMSE_mm_h=item['RMSE_mm_h'],Bias_mm_h=item['MeanBias_mm_h'],CC=item['Pearson_CC'],peak_underestimate_mm_h='',status='SAVED_NOT_FROZEN;EXTREME_CONDITIONAL_ERRORS_AND_PEAK_MISSING',source_id=sid,source_path=path,source_pointer='/new_metrics/point_estimates',checkpoint_sha256=cp_sha);raw.append(row)
            method=item['candidate'];zero_thresholds=[t for t in (5.,10.,20.) if nm['contingency'][method]['rows'][str(t)]['TP']+nm['contingency'][method]['rows'][str(t)]['FP']==0]
            if zero_thresholds:
                upper=float(np.nextafter(np.float32(min(zero_thresholds)),np.float32(np.inf)))
                emit('PEAK_UNDERESTIMATE_LOWER_BOUND',m,s,group='AT_TRUE_GLOBAL_PEAK',method=method,metric='peak_underestimate_lower_bound_mm_h',value=peak_truth-upper,n_total=nm['N_valid'],status='PROVEN_LOWER_BOUND_NOT_EXACT_PEAK_ERROR',source_id=sid+';'+qc_id,source_path=path+';'+str(qc_path),note=f'Truth global max={peak_truth};no float32 prediction above {min(zero_thresholds)};float64 upper conservatively uses nextafter={upper}')
                assert min(zero_thresholds)<=20
                c50=dict(TP=0,FP=0,FN=6,TN=nm['N_valid']-6)
                row=emit('CLASSIFICATION',m,s,group='ALL_SUPERVISED',method=method,threshold_mm_h=50.,truth_rule='R>50',prediction_rule=f'point_{method}>50',n_total=nm['N_valid'],n_positive=6,n_pixel_times=6,n_scenes=qc_scenes['>50'],**c50,**rates(c50),source_id=sid+';'+pack['dev_id'],source_path=path+';'+pack['run']['dev_report_path'],source_pointer='/new_metrics/contingency;/groups/all/summary/rain_strata/6',status='DERIVED_EXACT_FROM_NO_PRED_ABOVE20_AND_SAVED_N_R_GT50');raw.append(row)
                emit('CLASSIFICATION_PARTIALLY_IDENTIFIED',m,s,group='ALL_SUPERVISED',method=method,threshold_mm_h=50.,truth_rule='R>=50',prediction_rule=f'point_{method}>=50',n_total=nm['N_valid'],TP=0,FP=0,CSI=0.,POD=0.,n_scenes=qc_scenes['>=50'],source_id=sid+';'+pack['dev_id'],source_path=path+';'+pack['run']['dev_report_path'],status='FN_AND_TN_UNKNOWN_WITHOUT_EQUAL50;KNOWN_FN_AT_LEAST6',note='Exact0 CSI/POD because known positive count>=6, and all point predictions<50;not evidence for stable generalization')
        for method in ('A','B','C'):
            for threshold in (5.,10.,20.):
                c=nm['contingency'][method]['rows'][str(threshold)];assert c['N']==3303090 and sum(c[k] for k in ('TP','FP','FN','TN'))==c['N']
                derived=rates(c)
                for metric in ('CSI','POD','FAR'):assert derived[metric] is None and c[metric] is None or close(derived[metric],c[metric])
                row=emit('CLASSIFICATION',m,s,group='ALL_SUPERVISED',method=method,threshold_mm_h=threshold,truth_rule=f'R>{threshold:g}',prediction_rule=f'point_{method}>{threshold:g}',n_total=c['N'],n_positive=c['TP']+c['FN'],n_pixel_times=c['TP']+c['FN'],n_scenes=qc_scenes[f'>{int(threshold)}'],**{k:c[k] for k in ('TP','FP','FN','TN')},**derived,source_id=sid,source_path=path,source_pointer=f'/new_metrics/contingency/{method}/rows/{threshold}',checkpoint_sha256=cp_sha,status='SAVED_COUNTS_PRECISION_DERIVED;NOT_FROZEN');raw.append(row)
                # A classification at 0.5 is identifiable even without assigning
                # tail probabilities: above q32, P(R>r)<=1-tau32=1/64<0.5.
                # Keep it separate from a fully specified extreme probability.
                if method=='A':
                    block=nm['candidate_D'][str(threshold)];support=block['support'];old=block['supported_contingency'];outside_positive=c['TP']+c['FN']-old['TP']-old['FN'];outside=support['N_not_established']
                    assert 0<=outside_positive<=outside and support['N_supported']+outside==c['N']
                    full=dict(TP=old['TP'],FP=old['FP'],FN=old['FN']+outside_positive,TN=old['TN']+outside-outside_positive)
                    assert sum(full.values())==c['N']
                    row=emit('MIXTURE_DECISION_BOUND_COMPLETION',m,s,group='ALL_SUPERVISED',method='D_BOUND_PGE05',threshold_mm_h=threshold,truth_rule=f'R>{threshold:g}',prediction_rule='p*(1-F_cond(r))>=0.5;tail decision bound, not assigned tail probabilities',n_total=c['N'],n_positive=c['TP']+c['FN'],n_pixel_times=c['TP']+c['FN'],n_scenes=qc_scenes[f'>{int(threshold)}'],**full,**rates(full),source_id=sid+';'+infer_id,source_path=path,source_pointer=f'/new_metrics/candidate_D/{threshold}',status='DERIVED_FULL_POPULATION_DECISION_ONLY;NUMERIC_TAIL_PROBABILITIES_NOT_IDENTIFIED',note=f'Inherited support N={support["N_supported"]};tail N={outside};all monotone tail completions compatible with tau32 give negative at0.5');raw.append(row)
        summary=dev['groups']['all']['summary'];rs=summary['rain_strata'];assert len(rs)==7 and rs[6].get('n',rs[6].get('n_rain'))==6
        for label,indices in [('(0.1,1]',[0]),('(1,5]',[1]),('(5,10]',[2]),('(10,20]',[3]),('(20,30]',[4]),('(30,50]',[5]),('(20,50]',[4,5]),('>20',[4,5,6]),('>50',[6])]:
            n=sum(rs[k].get('n',rs[k].get('n_rain')) for k in indices);pin=sum(rs[k]['pinball_sum'] for k in indices)
            tail= tails.get((m,s));covered=sum(tail[0]['strata'][k]['q32_covered'] for k in indices) if tail else None
            row=emit('RAIN_STRATUM',m,s,group=label,method='CONDITIONAL_QUANTILES',n_pixel_times=n,n_positive=n,conditional_pinball=div(pin,n),q32_coverage=div(covered,n) if covered is not None else '',source_id=pack['dev_id']+(';'+tail[1] if tail else ''),source_path=pack['run']['dev_report_path']+(';'+tail[2] if tail else ''),source_pointer='/groups/all/summary/rain_strata'+(';/strata' if tail else ''),note='Conditional log1p Pinball, not physical MAE;coverage conditional on true rain band is descriptive, not required to equal nominal98.4375%;legacy strict-lower/closed-upper bins');raw.append(row)
        for name,g in dev['groups'].items():
            if name=='all':continue
            z=g['summary'];row=emit('SAVED_SCENE_OR_UTC_SUBGROUP',m,s,group=name,method='FROZEN_PROBABILITY',n_total=z['n_valid'],n_positive=z['n_rain'],n_scenes=z['scenes'],brier=z['brier'],auroc=z['auroc'],ap=z['average_precision'],conditional_pinball=z['conditional_pinball'],q32_coverage=z['coverage'][-1],q32_absolute_error=abs(z['coverage'][-1]-NOMINAL),source_id=pack['dev_id'],source_path=pack['run']['dev_report_path'],source_pointer='/groups/'+name,status='SCENE_SUBSET_NOT_INDEPENDENT_EVENT' if name=='scene_max_ge20' else 'SAVED_SUBGROUP');raw.append(row)
        if (m,s) in tails:
            tail,tid,tpath=tails[(m,s)];scenes=tail['scene_sufficient_statistics'];assert len(scenes)==963
            for label,indices in [('>5',[2,3,4,5,6]),('>10',[3,4,5,6]),('>20',[4,5,6]),('(20,50]',[4,5]),('>50',[6])]:
                active=[x for x in scenes if sum(x['strata'][k]['n_rain'] for k in indices)>0];n=sum(x['strata'][k]['n_rain'] for x in active for k in indices)
                emit('SAMPLED_WINDOW_COUNTS',m,s,group=label,n_pixel_times=n,n_scenes=len(active),source_id=tid,source_path=tpath,source_pointer='/scene_sufficient_statistics',note='Sample windows, not weather events')
            for label,z in tail.get('elevation_diagnostics',{}).get('bins',{}).items():
                row=emit('ELEVATION_MARGINAL',m,s,group=label,method='CONDITIONAL_QUANTILES',n_total=z['n_valid'],n_positive=z['n_rain'],brier=z['brier'],conditional_pinball=z['conditional_pinball'],q32_coverage=z['q32_coverage'],q32_absolute_error=abs(z['q32_coverage']-NOMINAL),source_id=tid,source_path=tpath,source_pointer='/elevation_diagnostics/bins/'+label,status='ALL_RAIN_ELEVATION_MARGINAL_NOT_EXTREME_X_ELEVATION');raw.append(row)
        for label in ('>=20','[20,50)','>=50','EVENT','EXTREME_X_ELEVATION','WINDWARD_LEEWARD','MOISTURE','EXTREME_MAE_RMSE_BIAS_AND_PEAK'):
            emit('MISSING',m,s,group=label,status='NOT_IDENTIFIABLE_FROM_EXISTING_SUFFICIENT_STATISTICS',source_id=pack['dev_id']+';'+sid,source_path=pack['run']['dev_report_path'],note='No exact equality boundary or joint pixel/event prediction statistics;no new inference performed')
    # Same-seed contrasts; no cross-year/pixel independence claims.
    available={(r['model'],r['seed'],r['record_type'],r.get('group'),r.get('method'),r.get('threshold_mm_h')):r for r in raw}
    pairs=[];numeric=('TP','FP','FN','TN','CSI','POD','FAR','Precision','MAE_mm_h','RMSE_mm_h','Bias_mm_h','CC','brier','auroc','ap','conditional_pinball','q32_coverage','q32_absolute_error')
    for newer,older in (('B7','B4'),('B8','B4'),('B8','B7')):
        for r in raw:
            if r['model']!=newer:continue
            b=available.get((older,r['seed'],r['record_type'],r.get('group'),r.get('method'),r.get('threshold_mm_h')))
            if not b:continue
            diffs={k:r[k]-b[k] for k in numeric if isinstance(r.get(k),(int,float)) and isinstance(b.get(k),(int,float))}
            pair=emit('PAIRED_DIFFERENCE',newer,r['seed'],comparison=newer+'−'+older,reference_model=older,group=r.get('group',''),method=r.get('method',''),threshold_mm_h=r.get('threshold_mm_h',''),truth_rule=r.get('truth_rule',''),prediction_rule=r.get('prediction_rule',''),original_record_type=r['record_type'],n_total=r.get('n_total',''),n_positive=r.get('n_positive',''),n_pixel_times=r.get('n_pixel_times',''),n_scenes=r.get('n_scenes',''),**diffs,source_id=r['source_id'],reference_source_id=b['source_id'],source_path=r['source_path'],reference_path=b['source_path'],source_pointer=r.get('source_pointer',''),reference_pointer=b.get('source_pointer',''),status='SAME_SEED_NEW_MINUS_REFERENCE;DESCRIPTIVE_ONLY');pairs.append(pair)
    grouped=defaultdict(list)
    for r in pairs:
        for metric in numeric:
            if isinstance(r.get(metric),(int,float)):grouped[(r['comparison'],r['original_record_type'],r['group'],r['method'],r.get('threshold_mm_h',''),metric)].append(r)
    for (comparison,kind,group,method,threshold,metric),members in grouped.items():
        values=[r[metric] for r in members];n=len(values);direction=-1 if metric in ('FAR','MAE_mm_h','RMSE_mm_h','brier','conditional_pinball','q32_absolute_error') else 1 if metric in ('CSI','POD','Precision','CC','auroc','ap') else 0
        emit('PAIRED_SEED_SUMMARY',comparison.split('−')[0],'ALL',comparison=comparison,original_record_type=kind,group=group,method=method,threshold_mm_h=threshold,truth_rule=members[0].get('truth_rule',''),prediction_rule=members[0].get('prediction_rule',''),metric=metric,value=statistics.mean(values),sample_sd=statistics.stdev(values) if n>1 else '',n_seeds=n,improved_seeds=sum(v*direction>0 for v in values) if direction else '',status='DESCRIPTIVE_N_MINUS_1_SD;NO_INDEPENDENT_EVENT_INFERENCE',source_id=';'.join(sorted(set(r['source_id'] for r in members))),source_path=';'.join(sorted(set(r['source_path'] for r in members))),reference_path=';'.join(sorted(set(r['reference_path'] for r in members))))
    all_file_status=Counter(x['status'] for x in files.values())
    def public_path(p):
        q=Path(p)
        try:return q.relative_to(ROOT).as_posix() if '.local' not in q.relative_to(ROOT).parts else 'LOCAL_ONLY/'+files[str(q.absolute())]['id']+'/'+q.name
        except (ValueError,KeyError):return 'LOCAL_ONLY/'+files.get(str(q.absolute()),{}).get('id','SCOPED_DIRECTORY')+'/'+q.name
    for f in files.values():emit('FILE',split='METADATA_OR_CHECKPOINT_ONLY',source_id=f['id'],source_path=f['path'],status=f['status'],metric=f['kind'],value=f['bytes'],file_sha256=f['sha256'],expected_sha256=f['expected_sha256'],note=f.get('hash_validation',''))
    thresholds=[r for r in rows if r['record_type']=='CLASSIFICATION' and r['method']=='A' and r['threshold_mm_h']<=20]
    detection_summaries=[r for r in rows if r['record_type']=='PAIRED_SEED_SUMMARY' and r['original_record_type']=='CLASSIFICATION' and r['method']=='A' and r['metric'] in ('CSI','POD') and r['threshold_mm_h'] in (5.,10.,20.)]
    context_summaries=[r for r in rows if r['record_type']=='PAIRED_SEED_SUMMARY' and (r['original_record_type']=='ELEVATION_MARGINAL' or r['group'] in ('scene_max_ge20','analysis_UTC_06')) and r['metric'] in ('brier','ap','conditional_pinball','q32_absolute_error')]
    pin_summaries=[r for r in rows if r['record_type']=='PAIRED_SEED_SUMMARY' and r['original_record_type']=='RAIN_STRATUM' and r['metric']=='conditional_pinball' and r['group'] in ('(20,30]','(30,50]','(20,50]','>50')]
    no20=[r for r in rows if r['record_type']=='CLASSIFICATION' and r['threshold_mm_h']==20]
    assert len(no20)==27 and all(r['TP']==r['FP']==0 and r['FN']==717 for r in no20)
    peak_bounds=[r for r in rows if r['record_type']=='PEAK_UNDERESTIMATE_LOWER_BOUND']
    assert len(peak_bounds)==27 and all(r['value']>48.05 for r in peak_bounds)
    headers=['模型','seed','r(mm/h)','TP','FP','FN','CSI','POD','FAR','Precision','真值像元时次']
    body=['# YunTAPR-Net V1.3 极端降水专项审计',f'审计基线提交：`{base_commit}`。只读已有证据，新训练/推理/原始气象及2025载荷读取均0。新输出不覆盖任何旧结果。完整私有路径只在本地版本保留，公开副本用可追溯源ID脱敏。',
    '**核心发现：九个模型、A/B/C三种点估计在严格>20mm/h均TP=0、FP=0、FN=717，CSI/POD=0；没有强雨点检出改进证据。B7相对B4的20–30、30–50条件Pinball仅改善2/3，B8相对B7仅改善1/3。总体指标收益不能提升为极端降水技能或物理机制结论。**',
    '## 1. 范围、身份与可识别性',
    f'以指定31配置Excel（{index_id}）选中B4/B7/B8各seed2029/2030/2031，E0、固定E9 LAST。九个检查点逐文件重新流式SHA256核对，未反序列化；结果如下。数据为2023 Train959、2024 Dev963，监督像元时次3,303,090、有雨像元时次407,820。9个Dev的完整source_identity、场景ID及同seed的E9训练顺序一致；原指标与METRICS.csv及保存的补算gate逐项相符。',
    table(['模型','seed','本次权重SHA通过','E9 SHA256','实际执行版本'],[(m,s,c['checkpoint_ok'],c['actual_sha256'],c['run']['executed_commit']) for (m,s),c in checked.items()]),
    f'共同人口SHA `{identity["population_sha256"]}`；Dev场景ID SHA `{population_ids[0]}`；归一化SHA `{identity["statistics_sha256"]}`；QC SHA `{identity["target_QC_sha256"]}`。行政区mask为GADM4.1中心点规则，文件SHA `{mask_ref["sha256"]}`，裁剪后100×100、3430有效点。数据valid与行政区region相交监督，不将地下压力层无效当作监督无效。配置检查是收据/执行副本/源代码与身份绑定；本轮未从权重内部重新提取架构。',
    f'标签窗口[T,T+30min)，分析时刻T+30min；实际窗口从 `{dev_ids[0]}` 至 `{dev_ids[-1]}`，分析时刻只含00/06/12/18UTC，GFS f006 retrospective（回顾估计）。不是业务全天近实时预报。',
    '## 2. 单位与边界',
    'IMERG读取器检查precipitation单位为`mm hr-1`并解码scale/offset；现存点估计结果明确为mm/h，本轮没有重开原始IMERG载荷。30分钟累计量=雨强×0.5h，因此5/10/20/50mm/h分别对应2.5/5/10/25mm每30分钟。现有标签已是雨强，不能再乘2。若报告累计量，MAE/RMSE/Bias相应乘0.5。',
    '原阈值统计严格使用float32 `Truth>r`与`Pred>r`；原雨强分层为(20,30]、(30,50]、(50,∞)。没有保存Truth/Pred恰等于20或50的联合计数，故不能将>20改写成>=20，也不能把(20,50]改写成[20,50)。建议后续要求的互斥层明确为[20,50)和[50,∞)，本轮不篡改旧边界。所有CSV行含truth_rule或明确的group。',
    '边界差异并非假设：QC的>20窗口为207个，>=20为208个，说明至少1个窗口的保存最大值恰等于20。>=20真实像元至少718个，但精确总数及预测恰等于20的联合分布未知。三seed看到的是相同标签人口，717或6不能乘seed数当成新增独立样本。',
    table(['观测范围','像元时次数','采样窗口数','独立天气事件数'],[['>5',thresholds[0]['n_positive'] if thresholds else None,qc_scenes['>5'],'NOT_IDENTIFIED'],['>10',next(r['n_positive'] for r in thresholds if r['threshold_mm_h']==10),qc_scenes['>10'],'NOT_IDENTIFIED'],['>20',next(r['n_positive'] for r in thresholds if r['threshold_mm_h']==20),qc_scenes['>20'],'NOT_IDENTIFIED'],['>=20','缺边界相等计数',qc_scenes['>=20'],'NOT_IDENTIFIED'],['>50',6,qc_scenes['>50'],'NOT_IDENTIFIED'],['>=50','缺边界相等计数',qc_scenes['>=50'],'NOT_IDENTIFIED']]),
    f'QC记录的全人口真值峰值为{peak_truth:.8g}mm/h。真实独立极端事件数量**无法由现存证据识别**；963个窗口、208个强雨窗口、35个周块和相关像元均不是独立暴雨事件。不能把NOT_IDENTIFIED填成0。',
    '## 3. 5/10/20mm/h分类',
    '下表展示A诊断代理，非科学选定的最终点估计。A/B/C三种方案全部逐seed原值、TP/FP/FN/TN、CSI/POD/FAR/Precision及配对差值在CSV中。FAR=FP/(TP+FP)，Precision=TP/(TP+FP)；无预测阳性时二者分母为0，留空而不填0。',
    table(headers,[[r['model'],r['seed'],r['threshold_mm_h'],r['TP'],r['FP'],r['FN'],r['CSI'],r['POD'],r['FAR'],r['Precision'],r['n_positive']] for r in thresholds]),
    'A方案的同seed分类差值（不选择最好seed；n=3为训练随机性，非三场暴雨）：',
    table(['比较','r(mm/h)','指标','Δ均值','样本SD','改善seed数'],[[r['comparison'],r['threshold_mm_h'],r['metric'],r['value'],r['sample_sd'],r['improved_seeds']] for r in detection_summaries]),
    '## 4. 连续误差与峰值',
    'A=p×mean(expm1(q))；B为混合中位数；C=p×expm1(mean(q))。C不是真实条件算术均值。三种点估计都未科学冻结。以下MAE/RMSE/Bias来自全部监督像元，**不是强雨条件误差**；Bias为Pred−Truth。',
    table(['模型','seed','方案','MAE(mm/h)','RMSE(mm/h)','Bias(mm/h)'],[[r['model'],r['seed'],r['method'],r['MAE_mm_h'],r['RMSE_mm_h'],r['Bias_mm_h']] for r in raw if r['record_type']=='CONTINUOUS']),
    '没有保存强雨条件下的逐像元点估计误差、逐事件峰值预测及其位置/时刻，不能从总体误差矩重建>=20/20–50/>=50的MAE/RMSE/Bias或精确峰值低估。q32_shortfall_log_sum是最高分位数在log1p尺度的欠幅充分量，不能冒充物理雨强峰值偏差。',
    '但可给严格的峰值低估**下界**：所有点预测都没有超过20的float32值，真值全域峰值68.0599976，因此真值峰值位置的预测低估至少约48.06mm/h。CSV还按各配置最紧的已保存“预测阳性为0”阈值给更紧下界；为覆盖float64预测转float32的舍入，预测上界保守取nextafter(threshold,+∞)。这不是精确误差，也不是模型之间优劣排名。',
    table(['模型','seed','A方案峰值低估下界(mm/h)'],[[r['model'],r['seed'],r['value']] for r in peak_bounds if r['method']=='A']),
    '同理可严格补出>50mm/h点分类：27种模型/seed/方案均TP=FP=0、FN=6、TN=3,303,084，CSI/POD=0。对>=50虽不知精确FN/TN，但已知真实阳性至少6且点预测均<50，因此TP/FP=0及CSI/POD=0仍可识别；CSV标PARTIALLY_IDENTIFIED，不伪造精确FN。样本稀少，不由此作稳定泛化或因果结论。',
    '## 5. 强雨、UTC、海拔与事件证据',
    '以下为实验组−参考组的条件Pinball三seed均值、样本标准差和改善seed数，负值表示改善。尺度为log1p(mm/h)，不是mm/h。保留所有模型/seed/层的原值与差值；>50层只有6个相关像元时次，方向仅描述。',
    table(['比较','真实雨强层','配对seed数','ΔPinball均值','样本SD','改善seed数'],[[r['comparison'],r['group'],r['n_seeds'],r['value'],r['sample_sd'],r['improved_seeds']] for r in pin_summaries]),
    '原scene_max_ge20含208个采样窗口，子集概率指标及四UTC均按既有分组完整收入CSV；它是强雨发生窗口子集，不是“仅强雨像元”或独立事件。逐场景尾部充分量在8/9目标模型找到，B4/2029缺少tail_09文件但聚合七层仍在Dev报告中。',
    '三个海拔分组(<1000、[1000,2000)、>=2000m)在B7/B8尾部文件中存在，只是全部有雨的边际统计；B4对应海拔结果未保存，且没有极端雨强×高程联合误差。因此只能给B8−B7的边际比较，不能声称B7/B8相对B4在高山极端降水已经改善。CSV对此单独标记。',
    '强雨窗口、06UTC和海拔边际的配对摘要如下。N是相同口径的实际可用seed数；q32误差为距名义水平的绝对误差。按真实雨强条件化的覆盖率仅作描述，不要求每个雨强层都达到名义覆盖。',
    table(['比较','分组','指标','配对n','Δ均值','样本SD','改善seed数'],[[r['comparison'],r['group'],r['metric'],r['n_seeds'],r['value'],r['sample_sd'],r['improved_seeds']] for r in context_summaries]),
    '迎风/背风和PWAT水汽条件没有联合误差充分量；少量工程缓存不能代表全963场景。不能凭DOTE输入存在就声称归因完成。现有精确概率SQLite仅按分数/周块聚合pos/neg，没有完整(scene,pixel,y,p,q)及事件追踪键。',
    '## 6. 极端概率识别的可用边界',
    '正确混合超阈概率是P(R>r)=p_occ×[1−F_cond(log1p(r))]，不能复用P(R>0.1)>=0.5。既有D表只保留q32以内CDF，模型间支持子集不同，原D子集率不得公平排名。',
    '本次另在CSV给出D_BOUND_PGE05：对q32以外或等于q32的阈值，任何与tau32=63/64一致的单调尾部补全均满足P(R>r)<=1/64<0.5，所以0.5决策必为阴性。保留原支持域TP/FP，将域外真实阳性加入FN，其余加入TN，可恢复同一全人口的0.5分类计数。此为条件分位数语义下的**决策界补全**，不是把域外概率设0，也没有恢复域外精确概率、极端Brier、AUROC或AP；不作为已冻结科学指标。',
    '## 7. Train P95/P99候选方案',
    f'建议先以2023 Train959个场景、同行政区/valid交集，汇集R>0mm/h的{train_positive}个正值像元时次，固定线性分位定义计算P95/P99；另以训练发生定义R>0.1的{train_rain}个像元时次作明确标注的敏感性方案。采用哪个正雨口径应在新增评价前冻结，不能看Dev结果再选择。当前Train归一化文件只有光谱/环境和PWAT尺度，没有正雨标签完整分布，故P95/P99数值NOT_COMPUTED。禁止拿逐场景最大值的分位数或Dev分位数替代像元正雨分布。',
    '## 8. 异常、缺失与最低补算范围',
    '\n'.join('- '+x for x in anomalies) if anomalies else '本次已用身份和阈值计数中未发现冲突；下述不可识别缺口仍存在。',
    '缺失：独立事件ID/追踪；等于20/50的标签和预测边界计数；强雨物理尺度连续误差与峰值；极端×高程、迎/背风、水汽联合统计；Train正雨P95/P99；完整数值尾部CDF。缺失项逐模型记录在CSV，不捏造指标。',
    f'优先下一步是**0个新增训练模型**：冻结事件与边界定义，然后只补一遍共享2023标签正雨统计，并对现有九份E9各一次2024 Dev前向，保存必要逐场景/逐像元联合预测或足够的交叉充分量。按本轮读取的九个既有read_scope清单合计，天气/掩膜逻辑读取参考为{scope_weather:,}字节/{scope_files:,}实例，另需六次静态包读取和九份检查点，不能套用九轮训练预算。既有九次补算的elapsed合计{sum(historical_times):.1f}秒仅供估时，不是新增授权或硬预算。本轮未执行。四UTC稀疏采样若不足追踪天气系统，还需独立事件目录/高频观测；不能只靠九次前向解决独立性。',
    '## 9. 最终科研判断',
    '1. **有证据的有限收益**：B7−B4在20–30和30–50的条件Pinball各改善2/3，三seed均值分别−0.00772516、−0.00733308；标准差约0.0322、0.0366，方向不稳定。B7在208个强雨发生窗口的总体Brier改善3/3，但窗口内也包含弱雨/无雨，不能等同极端雨强的概率校准改善。没有任何方案在>20点检出取得改善。',
    '2. **明确退化/不稳定**：A方案5mm/h的B7−B4 CSI均值−0.00291161，虽2/3 seed改善仍不稳定；B8−B4仅1/3改善、均值−0.00574371，B8−B7仅1/3改善、均值−0.00283210。B8−B7在20–30/30–50的Pinball均值分别+0.00466719/+0.00400148，均仅1/3改善。10mm/h漏报严重；>20全部漏报；>50的6个像元落在5个采样窗口，不能叫5场独立暴雨。FAR无定义不是零虚警优势。',
    '3. **DOTE主张缺口**：B7−B4同时增加静态地形、DOTE及融合，不能独立归因DOTE。已有ZERO三seed仅Brier3/3改善、排序/强雨不稳定；128无损失梯度权重限制保留，PERP仅单seed且有分布/空间混杂。尚缺可识别的物理对应关系控制和联合事件/空间误差证据。',
    '4. **DTFM主张缺口**：B8−B7是在同输入、同名义活跃参数量、同seed下替换融合；总体AUROC三seed方向一致不能替代极端命中、尾部校准、事件稳健性或独立年份验证。',
    '5. **是否训练**：现在不需要重训B0–B8或追加模块。先完成上述零训练评价缺口；若之后仍要宣称DOTE物理因果，另行设计控制有效容量和空间混杂的实验并申请预算，不能为改善Dev而追加强雨损失/seed。2025继续冻结，不擅自选择最终模型。',
    '## 10. 本次实际定位的源文件与查找范围',
    '下表列出本次实际打开/核验或定位的目标源文件，MISSING行明确区分未找到。范围限指定索引、九个E9输出和结果目录、其声明的配置/人口/掩膜；不是全磁盘扫描，未定位的联合明细只标“该范围未找到”，不声称电脑上绝对不存在。',
    '{{FILE_TABLE}}','\n逐项指标、缺失、路径、配置/权重校验、同seed差值及三seed统计见同目录`EXTREME_PRECIPITATION_AUDIT.csv`。所有源文件未覆盖。']
    # Keep the researcher's four decision questions after the source inventory.
    decision=body.index('## 9. 最终科研判断');inventory=body.index('## 10. 本次实际定位的源文件与查找范围')
    body=body[:decision]+[x.replace('## 10. 本次实际定位','## 9. 本次实际定位') for x in body[inventory:]]+[x.replace('## 9. 最终科研判断','## 10. 最终科研判断') for x in body[decision:inventory]]
    # Full and public versions share values; only path rendering differs.
    fieldnames=list(dict.fromkeys(k for r in rows for k in r))
    for folder,is_private in ((a.private_output,True),(a.output,False)):
        folder.mkdir(parents=True,exist_ok=False)
        lines=[]
        for f in files.values():lines.append([f['id'],f['kind'],f['path'] if is_private else public_path(f['path']),f['status'],f['bytes'],f['sha256']])
        text='\n\n'.join(body).replace('{{FILE_TABLE}}',table(['源ID','类别','实际路径/公开定位','状态','字节','SHA256'],lines))
        (folder/'EXTREME_PRECIPITATION_AUDIT.md').write_bytes((text+'\n').encode('utf-8'))
        with (folder/'EXTREME_PRECIPITATION_AUDIT.csv').open('x',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fieldnames);writer.writeheader()
            for row in rows:
                item=dict(row)
                if not is_private:
                    for k in ('source_path','reference_path'):
                        if k in item:item[k]=';'.join(public_path(p) for p in item[k].split(';') if p)
                writer.writerow(item)
    result=dict(status='COMPLETE_READ_ONLY_AUDIT_WITH_EXPLICIT_GAPS',base_commit=base_commit,checkpoints_verified=sum(x['checkpoint_ok'] for x in checked.values()),checkpoint_hashes_reused_from_this_audit_initial_pass=sum('hash_validation' in f for f in files.values()),scope_models=list(MODELS),seeds=list(SEEDS),input_files=len(files),file_status=dict(all_file_status),csv_rows=len(rows),pixel_prediction_scope_dirs=len(scoped_dirs),true_independent_events='NOT_IDENTIFIED',qc_sampled_window_counts=qc_scenes,truth_max_mm_h=peak_truth,training_updates=0,new_inference=0,raw_meteorological_loads=0,checkpoint_deserialization=0,final2025='FROZEN_NO_ACCESS',metadata_and_checkpoint_reads_only=True,weather_reference_bytes_next_evaluation=scope_weather,weather_reference_instances_next_evaluation=scope_files)
    (a.private_output/'validation.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__':main()
