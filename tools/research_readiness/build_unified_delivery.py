"""Export the five public research entry points from existing receipts only.

No torch, raw observations, checkpoint loading, training, or network access.
Default rebuild uses the dated status embedded in EVIDENCE_INDEX.md. A new
sanitized metadata snapshot may be supplied explicitly with --status-json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READY = 'docs/research_readiness/20261025/'
PROGRESS = 'docs/research_progress/'
OLD = PROGRESS + 'evidence/experiments.json'
B2 = READY + 'evidence/b2_completion_and_paired_evidence.json'
B34 = READY + 'evidence/b3_b4_three_seed_completion.json'
FULL = READY + 'evidence/b3_b4_full_endpoint_metrics_20261027.json'
GROUPS = PROGRESS + 'evidence/seed2029_groups.json'
BASE = READY + 'B0_B4_EXPERIMENT_MATRIX.csv'
FIELDS = ('record_type,experiment_id,model_id,seed,loss_arm,epoch,split,'
          'comparison_population,group,group_ids_sha256,metric,value,status,unit,'
          'comparison,reference_experiment_id,reference_value,n_seeds,'
          'improvement_direction,source_file,source_pointer,reference_source_file,'
          'reference_source_pointer,executed_commit,evaluation_script,checkpoint_sha256').split(',')
HEADLINE = ('brier', 'auroc', 'average_precision', 'conditional_pinball',
            'q32_coverage', 'q32_signed_bias', 'q32_absolute_error')


def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))


def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def write_csv(name, fields, rows):
    with (ROOT / name).open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fields, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def leaves(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from leaves(v, path + '/' + str(k).replace('~', '~0').replace('/', '~1'))
    elif isinstance(obj, list):
        for k, v in enumerate(obj):
            yield from leaves(v, path + '/' + str(k))
    else:
        yield path, obj


def favorable(metric):
    if metric in ('brier', 'conditional_pinball', 'q32_absolute_error') or metric.endswith('/conditional_pinball'):
        return 'LOWER'
    if metric in ('auroc', 'average_precision'):
        return 'HIGHER'
    if metric in ('q32_coverage', 'q32_signed_bias'):
        return 'CLOSER_TO_NOMINAL_0.984375'
    if metric.startswith('coverage/'):
        return 'CLOSER_TO_CORRESPONDING_TAU'
    return 'DESCRIPTIVE_ONLY'


def unit(metric):
    if metric.endswith('conditional_pinball') or metric.endswith('pinball_sum') or metric == 's_qr':
        return 'FROZEN_LOG1P_RAIN_PINBALL_SCALE'
    if metric in ('scenes', 'n_valid', 'n_rain', 'q32_covered') or metric.startswith('covered/'):
        return 'COUNT'
    return 'AS_RECORDED_SEE_SOURCE'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status-json', type=Path)
    args = parser.parse_args()
    if args.status_json:
        snapshot = json.loads(args.status_json.read_text(encoding='utf-8'))
    else:
        text = (ROOT / 'EVIDENCE_INDEX.md').read_text(encoding='utf-8')
        snapshot = json.loads(re.search(r'<!-- STATUS_SNAPSHOT -->\s*```json\s*(.*?)\s*```', text, re.S)[1])
    assert snapshot['source_commit'] == 'b251fd9ea06c0c90f48d2ac0decba0454114669d'
    assert snapshot['state'] == 'RUNNING' and snapshot['completed_models'] == 0, 'Terminal state requires a new evidence-based closeout first.'
    assert {r['model'] for r in snapshot['runs']} == {'B5', 'B6'}
    as_of = snapshot['snapshot_utc']
    with (ROOT / BASE).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames
        matrix = list(reader)
    assert len(matrix) == 29
    experiments = {r['experiment_id']: r for r in matrix}
    assert len(experiments) == 29
    old = read(OLD)
    b2, b34, groups29 = read(B2), read(B34), read(GROUPS)
    original_configs = {r['experiment_id']: ';'.join(r['source_ids']) for r in old['experiments']}
    runs = {r['model']: r for r in snapshot['runs']}
    for r in matrix:
        for key in ('protocol_reference', 'source_manifest_reference', 'evidence_path'):
            val = r[key]
            if val.startswith('../../research_progress/'):
                r[key] = PROGRESS + val.removeprefix('../../research_progress/')
            elif val.startswith('evidence/') or val.startswith('rechecked_snapshot/') or (ROOT / READY / val).is_file():
                r[key] = READY + val
        p = r['metrics_path']
        if p.startswith('evidence/experiments.json'):
            r['metrics_path'] = PROGRESS + p
        elif p.startswith('evidence/'):
            r['metrics_path'] = READY + p
        r.update(execution_state='CLOSED_SEE_STATUS', planned_epochs='SEE_ORIGINAL_PROTOCOL',
                 train_batch_size='NOT_VERIFIED_FROM_THIS_PUBLIC_EXTRACT',
                 dev_batch_size='NOT_VERIFIED_FROM_THIS_PUBLIC_EXTRACT',
                 optimizer='SEE_ORIGINAL_CONFIG', learning_rate_rule='SEE_ORIGINAL_CONFIG',
                 input_spec='SEE_MODEL_CONFIG', parameter_count='NOT_REEXTRACTED',
                 training_config_reference=original_configs.get(r['experiment_id'], r['protocol_reference']),
                 unified_metrics='METRICS.csv', status_as_of=r['verified_at'])
        if r['comparison_population'] == 'CORE_F006_959_963':
            r.update(planned_epochs='9', train_batch_size='2', dev_batch_size='8',
                     optimizer='AdamW(lr=1e-4;betas=0.9/0.999;eps=1e-8;conv_decay=1e-4;bias_GN_decay=0;clip=5)',
                     learning_rate_rule='480_WARMUP_THEN_ORIGINAL_24000_STEP_COSINE_PREFIX_TO_4320')
            specs = {'B2': ('7x1_HIMAWARI_t_minus_10min', 4332290),
                     'B3': ('7x6_HIMAWARI', 4349090),
                     'B4': ('7x6_HIMAWARI_PLUS_13_GFS_MEE', 4355986),
                     'B5': ('B4_PLUS_1_ELEVATION_WIDTH16_SP04_RESIDUAL', 4359426),
                     'B6': ('B4_PLUS_6_STATIC_WIDTH16_SP04_RESIDUAL', 4360866)}
            r['input_spec'], params = specs[r['model_id']]
            r['parameter_count'] = str(params)
        if r['model_id'] in runs:
            s = runs[r['model_id']]
            r.update(status='IN_PROGRESS', execution_state=s['state'], epochs=str(s['sealed_epochs']),
                     global_steps=str(s['returned']), verified_at=as_of, status_as_of=as_of,
                     evidence_path='EVIDENCE_INDEX.md#当前训练状态快照',
                     notes='DATED_METADATA_SNAPSHOT_ONLY; E9 results unavailable; B6 queue PENDING is not completed training.')
    matrix_fields = original_fields + [k for k in matrix[0] if k not in original_fields]
    write_csv('EXPERIMENT_MATRIX.csv', matrix_fields, matrix)
    rows, seen = [], {}

    def add(eid, obj, source, pointer, *, group='all', ids='', epoch='ENDPOINT', kind='RAW_ENDPOINT', split='2024_Development'):
        exp = experiments[eid]
        for sub, value in leaves(obj):
            # SHA, paths and descriptive strings are provenance, not numeric metrics.
            if isinstance(value, str) and not value.startswith(('NOT_', 'UNDEFINED')):
                continue
            metric = sub.lstrip('/')
            key = (eid, str(epoch), split, group, metric)
            if key in seen:
                previous = seen[key]
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    assert math.isclose(float(previous['value']), value, rel_tol=1e-12, abs_tol=1e-12), (eid, metric)
                continue
            numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
            if numeric:
                assert math.isfinite(value)
            row = dict.fromkeys(FIELDS, '')
            row.update(record_type=kind if numeric else 'MISSING_OR_NULL', experiment_id=eid,
                       model_id=exp['model_id'], seed=exp['seed'], loss_arm=exp['loss_arm'], epoch=str(epoch),
                       split=split, comparison_population=exp['comparison_population'], group=group,
                       group_ids_sha256=ids, metric=metric, value=repr(value) if numeric else '',
                       status='RECORDED' if numeric else ('NULL_AS_RECORDED' if value is None else str(value)),
                       unit=unit(metric), source_file=source, source_pointer=pointer + sub,
                       executed_commit=exp['executed_commit'], evaluation_script=exp['evaluation_script'],
                       checkpoint_sha256=exp['checkpoint_reference'] if epoch == 'ENDPOINT' else '')
            rows.append(row)
            seen[key] = row

    for i, exp in enumerate(old['experiments']):
        add(exp['experiment_id'], exp['metrics'], OLD, f'/experiments/{i}/metrics')
    for model, groups in groups29.items():
        for group, obj in groups.items():
            add(f'{model}__E0__s2029__f006', obj['summary'], GROUPS, f'/{model}/{group}/summary', group=group, ids=obj.get('ids_sha256', ''))
    for model, groups in b2['endpoint_groups'].items():
        for group, obj in groups.items():
            eid = f'{model}__E0__s2029__f006'
            add(eid, obj['summary'], B2, f'/endpoint_groups/{model}/{group}/summary', group=group, ids=obj['ids_sha'])
            add(eid, {'q32_coverage': obj['summary']['coverage'][-1]}, B2, f'/endpoint_groups/{model}/{group}/summary', group=group, ids=obj['ids_sha'])
            # The alias points at the actual numeric source, not an invented JSON field.
            alias = seen[(eid, 'ENDPOINT', '2024_Development', group, 'q32_coverage')]
            alias['source_file'] = B2
            alias['source_pointer'] = f'/endpoint_groups/{model}/{group}/summary/coverage/31'
    add('B2__E0__s2029__f006', b2['B2_tail_strata'], B2, '/B2_tail_strata', group='tail_diagnostics')
    add('B2__E0__s2029__f006', b2['epochs'][-1]['development'], B2, '/epochs/8/development')
    for i, item in enumerate(b2['epochs']):
        add('B2__E0__s2029__f006', item['development'], B2, f'/epochs/{i}/development', epoch=item['epoch'], kind='RAW_EPOCH')
        add('B2__E0__s2029__f006', item['train'], B2, f'/epochs/{i}/train', epoch=item['epoch'], kind='RAW_EPOCH', split='2023_Train')
    for seed, models in read(FULL)['groups'].items():
        for model, groups in models.items():
            for group, obj in groups.items():
                add(f'{model}__E0__s{seed}__f006', obj['summary'], FULL,
                    f'/groups/{seed}/{model}/{group}/summary', group=group, ids=obj['ids_sha256'])
    for seed, models in b34['endpoint_groups'].items():
        for model, groups in models.items():
            eid = f'{model}__E0__s{seed}__f006'
            for group, obj in groups.items():
                add(eid, obj, B34, f'/endpoint_groups/{seed}/{model}/{group}', group=group, ids=obj['ids_sha256'])
            add(eid, b34['summary']['endpoints'][seed][model], B34, f'/summary/endpoints/{seed}/{model}')
            add(eid, b34['tail_diagnostics'][seed][model], B34, f'/tail_diagnostics/{seed}/{model}', group='tail_diagnostics')
    # Existing epoch CSV is inherited verbatim numerically; no historical receipt audit.
    epoch_source = PROGRESS + 'epoch_metrics.csv'
    with (ROOT / epoch_source).open(encoding='utf-8-sig', newline='') as f:
        for i, item in enumerate(csv.DictReader(f)):
            for metric, value in item.items():
                if metric in ('experiment_id', 'epoch'):
                    continue
                obj = {metric: float(value)} if value not in ('NOT_AVAILABLE', '') else {metric: 'NOT_AVAILABLE'}
                split = '2023_Train' if metric == 'training_loss' else '2024_Development'
                add(item['experiment_id'], obj, epoch_source, f'/row/{i}', epoch=item['epoch'], kind='RAW_EPOCH', split=split)
    for r in matrix:
        if not any(x['experiment_id'] == r['experiment_id'] for x in rows):
            add(r['experiment_id'], {'endpoint_metrics': 'NOT_AVAILABLE'}, 'EXPERIMENT_MATRIX.csv', '/experiment_id/' + r['experiment_id'])
    raw_rows = list(rows)
    by_exp = defaultdict(dict)
    for row in rows:
        if row['epoch'] == 'ENDPOINT' and row['status'] == 'RECORDED':
            by_exp[row['experiment_id']][(row['group'], row['metric'])] = row
    pairs = [(f'B1_V2__{arm}__s{seed}', f'B0_MATCHED_V2__{arm}__s{seed}', 'B1_MINUS_B0')
             for seed in (2026, 2027) for arm in ('E0', 'E1', 'E2')]
    pairs += [('B2__E0__s2029__f006', 'B3__E0__s2029__f006', 'B2_MINUS_B3')]
    pairs += [(f'B4__E0__s{seed}__f006', f'B3__E0__s{seed}__f006', 'B4_MINUS_B3') for seed in (2029, 2030, 2031)]
    aggregates = defaultdict(list)
    for target, base, comparison in pairs:
        for key in sorted(by_exp[target].keys() & by_exp[base].keys()):
            group, metric = key
            eligible = metric in HEADLINE or metric.startswith('coverage/') or metric.endswith('/conditional_pinball') or metric.endswith('/q32_coverage')
            if not eligible:
                continue
            t, b = by_exp[target][key], by_exp[base][key]
            assert experiments[target]['train_scenes'] == experiments[base]['train_scenes']
            assert experiments[target]['dev_scenes'] == experiments[base]['dev_scenes']
            if t['group_ids_sha256'] and b['group_ids_sha256']:
                assert t['group_ids_sha256'] == b['group_ids_sha256']
            delta = float(t['value']) - float(b['value'])
            row = dict(t, record_type='PAIRED_DELTA', value=repr(delta), reference_value=b['value'],
                       comparison=comparison, reference_experiment_id=base,
                       reference_source_file=b['source_file'], reference_source_pointer=b['source_pointer'],
                       improvement_direction=favorable(metric), n_seeds='1', status='DESCRIPTIVE_PAIRED')
            rows.append(row)
            aggregates[(comparison, t['loss_arm'], group, metric)].append(row)
    for (comparison, arm, group, metric), values in sorted(aggregates.items()):
        if comparison == 'B2_MINUS_B3' or len(values) < 2:
            continue
        nums = [float(r['value']) for r in values]
        seeds = ';'.join(r['seed'] for r in values)
        for kind, value in [('PAIRED_MEAN', statistics.mean(nums)), ('PAIRED_SAMPLE_SD', statistics.stdev(nums))]:
            row = dict(values[0], record_type=kind, experiment_id='AGGREGATE_' + comparison + '_' + arm,
                       seed=seeds, value=repr(value), reference_value='', n_seeds=str(len(values)),
                       reference_experiment_id=';'.join(r['reference_experiment_id'] for r in values),
                       source_file='METRICS.csv', source_pointer='PAIRED_DELTA:' + comparison + ':' + arm + ':' + group + ':' + metric,
                       reference_source_file='', reference_source_pointer='', executed_commit='SEE_CONSTITUENT_ROWS', checkpoint_sha256='')
            rows.append(row)
    # Check this export's seven headline differences against the existing closeout,
    # not the original training or the 126 inherited epoch receipts.
    for metric, result in b34['summary']['metrics'].items():
        vals = aggregates[('B4_MINUS_B3', 'E0', 'all', metric)]
        assert len(vals) == 3
        assert math.isclose(statistics.mean(float(r['value']) for r in vals), result['mean'], abs_tol=1e-15)
        assert math.isclose(statistics.stdev(float(r['value']) for r in vals), result['sample_sd'], abs_tol=1e-15)
    write_csv('METRICS.csv', FIELDS, rows)
    counts = Counter(r['record_type'] for r in rows)
    summary_table = '\n'.join(f"|{metric}|{data['B4_minus_B3_by_seed']['2029']:.12g}|{data['B4_minus_B3_by_seed']['2030']:.12g}|{data['B4_minus_B3_by_seed']['2031']:.12g}|{data['mean']:.12g}|{data['sample_sd']:.12g}|" for metric, data in b34['summary']['metrics'].items())
    status_table = '\n'.join(f"|{r['model']}|2029|IN_PROGRESS|{r['state']}|{r['returned']}|{r['sealed_epochs']}|" for r in snapshot['runs'])
    stage = f'''# 阶段验收统一入口

状态时点：`{as_of}`。B0–B4限定基线交接为 **COMPLETE_WITH_LIMITATIONS（带局限完成）**；B5/B6为 **IN_PROGRESS（进行中）**；最终泛化验收为 **NOT_VERIFIED（未核实）**。这是研究者已限定范围的验收记录，不能把训练完成等同于全部科学假设通过。

|模型|已经完成|尚未完成或限制|本阶段判断|
|---|---|---|---|
|B0/B1|seed2026、2027，各E0/E1/E2固定九轮Train/2024 Dev|两seed；10,455/10,501人口；历史执行commit绑定不完整；历史不确定尝试未追认|限定人口内基线对照可交接|
|B2|seed2029/E0/f006，九轮、4,320更新及2024 Dev，固定E9 LAST|仅一seed；B2/B3指标方向混合，未证明时序增量全面改善|当前探索性配对条目完成|
|B3/B4|2029/2030/2031三个独立seed的九轮Train/Dev及固定E9配对|强雨和q32缺陷、同一开发年，未证明最终泛化或统计显著性|描述性随机性复现完成|
|B5/B6|真实地形准备、冻结方案、明确纠正启动批准；当前串行执行中|两模型各九轮完整Train/Dev、最终权重身份和公平配对尚未齐备|IN_PROGRESS，未通过结果验收|
|B7/B8|保留既有候选实现与工程证据|没有正式科研训练/消融结果|NOT_STARTED（正式训练未启动）|
|2025最终测试|继续冻结|没有当前最终模型推理与评价|NOT_STARTED，不得据此选模|

## 同人口比较范围

- B0/B1：同seed、同E臂的10,455 Train / 10,501 Dev，允许比较单通道时序增量。E0/E1/E2分别记录，损失臂及恢复不算新seed。
- B2/B3：seed2029，959/963，E0/f006、固定E9 LAST。B2为7通道×1时次t−10分钟，4,332,290参数；B3为7×6，4,349,090参数。槽位权重映射乘sqrt(6)，其余72个兼容张量同初始化，不宣称模型完全等价。
- B3/B4：三seed各自共享959/963、初始化兼容部分、顺序与评价掩膜；B4增加13变量GFS MEE（气象环境编码器）。跨seed改变初始化与排列，恢复重放仍属于原seed。
- B5/B6：将与B4 seed2029在同人口、同评价口径下比较；当前没有固定E9结果。不得跨B0/B1与B2–B6的不同训练人口直接归因架构优势。

## 当前训练状态

以下为一次只读元数据快照，不是实时页面，也不把已封口的一轮当作九轮完成。

|模型|seed|阶段状态|执行状态|已返回更新|完整Train/Dev轮数|
|---|---|---|---|---|---|
{status_table}

## 本轮交付核对

五个根目录文件为统一入口，旧报告和实验收据保留。矩阵含29条历史/当前记录；不是29个独立seed或29个已完成模型。`epochs`表示该记录已封口轮数，`global_steps`的当前运行值为快照中的已返回更新；最终训练完成必须同时具备全部Train/Dev收据、账本、预算和固定E9身份。

本轮仅从现有公开数值与只读状态生成交付并核对新CSV结构、原值来源和配对差值。没有重跑训练、模型推理、129个来源审查、126轮收据审查、合成测试或全量归一化。

本轮出版基线：`2ea3c9ce87f4e26c36ed7529c99122bea7cb3f54`。文件所属最终提交由Git历史标识；实际训练代码另见[矩阵](EXPERIMENT_MATRIX.csv)和[证据索引](EVIDENCE_INDEX.md)，不得用本次文档commit替代执行commit。

[实验矩阵](EXPERIMENT_MATRIX.csv) · [完整数值与差值](METRICS.csv) · [科学分析](SCIENTIFIC_ANALYSIS.md) · [证据索引](EVIDENCE_INDEX.md)
'''
    (ROOT / 'STAGE_ACCEPTANCE.md').write_text(stage, encoding='utf-8')
    analysis = f'''# 科学分析统一入口

B0–B4在已限定范围内可作基线交接；当前证据支持开发集上的局部描述性结论。B5/B6仍IN_PROGRESS，地形增益及最终泛化均未验证。

## B3/B4：全部三个seed

下表统一为 **B4−B3**。Brier Score（布里尔分数）及Conditional Pinball Loss（条件分位数损失）越低越好；AUROC（ROC曲线下面积）和AP（平均精确率）越高越好。q32 Coverage（最高分位数覆盖率）应接近名义0.984375，不能无条件理解为越大越好。表中仅为便读而舍入，CSV保存原始浮点精度。

|指标|2029差值|2030差值|2031差值|差值均值|样本标准差（ddof=1）|
|---|---|---|---|---|---|
{summary_table}

三个seed的总体Brier、AUROC、AP和条件Pinball均同向改善，支持本人口/开发年中MEE增量的描述性复现。它不能区分GFS信息、额外参数及融合结构各自的因果贡献，不能直接证明物理机制或全部雨强均获益。

## 必须保留的反例

- (20,30]与(30,50] mm/h条件Pinball的三seed平均B4−B3分别为+0.02284020139478345和+0.02926448537140706，均退化；(30,50]三个seed均退化。seed2031两层分别+0.06578915690489107、+0.08003864767502422。
- seed2029的06 UTC Brier退化+0.0001363967192149207；seed2030的18 UTC退化+0.0004587919574727817。不能用三seed平均改善掩盖单seed/时次反例。
- q32六个终点仅约93.5050%–94.6094%，低于98.4375%名义水平约3.8281–4.9325个百分点。seed2031 B4覆盖率比B3下降0.0015423471139228706；均值改善不等于校准通过。
- seed2030强雨q32 covered：B3为12/564、0/147，B4为5/564、0/147；seed2031 B3为109/564、12/147，B4为20/564、0/147。seed2029雨强层covered未保存，标记NOT_AVAILABLE，不补造或追加推理。按真实雨强分层是按结果条件化，不能要求每个层都达到同一名义分位覆盖。
- >50 mm/h在959/963人口中只有6个有雨像元时次，不能当作6场独立暴雨，也不能稳定评价极端尾部。

## B0/B1与B2/B3

B0/B1在10,455/10,501人口的两seed配对提供时序信息增量的限定证据；CSV分别保留六个同seed/同损失臂配对，禁止将损失臂当独立seed。旧Phase-A、BEST与FinalFit是不同协议，仅列示原记录，不纳入固定九轮配对均值。

B2相对B3（统一B2−B3）：Brier为−0.0009406648154928754，AUROC为−0.0026810498852304354，AP为−0.012892029278753436，条件Pinball为+0.0002321528279146945，q32覆盖为−0.004654014025795683。B2 Brier更好而B3区分能力及条件Pinball更好，单seed不支持时间增量全面改善；输入维度和参数差异已明确记录。

## B5/B6与结论边界

本轮地形实验采用已批准的WGS84面积聚合、原生米制梯度、目标footprint、width16 SP04残差融合；B5增加海拔，B6增加完整六静态通道。DEM本地源SHA固定，但供应商发布版本链NOT_VERIFIED；研究者接受该限制用于探索性消融。零输出残差保证起点行为与B4相同，不证明训练后一定获益。当前两个模型固定E9尚未齐备，地形正/负结果均不得预填。

三seed主要检验训练随机性；相邻seed按seed+epoch−1排列规则存在移位重叠，不能声称所有轮排列彼此独立。大量像元也不是大量独立事件。重复使用2024 Dev存在开发集选择影响，没有事件级独立性估计、置信区间或显著性声明。不同人口不可跨模型排名归因，2025最终测试继续冻结；旧catalogue/QC访问事实不改写为历史从未访问。

## CSV读取规范

`METRICS.csv`为长表（一个数值一行），共{len(rows)}行。`RAW_ENDPOINT`保存现有完整终点指标对象的数值叶子，包括总体、四UTC、强雨场景、七雨强层、已保存的32分位数及可靠性分箱/充分量；`RAW_EPOCH`继承已有逐轮公开数值与B2九轮摘要。为补齐新seed的完整终点字段，本轮仅摘录4份既有E9评价JSON的summary并核对原有字节SHA，未重做历史逐轮审查；[完整终点摘录]({FULL})不含场景ID、逐像元预测或私有路径。未扩展发布的新seed逐轮完整数值仍按原收据ID索引。这里的“原始指标”指未舍入的已保存统计量，不是逐像元预测或原始气象载荷。

`PAIRED_DELTA`为目标值减reference_value；`PAIRED_MEAN`、`PAIRED_SAMPLE_SD`只对同口径seed差值计算，样本数在n_seeds，非独立事件数。不同E臂不混合聚合。`metric`中`/数字/`为源数组的零起始下标，32分位数中31即q32；雨强层upper=null表示无穷上界，其他null保持原含义。计数、分子、tau和边界只是充分量/元数据，不全是性能指标，不能对它们解释“提升”。coverage数组方向应看对应tau偏差。

`MISSING_OR_NULL`原样保留缺失/不可估计状态，value为空，不是零；B5/B6不填最终数值。源文件和JSON Pointer（JSON定位指针）或CSV零起始row可回查；q32别名指向coverage/31。共享内容只保留一个数值行；新增来源不能改写旧值。详细配置、Git执行身份、评价脚本和数据版本由experiment_id连接[矩阵](EXPERIMENT_MATRIX.csv)。
'''
    (ROOT / 'SCIENTIFIC_ANALYSIS.md').write_text(analysis, encoding='utf-8')
    input_names = [BASE, OLD, GROUPS, B2, B34, FULL, epoch_source,
                   READY + 'evidence/b5_b6_corrected_start_launch.json',
                   READY + 'evidence/b5_b6_initial_start_stop.json',
                   READY + 'evidence/b5_b6_terrain_production.json']
    source_table = '\n'.join(f'|[{name}]({name})|`{digest(name)}`|' for name in input_names)
    identity_table = '\n'.join(f"|{r['model_id']}|{r['seed']}|`{r['checkpoint_reference']}`|`{r['executed_commit']}`|" for r in matrix if r['comparison_population'] == 'CORE_F006_959_963' and 'failed' not in r['experiment_id'])
    output_table = '\n'.join(f'|[{name}]({name})|`{digest(name)}`|' for name in ['STAGE_ACCEPTANCE.md', 'EXPERIMENT_MATRIX.csv', 'METRICS.csv', 'SCIENTIFIC_ANALYSIS.md'])
    evidence = f'''# 统一证据索引

出版基线commit：`2ea3c9ce87f4e26c36ed7529c99122bea7cb3f54`。本五文件的版本由所属Git提交标识，不伪造自引用commit。实际模型代码独立绑定如下。研究者为主体，AI辅助摘录；公开SHA约束原件身份，不等于外部已独立复现未公开数据。

## 当前训练状态快照

仅摘录现有只读进度服务元数据；状态时点是UTC（北京时间加8小时），不是页面实时值。B5/B6阶段均IN_PROGRESS，B6执行PENDING。终态须依据完整新收据另行收口，不从checkpoint存在或部分轮次判完成。

<!-- STATUS_SNAPSHOT -->
```json
{json.dumps(snapshot, ensure_ascii=False, indent=2)}
```

## 训练日志与本地原件定位

公开脱敏ID与原件的映射沿用既有索引；不公开私人绝对路径、原始数据、权重或未脱敏账本。

|范围|训练日志/逐轮收据|模型、评价与本地原件身份|
|---|---|---|
|B0/B1，2026/2027及历史失败|[原实验摘录]({OLD})、[逐轮日志索引]({PROGRESS}evidence/epoch_receipts.json)、[历史campaign]({PROGRESS}evidence/historical_campaigns.json)|[原件source_id、bytes、SHA及可公开URL]({PROGRESS}evidence/source_manifest.json)；每实验source_ids连接原结果，矩阵保留历史执行commit NOT_VERIFIED|
|B2/2029|[完成证据]({B2})的epochs、checkpoint_metadata、ledger、actual_io|sources中B2_COMPLETION、B2_DEV_E*、B2_IO_*等脱敏ID/字节SHA；全部9轮原始JSON/SQLite/权重LOCAL_ONLY；E9文件曾实际重哈希|
|B3/B4，2029|[保留执行收据]({PROGRESS}evidence/seed2029_execution.json)、[原件清单]({PROGRESS}evidence/source_manifest.json)|[总体及分组指标]({GROUPS})、[三seed完成收据]({B34})的s2029/B3或B4/development_09.json字节SHA；继承既有权重核验|
|B3/B4，2030/2031|[原中止事实]({READY}evidence/b3_b4_multiseed_stop.json)、[三seed收口]({B34})的epochs/tasks/budget_closure|sources中s2030/s2031/{'{model}'}/development_09.json、训练日志、LAST receipt、updates.sqlite、读取账本分别有SHA；每个epoch/模型/seed定位，不把恢复段计为新seed|
|2030/2031完整终点字段|[本轮4份既有E9数值摘录]({FULL})|groups包含六评价分组的完整summary，sources字节SHA与既有三seed收口一致；仅补足数值出版，不重新推理或读取原始气象|
|B5/B6，2029|[一次纠正启动]({READY}evidence/b5_b6_corrected_start_launch.json)、[原失败]({READY}evidence/b5_b6_initial_start_stop.json)|[冻结纠正提案]({READY}evidence/b5_b6_corrected_start_proposal.json)、[地形源/网格/静态包SHA]({READY}evidence/b5_b6_terrain_production.json)；当前E9身份NOT_AVAILABLE|

本地原件由研究者保存，公开源ID不是可下载原件的承诺。旧缺口保留：seed2027历史未核验尝试、旧恢复授权边界，以及未直接绑定的B0/B1历史执行commit。原始validation规范化digest、文件字节SHA和权重SHA互不替代。旧记录中的状态是当时快照，由此统一入口给出当前判断；原件未改写。

## 当前核心模型的固定E9身份

|模型|seed|固定E9权重SHA256|实际执行commit或分段|
|---|---|---|---|
{identity_table}

B4/2030矩阵终点commit为943da95，其E1继承52a8e90，E2–9由943da95执行；累计4,710实际尝试含390必要重放，有效轨迹4,320，成本见三seed收口。历史原始失败段仍保留。B5/B6本次纠正批准已消费，不允许额外重试。

## 数据与评价绑定

当前959/963人口SHA256：`{b34['data_version']['population_sha256']}`；populations文件SHA：`{b34['data_version']['populations_sha256']}`；训练统计SHA：`{b34['data_version']['statistics_sha256']}`；target QC SHA：`{b34['data_version']['target_QC_sha256']}`。2023 Train / 2024 Development、四UTC、f006回顾估计；2025冻结。B13保持既有训练集scaler（mean=271.60515414265217 K，std=19.93959597783802 K，源身份656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31），不声称它在当前959重新拟合。

核心评价脚本：[{b34['evaluation_script']}]({b34['evaluation_script']})，执行版SHA256 `{b34['evaluation_script_sha256']}`；精确AUROC/AP及冻结float32阈值>0.1 mm/h口径继承[metrics.py](src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/metrics.py)。Dev有效像元3,303,090、有雨407,820；不同人口和旧终点逐行保留。脚本链接指工作分支，重现执行身份必须同时使用矩阵中的执行commit及上述SHA。

## 本轮输入身份与交付校验

本轮仅校验新增导出及差值，不重复历史129来源/126轮审查；历史收据本身不被改为本轮重新核验。以下为直接采用的公开输入字节身份：

|公开输入|SHA256|
|---|---|
{source_table}

五个统一文件及[生成器](tools/research_readiness/build_unified_delivery.py)不读取原始气象、权重或2025。运行`python tools/research_readiness/build_unified_delivery.py`可按本页嵌入快照重建四个表/报告及本索引；它继承源收据，检查29个唯一实验ID、原值一致性、人口/组ID配对和三seed均值/样本标准差。它不是训练或全量实验复核命令。

导出构成：`{json.dumps(dict(counts), ensure_ascii=False, sort_keys=True)}`。存在完整指标的每个源数值叶子都保留；旧逐轮摘要数值仅转录。缺失结果不补零，q32缺失分层不反推。公开输入与本索引嵌入快照足以重建本交付，不需要公开私有目录。

|统一交付|SHA256|
|---|---|
{output_table}

本索引自身身份由Git标识，不写自引用文件哈希。旧索引、历史PUBLICATION_MANIFEST与已批准实验收据保持原字节。当前工作分支提交/推送不构成main合并或新训练批准。
'''
    (ROOT / 'EVIDENCE_INDEX.md').write_text(evidence, encoding='utf-8')
    # Publication-only checks: no private absolute paths or accidental data blobs.
    for name in ['STAGE_ACCEPTANCE.md', 'SCIENTIFIC_ANALYSIS.md', 'EVIDENCE_INDEX.md', 'EXPERIMENT_MATRIX.csv', 'METRICS.csv']:
        text = (ROOT / name).read_text(encoding='utf-8')
        assert not re.search(r'[A-Za-z]:[\\/]|/Users/|/home/', text), name
    assert all(r['status'] == 'IN_PROGRESS' for r in matrix if r['model_id'] in ('B5', 'B6'))
    assert not any(r['model_id'] in ('B5', 'B6') and r['status'] == 'RECORDED' for r in raw_rows)
    print(json.dumps(dict(status='PASS_PUBLIC_EXPORT_ONLY', experiments=len(matrix), metrics=len(rows), records=counts,
                          historical_audits_rerun=False, optimizer_updates=0, raw_weather_reads=0, status_as_of=as_of), ensure_ascii=False))


if __name__ == '__main__':
    main()
