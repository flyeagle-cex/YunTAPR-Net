import json
from pathlib import Path
import pandas as pd
import pytest
from config import OUT,BASE_MAIN,BASE_THERMO,CACHE
from common import output_path,source_path,sha256
from provenance_rules import classify_evidence,operational_release,token_agreement,acquisition_link,vintage_candidates,CONFIDENCES

def table(rel):return pd.read_csv(OUT/rel,keep_default_na=False)
def data(rel):return json.loads((OUT/rel).read_text(encoding='utf8'))
@pytest.mark.parametrize('origin,expected',[('observed_attribute',('DIRECT_EVIDENCE','DIRECT')),('log',('DIRECT_EVIDENCE','DIRECT')),('official_document',('DIRECT_EVIDENCE','DIRECT')),('script_behavior',('INFERRED_FROM_SCRIPT','PARTIAL')),('filename',('INFERRED_FROM_FILENAME','PARTIAL')),('unrecognized',('NOT_ESTABLISHED','UNKNOWN'))])
def test_evidence_classification(origin,expected):assert classify_evidence(origin)==expected

def test_missing_script_never_direct():assert classify_evidence('script_behavior',False)==('NOT_ESTABLISHED','UNKNOWN')

@pytest.mark.parametrize('semantic',['LOCAL_DOWNLOAD','LOCAL_MANIFEST_EVENT','FILESYSTEM_MTIME','CONVERSION_TIME','FORECAST_REFERENCE_TIME','FORECAST_VALID_TIME','FORECAST_LEAD_DURATION','CONSERVATIVE_ASSUMPTION','ARCHIVE_TIME','HTTP_RESPONSE_DATE','UNKNOWN'])
def test_other_clocks_cannot_be_promoted_even_with_verification_flags(semantic):assert operational_release('2023-07-01T05:00:00Z',semantic,True,True) is None

def test_official_time_requires_identity_and_semantics():
 t='2023-07-01T04:00:00Z'
 assert operational_release(t,'OBSERVED_OFFICIAL_PUBLICATION',False,True) is None
 assert operational_release(t,'OBSERVED_OFFICIAL_PUBLICATION',True,False) is None
 assert operational_release(None,'OBSERVED_OFFICIAL_PUBLICATION',True,True) is None
 assert operational_release(t,'OBSERVED_OFFICIAL_PUBLICATION',True,True)==t

def test_upstream_tokens_match_cross_archive():
 assert token_agreement('https://x/gfs.20230701/00/atmos/gfs.t00z.pgrb2.0p25.f003','gfs.0p25.2023070100.f003.grib2','2023070100',3)=='MATCH'

def test_current_nc_filename_is_not_source_token():
 assert token_agreement('gfs_0p25_2023070100_f003.nc','gfs_thermo_0p25_2023070100_f003.nc','2023070100',3)=='UNKNOWN'

def test_wrong_original_cycle_or_lead_conflicts():
 assert token_agreement('gfs.0p25.2023070100.f006.grib2','gfs.0p25.2023070100.f003.grib2','2023070100',3)=='CONFLICT'

def test_logical_root_and_size_not_content_identity():
 assert acquisition_link(r'F:\old\raw\GFS\a.nc',r'F:\new\raw\GFS\a.nc',100,100)=='LOGICAL_CASE_ONLY_PHYSICAL_LINK_UNKNOWN'
 assert acquisition_link(r'F:\same\a.nc',r'F:\same\a.nc',100,100)=='SAME_PATH_SIZE_ONLY'
 assert acquisition_link(r'F:\same\a.nc',r'F:\same\a.nc',100,101)=='SIZE_MISMATCH_VERSION_LINK_UNKNOWN'

def test_candidates_do_not_freeze_or_set_x():
 assert data('TIME_AVAILABILITY/vintage_candidates.json')==vintage_candidates()
 assert all(not r['selected'] and not r['frozen'] and r['delay_hours'] is None for r in vintage_candidates())

def test_source_chain_preserves_unknown_conversion():
 t=table('PROVENANCE/provenance_chain.csv');assert set(t.confidence)<=CONFIDENCES
 c=t[t.stage=='conversion/subset script'];assert len(c)==2 and set(c.confidence)=={'UNKNOWN'}
 assert not any((t.evidence_type=='INFERRED_FROM_SCRIPT')&(t.confidence=='DIRECT'))

