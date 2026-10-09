"""Evidence-only acceptance materials, never a scientific acceptance decision."""
import json,csv,hashlib,math,argparse
from pathlib import Path
from datetime import datetime,timezone
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,text):
    with p.open('x',encoding='utf-8',newline='\n') as f:f.write(text)
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args();r=args.run;d=args.output
    repo=Path(__file__).resolve().parents[3]
    metrics=read(r/'paired_best_metrics.json'); uncertainty=read(r/'paired_uncertainty.json')
    old=read(repo/'docs/v2_paired_phase_a_review/runs/run_20261009T072307_459014Z/paired_best_metrics.json')
    assert all(metrics['models'][k]['metrics']==old['models'][k]['metrics'] for k in old['models'])
    overall=uncertainty['comparisons']['ALL']; lines=[]
    for name,v in overall.items():
        interval=v['paired_difference_95_percentile_interval']
        lines.append(f"|{name}|{v['B0']:.12g}|{v['B1']:.12g}|{v['B1_minus_B0']:.12g}|{v['relative_percent_of_B0']:.5g}%|[{interval['lower']:.12g}, {interval['upper']:.12g}]|")
    tab='|指标|B0-Matched-v2|B1-v2|B1−B0|相对 B0|配对差异 95% 探索区间|\n|---|---:|---:|---:|---:|---:|\n'+'\n'.join(lines)+'\n'
    method='''分析对象是冻结 common intersection 的 10,501 个 2024 验证场景、36,018,430 个有效云南 scene-pixel 暴露和 4,496,600 个真实雨像元暴露。场景不是独立样本；像元也不是独立重复。所有点估计逐字段复核已发表的全量 BEST 结果，零容差一致；新逐日期统计只用于分层、校准和不确定性。两个 BEST 均为 Epoch 9，本次不重新选择。

UTC target window_start 日期从 2024-03-01 至 2024-10-31 分成 35 个固定、互不重叠的连续 7 日区块。每次有放回抽取 35 块，两模型共享相同区块次数，保留块内所有时次、空间格点和原有效/真实雨条件；seed=2026，2,000 次，2.5/97.5 百分位区间。Core、Brier、pinball 用全局分子/分母重新累计；AUROC/AP 对抽中的原始 BF16 概率精确并列分数组重新排序累计，不平均日期 AUC，不独立抽像元。相对差异=(B1−B0)/|B0|×100%。

区块方法假设跨周依赖足够弱；天气系统可跨越区块边界，季节分布并非平稳，单一年份和 35 块限制有效信息量。7 日不是结果优化所得，也不宣称是最优块长。方法背景参见 [Künsch (1989)](https://doi.org/10.1214/aos/1176347265) 和 [Politis–Romano (1994)](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870)；本实现是预声明的固定非重叠周块方案，不等同于随机长度 stationary bootstrap。

全部区间属于开发验证集上的探索性分析，是点对点区间，未作多重比较校正，不给确认性 p 值。区间不校正利用同一验证集选择 BEST 的乐观偏差，也不估计训练随机种子变异，更不代表 2025 或真实未来泛化误差。实际有效重采样次数在 paired_uncertainty.json 中逐项记录；单一类别/空条件集合的指标保持不可计算。
'''
    frozen='''Scientific Freeze v2、model/head、loss、epsilon、LR、normalization、样本集合、划分及正式评价规则没有修改。2023 Train=10,455、2024 Validation=10,501；本次只读 2024。源代码执行 checkout 固定为 a1af0325b481202941c57e8fc94f3b20e441630a，完成证据基线为 166b1f86291bbcde167dbec30d3ae43ac23bba4c；科学批准提交为 d049f7ab7b8a382f47a5fe54384ea9416a22cde9。协议、head、normalization SHA 分别为 a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be、3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e、656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31。
'''
    supplemental='\n'.join(f"- {k}: 新增只读 forward={v['REVIEW_FORWARD_CALLS']}；raw opens={v['io']['RAW_SOURCE_OPENS']}；native decodes={v['io']['NATIVE_DECODES']}；BEST SHA={v['BEST']['sha256']}。" for k,v in metrics['models'].items())
    packet='# v2 paired Phase-A 科学验收证据包\n\n研究者科学批准仍待定；本材料不批准 Phase-B。\n\n'+tab+'\n'+method+'\n## 六时相增益的解释与边界\n\n'
    packet+='B1 增加最近一小时的六个因果 B13 时次，B0 只用最新时次。配对样本、normalization、backbone/heads/loss/优化及评估相同；参数量为 4,329,410 与 4,331,810，增加 2,400，仅来自输入层接口。时间序列可能携带云系演变、移动和生命周期信息，但本实验没有对这些机制做独立因果消融，不能将指标变化证明为某一种物理机制。输入层参数数目也并非完全相同，应公开该限制。\n\n'
    a,b=(metrics['models'][k]['metrics'] for k in ('B0_MATCHED_V2','B1_V2'))
    packet+=f"冻结核心损失差异分解：occurrence 项变化 {b['global_L_occ']-a['global_L_occ']:.12g}，以全部有效像元为分母的 quantile 项变化 {b['global_core_L_qr']-a['global_core_L_qr']:.12g}。Conditional pinball 则使用真实雨暴露为分母，不与 core quantile 项混用。概率区分、总体损失、条件分位数和上尾风险应分别判断，不能用一个综合增益代替科学审查。\n\n"
    packet+='## 分层与缺失证据\n\n固定雨强区间继承原 Scientific Review：干条件 ≤float32(0.1)，真实雨条件 (0.1,1]、(1,5]、(5,10]、(10,20]、(20,30]、(30,50]、(50,∞)。这些是依据 IMERG 监督真值的预声明诊断条件，不改变训练资格，也不是根据模型输出事后筛选。真雨区间内 AUROC 因单一正类无法定义，AP=1 属于数学平凡值，不是强雨检测成功。POD/FAR/CSI 保持 THRESHOLD_NOT_FROZEN，没有挑选概率阈值。\n\n'
    packet+='季节使用 MAM、JJA、SO（不完整秋季），月度为 3–10 月；日夜使用最新冻结 B13 nominal 在 UTC+8 的 [06:00,18:00) civil-clock proxy。它不是日出日落或太阳高度定义，没有从结果选择时段。该定义在补充推理前登记，属于描述性新增分层。没有既有正式地形区域/高程掩膜，terrain stratification=NOT_ESTIMABLE_NO_PREDEFINED_SUBREGION_MASK_AVAILABLE。未新建地形区域、未处理 DEM。未定义独立降水事件目录，事件数不可估计。\n\n'
    packet+='## 证据可靠性及治理\n\n'+frozen+'\n两个模型在只读推理前后 state SHA 不变；238 项历史 checkpoint/epoch artifact 的 SHA 重新核验，代码与冻结配置不变。新分析的浮点分层汇总与原全局分母和点估计采用 1e-12 核验；原冻结 core 的 12 项字段和既有点估计则零容差一致。不得把分层浮点求和次序差异隐瞒成全量结果变化。\n\n'
    packet+='B1 独立恢复审批要求与实际沿用原始授权之间的治理偏差，见 RECOVERY_GOVERNANCE_DEVIATION.md。工程恢复和重放通过不能追认审批。失败、草稿更正、原始字节和恢复证据完整保留，科学可信度与治理处置由研究者分别判断。\n\n## 新只读计数\n\n'+supplemental+'\n\nFORMAL_OPTIMIZER_STEPS_ADDED=0；BACKWARD_CALLS=0；MODEL_PARAMETERS_UPDATED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0；V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true。\n\n完整分层表、概率校准数据、上尾与治理报告及待填写决策表均位于本独立目录；图表生成状态单独登记。来源和分析代码逐文件 SHA 见 acceptance_manifest.json。\n'
    write(d/'PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md',packet)
    coverage=list(csv.DictReader((r/'conditional_quantile_calibration.csv').open(encoding='utf-8')))
    cal='# 概率与条件分位数校准审查\n\n'+method+'\n## Occurrence\n\n发生标签沿用 float32 IMERG>float32(0.1)，包含全部有效云南真实干/雨像元。固定十个概率分箱 [0,.1)、…、[.9,1] 原样继承；每箱 mean predicted probability、observed frequency、样本暴露数和配对周块点对点探索区间见 reliability_fixed_bins.csv。箱中像元不是独立样本，空箱不虚构值。可靠性图横轴为平均预测概率、纵轴为真实雨比例；对角线是参考线，误差带不是独立像元二项区间。\n\n'
    cal+=tab+'\n## 条件分位数\n\n只在真实雨且有效的云南像元上计算覆盖：log1p(IMERG)≤qlog_i；tau=(i−0.5)/32。条件集合和 per-tau pinball 与冻结 head 一致。覆盖误差为 empirical coverage−tau；干像元上的条件分位数不参与这张校准图。所有 32 个 tau 均报告，不按结果挑选。区间为相同日期区块重采样的 pointwise interval，32 个区间不构成同时置信带。\n\n'
    for k in metrics['models']:
        selected=[x for x in coverage if x['model']==k]; err=[float(x['coverage_error']) for x in selected]
        q32=selected[-1]
        cal+=f"- {k}: 32 tau 平均绝对覆盖误差={sum(abs(v) for v in err)/32:.8g}；q32 tau=0.984375，实际覆盖={float(q32['coverage']):.8g}，探索区间=[{float(q32['coverage_ci_lower']):.8g},{float(q32['coverage_ci_upper']):.8g}]。\n"
    cal+='\n图表生成记录单独登记。研究者已批准本轮本地科学绘图；原网页访问限制记录保留在上一级目录。只有 figure_provenance.json 和 visual_delivery_audit.json 通过后图表才登记完成。不存在 temperature scaling、isotonic/Platt calibration、阈值调优或 normalization refit；此处“校准分析”仅评估，没有改变预测。\n'
    write(d/'PROBABILITY_CALIBRATION_REPORT.md',cal)
    tail='# 上尾物理合理性与暴露单位审查\n\nq32 为条件 tau=0.984375 分位数，不是无条件均值，也不是点预测。对高分位数不能要求每次等于 IMERG。另一方面，过高尾部、真实干条件下缺少 quantile 直接监督和发生概率需要联合审查。没有 clamp、sort、物理上限或任何结果修改。\n\n'
    tail+='|模型|区域|最大 qlog|对应 mm/h（诊断转换）|q32 每 forward max p99|p99.9|FP64 overflow risk|\n|---|---|---:|---:|---:|---:|---|\n'
    tail_rows=[]; cases=[]; location_paragraphs=[]
    for k,v in metrics['models'].items():
        summary=v['supplemental_statistics']
        for region,name in enumerate(('YUNNAN_INSIDE','YUNNAN_OUTSIDE')):
            t=v['upper_tail_diagnostics'][name]
            assert summary['max_qlog'][region] == t['max_qlog']
            tail+=f"|{k}|{name}|{t['max_qlog']:.12g}|{math.expm1(t['max_qlog']):.8g}|{t['q32_per_forward_max_p99']:.12g}|{t['q32_per_forward_max_p99_9']:.12g}|{t['FP64_PHYSICAL_OVERFLOW_RISK']}|\n"
            for j,threshold in enumerate((10,50,100,500,1000)):
                counts=summary['threshold_scene_pixel_tau_and_any_counts'][region][j]
                frozen_counts=t['threshold_exceedances'][str(threshold)]
                assert counts==[frozen_counts['scene_pixel_tau_exposure'],frozen_counts['scene_pixel_any_tau_exposure']]
                tail_rows.append({'model':k,'region':name,'threshold_mm_h':threshold,'scene_pixel_tau_exposure':counts[0],
                    'scene_pixel_any_tau_exposure':counts[1],'unique_grid_cells':summary['threshold_unique_grid_cells'][region][j],
                    'scenes':summary['threshold_scenes'][region][j],'any_tau_valid_rainy_truth_exposure':summary['threshold_rainy_true_scene_pixels'][region][j],
                    'independent_events':'NOT_ESTIMABLE_NO_PREDEFINED_EVENT_CATALOGUE'})
            location=summary['max_locations'][region]
            location_paragraphs.append(f"{k} {name} 最大值位置：{json.dumps(location,ensure_ascii=False)}。")
        with (r/k/'threshold_locations.jsonl').open(encoding='utf-8') as f:
            cases.extend({'model':k,**json.loads(line)} for line in f)
    with (d/'upper_tail_exposure_units.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(tail_rows[0]));writer.writeheader();writer.writerows(tail_rows)
    tail+='\n\n'+'\n\n'.join(location_paragraphs)+'\n'
    tail+='\nscene-pixel-tau exposure 将每个时次、像元和 tau 分别计数；scene-pixel any-tau exposure 每个时次像元只计一次，严格单调时等同 q32 超阈值；unique grid cells 跨场景去重同一目标格点；scenes 计有任何超阈值格点的场景。四者都不是独立降水事件。无预定义事件目录，不能从相邻场景自动制造独立事件数。超阈值采用 qlog>log1p(threshold)，阈值只作描述，不是 QC 或训练规则。\n\n'
    tail+='各区域全部阈值计数、唯一格点和场景数见 upper_tail_exposure_units.csv；每个 q32>50 的预声明诊断像元保存 sample_id、row/column、q32、p_rain、IMERG 真值及 valid/rainy 条件，见各模型 threshold_locations.jsonl。这是预测条件下的描述集合，不是新监督资格，也不是概率校准的全量条件集合。outside 数据不是主科学评价区域；目标 invalid 时不能当作无雨真值。\n\n'
    for k in metrics['models']:
        selected=[c for c in cases if c['model']==k and c['region']=='YUNNAN_INSIDE' and c['target_valid']]
        for th in (100,500,1000):
            subset=[c for c in selected if c['q32_log']>math.log1p(th)]
            if subset:
                truth=[c['truth_mm_h'] for c in subset]; prob=[c['p_rain'] for c in subset]
                tail+=f"- {k} 云南 q32>{th}: {len(subset)} 个 scene-pixel；真实雨 {sum(c['rainy_truth'] for c in subset)}；真值 min/max={min(truth):.8g}/{max(truth):.8g} mm/h；p_rain min/max={min(prob):.8g}/{max(prob):.8g}。\n"
            else: tail+=f"- {k} 云南 q32>{th}: 0 个 scene-pixel；相关真值/概率分布不可估计，不填零分布。\n"
    tail+='\nFP64 physical boundary=log1p(float64_max)≈709.782712893384；这里报告 false 仅指此次冻结 BEST 2024 轨迹没有超过浮点边界，不是物理合理性通过，也不保证未来。100/500/1000 mm/h 的科学可信性仍需结合 IMERG 误差、实际概率、持续时间、地理位置和研究者领域判断。未与独立雨量站或雷达核验，IMERG 是监督参考，不是无误差绝对真值。\n\n'
    tail+='逐 epoch 历史直接复用 upper_tail_full_history_comparison_20261009_v1.json 和 upper_tail_history.csv，保持 Train/Validation 分开；不能将逐 epoch p99 平均或把区间 extrema 当作 pooled percentile。早期训练的高尾部与冻结 BEST 结果分开呈现。历史聚合无法恢复每 epoch 唯一格点/独立事件，该缺项明确保留。\n'
    write(d/'UPPER_TAIL_PHYSICAL_REVIEW.md',tail)
    form='''# 研究者科学决策表（未填写）

本表没有自动验收，不追认历史恢复，不批准 Phase-B。

|决策项|供审查证据|研究者选择/说明|
|---|---|---|
|两模型 Phase-A 科学结果是否接受|总体点估计、配对探索区间、同一样本集合与 BEST 身份|待填写：接受 / 有条件接受 / 不接受 / 需补充证据|
|六时次增益是否达到科学与实际意义|Core/Brier/AUROC/AP/conditional pinball；单一种子、输入接口参数差异|待填写|
|概率可靠性与条件覆盖是否充分|固定 reliability bins、全部 32 tau、开发集选择局限|待填写|
|云南 q32 上尾是否可接受|上尾暴露、唯一格点/场景、实际真值和 p_rain|待填写|
|分层证据是否充分|固定真值雨强、月/季节、civil day proxy；地形掩膜缺失|待填写|
|独立事件及地形证据不足如何处理|没有预定义事件目录/地形分区，未虚构数值|待填写|
|B1 恢复治理偏差如何处置|独立审批要求与沿用原授权；不能以技术对账代替审批|待填写：记录整改 / 独立调查 / 其他|
|是否需要新的科研工作|此表仅收集意见；任何后续工作需新授权|待填写|

研究者姓名：________    日期：________    签字/审批记录：________

RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true
V2_PHASE_B_AUTHORIZED=false
2025_RAW_ACCESS=0
2025_PIXELS_READ=0

本次交付后停止。Phase-B、FinalFit 或 2025 评价必须独立获得研究者正式授权。
'''
    write(d/'RESEARCHER_SCIENTIFIC_DECISION_FORM.md',form)
    write(d/'METHODS_AND_EVIDENCE_LIMITATIONS.md','# 方法和证据限制\n\n'+method+'\n'+frozen+'\n新增分析与旧证据、代码和 source SHA 在总清单分开登记；原历史产物没有覆盖。')
    print('Six requested report files present; figures/PDF and final manifest still require verified delivery.')
if __name__=='__main__': main()
