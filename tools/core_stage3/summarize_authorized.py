"""Read-only reconciliation of completed receipts; never reopens weather sources."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,json,math,os,sqlite3,sys
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.core_innovation.stage3.planning import digest,utc,rainfall_summary


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)


def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def verified(path,key):
    value=read(path);body=dict(value);sha=body.pop(key)
    if digest(body)!=sha:raise ValueError('Artifact digest conflict')
    return value


def main(args):
    # This helper permits indexes, JSON receipts and SQLite only, including on failure.
    def audit(event,values):
        if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)):
            if os.fsdecode(values[0]).lower().endswith(('.nc','.hgt','.hgt.zip','.h5','.hdf5')):
                raise PermissionError('Cached-only reconciliation prohibits raw opens')
    sys.addaudithook(audit)
    run=args.run.resolve();request=verified(args.request,'request_sha256')
    if (request['total_new_source_files'],request['budget_round_up_bytes'])!=(15375,52683603968):raise ValueError('Wrong campaign')
    completion=read(run/'completion.json');pops=read(run/'populations.json');fit=read(run/'train_statistics.json')
    authorization=read(run/'authorization.json')
    if authorization['grant']['request_sha']!=request['request_sha256']:raise ValueError('Grant mismatch')
    if authorization['request_file_sha256']!=file_sha(args.request):raise ValueError('Request file changed')
    manifests={role:verified(args.request.parent/info['manifest'],'manifest_sha256') for role,info in request['roles'].items()}
    expected={}
    for role,m in manifests.items():
        if m['manifest_sha256']!=request['roles'][role]['manifest_sha256']:raise ValueError('Manifest changed')
        for f in [*m['satellite_files'],*m['gfs_files']]:
            if not f.get('new_read_needed',True):continue
            tail='/'+f['relative_path'].replace('\\','/').lower()
            if tail in expected:raise ValueError('Non-unique approved suffix')
            expected[tail]=dict(role=role,kind=f.get('kind','satellite'),bytes=f.get('expected_bytes',f.get('bytes')),sha=f.get('expected_sha256'))
    db=sqlite3.connect((run/'statistics.sqlite').as_uri()+'?mode=ro',uri=True)
    jobs=dict(db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state'))
    if jobs!={'COMPLETE':13453}:raise ValueError('Unfinished or uncertain jobs; do not retry')
    files=list(db.execute('SELECT path,state,expected_bytes,actual_bytes,sha256,prior_sha_available FROM file_io'))
    if len(files)!=len(expected) or len(files)!=15375:raise ValueError('Read set cardinality mismatch')
    expected_by_name={tail.rsplit('/',1)[-1]:tail for tail in expected}
    if len(expected_by_name)!=len(expected):raise ValueError('Ambiguous source basename')
    seen=set();by_role={};prior=Counter();actual_bytes=0
    for path,state,reserved,actual,sha,known in files:
        normal=path.replace('\\','/').lower();tail=expected_by_name.get(normal.rsplit('/',1)[-1])
        if tail is None or not normal.endswith(tail) or tail in seen:raise ValueError('Unlisted or duplicate source')
        e=expected[tail];seen.add(tail)
        if state!='READ_COMPLETE' or reserved!=actual or actual!=e['bytes'] or len(sha)!=64:raise ValueError('Incomplete measured read')
        if e['sha'] is not None and sha!=e['sha']:raise ValueError('Source hash conflict')
        c=by_role.setdefault(e['role'],{}).setdefault(e['kind'],dict(files=0,bytes=0));c['files']+=1;c['bytes']+=actual
        prior['matched_prior_sha' if known else 'first_observed_sha']+=1;actual_bytes+=actual
    if seen!=set(expected) or actual_bytes!=request['total_indexed_read_bytes'] or actual_bytes>request['budget_round_up_bytes']:raise ValueError('Final set/byte mismatch')
    qc=Counter();errors=Counter();dev_moment_violations=0;support={};job_years=Counter()
    for key,payload in db.execute('SELECT id,payload FROM jobs'):
        p=json.loads(payload);job_years[p['year']]+=1;qc[p['QC_status']]+=1;errors.update(p['QC_errors'])
        if p['year']==2024 and (p.get('moments') or p.get('pwat_positive_count')):dev_moment_violations+=1
        if key.startswith('gfs:'):support[key]=p
    db.close()
    if dev_moment_violations or set(job_years)!={2023,2024}:raise ValueError('Year/fitting leakage')
    joint=digest({r:sorted(pops['populations'][r]['accepted_ids']) for r in ('Train','Development')})
    if joint!=pops['joint_population_sha256'] or joint!=fit['population_sha256']:raise ValueError('Population fit binding conflict')
    if fit['fit_years']!=[2023] or fit['B13_refitted'] or len(fit['spectral_scalers'])!=7 or len(fit['environment_scalers'])!=13:raise ValueError('Statistics contract conflict')
    for s in fit['environment_scalers'].values():
        if not (s['count']>0 and math.isfinite(s['mean']) and math.isfinite(s['std']) and s['std']>0 and 0<s['valid_fraction']<=1):raise ValueError('Invalid environment moments')
    target=ROOT/'docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv'
    with target.open(encoding='utf-8-sig',newline='') as f:labels={r['window_start']:r for r in csv.DictReader(f)}
    roles={}
    for role,m in manifests.items():
        pop=pops['populations'][role];accepted=set(pop['accepted_ids']);records=[r for r in m['scene_records'] if r['sample_id'] in accepted]
        if digest(sorted(accepted))!=pop['population_sha256']:raise ValueError('Role population digest conflict')
        dist=rainfall_summary([dict(record=r) for r in records],labels)
        if dist!=completion['distributions'][role] or dist['qc_evidence_missing']:raise ValueError('Rainfall evidence mismatch')
        baseline={k:request['roles'][role]['rainfall_evidence'][k]+v for k,v in request['roles'][role]['loss_from_inherited_B1'].items()}
        high=[r for r in records if float(labels[r['sample_id']]['imerg_max_yunnan_mmhr'] or 0)>=20]
        reasons=Counter(reason for rs in pop['excluded'].values() for reason in rs)
        basepath=ROOT/'docs/b1_scientific_freeze/runs/run_20261003T045139_110133Z'/f"b1_{m['year']}_formal_manifest.csv"
        with basepath.open(encoding='utf-8-sig',newline='') as f:base_records=list(csv.DictReader(f))
        baseline_dist=rainfall_summary([dict(record=r) for r in base_records],labels)
        if any(baseline[k]!=baseline_dist[k] for k in baseline):raise ValueError('Inherited baseline mismatch')
        roles[role]=dict(population_sha256=pop['population_sha256'],candidate_scenes=len(m['scene_records']),actual_scenes=len(accepted),
            excluded_after_raw_QC=len(m['scene_records'])-len(accepted),exclusion_reasons=dict(reasons),distribution=dist,
            inherited_B1_distribution=baseline_dist,high_intensity_scene_retention=dist['scenes_max_ge_20_mm_h']/baseline['scenes_max_ge_20_mm_h'],
            total_scene_retention=len(accepted)/baseline['scenes'],
            high_intensity_analysis_utc_hour=dict(sorted(Counter(utc(r['analysis_time']).strftime('%H') for r in high).items())),
            high_intensity_month=dict(sorted(Counter(utc(r['analysis_time']).strftime('%Y%m') for r in high).items())))
    n=roles['Train']['actual_scenes'];v=roles['Development']['actual_scenes']
    budget=dict(status='PROPOSED_NOT_AUTHORIZED',models=['B3','B4'],seed_count=1,seed_value=None,loss_arm_candidate='E0',epochs=9,
        physical_batch=2,validation_batch=8,drop_last=False,gradient_accumulation=1,train_scenes=n,dev_scenes=v,
        updates_per_epoch_per_model=(n+1)//2,updates_per_model=9*((n+1)//2),paired_update_cap=18*((n+1)//2),
        validation_batches_per_epoch_per_model=(v+7)//8,paired_validation_batches=18*((v+7)//8),replay_allowance=0,inherited_allowance=0,
        wall_time_and_VRAM='Prior Stage2 shape checks are not runtime calibration for this actual population; no benchmark/optimizer executed',population_sha256=joint)
    if budget['paired_update_cap']!=completion['training_budget']['exact_optimizer_attempt_cap']:raise ValueError('Update budget mismatch')
    summary=dict(status='VERIFIED_COMPLETED_DATA_ONLY',base_commit='c5ccd52afb9f7890278109c28a93cd0d13760c5d',
        execution_code_commit='d8920ab78cf04834e6f3f95bf514779e59d8e41a',request_sha256=request['request_sha256'],joint_population_sha256=joint,
        actual_read_files=len(files),actual_read_bytes=actual_bytes,approved_max_bytes=request['budget_round_up_bytes'],unused_bytes=request['budget_round_up_bytes']-actual_bytes,
        file_states={'READ_COMPLETE':len(files)},job_states=jobs,source_hash_evidence=dict(prior),read_breakdown=by_role,
        source_job_QC=dict(qc),source_job_QC_errors=dict(errors),roles=roles,
        statistics=dict(status=fit['status'],new_spectral_variables=[k for k in fit['spectral_order'] if k!='B13'],
            new_band_count_each=fit['new_band_count_each'],scene_slot_exposures=fit['scene_slot_exposures'],B13_refitted=False,
            environment_order=fit['environment_order'],environment_units=fit['environment_units'],environment_valid_fractions={k:s['valid_fraction'] for k,s in fit['environment_scalers'].items()},
            fit_years=fit['fit_years'],dev_fit_contributions=0,T500_RH500='QC_AND_TRAIN_MOMENTS_READY_MODEL_ADAPTER_UNFROZEN',
            PWAT_positive_reference_kg_m2=fit['positive_PWAT_reference_kg_m2'],PWAT_positive_exposures=fit['positive_PWAT_count'],
            PWAT_reference_rule='Final 2023 Train valid positive scene-pixel exposure arithmetic mean; candidate only'),
        budget=budget,source_receipt_hashes={f:file_sha(run/f) for f in ('authorization.json','pilot_receipt.json','populations.json','train_statistics.json','completion.json')},
        completion_placeholder_correction='Use roles.*.inherited_B1_distribution; completion.baseline_descriptive_high_intensity mistakenly contains year placeholders and is not scientific evidence.',
        limitations=['Fixed f006 retrospective, historical release times unknown; no operational NRT claim.',
            'Inherited scene-max >=20 mm/h is descriptive; not independent storm events or high-intensity pixel counts.',
            '00/06/12/18 UTC analysis population only; cannot generalize to all hours or sealed 2025.',
            'Most GFS original inventories lacked source hashes; hashes established at authorized first read.',
            'Statistics and exact population do not approve science definitions, MEE13, optimizer or formal training.'],
        formal_training_launched=False,optimizer_updates=0,raw_2025_reads=0,target_payload_reads=0,raw_rereads_by_this_helper=0)
    out=args.output.resolve()
    if not out.is_relative_to(ROOT/'docs/core_stage3/.local'):raise PermissionError('Private final reconciliation must stay local')
    write(out,summary)
    print(json.dumps(dict(status=summary['status'],actual_files=len(files),actual_bytes=actual_bytes,populations={r:x['actual_scenes'] for r,x in roles.items()},paired_candidate_updates=budget['paired_update_cap'])))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--request',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