def test_real_time_inventory_never_claims_release():
 t=table('TIME_AVAILABILITY/time_evidence_inventory.csv');assert len(t)>=11
 assert set(t.usable_as_operational_release)=={False}
 assert {'CONSERVATIVE_ASSUMPTION','FILESYSTEM_MTIME','CONVERSION_TIME','LOCAL_MANIFEST_EVENT','FORECAST_REFERENCE_TIME','FORECAST_VALID_TIME'}<=set(t.semantic_class)

def test_actual_token_rows_not_nc_filename_only():
 t=table('PROVENANCE/original_filename_token_comparison.csv');assert len(t)==12960
 assert t.both_current_token_match.all() and t.same_declared_gfs_family.all() and not t.direct_token_conflict.any()
 assert (t.thermo_source_tokens!='[]').all()

def test_selected_case_coverage_and_consistency():
 t=table('PROVENANCE/forecast_case_trace.csv');assert len(t)==20
 assert set(t.period)=={'2023-03','2023-07','2024-01','2024-07','2025-03','2025-07','2025-10'}
 for _,g in t.groupby('period'):assert {'00','12'}<=set(g.init_time.str[11:13])
 for p,g in t.groupby('period'):
  if p!='2024-01':assert {0,3,6}<=set(g.lead)
 assert set(t.pairing_consistency)=={'PASS_CURRENT_TIME_AND_EXACT_COORDINATE_HASH'}

def test_event_failures_and_skips_not_hidden():
 t=table('TIME_AVAILABILITY/download_manifest_case_events.csv');assert len(t)==91
 assert {'failed','skipped','downloaded','complete'}<=set(t.status)
 l=table('PROVENANCE/case_acquisition_links.csv');assert not l.release_established.any()
 assert (l.operational_release_time=='').all()
 assert set(l.link_status)<= {'SIZE_MISMATCH_VERSION_LINK_UNKNOWN','SAME_PATH_SIZE_ONLY','LOGICAL_CASE_ONLY_PHYSICAL_LINK_UNKNOWN'}

def test_prior_stale_class_scope_not_overwritten():
 s=data('TIME_LINEAGE/history_token_summary.json');t=table('TIME_LINEAGE/history_token_scope_reconciliation.csv')
 assert s['prior_stale_history_class']==3628 and s['prior_auxiliary_conflicts']==17665
 assert len(t)==s['all_main_rows_with_any_stale_history_field']==11805
 assert s['matched_pair_stale_history_fields']==9385
 assert s['stale_rows_matching_logged_templates']==11803
 assert not t.real_primary_time_conflict.any()

def test_legacy_index_assumption_not_release():
 t=table('PROVENANCE/legacy_vintage_index_comparison.csv');assert len(t)==17640 and t.size_match.all()
 assert not t.legacy_index_is_release_evidence.any()
 assert set(t.content_identity)=={'NOT_ESTABLISHED'}

def test_old_run_output_guard():
 for p in [BASE_MAIN/'audit_final_status.json',BASE_THERMO/'audit_final_status.json',OUT.parent/'wrong_run.txt']:
  with pytest.raises(ValueError):output_path(p)

def test_only_selected_raw_paths_accepted():
 with pytest.raises(ValueError):source_path(r'F:\some_unselected_source.nc')

def test_old_baseline_hashes_are_still_equal():
 for r in data('logs/reused_baseline_hashes_before.json'):assert sha256(r['path'])==r['sha256']

def test_raw_artifact_and_environment_integrity():
 r=data('logs/integrity_verification.json')
 for k in ['all_selected_raw_unchanged','all_historical_artifacts_unchanged','all_baseline_hashes_unchanged','dependencies_unchanged','fixed_interpreter']:assert r[k]
 assert r['selected_raw_files_checked']==40 and r['historical_artifacts_checked']==219

def test_staging_bounded_and_empty():
 s=data('logs/staging_summary.json');assert s['copy_count']==40 and s['copied_bytes']==7510442
 assert s['max_single_temporary_bytes']<=s['bounded_limit_bytes']
 assert s['cleanup_failures']==s['remaining_staged_bytes']==s['remaining_file_count']==0
 assert s['all_copy_sha256_verified'] and s['all_reads_success'] and not list(CACHE.iterdir())

def test_all_csv_parquet_roundtrips_recorded_and_equal():
 t=table('logs/parquet_validation.csv');assert len(t)==22 and set(t.status)=={'PASS'}
 for r in t.itertuples():
  c=pd.read_csv(OUT/r.csv,dtype=str,keep_default_na=False);p=pd.read_parquet(OUT/r.parquet,engine='pyarrow');pd.testing.assert_frame_equal(c,p)
