"""New closeout attempt; preserves failed v1 and never imports model code."""
import json, hashlib, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/run_20261009T112710_013267Z'
OUT=RUN/'delivery_v2'
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def identity(p):
    return {'path':str(p.resolve()),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,data):
    with p.open('x',encoding='utf-8',newline='\n') as stream:
        if isinstance(data,str): stream.write(data)
        else: json.dump(data,stream,ensure_ascii=False,indent=2)

def main():
    assert read(RUN/'paired_best_metrics.json')['status']=='PAIRED_SCIENTIFIC_ACCEPTANCE_READ_ONLY_2024_PASS'
    assert read(RUN/'paired_uncertainty.json')['status']=='EXPLORATORY_DEVELOPMENT_ANALYSIS_COMPLETE'
    failed=read(RUN/'closeout_failure.json'); assert failed['status']=='ANALYSIS_CLOSEOUT_FAILED_STOP'
    OUT.mkdir()
    originals=[identity(p) for p in RUN.iterdir() if p.is_file()]
    write(OUT/'prior_closeout_preservation.json',{'status':'FAILED_V1_PRESERVED','cause':'TypeError: frozen protocol prose variable was shadowed by threshold-count dictionary during report generation','new_scope':'Report rendering only; no inference, bootstrap rerun or training','original_files':originals})
    write(OUT/'LOCAL_SCIENTIFIC_PLOTTING_AUTHORIZATION.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'researcher_reply':'批准上述所有申请','interpreted_scope':'Current task local scientific matplotlib figures; read-only aggregate data and editable LaTeX/PDF delivery','historical_recovery_retroapproval':False,'scientific_acceptance_granted':False,'V2_PHASE_B_AUTHORIZED':False,'2025_RAW_ACCESS':0})
    for name in ['PAIRED_STRATIFIED_ANALYSIS.csv','paired_uncertainty.json','reliability_fixed_bins.csv','conditional_quantile_calibration.csv','RECOVERY_GOVERNANCE_DEVIATION.md','recovery_governance_source_audit.json','recovery_best_chronology_note.json','stratification_definition_audit.json']:
        shutil.copyfile(RUN/name,OUT/name)
    # Minimal documented correction, published separately from original bound code.
    code=(ROOT/'analysis_v1/build_reports.py').read_text(encoding='utf-8')
    code=code.replace("p.add_argument('--run',type=Path,required=True);args=p.parse_args();r=args.run", "p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();r=args.run;d=args.output")
    code=code.replace("write(r/", "write(d/").replace("with (r/'upper_tail_exposure_units.csv').open('x'", "with (d/'upper_tail_exposure_units.csv').open('x'")
    code=code.replace("frozen=t['threshold_exceedances'][str(threshold)]", "frozen_counts=t['threshold_exceedances'][str(threshold)]")
    code=code.replace("[frozen['scene_pixel_tau_exposure'],frozen['scene_pixel_any_tau_exposure']]", "[frozen_counts['scene_pixel_tau_exposure'],frozen_counts['scene_pixel_any_tau_exposure']]")
    code=code.replace('若 figure_provenance.json 尚不存在，图表仍待网页 GPT 界面授权或研究者批准本轮本地科学绘图；数据表已计算，不将未生成的图表标记为完成。figure_provenance_pending.json 保留工具访问限制。', '研究者已批准本轮本地科学绘图；原网页访问限制记录保留在上一级目录。只有 figure_provenance.json 和 visual_delivery_audit.json 通过后图表才登记完成。')
    write(ROOT/'analysis_v2/build_reports_corrected.py',code)
    write(OUT/'report_code_binding.json',{'original':identity(ROOT/'analysis_v1/build_reports.py'),'corrected':identity(ROOT/'analysis_v2/build_reports_corrected.py'),'inputs':identity(RUN/'paired_uncertainty.json'),'inference_repeated':False})
    subprocess.run([sys.executable,str(ROOT/'analysis_v2/build_reports_corrected.py'),'--run',str(RUN),'--output',str(OUT)],check=True)
    text='''\n## 需要单独审查的结果\n\n总体 Core loss、Brier、AUROC 和 AP 的配对探索区间方向一致；conditional pinball 差异为 −0.0007722354（−0.61835%），95% 探索区间 [−0.0016988887, 0.0002350280] 跨越零，不能据此宣称条件分位数提升已确定。固定真实雨强 5 mm/h 以上各区间的 pinball 点估计均是 B1 更高；最高区间仅 69 个 scene-pixel 暴露，其独立信息量更少。总体增益不能改写为所有强降水条件都改善。\n\n低发生概率箱普遍高估真实雨频率，中高概率箱出现低估；Brier 改善不等于预测已经校准。q32 实际覆盖低于 0.984375，需结合全部 tau 图审查。未进行任何校准变换。\n\nB1 云南 q32>100 mm/h 有 58 个 scene-pixel 暴露、44 个跨场景去重格点；B0 为零。二者云南 >500/>1000 均为零。这些是高条件分位数诊断，不是 58 次独立暴雨事件，也不自动视为科学合理。\n\n'''
    with (OUT/'PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md').open('a',encoding='utf-8') as f:f.write(text)
    history=read(ROOT.parents[0]/'v2_phase_a_review/upper_tail_full_history_comparison_20261009_v1.json')
    rows=[]
    for model,phases in history['models'].items():
        for phase,regions in phases.items():
            for region,v in regions.items():
                rows.append(f"|{model}|{phase}|{region}|{v['max_qlog_across_all_completed_epochs']:.9g}|{v['max_qlog_epoch']}|{v['FP64_PHYSICAL_OVERFLOW_RISK_OBSERVED']}|")
    with (OUT/'UPPER_TAIL_PHYSICAL_REVIEW.md').open('a',encoding='utf-8') as f:
        f.write('\n## 已发表 17 epoch 历史\n\n|模型|阶段|区域|跨完整 epoch 最大 qlog|所在 epoch|FP64 风险|\n|---|---|---|---:|---:|---|\n'+'\n'.join(rows)+'\n\n历史训练/验证反复使用样本，这里是 exposure，不是新增独立观测。逐 epoch 描述性阈值计数和 p99/p99.9 原始序列见已发表 upper_tail_history.csv；上表最大值不是 pooled p99。\n')
    print(OUT)
if __name__=='__main__':main()
