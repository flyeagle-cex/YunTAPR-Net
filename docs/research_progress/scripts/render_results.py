"""Render the requested Markdown scientific readout from public extracts only."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def fmt(value):
    return 'NOT_AVAILABLE' if value is None else f'{value:.12g}'


def table(headers, rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join('---' for _ in headers)+'|']+
                     ['|'+'|'.join(str(v) for v in row)+'|' for row in rows])


def main():
    data=json.loads((ROOT/'evidence/experiments.json').read_text(encoding='utf-8'))
    records=data['experiments']; by_id={r['experiment_id']:r for r in records}
    groups=json.loads((ROOT/'evidence/seed2029_groups.json').read_text(encoding='utf-8'))
    text=['# 已有真实实验结果与科学边界',
          f"数值核查时间：{data['as_of']}。只读既有记录；未重新训练、推理或评价模型。表中显示约12位有效数字，全精度见 CSV/JSON。",
          '## 比较口径',
          '所有当前配对结论来自 2024 Development，不是 2025 独立测试。发生事件为 float32 降水率 > float32(0.1 mm/h)；Brier 使用全部有效云南像元，AUROC/AP 保留既定精确并列分数口径。条件 Pinball 是真实雨像元上的32个冻结分位数平均，单位为 log1p(mm/h)。q32 名义水平为 (32−0.5)/32=0.984375，覆盖为 covered/N_rain。',
          'E0/E1/E2 是损失臂；不能与模型编号混用。B0/B1 的 10,455/10,501 人口与 B3/B4 的 959/963 人口不同，不能跨表直接排名或解释为架构增益。固定 f006 仅为回顾实验、只覆盖 00/06/12/18 UTC，且只覆盖三月至十月。',
          '## B0/B1：seed2026、seed2027 分别列示',
          '各行均为固定第九轮、每模型保留47,052次更新。E1 的发生损失与 E0 不同，跨损失臂的训练 loss 不作同口径性能比较。']
    phaseb=[r for r in records if r['phase']=='PHASE_B_V2']
    text.append(table(['seed','模型','损失臂','Brier ↓','AUROC ↑','AP ↑','条件 Pinball ↓','q32 coverage'],
        [[r['seed'],r['model_id'],r['loss_arm'],*[fmt(r['metrics'][k]) for k in ('brier','auroc','average_precision','conditional_pinball','q32_coverage')]] for r in phaseb]))
    deltas=[]
    for seed in (2026,2027):
        for arm in ('E0','E1','E2'):
            a=by_id[f'B0_MATCHED_V2__{arm}__s{seed}']['metrics'];b=by_id[f'B1_V2__{arm}__s{seed}']['metrics']
            deltas.append([seed,arm,*[fmt(b[k]-a[k]) for k in ('brier','auroc','average_precision','conditional_pinball','q32_coverage')]])
    text += ['B1−B0 配对差值（coverage 为比例差，不是百分点）：',
             table(['seed','损失臂','Δ Brier','Δ AUROC','Δ AP','Δ 条件 Pinball','Δ q32 coverage'],deltas),
             '两个 seed、三个损失臂的总体发生识别方向一致，条件 Pinball 也改善；q32 并非一致改善。它们使用相同开发年，且 Phase-A 与 Phase-B 的 seed2026/E0 不是额外独立随机种子。已有探索性区块分析及恢复治理限制仍须保留，不能据此宣称最终泛化或所有强雨条件占优。',
             '## B2 与 B3',
             '**尚无可核实的 B2 正式训练与指标，故 B2 vs B3 对照尚无可核实结果。** 已存在七通道单时次构造器，不等于正式实验。B3 的证据是下面独立列出的 seed2029/f006/E0 运行，不能用 B1 的指标充当 B2 或 B3。',
             '## B3/B4：seed2029、固定 f006、E0、第九轮',
             'B3 为 B08/B09/B10/B11/B13/B15/B16 × 六时次；B4 加入13变量 MEE、width16、目标 SP04 网格残差。输入人口、标签、Train-only 统计、公共初始化及各轮样本顺序已核对一致；AdamW、batch2/验证batch8、九轮终点沿用本次已授权配置。每模型保留4,320次更新，没有 BEST 选择。']
    a,b=(groups[m]['all']['summary'] for m in ('B3','B4'))
    text.append(table(['指标','B3','B4','B4−B3'],
        [[k,fmt(a[k]),fmt(b[k]),fmt(b[k]-a[k])] for k in ('core_fp64','brier','auroc','average_precision','conditional_pinball','q32_coverage','q32_signed_bias','q32_absolute_error')]))
    text += [f"Dev 为963场景、{a['n_valid']:,}个有效场景像元暴露、{a['n_rain']:,}个真实雨像元暴露。B3/B4 q32 分别覆盖{a['covered'][-1]:,}/{b['covered'][-1]:,}个雨像元；与98.4375%名义覆盖的差距分别为{100*(a['q32_coverage']-.984375):.6f}/{100*(b['q32_coverage']-.984375):.6f}个百分点。总体稍有改善仍不足以称为校准通过。",
             '### 七个雨强条件层',
             '每行 n 为有效真实雨的场景像元暴露，两模型相同；不是独立暴雨数量。Pinball 越低越好。']
    strata=[];lower=.1
    for x,y in zip(a['rain_strata'],b['rain_strata']):
        upper=x['upper'];label=f'({lower:g},{upper:g}]' if upper is not None else f'({lower:g},∞)'
        strata.append([label,x['n'],fmt(x['conditional_pinball']),fmt(y['conditional_pinball']),fmt(y['conditional_pinball']-x['conditional_pinball'])])
        lower=upper
    text.append(table(['mm/h','n','B3 Pinball','B4 Pinball','B4−B3'],strata))
    text += ['`(20,30]` 的564个、`(30,50]` 的147个像元暴露合计711个，只占雨像元的约0.1743%；这两个层的条件误差均未改善。`(1,5]` 也略差。`>50` 只有6个暴露，不能据其数值波动推断极端降水能力。未新增像元独立性假设、p值或显著性声明。',
             '现存结果没有按真实雨强层保存 q32 的 covered 计数/逐像元分位数预测，因此**不能核实20–30、30–50 mm/h各自的q32覆盖率**。预测上尾超过某阈值的暴露数不是按真实雨强条件的覆盖率，不能替代。',
             '### 四个 UTC 时次',
             '差值均为 B4−B3。q32 列为实际条件覆盖率，06 UTC 的 Brier 是反例，00/18 UTC 的 q32 覆盖也下降。']
    utc=[]
    for hour in (0,6,12,18):
        key=f'analysis_UTC_{hour:02d}';x,y=(groups[m][key]['summary'] for m in ('B3','B4'))
        utc.append([f'{hour:02d}',x['scenes'],x['n_rain'],*[fmt(y[k]-x[k]) for k in ('brier','auroc','average_precision','conditional_pinball')],fmt(x['q32_coverage']),fmt(y['q32_coverage'])])
    text.append(table(['UTC','场景','雨像元暴露','Δ Brier','Δ AUROC','Δ AP','Δ Pinball','B3 q32','B4 q32'],utc))
    x,y=(groups[m]['scene_max_ge20']['summary'] for m in ('B3','B4'))
    text += [f"现有“场景最大雨强≥20 mm/h”分组有{x['scenes']}场景、{x['n_rain']:,}个雨像元暴露；Brier、AUROC、AP和总体条件Pinball方向改善，但q32覆盖从{fmt(x['q32_coverage'])}变为{fmt(y['q32_coverage'])}。这个分组包含场景内全部真实雨像元，不能被说成仅对≥20 mm/h像元计算。",
             '### 完成状态、恢复和历史消耗',
             'B3 原始段完成前三轮；第四轮训练返回后、验证阶段读取失败。研究者批准从第三轮 LAST 恢复并重放第四轮。原段1,920次返回 + 恢复段B3 2,880/B4 4,320次返回 = 9,120次累计实际更新；其中8,640次为保留轨迹、480次为获批重放。失败段保留独立记录，不作为额外 seed 或成功完整 epoch。',
             '源读取299,968实例、实际交付1,003,563,940,849字节；保守预登记1,003,568,959,114字节。LAST E9 SHA：B3 `c7780bc6e45992639c90339c88553fe3a722f6d9681bd247a82ad2dce0c08283`；B4 `7c74eb80ab7d754e3262781d85ac370b2319c3bf27d37ac362860c104acfb34d`。本轮未读取这些权重载荷。',
             '## 历史 Phase-A / FinalFit 不与当前实验混合',
             '以下是另外的科学版本和选择规则；缺项保留 NOT_AVAILABLE，不能用其他模型或阶段的指标补齐。']
    legacy=[r for r in records if r['phase'].startswith(('PHASE_A','LEGACY_'))]
    text.append(table(['实验','seed','完成epoch','保留/报告更新','选择','Brier','条件Pinball'],
        [[r['experiment_id'],r['seed'],r['epochs'],r['global_steps'],r['checkpoint_selection'],fmt(r['metrics'].get('brier')),fmt(r['metrics'].get('conditional_pinball'))] for r in legacy]))
    text += ['旧独立 B0 FinalFit 11轮完成是历史事实，未执行2025模型评估；旧 B0-Matched FinalFit 在第五轮内发生分位数物理溢出，仅4轮完整，50,537次报告更新，保持失败。Phase-A V2 两模型各17轮并按原规则选择第9轮 BEST；不能改写为本次九轮终点，也不能算作新的独立随机种子。',
             '旧记录中发现的 RMSE/MAE/Bias 已保留在 endpoint_metrics.csv 的 diagnostic_proxy_metric；其定义为 `p_rain × mean(32个条件物理分位数)` 的诊断代理，不是精确混合分布均值，不能与未实现的新模型 RMSE 对比。CSI/POD/FAR 在相关原收据中为 THRESHOLD_NOT_FROZEN，未编造阈值或数字。',
             '## 可以与不能成立的结论',
             '**有证据**：在固定f006、四个UTC时次的小共同人口、单seed2029/E0中，增加MEE后总体Brier、AUROC、AP、条件Pinball改善；B0/B1在另外的共同人口上有两个seed的方向一致观察。',
             '**尚不能成立**：B4全面优于B3；20–50 mm/h改善；q32上尾校准已解决；全天/业务近实时可用；2025独立泛化；多seed的B3/B4复现；DOTE/DTFM有效或物理机制被验证。两个模型共用2024开发集，不是新的独立验证集。相关像元、相邻时次和35个既定周区块都不能当成数百万独立天气事件。',
             '高海拔指标缺少冻结目标DEM/分层边界，原结果为 NOT_ESTIMABLE_TARGET_DEM_AND_ALTITUDE_EDGES_NOT_FROZEN。实际正式运行GPU峰值未在本轮所核对的结果摘要中独立核验，不能用 dry-run 的显存代替。',
             '## 核心创新的证据层级与下一步',
             'DOTE 候选保留 `O=u·∂h/∂x+v·∂h/∂y`、850/700 hPa地表以上层、`W=max(O,0)`、`L=max(−O,0)`，以及显式选择的 `M=Q·W` 或 `Q·O`。米制导数、方向、单位、有效掩膜和聚合接口已有测试；O仍是诊断代理，不是被验证的真实垂直速度。PWAT参考尺度/耦合基底、0.02°/0.10° DEM footprint与边界规则仍由研究者冻结。',
             'DTFM已有恒等初始化、多尺度条件投影、有界gamma/beta、融合卷积/残差，以及同输入和活动参数数目匹配的B7 concat/B8调制候选。完整B5–B8链、正式降水消融和物理机制验证均未完成；插入位置、尺度与调制上界仍需科学决定。52项原接口检查和20项Stage2增量结果被继承，本轮没有重跑它们。',
             '最值得优先审议的是：**在保持当前分位数水平与数据人口的前提下，固定高τ权重是否改善上尾校准而不损害总体概率识别**。依据是总体环境融合已改善，而强雨与上尾仍有明确反例；该假设能与新增地形机制分开验证。它只是待研究者批准的最小损失消融建议，不自动改变损失、启动训练或授予预算。按真实降水值自适应加权还会改变加权目标分布，不能不加说明地当作原条件分位数。',
             'DOTE/DTFM通道继续保留；先冻结少量物理/融合选项，再由研究者决定与上尾损失的先后和最小对照。不以本报告替代科学决策。',
             '## 复核材料',
             '[全精度终点](endpoint_metrics.csv)、[逐轮loss/Dev曲线数值](epoch_metrics.csv)、[雨强分层](rain_strata.csv)、[32分位数覆盖](quantile_calibration.csv)、[源SHA和公开性](evidence/source_manifest.json)、[证据边界](EVIDENCE_INDEX.md)。']
    (ROOT/'SCIENTIFIC_RESULTS.md').write_text('\n\n'.join(text)+'\n',encoding='utf-8')


if __name__=='__main__':main()
