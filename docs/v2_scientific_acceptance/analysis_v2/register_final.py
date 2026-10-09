"""Register actual reviewed delivery; immutable original failure remains."""
import json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/run_20261009T112710_013267Z';OUT=RUN/'delivery_v2';REPO=ROOT.parents[1]
EXEC=REPO.parent/'YunTAPR-Net-v2-phase-a-execution'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def ident(p):
    with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
    return {'path':str(p.resolve()),'repository_path':str(p.relative_to(REPO)).replace('\\','/') if p.is_relative_to(REPO) else None,'bytes':p.stat().st_size,'sha256':sha}
def save(name,obj):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def main():
    assert read(OUT/'verification_tests_attempt_002.json')['status']=='PASS'
    assert read(OUT/'frozen_identity_closeout_audit.json')['status']=='PASS'
    configs=[]
    for rel,expected in [('config/science_v2/phase_a_protocol_frozen_v1.json','a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be'),('config/science_v2/quantile_head_v2_frozen_v1.json','3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e')]:
        v=ident(EXEC/rel);assert v['sha256']==expected;configs.append(v)
    save('frozen_protocol_and_head_closeout.json',{'status':'PASS','files':configs,'policy_changed':False})
    save('verification_test_reconciliation.json',{'status':'PASS','actual_successful_counts':{'pure_aggregate_unit_tests':11,'bootstrap_numerical_checks':3,'delivery_verification_tests':14},'total_successful_checks':28,'delivery_attempt_001':'12 pass / 2 fail; preserved','delivery_attempt_002':'14 / 14 PASS','correction':'AP in one positive-only stratum evaluates to 1.0000000000000002 by exact original float accumulation; assertion corrected to existing 1e-12 reporting tolerance without altering predictions or metrics. Governance assertion corrected to exact original equivalent wording.','current_result':'verification_tests_attempt_002.json','old_training_regression_suite_executed':False,'training_optimizer_steps':0})
    pages=[OUT/('render_final-'+str(i).zfill(2)+'.png') for i in range(1,12)]
    assert all(p.is_file() for p in pages)
    save('visual_delivery_audit.json',{'status':'PASS','method':'All 11 final PDF pages and all four full-resolution figure PNGs visually inspected through view_image; no clipped tables, overlaps or missing mathematical glyphs','PDF':ident(OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf'),'LaTeX':ident(OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE.tex'),'page_count':11,'reviewed_page_hashes':[ident(p) for p in pages],'figures':[ident(p) for p in (OUT/'figures').glob('*.png')],'compile_exit_code':0,'final_compile':'compile_pass_002.log','missing_characters':0,'overfull_boxes':0,'earlier_missing_leq_glyph':'Recorded in compile_pass_001.log; corrected in final PDF'})
    save('figure_final_status.json',{'status':'PASS','figure_count':4,'svg_count':4,'png_count':4,'inputs_and_outputs':'figure_provenance.json','visual_verification':'visual_delivery_audit.json','researcher_local_plot_exception':'LOCAL_SCIENTIFIC_PLOTTING_AUTHORIZATION.json'})
    for name,extra in [('PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md','\n## 完整图表与最终检查\n\n[可编辑 LaTeX](PHASE_A_SCIENTIFIC_ACCEPTANCE.tex) / [PDF](PHASE_A_SCIENTIFIC_ACCEPTANCE.pdf)；[配对分层差异表](PAIRED_STRATIFIED_COMPARISONS.csv)。当前 14 项交付检查见 verification_tests_attempt_002.json；首轮失败另行保留。\n'),('PROBABILITY_CALIBRATION_REPORT.md','\n![发生概率可靠性](figures/occurrence_reliability.png)\n\n![全部 32 tau 条件覆盖](figures/conditional_quantile_calibration.png)\n\n固定 bins 的低分值箱高估频率、中高箱低估频率。B1 的 q32 覆盖为约 0.95077，B0 约 0.95744，均低于 0.984375；不能以总体 Brier 改善自动认定校准通过。\n'),('UPPER_TAIL_PHYSICAL_REVIEW.md','\n![云南 q32 与 IMERG 监督参考](figures/inside_q32_vs_truth.png)\n\n[逐暴露诊断表](figures/inside_q32_gt50_observations.csv)保留真实干值零；未据此定义独立事件。\n')]:
        with (OUT/name).open('a',encoding='utf-8') as f:f.write(extra)
    status={'status':'SCIENTIFIC_ACCEPTANCE_EVIDENCE_READY_FOR_RESEARCHER_REVIEW','created_utc':datetime.now(timezone.utc).isoformat(),'completion_baseline':'166b1f86291bbcde167dbec30d3ae43ac23bba4c','BEST_epoch':{'B0_MATCHED_V2':9,'B1_V2':9},'validation_scenes_per_model':10501,'READ_ONLY_2024_INFERENCE_FORWARDS_ADDED':2626,'READ_ONLY_2024_RAW_SOURCE_OPENS':189018,'MODEL_PARAMETERS_UPDATED':False,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'FORMAL_OPTIMIZER_STEPS_ADDED':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,'V2_SCIENTIFIC_FREEZE_APPROVED':True,'V2_PHASE_B_AUTHORIZED':False,'FINALFIT_STARTED':False,'FORMAL_RESUME_STARTED':False,'RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED':True,'SCIENTIFIC_ACCEPTANCE_DECISION':'UNDECIDED','GOVERNANCE_DEVIATION_RESEARCHER_DISPOSITION':'UNDECIDED','terrain_stratification':'NOT_ESTIMABLE_NO_PREDEFINED_SUBREGION_MASK_AVAILABLE','independent_precipitation_events':'NOT_ESTIMABLE_NO_PREDEFINED_EVENT_CATALOGUE','verification_checks_passed':28,'PDF_VISUAL_VERIFICATION':'PASS','publication_status':'PENDING_COMMIT_AND_REMOTE_VERIFICATION','AUTOMATIC_NEXT_STAGE':False,'STOP_AFTER_PUBLICATION':True}
    save('final_status.json',status)
    def include(p):
        if not p.is_file():return False
        if p.suffix in {'.pt','.pth','.ckpt','.aux','.out','.tmp','.pyc'}:return False
        if any(x in p.parts for x in ('mpl_cache','__pycache__','fixtures')):return False
        if p.name.startswith('render_'):return False
        if p.name.startswith('monitor_') and p.suffix=='.log':return False
        if p.name.startswith('raw_access_') and p.suffix=='.jsonl':return False
        if p.name=='acceptance_manifest.json':return False
        return p.suffix in {'.py','.ps1','.json','.jsonl','.csv','.md','.txt','.tex','.pdf','.png','.svg','.npy','.npz','.gz','.log'}
    files=[p for p in ROOT.rglob('*') if include(p)]
    evidence=read(OUT/'frozen_identity_closeout_audit.json')
    save('acceptance_manifest.json',{'schema':'V2_PHASE_A_SCIENTIFIC_ACCEPTANCE_EVIDENCE_v1','created_utc':datetime.now(timezone.utc).isoformat(),'execution_scientific_scope':status,'artifacts':[ident(p) for p in sorted(files)],'sources_and_frozen_evidence':evidence,'protocol_and_head':configs,'manifest_self_hash':'Excluded to avoid recursive self-hashing; git blob SHA/commit binds this manifest','publication_allowlist_policy':'Only this independent scientific acceptance directory; raw access log originals local, lossless gzip published; no model/optimizer/checkpoint binaries or raw pixels','old_run_closeout_failure_preserved':ident(RUN/'closeout_failure.json')})
    print('Manifest registered; git remote publication still pending')
if __name__=='__main__':main()
