"""Metadata/aggregate verification only. No model import, forward or optimizer."""
import json,csv,hashlib,gzip,shutil,subprocess,unittest,io,ast
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; REPO=ROOT.parents[1]
RUN=ROOT/'runs/run_20261009T112710_013267Z'; OUT=RUN/'delivery_v2'
EXEC=REPO.parent/'YunTAPR-Net-v2-phase-a-execution'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def identity(p):return {'absolute_local_path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':digest(p)}
def write(name,value):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,ensure_ascii=False,indent=2)
def git(*args,root=REPO):return subprocess.check_output(['git','-c','core.longpaths=true',*args],cwd=root,text=True,encoding='utf-8').strip()
def rows(name):
    with (OUT/name).open(encoding='utf-8') as f:return list(csv.DictReader(f))
METRICS=read(RUN/'paired_best_metrics.json'); U=read(OUT/'paired_uncertainty.json'); MODELS=('B0_MATCHED_V2','B1_V2')
class EvidenceTests(unittest.TestCase):
    def test_full_published_metrics_exact(self):
        old=read(REPO/'docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/paired_best_metrics.json')
        for m in MODELS:self.assertEqual(METRICS['models'][m]['metrics'],old['models'][m]['metrics'])
    def test_same_complete_validation_identities(self):
        a,b=[METRICS['models'][m]['supplemental_statistics']['scene_ids'] for m in MODELS]
        self.assertEqual(a,b);self.assertEqual(len(a),10501);self.assertEqual(len(set(a)),10501)
        self.assertTrue(all(x.startswith('2024-') and 3<=int(x[5:7])<=10 for x in a))
    def test_model_state_and_counters(self):
        for v in METRICS['models'].values():
            self.assertEqual(v['model_state_sha256_before'],v['model_state_sha256_after'])
            for k in ('OPTIMIZER_STEPS','BACKWARD_CALLS','2025_RAW_ACCESS','2025_PIXELS_READ','staging_temporary_files_remaining'):self.assertEqual(v[k],0)
            self.assertFalse(v['MODEL_PARAMETERS_UPDATED']);self.assertFalse(v['V2_PHASE_B_AUTHORIZED'])
            self.assertEqual(v['BEST']['epoch'],9);self.assertEqual(v['REVIEW_FORWARD_CALLS'],1313)
    def test_pair_metrics_and_uncertainty(self):
        for v in U['comparisons']['ALL'].values():
            self.assertEqual(v['B1_minus_B0'],v['B1']-v['B0'])
            self.assertAlmostEqual(v['relative_percent_of_B0'],100*(v['B1']-v['B0'])/abs(v['B0']))
            ci=v['paired_difference_95_percentile_interval'];self.assertEqual(ci['valid_replicates'],2000);self.assertLessEqual(ci['lower'],ci['upper'])
        ci=U['comparisons']['ALL']['conditional_pinball']['paired_difference_95_percentile_interval']
        self.assertLess(ci['lower'],0);self.assertGreater(ci['upper'],0)
    def test_bootstrap_exact_paired_counts(self):
        a=np.load(RUN/'paired_bootstrap_block_multiplicities.npy',allow_pickle=False)
        self.assertEqual(a.shape,(2000,35));self.assertTrue(np.issubdtype(a.dtype,np.integer));self.assertTrue((a.sum(axis=1)==35).all());self.assertTrue((a>=0).all())
    def test_fixed_strata_partitions(self):
        data=rows('PAIRED_STRATIFIED_ANALYSIS.csv');self.assertEqual(len(data),44)
        for m in MODELS:
            vals={r['group']:r for r in data if r['model']==m};self.assertEqual(len(vals),22)
            for groups in ([g for g in vals if g.startswith('MONTH_')],['MAM','JJA','SO_PARTIAL_AUTUMN'],['CIVIL_DAY_PROXY','CIVIL_NIGHT_PROXY'],[g for g in vals if g.startswith('(') or g.startswith('DRY_')]):
                self.assertEqual(sum(int(vals[g]['N_valid']) for g in groups),36018430);self.assertEqual(sum(int(vals[g]['N_rain']) for g in groups),4496600)
            self.assertEqual(vals['DRY_LE_0.1']['conditional_pinball'],'')
            for g in vals:
                if g.startswith('('):self.assertEqual(vals[g]['AUROC'],'');self.assertEqual(float(vals[g]['AP']),1)
    def test_reliability_and_coverage_conditions(self):
        rel=rows('reliability_fixed_bins.csv');cov=rows('conditional_quantile_calibration.csv')
        for m in MODELS:
            rr=[r for r in rel if r['model']==m];cc=[r for r in cov if r['model']==m]
            self.assertEqual(len(rr),10);self.assertEqual(sum(int(r['count']) for r in rr),36018430)
            self.assertEqual(len(cc),32);self.assertEqual([float(r['tau']) for r in cc],[(i-.5)/32 for i in range(1,33)])
            self.assertTrue(all(int(r['N_rain'])==4496600 for r in cc))
            self.assertTrue(all(0<=float(r['coverage'])<=1 for r in cc))
            self.assertEqual(rr[-1]['observed_frequency'],'')
    def test_upper_tail_frozen_counts(self):
        ex=rows('upper_tail_exposure_units.csv');self.assertEqual(len(ex),20)
        for r in ex:
            v=METRICS['models'][r['model']]['upper_tail_diagnostics'][r['region']]['threshold_exceedances'][r['threshold_mm_h']]
            self.assertEqual(int(r['scene_pixel_tau_exposure']),v['scene_pixel_tau_exposure']);self.assertEqual(int(r['scene_pixel_any_tau_exposure']),v['scene_pixel_any_tau_exposure'])
            self.assertLessEqual(int(r['unique_grid_cells']),int(r['scene_pixel_any_tau_exposure']));self.assertIn('NOT_ESTIMABLE',r['independent_events'])
    def test_threshold_subset_observations_no_independent_event_claim(self):
        with (OUT/'figures/inside_q32_gt50_observations.csv').open(encoding='utf-8') as f:cs=list(csv.DictReader(f))
        counts={m:0 for m in MODELS}
        for c in cs:
            self.assertEqual(c['region'],'YUNNAN_INSIDE');self.assertGreater(float(c['q32_log']),np.log1p(50));counts[c['model']]+=1
        self.assertEqual(list(counts.values()),[653,957])
        c=[x for x in cs if x['model']=='B1_V2' and float(x['q32_log'])>np.log1p(100)]
        self.assertEqual(len(c),58);self.assertEqual(len({(x['row'],x['column']) for x in c}),44);self.assertEqual(len({x['sample_id'] for x in c}),28)
    def test_old_failed_closeout_preserved(self):
        for ref in read(OUT/'prior_closeout_preservation.json')['original_files']:
            p=Path(ref['path']);self.assertEqual(p.stat().st_size,ref['bytes']);self.assertEqual(digest(p),ref['sha256'])
        self.assertEqual(read(RUN/'closeout_failure.json')['status'],'ANALYSIS_CLOSEOUT_FAILED_STOP')
    def test_original_analysis_code_bindings(self):
        for name in ('analysis_code_binding.json','statistical_closeout_code_binding.json'):
            for path,sha in read(RUN/name).items():self.assertEqual(digest(Path(path)),sha)
    def test_figures_bound_to_actual_inputs(self):
        p=read(OUT/'figure_provenance.json')
        for ref in p['sources']+p['outputs']+[p['generator']]:self.assertEqual(digest(Path(ref['path'])),ref['sha256'])
        self.assertEqual(len(list((OUT/'figures').glob('*.png'))),4);self.assertEqual(len(list((OUT/'figures').glob('*.svg'))),4)
    def test_scientific_governance_and_no_false_acceptance(self):
        t=(OUT/'RECOVERY_GOVERNANCE_DEVIATION.md').read_text(encoding='utf-8');self.assertIn('不是独立恢复审批',t);self.assertIn('不能追认审批',t)
        self.assertFalse(read(OUT/'LOCAL_SCIENTIFIC_PLOTTING_AUTHORIZATION.json')['historical_recovery_retroapproval'])
        self.assertIn('未填写',(OUT/'RESEARCHER_SCIENTIFIC_DECISION_FORM.md').read_text(encoding='utf-8'))
        for p in OUT.glob('*.md'):self.assertNotIn('人口',p.read_text(encoding='utf-8'))
    def test_latex_compile_and_required_deliverables(self):
        for n in ('PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md','PAIRED_STRATIFIED_ANALYSIS.csv','PROBABILITY_CALIBRATION_REPORT.md','UPPER_TAIL_PHYSICAL_REVIEW.md','RECOVERY_GOVERNANCE_DEVIATION.md','RESEARCHER_SCIENTIFIC_DECISION_FORM.md','PHASE_A_SCIENTIFIC_ACCEPTANCE.tex','PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf'):
            self.assertTrue((OUT/n).is_file())
        log=(OUT/'compile_pass_002.log').read_text(encoding='utf-8',errors='replace')
        self.assertIn('(11 pages)',log);self.assertNotIn('Missing character',log);self.assertNotIn('Overfull',log)
        tex=(OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE.tex').read_text(encoding='utf-8');self.assertNotIn('人口',tex);self.assertIn('不自动验收',tex)
        self.assertEqual((OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf').read_bytes()[:5],b'%PDF-')

def main():
    buffer=io.StringIO();result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests))
    summary={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'console':buffer.getvalue(),'MODEL_FORWARD_CALLS':0,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'RAW_SOURCE_OPENS':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0}
    write('verification_tests.json',summary)
    if not result.wasSuccessful():raise RuntimeError(buffer.getvalue())
    pre=read(RUN/'pre_inference_identity.json');refs=pre['historical_checkpoint_and_epoch_artifacts']
    verified=[]
    for ref in refs:
        p=Path(ref['absolute_local_path']);actual=identity(p);assert actual['bytes']==ref['bytes'] and actual['sha256']==ref['sha256'];verified.append(actual)
    assert len(verified)==238
    completion=read(REPO/'docs/v2_phase_a_review/final_completion/run_20261009T083217_518899Z/FINAL_COMPLETION_AUDIT.json')
    cfg=[]
    for ref in completion['data_config_identities_reverified'].values():
        p=Path(ref['absolute_local_path']);actual=identity(p);assert actual['sha256']==ref['sha256'] and actual['bytes']==ref['bytes'];cfg.append(actual)
    scope=read(RUN/'B0_MATCHED_V2/inference_scope.json');code=[]
    for rel,sha in scope['code_sha256'].items():
        actual=identity(EXEC/rel);assert actual['sha256']==sha;code.append(actual)
    assert len(code)==74
    assert git('rev-parse','HEAD',root=EXEC)=='a1af0325b481202941c57e8fc94f3b20e441630a'
    assert not git('status','--porcelain','--untracked-files=normal',root=EXEC)
    assert git('rev-parse','HEAD')=='166b1f86291bbcde167dbec30d3ae43ac23bba4c'
    assert not git('diff','--name-only')
    write('frozen_identity_closeout_audit.json',{'status':'PASS','created_utc':datetime.now(timezone.utc).isoformat(),'execution_commit':git('rev-parse','HEAD',root=EXEC),'publication_baseline':git('rev-parse','HEAD'),'source_code_files':code,'data_config_files':cfg,'historical_checkpoint_and_epoch_artifacts':verified,'checkpoint_deserializations':0,'raw_source_opens':0,'proof_scope':'Current closeout byte hashes; inference before/after state receipts registered separately. No claim that unrelated unregistered drive files were enumerated.'})
    compressed=[]
    for m in MODELS:
        for p in sorted((RUN/m).glob('raw_access_*.jsonl')):
            output=p.with_suffix('.jsonl.gz')
            with p.open('rb') as a,output.open('xb') as b:
                with gzip.GzipFile(filename='',fileobj=b,mode='wb',mtime=0) as g:shutil.copyfileobj(a,g)
            with gzip.open(output,'rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==digest(p)
            compressed.append({'source':identity(p),'compressed':identity(output),'decompressed_sha_verified':True})
    write('compressed_io_evidence_registry.json',{'status':'LOSSLESS_GZIP_VERIFIED','files':compressed,'scope':'2024 source access metadata only, no raw pixel values; originals remain on local disk'})
    comparison=[]
    for group,items in U['comparisons'].items():
        for metric,v in items.items():
            comparison.append({'group':group,'metric':metric,'B0':v['B0'],'B1':v['B1'],'B1_minus_B0':v['B1_minus_B0'],'relative_percent_of_B0':v['relative_percent_of_B0'],**{'delta_'+key:value for key,value in v['paired_difference_95_percentile_interval'].items()},**{'relative_'+key:value for key,value in v['paired_relative_difference_95_percentile_interval'].items()},'scope':'EXPLORATORY_DEVELOPMENT_ONLY'})
    with (OUT/'PAIRED_STRATIFIED_COMPARISONS.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(comparison[0]));w.writeheader();w.writerows(comparison)
    write('io_reconciliation.json',{'status':'PASS','models':{m:METRICS['models'][m]['io'] for m in MODELS},'READ_ONLY_2024_FORWARDS_ADDED':2626,'READ_ONLY_2024_RAW_SOURCE_OPENS':189018,'READ_ONLY_2024_NATIVE_DECODES':115513,'CLOSEOUT_MODEL_FORWARD_CALLS':0,'CLOSEOUT_RAW_SOURCE_OPENS':0,'BACKWARD_CALLS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'proof_scope':'Controlled new analysis parent/worker accesses; aggregate/report/closeout operations use only saved evidence'})
    print('14 artifact tests PASS; 238 historical artifacts + 74 code files + 11 data/config identities rehashed; gzip roundtrip verified')
if __name__=='__main__':main()
