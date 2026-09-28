"""Readiness invariants and real coordinate/provenance checks; no ML execution."""
import copy, csv, hashlib, json, sys
from datetime import date,datetime
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import netCDF4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from contract_rules import validate_split, valid_target, normalization_scope_guard, formal_gate

RUN=Path(__file__).resolve().parents[1]
FREEZE=Path(r'F:\pytorch\Research\outputs\stage0_spatial_decision_update\run_20260928T102636_513428Z')
SMOKE=Path(r'F:\pytorch\Research\outputs\stage1_b0_engineering_smoke\run_20260928T121619_125413Z')
def readj(rel): return json.loads((RUN/rel).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest()
@pytest.fixture(scope='module')
def contract(): return readj('DATA_CONTRACT/b0_contract_candidate.json')
@pytest.fixture(scope='module')
def spatial():
    reg=json.loads((FREEZE/'freeze_registry.json').read_text(encoding='utf-8'))
    with np.load(FREEZE/reg['artifacts']['coordinates']['relative_path']) as z: lat,lon=z['lat'].copy(),z['lon'].copy()
    with np.load(RUN/'SPATIAL/himawari_actual_coordinates.npz') as z: hl,ho=z['latitude'].copy(),z['longitude'].copy()
    with netCDF4.Dataset(str(FREEZE/reg['artifacts']['primary_mask']['relative_path']),'r') as nc:
        mask=np.asarray(nc['yunnan_mask'][:],dtype=bool); ml=np.asarray(nc['lat'][:]); mo=np.asarray(nc['lon'][:])
    return reg,lat,lon,hl,ho,mask,ml,mo

def test_smoke_mapping_never_frozen(contract):
    assert contract['timing']['scientific_rule_frozen'] is False
    assert contract['timing']['smoke_mapping_status']=='ENGINEERING_SMOKE_TIME_MAPPING_ONLY'
    c=pd.read_csv(RUN/'TIME/b0_time_rule_candidates.csv')
    assert set(c.candidate_id)=={'T_START','T_CENTER','T_OTHER_REFERENCE','NOT_ESTABLISHED'}
    assert not c.selected.any() and not c.scientific_rule_frozen.any()

def test_gap_is_final_missing_not_late_substitute(contract):
    g=readj('GAPS/october_presence.json')
    assert g['status']=='MISSING' and not g['known_final_october_files']
    assert len(g['late_october_files'])==31 and not g['late_substitution']
    probe=next(x for x in readj('TIME/converted_metadata_probes.json') if 'imerg_late_20251001' in x['source'])
    assert probe['groups']['/']['attributes']['source']=='GPM_3IMERGHHL_07'
    assert not contract['gap']['research_period_changed'] and not contract['gap']['product_substituted']

def test_final_test_remains_2025_and_full_season(contract):
    assert contract['final_test_year']==2025
    assert contract['research_months']==[3,4,5,6,7,8,9,10]
    assert contract['development_years']==[2023,2024]

@pytest.mark.parametrize('candidate',readj('SPLIT/candidate_blocks.json'),ids=lambda c:c['candidate_id'])
def test_nonoverlapping_development_candidates(candidate):
    assert validate_split(candidate)
    for role,key in [('train','train_blocks'),('validation','validation_blocks')]:
        days=sum((date.fromisoformat(b)-date.fromisoformat(a)).days for a,b in candidate[key])
        assert candidate[role+'_calendar_days']==days
        assert candidate[role+'_nominal_halfhour_slots']==days*48
        assert candidate[role+'_imerg_inventory_days']==days
    assert candidate['buffer_hours_selected'] is None and not candidate['formal_sample_index_created']

@pytest.mark.parametrize('mutation',['test_year','overlap','season','selected'])
def test_split_guard_rejects_leakage(mutation):
    c=copy.deepcopy(readj('SPLIT/candidate_blocks.json')[0])
    if mutation=='test_year': c['train_blocks']=[['2025-03-01','2025-04-01']]
    elif mutation=='overlap': c['validation_blocks']=copy.deepcopy(c['train_blocks'])
    elif mutation=='season': c['train_blocks']=[['2023-01-01','2023-04-01']]
    else: c['selected']=True
    with pytest.raises(ValueError): validate_split(c)

def test_bbox_candidates_not_frozen(contract):
    assert contract['spatial']['formal_model_input_bbox'] is None
    assert not contract['spatial']['model_input_bbox_frozen'] and not contract['spatial']['context_margin_frozen']
    df=pd.read_csv(RUN/'SPATIAL/b0_input_domain_candidates.csv')
    assert len(df)==4 and not df.selected.any() and not df.scientific_rule_frozen.any()

def test_candidate_indices_shapes_coverage_and_padding(spatial):
    reg,lat,lon,hl,ho,mask,ml,mo=spatial
    idx=readj('SPATIAL/candidate_coordinate_indices.json')
    for r in pd.read_csv(RUN/'SPATIAL/b0_input_domain_candidates.csv').to_dict('records'):
        q=idx[r['candidate_id']]; ni=np.asarray(q['native_row_indices']); nj=np.asarray(q['native_col_indices'])
        ti=np.asarray(q['target_row_indices']); tj=np.asarray(q['target_col_indices'])
        assert np.array_equal(ni,np.flatnonzero((hl>=r['actual_native_south'])&(hl<=r['actual_native_north'])))
        assert np.array_equal(nj,np.flatnonzero((ho>=r['actual_native_west'])&(ho<=r['actual_native_east'])))
        assert mask[np.ix_(ti,tj)].sum()==3430
        assert [len(ni),len(nj)]==json.loads(r['native_shape'])
        assert [len(ti),len(tj)]==json.loads(r['target_shape'])
        assert hl[ni].min()>=20 and hl[ni].max()<=30 and ho[nj].min()>=97 and ho[nj].max()<=107
        for stride in (16,32):
            for group,rr,cc in [('native',len(ni),len(nj)),('target',len(ti),len(tj))]:
                er=r[f'{group}_extra_rows_if_stride{stride}']; ec=r[f'{group}_extra_cols_if_stride{stride}']
                assert 0<=er<stride and (rr+er)%stride==0
                assert 0<=ec<stride and (cc+ec)%stride==0

def test_frozen_mask3430_hash_and_true_coordinates(spatial):
    reg,lat,lon,hl,ho,mask,ml,mo=spatial
    assert mask.shape==(130,140) and int(mask.sum())==3430
    assert sha(FREEZE/reg['artifacts']['primary_mask']['relative_path'])=='9d921def661fc3e58cd1ed783fcf87abbf493da6ae5e5fea79c28043f73495ef'
    assert np.array_equal(lat,ml) and np.array_equal(lon,mo)
    assert np.all(np.diff(lat)>0) and np.all(np.diff(lon)>0) and np.all(np.diff(hl)<0)
    im=next(x for x in readj('TIME/converted_metadata_probes.json') if 'imerg_20240701.nc' in x['source'])['groups']['/']['variables']
    assert np.array_equal(lat,np.asarray(im['lat']['raw_values'],dtype=im['lat']['dtype']))
    assert np.array_equal(lon,np.asarray(im['lon']['raw_values'],dtype=im['lon']['dtype']))
    check=readj('SPATIAL/frozen_spatial_anchor_verification.json')
    assert not check['flip_applied'] and not check['transpose_applied'] and not check['coordinates_generated']
    assert sha(FREEZE/reg['artifacts']['intersection_comparison']['relative_path'])==reg['artifacts']['intersection_comparison']['sha256']
    assert reg['intersection']['is_primary_evaluation_mask'] is False

def test_normalization_defined_not_fitted(contract):
    n=contract['normalization']
    assert n['rule_defined'] and n['fit_roles']==['Train']
    assert not n['fitted'] and n['parameters'] is None and not n['scientific_method_frozen']
    assert n['missing_mask_required'] and n['exclude_invalid_from_fit'] and n['versioning_required']
    assert not n['test_feedback_allowed']
    assert normalization_scope_guard('Train',np.array([True,False]))

@pytest.mark.parametrize('role',['Validation','Test','Unassigned','train'])
def test_nontrain_statistics_rejected(role):
    with pytest.raises(ValueError): normalization_scope_guard(role,np.array([True]))

def test_zero_valid_missing_not_zero_no_mutation(contract):
    a=np.array([0.0,np.nan,-9999.9,2.5,np.inf]); before=a.copy()
    valid=valid_target(a,[-9999.9])
    assert valid.tolist()==[True,False,False,True,False]
    np.testing.assert_equal(a,before)
    assert contract['qc']['rain_zero_is_valid'] and not contract['qc']['missing_equals_zero']
    assert not contract['qc']['interpolation_allowed'] and contract['qc']['formal_thresholds'] is None

def test_sequence_metadata_not_six_frame_b0_requirement(contract):
    assert contract['qc']['sequence_metadata_preserved']
    assert not contract['qc']['six_frame_completeness_required_for_B0']

def test_no_gfs_dem_or_formal_model(contract):
    assert contract['inputs']==['Himawari_B13'] and contract['single_time']
    assert not any(x in contract['inputs'] for x in contract['prohibited_required_inputs'])
    assert not contract['architecture']['scientific_rule_frozen']
    assert not contract['architecture']['deterministic_default']
    assert not contract['architecture']['smoke_architecture_is_formal']
    assert not contract['formal_training_enabled']
    assert not contract['split']['formal_split_executed']

def test_causal_time_and_record_only_created():
    rows=pd.read_csv(RUN/'TIME/prior_smoke_time_evidence.csv')
    assert len(rows)==16
    for r in rows.to_dict('records'):
        assert datetime.fromisoformat(r['obs_end'])<=datetime.fromisoformat(r['candidate_analysis_time'])
        assert r['mapping_status']=='ENGINEERING_SMOKE_TIME_MAPPING_ONLY'
    assert readj('DATA_CONTRACT/b0_contract_candidate.json')['timing']['date_created_role']=='RECORD_ONLY'

def test_native_bounds_evidence_scope():
    df=pd.read_csv(RUN/'TIME/native_converted_time_comparison.csv'); f=df[df['product']=='Final']
    assert len(f)==9 and f.native_time_equals_bound_start.all() and f.converted_coordinate_equal.all()
    assert (f.duration_seconds==1800).all() and not f.formal_binding_frozen.any()
    assert (f.native_calendar==f.bounds_calendar_used).all()
    for r in f.to_dict('records'):
        assert datetime.fromisoformat(r['native_time'])==datetime.fromisoformat(r['filename_start'])
        assert datetime.fromisoformat(r['native_time'])==datetime.fromisoformat(r['header_start']).replace(tzinfo=None)
    probes=readj('TIME/native_metadata_probes.json')
    assert len([x for x in probes if 'error' in x])==1
    assert all('precipitation' not in k.lower() or 'raw_values' not in v for x in probes if 'groups' in x for g in x['groups'].values() for k,v in g['variables'].items())

def test_converted_has_no_native_bounds_but_no_global_claim():
    final=[x for x in readj('TIME/converted_metadata_probes.json') if 'imerg_late_' not in x['source']]
    assert len(final)==4
    for x in final:
        v=x['groups']['/']['variables']; assert 'bounds' not in v['time']['attributes']
        assert 'time_bnds' not in v and 'time_bounds' not in v
        assert 'raw_values' not in v['precipitation']

def test_all_old_registered_evidence_unchanged():
    records=readj('logs/immutable_inputs_before.json')
    assert len(records)==135
    for x in records:
        p=Path(x['path']); st=p.stat()
        assert st.st_size==x['size_bytes'] and st.st_mtime_ns==x['mtime_ns'] and sha(p)==x['sha256'],str(p)
    old=json.loads((SMOKE/'b0_smoke_status.json').read_text(encoding='utf-8'))
    assert old['engineering_status']=='PASS' and old['tests']['tests']==47

def test_staging_bounded_verified_clean_and_raw_unchanged():
    rows=[json.loads(x) for x in (RUN/'logs/staging.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(rows)==18
    for r in rows:
        assert r['size_verified'] and r['sha256_verified'] and r['source_unchanged']
        assert r['cleanup_success'] and not Path(r['temporary_path']).exists()
        assert r['before']==r['after']
        assert Path(r['temporary_path']).parent==(RUN/'cache/staging')
        assert sha(r['source'])==r['before']['sha256']

def test_discovery_limitations_not_absolute_absence():
    d=readj('logs/discovery_summary.json')
    assert d['access_errors']>0 and d['skipped_directories']>0
    assert set(d['drives'])=={'C:\\','D:\\','E:\\','F:\\','G:\\','H:\\'}
    text=(RUN/'GAPS/IMERG_2025_10_DECISION_CARD.md').read_text(encoding='utf-8')
    assert '未找到不等于全盘绝对不存在' in text

def test_entry_matrix_real_gate():
    entries=readj('DATA_CONTRACT/entry_matrix_machine.json')
    assert len(entries)==16 and not formal_gate(entries)
    assert sum(x['status']=='BLOCKED' for x in entries)==12
    assert all(x['blocking_reason'] and x['researcher_decision_required'] for x in entries if x['status']=='BLOCKED')
    assert all(x['status'] in ('PASS','BLOCKED') for x in entries)
    assert not formal_gate([])
    base=dict(item='synthetic',status='PASS',engineering_ready=True,scientific_rule_frozen=True,data_ready=True,researcher_decision_required=False)
    assert formal_gate([base])
    for key in ['engineering_ready','scientific_rule_frozen','data_ready']:
        changed={**base,key:False}; assert not formal_gate([changed])

def test_required_documents_and_card_sections():
    required=['TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md','GAPS/IMERG_2025_10_DECISION_CARD.md',
              'SPATIAL/B0_INPUT_DOMAIN_DECISION.md','SPLIT/B0_TRAIN_VAL_DECISION.md',
              'DATA_CONTRACT/b0_missing_qc_contract_candidate.md','DATA_CONTRACT/b0_normalization_contract.md',
              'MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md','RESEARCHER_DECISIONS_REQUIRED.md']
    assert all((RUN/p).is_file() for p in required)
    cards=list((RUN/'DECISIONS').glob('*.md')); assert len(cards)==10
    for p in cards:
        text=p.read_text(encoding='utf-8')
        for heading in ['Decision required','Current evidence','Options','Consequences','What is already frozen','What must not be changed automatically']:
            assert '## '+heading in text

def test_csv_parquet_candidates_agree():
    for rel in ['B0_FORMAL_ENTRY_MATRIX.csv','TIME/b0_time_rule_candidates.csv','SPATIAL/b0_input_domain_candidates.csv','SPLIT/b0_train_val_candidates.csv']:
        # CSV text contains round-trip precision; default C parser can lose one ULP.
        a=pd.read_csv(RUN/rel,keep_default_na=False,float_precision='round_trip'); b=pd.read_parquet((RUN/rel).with_suffix('.parquet'),engine='pyarrow')
        assert list(a.columns)==list(b.columns) and len(a)==len(b)
        for c in a.columns:
            assert a[c].astype(str).tolist()==b[c].fillna('').astype(str).tolist(),(rel,c)
