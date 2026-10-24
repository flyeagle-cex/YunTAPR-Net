"""Existing-evidence-only manifests and one consolidated future read request."""
from pathlib import Path
import argparse, csv, hashlib, json, os, sys
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True; sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']=''; os.environ['OMP_NUM_THREADS']='1'; os.environ['MKL_NUM_THREADS']='1'
from yuntapr.experimental.core_innovation.stage3.planning import *
from yuntapr.data.dataset_b1 import FREEZE,AUDIT,PINS,FRAME_SHA,pinned
from yuntapr.experimental.core_innovation.stage2.coupling import TargetBinding

MAIN='stage0-b0-evidence/evidence/outputs/stage0_continuous_engineering/run_20260928T041855_828904Z/logs/gfs_source_manifest_before.csv'
THERMO='stage0-b0-evidence/evidence/outputs/stage0_gfs_thermo_compatibility/run_20260928T084334_575397Z/THERMO/gfs_thermo_inventory.csv'
TARGET='docs/b0_pretraining_closure/runs/run_20260930T095416Z/formal_sample_eligibility_2023_2024.csv'


def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))


def write(path,value):
    with path.open('x',encoding='utf-8') as f: json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--stage2-evidence',type=Path,required=True); args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/core_stage3/.local') or output.exists(): raise PermissionError('New ignored output directory required')
    # No NetCDF/HGT source or source-root metadata operation is needed here.
    attempts=[]
    def audit(event,values):
        if event=='open' and isinstance(values[0],(str,bytes,os.PathLike)):
            text=os.fsdecode(values[0]).lower().replace('/','\\')
            if text.endswith(('.nc','.hgt','.h5','.hdf5','.hgt.zip')):
                attempts.append(text);raise PermissionError('Stage3 planner forbids raw-source opens')
    sys.addaudithook(audit)
    main=forecast_index(csv_rows(ROOT/MAIN),kind='main');thermo=forecast_index(csv_rows(ROOT/THERMO),kind='thermo')
    pairs,pair_rejects=pair_index(main,thermo)
    index=json.loads(pinned(ROOT/AUDIT/'frame_identity_index.json',FRAME_SHA).read_text(encoding='utf-8'))
    frames={}; evidence_files=[ROOT/MAIN,ROOT/THERMO,ROOT/TARGET,ROOT/AUDIT/'frame_identity_index.json']
    for rel,sha in index['files'].items():
        if not re.fullmatch(r'native_frames/202[34](0[3-9]|10)\.csv',rel): raise PermissionError('Unexpected frame-index scope')
        source=pinned(ROOT/AUDIT/rel,sha); evidence_files.append(source)
        for f in csv_rows(source):
            if f['nominal'] in frames: raise ValueError('Duplicate nominal identity')
            frames[f['nominal']]=f
    target_index={r['window_start']:r for r in csv_rows(ROOT/TARGET) if utc(r['window_start']).year in (2023,2024)}
    prior=json.loads(args.stage2_evidence.read_text(encoding='utf-8'))
    prior_qc={r['evidence']['source_sha256']:r['evidence'] for r in prior['seven_band_checks'] if r['status']=='PASS_ONE_FRAME_ONLY'}
    output.mkdir(parents=True);report={};requests={};candidate_records={}
    for year in (2023,2024):
        source=pinned(ROOT/FREEZE/f'b1_{year}_formal_manifest.csv',PINS['B1',year]);evidence_files.append(source)
        all_scenes=scene_options(csv_rows(source),pairs);role='Train' if year==2023 else 'Development'
        baseline=rainfall_summary(all_scenes,target_index);groups={}
        for lead in (None,0,3,6):
            name='union_upper_bound' if lead is None else f'fixed_f{lead:03d}'
            indexed=select_by_lead(all_scenes,lead);selected=[];time_blocked=[]
            for scene in indexed:
                row=scene['record'];ff=[frames[row[f'slot_{i}_nominal']] for i in range(6)]
                try:
                    TargetBinding(utc(row['window_start']),utc(row['analysis_time']),tuple(utc(f['nominal']) for f in ff),
                        tuple(utc(f['obs_start']) for f in ff),tuple(utc(f['obs_end']) for f in ff))
                    selected.append(scene)
                except (ValueError,PermissionError) as exc:time_blocked.append(dict(sample_id=row['sample_id'],reason=str(exc)))
            satellite=satellite_manifest(selected,frames)
            # Real outputs and source lists remain local. No raw file is stat'ed.
            gfs={}
            for s in selected:
                for pair in s['options']:
                    if lead is None or pair['lead']==lead:
                        for kind in ('main','thermo'):
                            f=pair[kind]; gfs[(kind,f['relative_path'])]=dict(f,scope=role,verification='METADATA_ONLY')
            rain=rainfall_summary(selected,target_index)
            loss={k:baseline[k]-rain[k] for k in ('scenes','valid_target_pixels','rain_pixels_gt_0p1','scenes_with_rain','scenes_max_ge_20_mm_h')}
            qc_reused=0; required=[]
            for f in satellite['files']:
                verified=f['expected_sha256'] in prior_qc
                f['existing_stage2_seven_band_QC_reused']=verified
                f['statistics_cached']=False
                # A previously QC-checked Train source still needs statistics;
                # its values/moments were not persisted in Stage2. Dev does not fit.
                f['new_read_needed']=not verified or year==2023
                if verified: qc_reused+=1
                if f['new_read_needed']:required.append(f)
            group=dict(status='INDEX_UPPER_BOUND_NOT_VERIFIED_POPULATION',scenes=len(indexed),
                stage2_time_compatible_upper_bound=len(selected),time_adapter_blocked=time_blocked,
                satellite_unique_files=len(satellite['files']),scene_slot_exposures=satellite['scene_slot_exposures'],
                satellite_indexed_bytes=satellite['bytes'],satellite_new_read_files=len(required),
                satellite_new_read_bytes=sum(f['expected_bytes'] for f in required),stage2_QC_reused_files=qc_reused,
                missing_frame_evidence=len(satellite['missing']),gfs_files=len(gfs),gfs_indexed_bytes=sum(f['bytes'] for f in gfs.values()),
                rainfall_evidence=rain,loss_from_inherited_B1=loss,
                forbidden_raw_reads=0,final_population_sha256=None)
            groups[name]=group
            manifest=dict(year=year,role=role,lead_policy=name,status='CANDIDATE_NOT_FINAL',
                population_candidate_ids=[s['record']['sample_id'] for s in selected],
                scene_records=[s['record'] for s in selected],satellite_files=satellite['files'],gfs_files=list(gfs.values()),
                forecast_options=[dict(sample_id=s['record']['sample_id'],options=s['options']) for s in selected])
            manifest['manifest_sha256']=digest(manifest)
            write(output/f'manifest_{year}_{name}.json',manifest)
            if lead==6:
                candidate_records[role]=manifest['manifest_sha256'];requests[role]=dict(group,
                    manifest=f'manifest_{year}_{name}.json',manifest_sha256=manifest['manifest_sha256'])
        report[role]=dict(baseline=baseline,groups=groups,
            lead0_minus_lead6_ids=sorted(set(s['record']['sample_id'] for s in select_by_lead(all_scenes,0))-set(s['record']['sample_id'] for s in select_by_lead(all_scenes,6))),
            lead6_minus_lead0_ids=sorted(set(s['record']['sample_id'] for s in select_by_lead(all_scenes,6))-set(s['record']['sample_id'] for s in select_by_lead(all_scenes,0))))
    proposed_bytes=sum(r['satellite_new_read_bytes']+r['gfs_indexed_bytes'] for r in requests.values())
    proposed_files=sum(r['satellite_new_read_files']+r['gfs_files'] for r in requests.values())
    request=dict(status='PROPOSED_NOT_AUTHORIZED_DO_NOT_EXECUTE',recommended_vintage_candidate='FIXED_f006_RETROSPECTIVE_RESEARCHER_DECISION_REQUIRED',
        roles=requests,total_new_source_files=proposed_files,total_indexed_read_bytes=proposed_bytes,
        known_time_adapter_rejections_excluded_from_request=True,
        budget_round_up_bytes=((proposed_bytes+1024**2-1)//1024**2)*1024**2,
        raw_reads_this_round=0,raw_2025_reads=0,training_authorized=False,automatic_retry=False,
        per_satellite_file_cap=8*1024**2,per_GFS_file_cap=2*1024**2,
        failure_rule='No substitute sample or automatic reread; pending/crashed source needs explicit resolution',
        already_QC_Train_reread_reason='Stage2 did not retain sufficient statistics; one targeted statistics read is still necessary. Persist moments now to avoid all later rescans.',
        candidate_environment_variables=['pwat','cape','temperature850','temperature700','relative_humidity850','relative_humidity700','u850','v850','u700','v700','ps','temperature500','relative_humidity500'],
        environment_scope='Verify T500/RH500 and cache source-bound candidate moments using the SAME files. This does not approve a 13-channel model, new normalization definition or formal experiment.',
        GFS_previous_QC_reuse='Existing successful 11-channel checks remain evidence. Some previously read pairs need one new read for missing sufficient statistics or T500/RH500/support masks; arrays were not retained. No repeat of an unchanged completed source job is permitted once sufficient statistics are committed.',
        output_disk_reservation_bytes=512*1024**2,process_memory_reservation_bytes=512*1024**2,
        reservation_basis='Serial one-file decoding; raw <=8 MiB, 7x501x501 FP32+bool about8.4 MiB, six FP64 moment workspace <=24 MiB, no six-frame cube. 512 MiB is a conservative incremental workspace reservation, not measured total Python/runtime RSS. Local sufficient-statistic DB/receipts allowance 512 MiB; raw payload caching forbidden.',
        alternatives='Other fixed leads have their own immutable local manifests; changing vintage requires replacing this request, not silently adding reads.',
        target_payload_files_requested=0,DEM_files_requested=0,scientific_decision_id=None)
    request['request_sha256']=digest(request)
    summary=dict(scope='EXISTING_INDEX_AND_QC_EVIDENCE_ONLY',coverage=report,pair_index_rejects=pair_rejects,
        base_commit='e4563a0554ff6a6ffaaa8cc1e913cc005044688e',prior_stage2_receipt_sha256=hashlib.sha256(args.stage2_evidence.read_bytes()).hexdigest(),
        read_request='read_request_f006.json',budget=training_budget(),new_raw_source_opens=len(attempts),raw_2025_reads=0,
        caveats=['GFS source main index does not prove variable-level quality or historical release.',
                 'Union of leads is a coverage bound; not a fixed-vintage formal population.',
                 'All seven-band populations remain unverified; rainfall losses use prior target QC only.',
                 'Scene maximum >=20 mm/h is descriptive, not extreme-event or high-intensity pixel counts.'],
        evidence_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence_files})
    write(output/'population_preparation.json',summary);write(output/'read_request_f006.json',request)
    print(json.dumps(dict(coverage={r:{k:dict(scenes=v['scenes'],satellite_files=v['satellite_unique_files'],gfs_files=v['gfs_files']) for k,v in x['groups'].items()} for r,x in report.items()},
        recommended_request_files=proposed_files,recommended_request_bytes=proposed_bytes,new_raw_opens=len(attempts)),indent=2))
