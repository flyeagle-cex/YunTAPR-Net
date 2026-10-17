"""Package only this read-only analysis, without touching runtime/ledger files."""
from datetime import datetime,timezone
from pathlib import Path
import json,re,subprocess
from common import ROOT,OUT,read,save,sha

def main():
    tests=OUT/'tests';tests.mkdir(exist_ok=True)
    for attempt in (1,2):
        text=(OUT/f'.local/test_attempt_{attempt:03d}.txt').read_text(encoding='utf-8-sig',errors='replace')
        # Public logs omit private absolute source paths; retain failures/counts.
        text=re.sub(r'File ".*?test_analysis.py"','File "analysis/test_analysis.py"',text)
        (tests/f'attempt_{attempt:03d}.txt').write_text(text,encoding='utf-8')
    save('TEST_RESULTS.json',dict(initial=dict(run=16,passed=15,failed=1,reason='TEST_INDEX_SCHEMA_MISREAD'),
         final=dict(run=16,passed=16,failed=0),numeric_audit='PASS',receipts=54,contrasts=4,bootstrap_replicates=2000,
         pdf=dict(pages=12,terminal_xelatex='PASS',built_in_preview='UNAVAILABLE_SANDBOX_SPLIT_ROOTS',rendered_pages=12,visual_review='PASS'),
         figures=dict(count=10,formats=['SVG','PDF','PNG'],png_dpi=600),new_optimizer_updates=0))
    save('final_status.json',dict(status='SEED2026_SCIENTIFIC_ANALYSIS_DELIVERED',utc=datetime.now(timezone.utc).isoformat(),
        source_git_commit='dbccf220e8e88178388433e3d69e4e0e9682d652',
        six_epoch9_payload_sha='PASS',primary_payload_bytes=315858678,checkpoint_deserialization=False,
        independent_backup='NOT_VERIFIED',backup_search='ACCESSIBLE_NONEXCLUDED_NAMES_C_TO_H_WITH_SIX_PERMISSION_DENIALS',
        audited_epoch_receipts=54,primary_comparisons=4,paired_bootstrap='35_BLOCKS_2000_DRAWS_FIXED_SEED2026_EXACT_RECOMPUTATION_PASS',
        interpretation='2024_DEVELOPMENT_EXPLORATORY_SINGLE_SEED',hypothesis_HO='DIRECTIONAL_DEVELOPMENT_EVIDENCE_BOTH_MODELS',
        hypothesis_HQ='B0_DIRECTIONAL_EVIDENCE_B1_INTERVAL_CROSSES_ZERO',
        remaining_12_runs_started=False,additional_seed2026_training=False,new_optimizer_updates=0,
        model_inferences=0,raw_observation_content_reads=0,active_2025_child_attribute_queries=0,pixels_2025_read=0,
        historical_2025_path_attribute_access='NOT_INSTRUMENTED',historical_recovery_ratification='NOT_GRANTED',
        existing_ledgers_modified=False,source_or_frozen_evidence_modified=False,training_worker_processes_observed=0,
        unresolved=['INDEPENDENT_BACKUP_NOT_VERIFIED','FULL_SPAN_DISTRIBUTION_NOT_AVAILABLE','NO_INDEPENDENT_PHYSICAL_VALIDATION',
                    'SINGLE_SEED_NOT_MULTISEED_EVIDENCE','DRIVER_CRASH_AND_SLOW_EPOCH_ROOT_CAUSES_NOT_ESTABLISHED'],
        test_passed=16,test_failed_final=0,initial_failure_preserved=True))
    audit=read(OUT/'RECOMPUTATION_AUDIT.json');sources=dict(audit['sources'])
    code_roots=['src/yuntapr/experimental/phase_b_v2_ablations','src/yuntapr/experimental/phase_b_v2_formal_integration_candidate',
                'src/yuntapr/training/phase_b_v2_seed2026','src/yuntapr/training/phase_b_v2_seed2026_v2',
                'src/yuntapr/training/phase_b_v2_seed2026_resume_v2','src/yuntapr/training/phase_b_v2_seed2026_operator_v3']
    listed=subprocess.check_output(['git','ls-files',*code_roots],cwd=ROOT,text=True).splitlines()
    for name in listed:sources[name]=sha((ROOT/name).read_bytes())
    files={}
    for p in sorted(OUT.rglob('*')):
        relative=p.relative_to(OUT)
        if '.local' in relative.parts or '__pycache__' in relative.parts or not p.is_file():continue
        if p.name in ('manifest.json','texput.log') or p.suffix in ('.aux','.out','.log'):continue
        if p.suffix not in ('.py','.json','.md','.txt','.tex','.pdf','.svg','.png','.csv'):raise ValueError('UNREVIEWED_ARTIFACT_SUFFIX')
        raw=p.read_bytes()
        if p.suffix in ('.py','.json','.md','.txt','.tex','.svg','.csv'):
            # The repository deliberately uses '* -text' for frozen evidence.
            # Normalize only NEW analysis artifacts, never historical sources.
            raw=raw.replace(b'\r\n',b'\n');p.write_bytes(raw)
            if p.suffix=='.svg':raw=re.sub(rb'[ \t]+\n',b'\n',raw);p.write_bytes(raw)
            if re.search(rb'[A-Za-z]:[\\/](?:Users|pytorch|Data|data)[\\/]',raw):raise ValueError('PRIVATE_ABSOLUTE_PATH_IN_PUBLIC_OUTPUT:'+str(relative))
        files[relative.as_posix()]=dict(sha256=sha(raw),bytes=len(raw))
    save('manifest.json',dict(schema='SEED2026_ANALYSIS_V1',input_base_commit='dbccf220e8e88178388433e3d69e4e0e9682d652',
        public_sources_and_local_aggregate_receipt_sha256=sources,outputs=files,
        self_reference='manifest excluded from own hash; Git commit is authoritative publication identity',
        private_payloads_excluded=True,raw_observations_excluded=True))
    print(json.dumps(dict(outputs=len(files),source_identities=len(sources),status='PACKAGE_AUDIT_PASS')))

if __name__=='__main__':main()
