"""Final-gate acceptance tests; reads evidence only, never executes old tasks."""
from pathlib import Path
import csv, hashlib, json
import numpy as np
import netCDF4
import pytest
import pyarrow.parquet as pq

RUN=Path(__file__).resolve().parents[1]
def j(rel):return json.loads((RUN/rel).read_text(encoding='utf-8'))
def c(rel):
 with (RUN/rel).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
A=j('DECISIONS/gate_assessment.json')
F=j('EVIDENCE/collected_facts.json')
REF={r['evidence_id']:r for r in c('evidence_registry.csv')}
DEC={d['id']:d for d in A['decisions']}
SCI=A['scientific_facts']
FREEZE=Path(REF['FREEZE']['source_file']).parent
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as fh:
  for b in iter(lambda:fh.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def test_all_frozen_have_actual_evidence_and_approval():
 for x in A['frozen_conventions']:
  assert x['status']=='FROZEN'
  assert x['evidence_ids'] and x['approval_evidence']
  for eid in x['evidence_ids']+x['approval_evidence']:
   r=REF[eid];assert Path(r['source_file']).is_file()
   assert sha(r['source_file'])==r['sha256']

def test_provisional_native_window_not_frozen():
 assert SCI['native_imerg_window_status']=='PROVISIONAL'
 assert DEC['D02']['status']=='RESEARCHER_DECISION_REQUIRED'
 assert not any('[T,T+30)' in f['rule'] for f in A['frozen_conventions'])
 assert 'candidate' not in [f['status'] for f in A['frozen_conventions']]

def test_unknown_statuses_not_upgraded_to_pass():
 master={x['item']:x for x in A['master']}
 assert master['external validation']['engineering_status']=='NOT_AUDITED'
 assert 'NOT_ESTABLISHED' in master['GFS vintage']['scientific_status']
 assert 'SUPPORTED_WITH_CAVEATS' in master['GFS provenance']['scientific_status']
 assert 'NOT_AUDITED' in master['Himawari']['scientific_status']

def test_candidate_bbox_does_not_become_formal():
 assert SCI['model_input_bbox'] is None
 assert not SCI['model_input_bbox_frozen'] and not SCI['context_margin_frozen']
 assert F['freeze']['common_numerical_overlap']['is_model_input_bbox'] is False
 assert F['freeze']['common_numerical_overlap']['designation']=='CANDIDATE COMMON NUMERICAL OVERLAP'

def test_primary_mask_from_existing_file_without_regeneration():
 reg=F['freeze'];p=FREEZE/reg['artifacts']['primary_mask']['relative_path']
 assert sha(p)==reg['artifacts']['primary_mask']['sha256']
 with netCDF4.Dataset(str(p),'r') as ds:
  mask=ds.variables['yunnan_mask'][:]
  assert ds.variables['yunnan_mask'].dimensions==('lat','lon')
  assert mask.shape==(130,140)
  assert int(np.asarray(mask,dtype=bool).sum())==3430
  with np.load(FREEZE/reg['artifacts']['coordinates']['relative_path']) as anchor:
   assert np.array_equal(ds.variables['lat'][:],anchor['lat'])
   assert np.array_equal(ds.variables['lon'][:],anchor['lon'])
  assert np.all(np.diff(ds.variables['lat'][:])>0)
 assert A['scope']['mask_generated'] is False

def test_intersection_never_primary():
 assert SCI['intersection_primary'] is False
 reg=F['freeze'];a=reg['artifacts']['intersection_comparison']
 assert 'NON_PRIMARY' in a['role'] and reg['intersection']['true_cells']==3752
 assert sha(FREEZE/a['relative_path'])==a['sha256']

def test_2025_october_remains_missing():
 assert SCI['imerg_202510_status']=='MISSING'
 assert F['imerg_202510']['count']==0
 assert DEC['D01']['blocks_formal'] and DEC['D01']['blocks_full_stage0']
 assert not DEC['D01']['blocks_smoke']

def test_gfs_release_and_historical_vintage_unknown():
 assert SCI['gfs_release_status']=='NOT_ESTABLISHED'
 s=F['statuses']['provenance']
 assert s['operational_release_status']=='NOT_ESTABLISHED'
 assert s['historical_operational_vintage_status']=='NOT_ESTABLISHED'
 assert s['vintage_rule_frozen'] is False and s['fixed_latency_hours'] is None

def test_thermo_approval_not_fabricated():
 assert SCI['main_thermo_researcher_approved'] is False
 assert SCI['gfs_main_thermo_status']=='PARTIALLY_COMPATIBLE'
 assert DEC['D09']['requires_researcher_decision']
 assert not DEC['D09']['blocks_formal']

def test_smoke_formal_requirements_separated():
 r=A['requirements'];s=r['B0_ENGINEERING_SMOKE_ENTRY'];f=r['B0_FORMAL_EXPERIMENT_ENTRY']
 assert s['status']=='READY' and f['status']=='NOT_READY'
 assert s['formal_science_metrics_allowed'] is False
 assert s['actual_execution']==f['actual_execution']=='NOT_RUN_THIS_TASK'
 assert len(s['required']) and len(f['required'])
 assert not any(d['blocks_smoke'] for d in A['decisions'])

@pytest.mark.parametrize('profile',['B0_ENGINEERING_SMOKE_ENTRY','B0_FORMAL_EXPERIMENT_ENTRY'])
@pytest.mark.parametrize('source',['GFS main','GFS thermo','GFS vintage','DEM','DOTE','DTFM','MEE'])
def test_gfs_dem_not_mandatory_b0(profile,source):
 p=A['requirements'][profile]
 assert source in p['not_required']
 assert p['model_input']==['Himawari B13 single time']

def test_2025_test_development_framework_preserved():
 assert SCI['final_test_year']==2025 and SCI['development_years']==[2023,2024]
 assert 'March–October' in next(f['scope'] for f in A['frozen_conventions'] if f['id']=='F15')

def test_exact_train_val_blocks_not_auto_frozen():
 assert not SCI['formal_train_val_blocks_frozen']
 assert SCI['exact_train_blocks'] is None and SCI['exact_validation_blocks'] is None
 assert DEC['D05']['requires_researcher_decision']

def test_all_registered_old_evidence_unchanged():
 before=j('logs/input_protection_before.json')
 for p,b in before.items():
  p=Path(p);s=p.stat()
  assert s.st_size==b['size_bytes'] and s.st_mtime_ns==b['mtime_ns']
  assert sha(p)==b['sha256']
 assert j('logs/integrity_summary.json')['old_run_write_operations']==0

def test_prior_failure_history_kept_and_not_pass():
 statuses=F['statuses']
 assert statuses['himawari_failed_history']['status']=='DRY_RUN_FAILED'
 assert statuses['himawari_failed_history']['engineering_status']=='FAILED_DEPENDENCY_GATE'
 assert 'DRY_RUN_FAILED' in Path(REF['REPORT_himawari_failed_history']['source_file']).read_text(encoding='utf-8-sig')

def test_all_targeted_fingerprints_consistent():
 rows=c('EVIDENCE/evidence_fingerprint_check.csv')
 assert len(rows)>=20
 assert all(r['status']=='CONSISTENT' for r in rows)
 assert F['fingerprint_conflicts']==[]

def test_latency_review_not_qc_failure_or_exclusion():
 assert SCI['latency_tail_count']==44 and SCI['latency_tail_exclusion'] is False
 assert DEC['R14']['category']=='D' and not DEC['R14']['blocks_formal']
 assert not DEC['R14']['requires_researcher_decision']
 assert 'not an exclusion criterion, QC threshold, or scientific threshold' in F['statuses']['p0']['p99_rule']

def test_stage_specific_blockers_not_all_now():
 assert DEC['D09']['due_stage']==DEC['D10']['due_stage']=='BEFORE_B4'
 assert DEC['D10']['blocks_full_stage0'] and not DEC['D10']['blocks_formal']
 assert DEC['D11']['due_stage']=='BEFORE_B5_B8' and not DEC['D11']['blocks_full_stage0']
 assert DEC['D12']['due_stage']=='BEFORE_FINAL_PAPER' and not DEC['D12']['blocks_formal']
 assert not DEC['D13']['blocks_full_stage0']

def test_external_not_audited_not_ready_or_missing():
 assert SCI['external_validation_status']=='NOT_AUDITED'
 assert not SCI['external_required_B0_smoke'] and not SCI['external_required_B0_formal_imerg_baseline']
 assert SCI['external_required_final_paper_independent_claim']
 unknown=[x for x in A['data_gaps'] if x['id']=='U01'][0]
 assert unknown['confirmed_gap'] is False

def test_no_unauthorized_next_stage_or_raw_access():
 assert A['scope']==dict(raw_files_opened=0,raw_scan=False,old_scripts_executed=False,mask_generated=False,B0_started=False,formal_dataset_created=False,dependencies_changed=False)
 assert j('logs/collection_log.json')['raw_directories_scanned']==0

def test_master_conclusion_traceability():
 for m in A['master']:
  assert all(k in m for k in ['engineering_status','scientific_status','frozen_status','evidence_ids','next_action'])
  for eid in m['evidence_ids']:assert 'MASTER:'+m['item']+':'+eid in REF

def test_research_cards_exact_required_sections():
 expected=['Decision','Why it matters','Current evidence','Options','Engineering consequence','Scientific consequence','What happens if deferred','Codex recommendation']
 ds=[d for d in A['decisions'] if d['requires_researcher_decision']]
 cards=list((RUN/'DECISIONS/cards').glob('*.md'));assert len(cards)==len(ds)
 for d in ds:
  lines=(RUN/'DECISIONS/cards'/f"{d['id']}.md").read_text(encoding='utf-8').splitlines()
  assert [l.removeprefix('## ') for l in lines if l.startswith('## ')]==expected

def test_schema_needs_update_no_formal_sample_database():
 assert A['schema_status']=='NEEDS_UPDATE'
 text=(RUN/'SCHEMA/sample_schema_readiness.md').read_text(encoding='utf-8')
 assert 'stage_profile' in text and 'B0' in text and 'spatial_freeze_id' in text
 assert not list(RUN.glob('**/*.sqlite')) and not list(RUN.glob('**/*.db'))

def test_matrix_matches_staged_dependencies():
 rows={r['item'].split(' ')[0]:r for r in c('STAGE0_CLOSEOUT_MATRIX.csv')}
 for d in A['decisions']:
  r=rows[d['id']]
  assert r['required_for_B0_smoke']==str(d['blocks_smoke'])
  assert r['required_for_B0_formal']==str(d['blocks_formal'])
  assert r['required_for_full_stage0_closeout']==str(d['blocks_full_stage0'])
  assert r['due_stage']==d['due_stage']

def test_csv_parquet_roundtrips_actual_files():
 results=j('logs/parquet_validation.json')
 assert results['engine']=='pyarrow' and results['pairs']
 for pair in results['pairs']:
  assert pair['exact_roundtrip']
  rows=c(pair['csv'])
  assert pq.read_table(RUN/pair['parquet']).to_pylist()==rows

def test_unreviewed_coverage_not_inferred_ready():
 assert F['source_month_status_counts']['Himawari_available']=={'NOT_AUDITED':23,'PARTIAL':1}
 assert DEC['E15']['blocks_formal'] and not DEC['E15']['requires_researcher_decision']
 assert DEC['E15']['status']=='ENGINEERING_EVIDENCE_REQUIRED'

def test_gaps_do_not_include_unfrozen_bbox_choices():
 assert not any('bbox' in g['item'].lower() or 'context' in g['item'].lower() for g in A['data_gaps'])
 assert all(g['status']=='NOT_AUDITED' for g in A['data_gaps'] if not g['confirmed_gap'])
