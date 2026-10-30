"""Build the incremental decision record from public receipts; no model/data access.

This is a candidate scientific protocol, deliberately NOT a training proposal.
The final-year record remains a non-executable, researcher-unfrozen draft.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
E = ROOT / 'docs/research_readiness/20261025/evidence'


def read(name):
    return json.loads((E / name).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    (E / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code-commit', required=True)
    args = p.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', args.code_commit+'^{commit}'], cwd=ROOT, text=True).strip()
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    feature = read('physical_negative_train_diagnostics_20261030.json')
    cache = read('physical_negative_cached_train_check_20261030.json')
    rel = read('dote_reliability_increment_20261030.json')
    old = read('dote_control_proposal_20261029.json')
    init = read('dote_control_checks_20261029.json')
    paired = read('dote_control_three_seed_completion_20261029.json')
    coarse = read('scientific_attribution_diagnostics_20261029.json')
    final = read('final_test_preregistration_increment_20261030.json')
    assert feature['scenes'] == 959 and feature['all_real_masks_preserved']
    assert cache['status'] == 'NOT_VERIFIED_RESOURCE_ADMISSION_BLOCKED'
    assert final['status'] == 'DRAFT_NON_EXECUTABLE_NOT_RESEARCHER_FROZEN'
    tr, dev = old['source_scope_summary']['Train'], old['source_scope_summary']['Development']
    weather_bytes = 9*(tr['bytes_per_pass'] + dev['bytes_per_pass'])
    weather_instances = 9*(tr['file_count'] + dev['file_count'])
    static_bytes = old['budget']['static_source_bytes_per_model']['B7']
    assert weather_bytes + static_bytes == 477571953840
    assert weather_instances + 1 == 142813
    # Same frozen logical SourceCache inventory, counted explicitly, not copied as a new grant.
    costs = dict(status='CONDITIONAL_COST_ESTIMATE_NOT_A_FROZEN_EXECUTION_PACKAGE',
                 hypothetical_models=1, seed=2029, optimizer_updates=4320,
                 train_pass_bytes=tr['bytes_per_pass'], dev_pass_bytes=dev['bytes_per_pass'],
                 train_pass_instances=tr['file_count'], dev_pass_instances=dev['file_count'],
                 epochs=9, weather_bytes=weather_bytes, static_bytes=static_bytes,
                 logical_source_bytes=weather_bytes+static_bytes, source_instances=weather_instances+1,
                 dynamic_extra_raw_bytes=0, additional_feature_cache_bytes=0,
                 maximum_seconds_if_later_approved=21600, minimum_free_bytes=24*1024**3,
                 minimum_host_available_bytes=8*1024**3, minimum_CUDA_free_bytes=5*1024**3,
                 replay_allowance=0, additional_retry_allowance=0,
                 initialization='FROM_SCRATCH_MATCH_REAL_B7_SEED2029_NOT_E9_FINETUNING',
                 time_estimate='INHERITED_SIMILAR_B7_RUNS_ABOUT_3_TO_4_HOURS_NOT_MEASURED_FOR_THIS_CANDIDATE',
                 storage='NEW_INDEPENDENT_NAMESPACE_UNDER_RESEARCHER_CONFIRMED_STORAGE_PARENT_NOT_CREATED',
                 failure='STOP_AND_PRESERVE_LEDGER_CHECKPOINTS_NO_AUTO_REPLAY_NO_AUTO_RETRY',
                 not_included='No launcher/WMI allowlist or approval file; code and exact future output must be rebound before any approval')
    code_paths = ['src/yuntapr/experimental/research_readiness/dote_physical_controls.py',
                  'src/yuntapr/experimental/research_readiness/final_test_draft.py',
                  'tools/research_readiness/check_physical_negative_train.py',
                  'tools/research_readiness/check_physical_negative_cached_train.py',
                  'tools/research_readiness/diagnose_dote_reliability_increment.py',
                  'tools/research_readiness/build_physical_attribution_decision.py',
                  'tests/research_readiness/test_dote_physical_controls.py',
                  'tests/research_readiness/test_final_test_draft.py']
    for name in code_paths:
        committed = subprocess.check_output(['git', 'show', commit+':'+name], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == sha(ROOT/name), name
    protocol = dict(status='CANDIDATE_PROTOCOL_NOT_TRAINING_READY_NO_TRAINING_REQUEST',
        created_at=stamp, preparation_code_commit=commit, evidence_base='f3a3b50526f0a991a4680ca3399fa6f04474225a',
        authorized=False, formal_training_started=False, model='B7_PERP_GRADIENT', hypothetical_seed=2029,
        selection=feature['design_lock'], formula="O_perp = -u*dh_dy + v*dh_dx; W=max(O_perp,0); L=max(-O_perp,0); M=PWAT/reference*W",
        physical_definition=feature['definition'], channel_order=feature['channel_order'],
        transform_boundary='Rotate only the gradient pack passed to unchanged PhysicalDote; real B6 static input remains untouched',
        rotation_matrix_east_north=[[0,-1],[1,0]],
        units='Gradient m/m; raw east/north wind m/s; O/W/L/M m/s before unchanged explicit 1m/s scale',
        pressure_mask='Unchanged true surface-pressure, underground 850/700 hPa invalid, real PWAT/finite masks',
        nonzero='Eight varying channels, natural W/L/M zeros retained; no permanently all-zero input columns by construction',
        nominal_parameters=4411058, effective_capacity='No structural zero-input128 issue, but equal effective capacity not established by a tiny CPU gradient probe',
        unchanged='GFS13,real DEM6,SP04 backbone/fusion,real masks,supervision,populations,scalers,loss,heads,optimizer,LR',
        paired_initialization=dict(inherited_initial_state=init['initial_B7_seed2029'], main_seed=2029,
                                  static_aux_seed=12029, fusion_aux_seed=22029,
                                  nine_epoch_order_rule='seed+epoch-1; cross-seed shifted overlap inherited',
                                  full_model_check='NOT_VERIFIED_RESOURCE_ADMISSION_BLOCKED; inherited identity is not a new measured candidate identity'),
        data=feature['data_version'], protocol=old['protocol'], source_scope_summary=old['source_scope_summary'],
        alternatives=[dict(name='JOINT_MASK_CLASS_DERANGEMENT', seed=20261030,
                           preserves='Exact8-vector joint/marginal distribution within real mask signatures; real mask unchanged',
                           changes='Spatial correlation, elevation/region climate associations and pairing with local GFS/PWAT/DEM',
                           residual_confound='Scene-dependent true mask classes encode weather and constrain mappings; singleton classes cannot move',
                           question='Value of aligned local representation versus distribution-preserving mislocation, with spatial/climate confounding'),
                      dict(name='PERPENDICULAR_GRADIENT_90_CCW', selected=True,
                           preserves='Point location,real base inputs,masks,gradient magnitude and vector inner-product autocorrelation',
                           changes='Scalar O/W/L/M distributions and spatial correlations; rotated field generally nonintegrable',
                           question='Narrow directional projection/representation sensitivity; not clean physical correspondence or causal uplift')],
        full_Train_feature_diagnostics='physical_negative_train_diagnostics_20261030.json',
        targeted_checks=dict(synthetic_new_checks=6, draft_metadata_checks=3, status='PASS_RECORDED_FROM_THIS_TURN_TOOL_RESULTS',
                             old_tests_rerun=False, full_cached_model=cache['status']),
        identifiability='DOTE=f(GFS,DEM); breaking this deterministic relation cannot preserve its full joint distribution with unchanged base inputs. Prediction controls test inductive representation, not an observed uplift causal effect.',
        scientific_recommendation='DO_NOT_START_GPU_NOW; resource recovery alone does not resolve distribution/spatial confounding',
        conditional_cost=costs, code_sha256={n:sha(ROOT/n) for n in code_paths},
        final_2025='FROZEN_NO_NEW_PAYLOAD_INFERENCE_OR_METRICS')
    protocol['protocol_sha256'] = hashlib.sha256(json.dumps(protocol, ensure_ascii=False, sort_keys=True, separators=(',',':'), allow_nan=False).encode()).hexdigest()
    save('dote_physical_negative_protocol_20261030.json', protocol)
    coarsed = {}
    for seed, models in rel['models'].items():
        real = coarse['models'][f'B7__E0__s{seed}__f006__dynamic']['brier']
        zero = models['B7_ZERO_DOTE']['coarse_bin_diagnostic']
        coarsed[seed] = {k:real[k]-zero[k] for k in ('binned_reliability','binned_resolution','binning_residual')}
        d = rel['real_B7_minus_ZERO_DOTE'][seed]
        assert math.isclose(d['brier'], d['empirical_score_reliability']-d['empirical_score_resolution']+d['uncertainty'], abs_tol=1e-14)
    table='\n'.join(f"|{s}|{d['brier']:.12g}|{d['empirical_score_reliability']:.12g}|{d['empirical_score_resolution']:.12g}|" for s,d in rel['real_B7_minus_ZERO_DOTE'].items())
    oreal=feature['global_distribution']['real']['1']; operp=feature['global_distribution']['perpendicular']['1']
    ratio=operp['std']/oreal['std']
    east={x['method']:x['pearson'] for x in feature['spatial_and_geographic_associations'] if x['channel']==1 and x['kind']=='lag1_axis1'}
    markdown=f'''## 2026-10-30增量科学收口：不申请新的正式GPU训练

旧B0–B8及DOTE零数值三seed训练/评价状态均继承完成；本次不是重训或旧结果重审。[候选协议](docs/research_readiness/20261025/evidence/dote_physical_negative_protocol_20261030.json)为NOT_TRAINING_READY，不是获批提案。新增正式训练0次、模型推理0次、优化器更新0次；2025没有新增载荷、推理或指标。

### 概率可靠性：补齐ZERO三seed，继承真实B7/B8

此前真实B7/B8三seed已有原生概率分数精确分解，ZERO三seed没有。[本次增量](docs/research_readiness/20261025/evidence/dote_reliability_increment_20261030.json)只读取3份既有ZERO分数计数SQLite，文件共831,488字节并校验原生表digest；继承真实B7分解，不加载权重或新增Dev推理。统一差值为真实B7−ZERO。

|seed|ΔBrier|Δ经验REL（可靠性项，低优）|Δ经验RES（分辨能力项，高优）|
|---|---|---|---|
{table}

同一人口的UNC（不确定性项）相同，BS=REL−RES+UNC。经验REL在3/3下降，既有固定十箱REL也3/3下降；RES在2/3下降，且对应seed AUROC/AP较差。分辨能力项不等于AUROC/AP，前者按预测概率分组的有雨率差异，后者衡量排序；这里只能描述一致现象，不能把代数分解当作训练因果解释。各模型385–416个原生分数组，部分组只有1个像元时次；有限样本、空间/时间依赖和稀疏组使经验REL不能等同于总体校准改善。固定分箱还存在残差，不能用分箱恒等式替换原始Brier。

条件Pinball来自有雨条件下的另一个输出头，q32是尾部分位数覆盖；发生概率Brier下降没有数学上保证它们改善。总体Brier含大量无雨/弱雨像元，强雨的少数损失不会决定总体趋势；具体训练梯度竞争尚未验证。06 UTC的AP下降和q32距名义误差上升均3/3；20–30及30–50 mm/h Pinball仅2029改善，>50仅6个像元时次，不能写成6场暴雨。按实际雨强条件化的覆盖率是描述值，不能要求每个结果分层都达到0.984375。

### 非零负对照：实现完成，识别限制明确

比较固定mask类内8向量联合错配与固定90°逆时针梯度旋转。前者精确保留类内数值联合分布，却破坏空间、海拔、区域气候和局部GFS/PWAT对应；后者保留地理位置、真实GFS/DEM输入、梯度模长和mask，工程代价更小，因此在读取新诊断前锁定为唯一候选B7_PERP_GRADIENT。旋转只作用于PhysicalDote使用的梯度，不修改真实静态分支；O'=-u·h_y+v·h_x，W/L/M按原规则计算，不添加裁剪、系数或重新归一化。

[959个2023 Train场景诊断](docs/research_readiness/20261025/evidence/physical_negative_train_diagnostics_20261030.json)显示：全部真实mask保持，850/700有效率18.6490%/93.2089%；旋转后O700标准差比值{ratio:.9f}（降低约{(1-ratio)*100:.2f}%），东西相邻相关从{east['real']:.9f}变为{east['perpendicular']:.9f}；联合置乱为{east['permuted']:.9f}。因此候选不保留标量分布和空间相关，旋转场通常也不是另一真实DEM的可积梯度。月、UTC、海拔、四固定象限及经纬关联全部保留在诊断收据，不能视作独立区域气候验证。SP04实测约10.10 km×11.08 km，不是4 km。

新增6项CPU合成检查及3项最终测试元数据检查通过；非零输入探针可使原128列有损失梯度，但它不是整模容量相等证明。整模Train缓存零优化器前/反向在8 GiB RAM入场门槛停止，**NOT_VERIFIED**：事后可用RAM约4.81 GiB；未加载缓存或模型，未降低门槛、停止其他进程或更改精度。保留失败元数据。DOTE是GFS/DEM的确定性函数，破坏关系时无法同时保持其与全部基础输入的联合分布。当前候选只回答方向性表征敏感性，不能无混杂地识别真实空间对应关系，更不能证明地形抬升。

**决策：现在不值得立即投入正式GPU。** 不强行训练不可充分识别的控制。如果研究者日后接受较窄的方向性探针，应先恢复RAM并完成已有缓存检查，再绑定新可执行入口/输出目录及明确预算批准；不重复已通过的CPU或959场景诊断。本次条件成本按实际冻结清单计算：9×(26,424,262,556+26,639,253,112)+312,828=477,571,953,840逻辑源字节；9×(7,918+7,950)+1=142,813实例，单模型4,320更新/至多6小时/24 GiB/零重放零重试。相同字节数来自同一读取链路，无新增动态原始文件，不是复制成新授权；没有可直接执行的正式训练命令或批准文件。

### 论文主线与三级证据

当前最可信主张：相同人口、配对初始化/顺序及固定E9下，DOTE显式数值相对零控制跨三个训练seed均降低Brier及样本经验可靠性项；排序、强雨和分位数收益不稳定，q32仍欠覆盖。128个零输入权重的有效容量局限、真实mask信息及重复使用同一Dev年必须并列报告。DTFM相对concat是共享条件的融合替换，不能写成额外独立模块或将其增量全部归于DOTE。

第一层预测收益：固定协议内Brier复现成立，全面优势不成立。第二层物理启发表征：支持有限、带容量混杂的表征增量，新增探针尚无性能结果。第三层真实地形机制及独立年份泛化：NOT_VERIFIED。分辨率限制、E0目标与尾部稀少可列待检验解释，不能写成已经定位的原因，也不宣称当前业务近实时可用。

候选论文结构：①回顾估计问题与信息边界；②数据人口/时间网格/QC与掩膜；③配对初始化、DOTE/DTFM及控制方法；④全部三seed总体、可靠性、UTC/海拔/七雨强结果；⑤容量、依赖与归因限制；⑥冻结后独立年份验证。建议题目为“云南复杂地形概率降水回顾估计中物理启发表征的可重复增益与校准局限”。

图表清单（仅设计，未生成图）：信息流及真实网格/mask；三seed全部有符号差值；BS/REL/RES与概率箱；七雨强及q32含样本数；UTC/海拔反例；Train负对照分布/相关混杂。事件轨迹图和物理空间误差归因需联合逐场景预测、地理索引及独立事件定义，不能从边际分数计数恢复。旧35周块区间只属于B7/B8，不转用于DOTE−ZERO，也不称独立暴雨置信区间。

### 2025最终准入：DRAFT，不可执行

[增量草案](docs/research_readiness/20261025/evidence/final_test_preregistration_increment_20261030.json)建议在旧B4/B7/B8九模型集合中加入已有ZERO三seed，合计12份已登记E9身份，以便独立年比较DOTE。主比较建议真实B7−ZERO，Brier与Pinball为共同主要指标，保留表现混合的Pinball以避免只选有利指标；B8−B7等为次要比较。这是**待研究者冻结的范围变更**，并非原预注册已经批准。

已有E9 SHA/执行身份可继承；2025全模态共同人口、实际文件/掩膜/时次一致性均NOT_VERIFIED；新代码仅验证12模型身份目录及2001合成样本，不是2025读取/评价适配器。真实适配器NOT_IMPLEMENTED，原年份硬保护未放开。事件目录/依赖方案、一次性盲态清单与精确源读取/权重加载/存储/GPU时间预算仍待冻结；不预造人口数或把训练9轮读取量用于一次最终推理。所有准入条件通过并获新的一次性揭盲批准后才可执行，目前2025仍严格冻结。

最小缺口：①研究者接受有限论文主张并冻结最终模型/假设；②无2025载荷的适配器与失败即停工程准备；③独立事件定义或明确仅报告固定时块敏感性；④正式授权后核对全模态人口及一次性最终测试。物理因果主张另需可识别的对应关系控制和独立物理/事件证据，不能以本轮GPU探针代替。
'''
    decision = dict(status='INCREMENTAL_SCIENTIFIC_CLOSEOUT_COMPLETE_WITH_LIMITATIONS', created_at=stamp,
        preparation_code_commit=commit, candidate_protocol_sha256=protocol['protocol_sha256'],
        scientific_recommendation='NO_FORMAL_GPU_TRAINING_REQUEST_THIS_ROUND',
        exact_Brier_deltas=rel['real_B7_minus_ZERO_DOTE'], fixed_bin_deltas=coarsed,
        inherited_performance_summary=paired['summary']['groups']['all'],
        candidate_O700_std_ratio=ratio, candidate_O700_east_lag1_pearson=east,
        full_cached_model_check=cache['status'],
        sources={n:sha(E/n) for n in ['dote_reliability_increment_20261030.json','physical_negative_train_diagnostics_20261030.json',
                'physical_negative_cached_train_check_20261030.json','final_test_preregistration_increment_20261030.json',
                'dote_physical_negative_protocol_20261030.json']},
        additional_Dev_joint_error_advice=dict(status='OPTIONAL_NOT_AUTHORIZED_NOT_AN_ENTRY_GATE',
            models=['B7_seed2029','B7_ZERO_DOTE_seed2029'], optimizer_updates=0,
            inference_passes=2, checkpoint_loads=2,
            conditional_source_bytes=2*(dev['bytes_per_pass']+static_bytes),
            conditional_source_instances=2*(dev['file_count']+1),
            time_and_storage='NOT_VERIFIED_NOT_FROZEN',
            reason='Archived marginal scores cannot recover co-located model errors, event tracks or paired spatial covariance; needs independent event IDs too'),
        activity=dict(new_formal_training=0, optimizer_updates=0, model_inference=0, checkpoints_loaded=0,
                      raw_GFS_2023_files=959, raw_GFS_2023_bytes=272589016,
                      static_cache_bytes_including_failed_setup=625656,
                      archived_ZERO_score_SQLite_files=3, archived_SQLite_file_bytes=831488,
                      full_model_cache_check='BLOCKED_BEFORE_LOAD', final_2025='FROZEN_NO_ACCESS'),
        markdown=markdown)
    save('physical_attribution_decision_20261030.json', decision)
    print(json.dumps(dict(status='PASS_PUBLIC_DECISION_RECORDS_ONLY', code_commit=commit,
        protocol_sha256=protocol['protocol_sha256'], optimizer_updates=0, inference=0, new_raw_reads=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
