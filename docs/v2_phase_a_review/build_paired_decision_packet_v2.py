"""Metadata-only decision packet; requires real terminal audits and full BEST review.

Does not import torch, open raw sources/checkpoint binaries, apply state, train,
select a checkpoint or infer. LaTeX is editable; PDF verification/publication
remain separate required completion gates.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from completion_gate import check_pair, reconcile_selection, resolve_authority

KINDS = ('B0_MATCHED_V2', 'B1_V2')
FROZEN = {
    'protocol_sha256': 'a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be',
    'head_sha256': '3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e',
    'normalization_sha256': '656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31',
}
METRICS = ('global_val_core_loss', 'Brier_Score', 'AUROC', 'Average_Precision',
           'conditional_mean_pinball')
REPO = Path(__file__).resolve().parents[2]


def load(path):
    path = Path(path).resolve()
    if path.suffix != '.json' or not path.is_relative_to(REPO):
        raise PermissionError('Only repository JSON evidence may be read')
    with path.open(encoding='utf-8-sig') as stream:
        return json.load(stream)


def identity(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'absolute_local_path': str(path), 'bytes': path.stat().st_size, 'sha256': sha}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def no_training_or_2025(value):
    for key, expected in (('MODEL_PARAMETERS_UPDATED', False), ('OPTIMIZER_STEPS', 0),
                          ('BACKWARD_CALLS', 0), ('2025_RAW_ACCESS', 0),
                          ('2025_PIXELS_READ', 0), ('V2_PHASE_B_AUTHORIZED', False)):
        require(key in value and value[key] == expected, 'Forbidden operation or missing proof: ' + key)


def validate_inputs(review, audits, early, counters, histories):
    """Pure evidence checks, also exercised with isolated corruption fixtures."""
    require(review['status'] == 'PAIRED_FULL_2024_REVIEW_PASS', 'Real paired BEST review missing')
    no_training_or_2025(review)
    require(review['checkpoint_selection_performed'] is False, 'Reselection forbidden')
    require(set(review['models']) == set(KINDS), 'Both reviewed models required')
    for kind in KINDS:
        result, audit, es, count, history = (
            review['models'][kind], audits[kind], early[kind], counters[kind], histories[kind])
        require(result['status'] == 'FULL_2024_BEST_REVIEW_PASS' and result['model'] == kind,
                'Full review identity mismatch')
        no_training_or_2025(result)
        no_training_or_2025(audit)
        require(audit['status'] == 'TERMINAL_MODEL_AUDIT_PASS' and audit['model'] == kind,
                'Terminal audit missing')
        require(audit['historical_artifacts_unchanged'] is True and
                audit['STATE_APPLICATION_PERFORMED'] is False, 'Audit preservation proof missing')
        require(all(audit[k] == v for k, v in FROZEN.items()), 'Frozen SHA mismatch')
        require(result['BEST'] == audit['BEST'], 'Reviewed BEST differs from terminal BEST')
        require(result['model_state_sha256_before'] == result['model_state_sha256_after'],
                'Inference changed model state')
        require(result['training_best_metric_reconciliation']['tolerance'] == 0 and
                not result['training_best_metric_reconciliation']['mismatches'],
                'Saved BEST validation must reconcile exactly')
        actual_es = reconcile_selection(history)
        require(actual_es['termination_reason'] != 'NOT_TERMINATED', 'Premature completion')
        require(es['status'] == 'PASS' and es['patience'] == 8 and es['min_delta'] == 1e-4 and
                es['uses_only_global_val_core_loss'] is True, 'Early-stop frozen rule differs')
        require(all(es[k] == v and audit['final'][k] == v for k, v in actual_es.items()),
                'Early-stop reconciliation differs')
        require(audit['final']['status'] == 'COMPLETE', 'Incomplete terminal status')
        require(result['BEST'] == history[actual_es['best_checkpoint_epoch'] - 1]['checkpoint'] and
                audit['LAST'] == history[-1]['checkpoint'], 'History/BEST/LAST mismatch')
        metrics = result['metrics']
        require((metrics['scenes'], metrics['forwards'], metrics['N_valid']) ==
                (10501, 1313, 36018430), 'Full validation coverage differs')
        require(result['REVIEW_FORWARD_CALLS'] == 1313, 'Review forward count differs')
        saved = history[actual_es['best_checkpoint_epoch'] - 1]['validation']
        require(metrics['global_val_core_loss'] == saved['global_val_core_loss'] and
                metrics['N_rain'] == saved['N_rain'], 'BEST core loss/labels differ')
        for name in METRICS:
            require(name in metrics and (metrics[name] is None or math.isfinite(metrics[name])),
                    'Missing/nonfinite metric: ' + name)
            if metrics[name] is None:
                allowed = (name == 'AUROC' and metrics['N_rain'] in (0, metrics['N_valid'])) or (
                    name in ('Average_Precision', 'conditional_mean_pinball') and metrics['N_rain'] == 0)
                require(allowed, 'Undefined metric not justified by label count: ' + name)
        require(metrics['physical_materialization'] is False, 'Physical materialization forbidden')
        require(all(metrics[name] == 0 for name in
                    ('strict_crossing_count', 'support_violation_count', 'nonfinite_count')),
                'Numerical contract violated')
        require(count['status'] == 'PASS', 'Counter audit missing')
        exact = count['retained_trajectory_exact_counters']
        epochs = len(history)
        expected = {'FORWARD_CALLS': epochs * 6541, 'TRAIN_FORWARDS': epochs * 5228,
                    'VALIDATION_FORWARDS': epochs * 1313, 'BACKWARD_CALLS': epochs * 5228,
                    'OPTIMIZER_STEP_ATTEMPTS': epochs * 5228, 'OPTIMIZER_STEPS': epochs * 5228,
                    'CHECKPOINT_WRITES': epochs}
        require(all(exact[k] == v for k, v in expected.items()), 'Retained counters differ')
        require(all(count[k] == 0 for k in
                    ('audit_optimizer_steps', 'audit_backward_calls', 'audit_forward_calls')),
                'Audit operations contaminated formal counters')
        for io in (count['all_attempt_source_io'], result['io']):
            require(all(io[k] == 0 for k in
                        ('2025_RAW_ACCESS', '2025_PIXELS_READ', 'DENIED_ATTEMPTS')),
                    'Source firewall violated')
        tail = result['upper_tail_diagnostics']
        require((tail['phase'], tail['scenes'], tail['forwards']) == ('VALIDATION', 10501, 1313)
                and tail['affects_loss_BEST_early_stop_LR_parameters_batch_or_termination'] is False,
                'Read-only diagnostics coverage/policy differs')
    a, b = (review['models'][k] for k in KINDS)
    require(a['validation_sample_ids_sha256'] == b['validation_sample_ids_sha256'] and
            a['metrics']['N_rain'] == b['metrics']['N_rain'], 'Common validation sample set differs')


def tex(value):
    replacements = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
                    '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}'}
    return ''.join(replacements.get(c, c) for c in str(value))


def number(value):
    if value is None:
        return '未定义'
    return format(value, '.12g') if isinstance(value, float) else str(value)


def render_tex(packet):
    """No charts; all report numbers come from verified input evidence."""
    models = packet['models']
    labels = {'B0_MATCHED_V2': 'B0-Matched-v2', 'B1_V2': 'B1-v2'}
    lines = [
        r'\documentclass[UTF8,a4paper,11pt,fontset=windows]{ctexart}',
        r'\usepackage[margin=22mm]{geometry}',
        r'\usepackage{booktabs,longtable,array,hyperref}',
        r'\hypersetup{hidelinks}\setlength{\parindent}{0pt}',
        r'\setlength{\parskip}{5pt}\renewcommand{\arraystretch}{1.15}',
        r'\title{YunTAPR-Net v2 配对 Phase-A\\开发实验决策包}',
        r'\author{工程审计记录}\date{' + tex(packet['created_utc']) + '}',
        r'\begin{document}\maketitle',
        r'\section{执行范围与完成边界}',
        '两个模型均按冻结规则完成 Phase-A。BEST 仅由 global validation core loss 选择；'
        '上尾诊断不影响损失、BEST、早停、学习率、参数或 batch。',
        '本报告使用共同的 2023 训练样本集合（10,455 场景）与 2024 验证样本集合'
        '（10,501 场景）。2024 指标属于开发阶段验证，不构成 2025 泛化评价。',
        r'\textbf{2025 raw access=0；2025 pixels read=0；Phase-B 未授权。}',
        '研究者仍需审查本决策包。PDF 排版核验和最终 GitHub 发布由独立收尾记录证明。',
        r'\section{冻结协议与配对输入}',
        'B0-Matched-v2 使用最新 B13 单帧；B1-v2 使用六个因果历史 B13 时相。'
        '其余 backbone、SP04、输出头、损失、优化器和评价合同一致。',
        'Seed=2026；全新同名同形配对初始化；共享 normalization：'
        'mean=271.60515414265217 K，std=19.93959597783802 K。',
        'AdamW；训练 batch=2、尾部 singleton 保留；每 epoch 5,228 updates；最多 50 epochs；'
        r'base LR=$10^{-4}$，cosine min LR=$10^{-6}$；warmup=5,228，固定 horizon=261,400；'
        'gradient clip=5；validation batch=8，尾部 5 场景。',
        r'32 条件分位数，$\tau_i=(i-0.5)/32$；$z_0=\log(1+0.1)$；'
        r'$\epsilon_w=\epsilon_{span}=10^{-4}$；FP64 归一化单调变换。',
        '训练与验证核心路径不实例化物理降水。严格有限性、单调性、支持域和梯度保护保持冻结；'
        '无 clamp、sort、静默修复或自动跳 batch。',
        r'\section{BEST、早停与正式计数}',
        r'\begin{tabular}{lrr}\toprule 项目 & B0-Matched-v2 & B1-v2\\\midrule',
    ]
    fields = [
        ('完整 epoch', lambda m: m['early_stopping']['completed_epoch']),
        ('BEST epoch', lambda m: m['early_stopping']['best_checkpoint_epoch']),
        ('early-stop best epoch', lambda m: m['early_stopping']['best_es_epoch']),
        ('early-stop best value', lambda m: m['early_stopping']['best_es_value']),
        ('最终 patience counter', lambda m: m['early_stopping']['final_early_stop_counter']),
        ('保留轨迹 optimizer steps', lambda m: m['formal_counters']['retained_trajectory_exact_counters']['OPTIMIZER_STEPS']),
    ]
    for label, getter in fields:
        lines.append(tex(label) + ' & ' + ' & '.join(tex(number(getter(models[k]))) for k in KINDS) + r'\\')
    lines += [r'\bottomrule\end{tabular}',
              r'早停固定 patience=8、min\_delta=$10^{-4}$；BEST 严格最小值选择与 early-stop '
              '最小改善量分别重算，不能互相替代。']
    for kind in KINDS:
        m = models[kind]
        bounds = m['formal_counters']['all_attempt_optimizer_reconciliation']
        lines.append(tex(labels[kind]) + '：termination=' +
                     tex(m['early_stopping']['termination_reason']) + '；all-attempt updates=' +
                     tex(str(bounds['all_attempt_updates_lower_bound']) + ' 至 ' +
                         str(bounds['all_attempt_updates_upper_bound'])) +
                     '；discarded updates=' + tex(str(bounds['discarded_updates_lower_bound']) +
                     ' 至 ' + str(bounds['discarded_updates_upper_bound'])) + '。')
    lines += ['中断尝试完整保留。已知区间不补造精确值；半 epoch 状态没有进入保留轨迹。'
              '正式、工程测试、审计与只读推理计数分别登记。',
              r'\section{全量 2024 只读 BEST 比较}',
              '两模型按共同固定顺序完成各 1,313 次只读 forward。每模型有效云南 scene-pixel exposure '
              '为 36,018,430；固定 mask 含 3,430 格点。核心损失逐项零容差对账通过，模型参数 SHA 前后一致。',
              r'\begin{tabular}{lrr}\toprule 指标 & B0-Matched-v2 & B1-v2\\\midrule']
    for name in METRICS:
        lines.append(tex(name) + ' & ' + ' & '.join(tex(number(models[k]['metrics'][name])) for k in KINDS) + r'\\')
    lines += [r'\bottomrule\end{tabular}',
              '核心损失按全体有效格点的原始分子全局累计；Brier 使用发生概率；AUROC/AP 使用'
              '固定事件标签和并列分数组；conditional mean pinball 的分母为雨像元数，单位为 log1p(mm/h)。'
              '不定义 POD/FAR/CSI 新阈值，不做校准、阈值调优、checkpoint 或 epoch 重选。',
              r'\section{只读上尾诊断}',
              '下面为各 BEST 的全量 2024 验证诊断。全部完整 epoch 的 TRAIN/VALIDATION 诊断另存'
              ' upper-tail history。p99/p99.9 是每次 forward 的 q32 最大值分布，采用 FP64 linear quantile；'
              '每次 forward 等权，不是全部像元池的分位数。',
              r'\begin{longtable}{llrrr}\toprule 模型/区域 & max qlog & p99 & p99.9 & FP64风险\\\midrule\endhead']
    for kind in KINDS:
        for partition, label in (('YUNNAN_INSIDE', '云南内'), ('YUNNAN_OUTSIDE', '云南外')):
            tail = models[kind]['upper_tail_diagnostics'][partition]
            cells = [labels[kind] + '/' + label, number(tail['max_qlog']),
                     number(tail['q32_per_forward_max_p99']), number(tail['q32_per_forward_max_p99_9']),
                     str(tail['FP64_PHYSICAL_OVERFLOW_RISK'])]
            lines.append(' & '.join(tex(x) for x in cells) + r'\\')
    lines += [r'\bottomrule\end{longtable}',
              'FP64 物理边界为 log1p(float64 max)=709.782712893384。风险标记仅针对观察到的轨迹，'
              '不保证未来不存在风险；它不是训练停止或修复条件。',
              r'\begin{longtable}{llrrr}\toprule 模型 & 区域 & mm/h阈值 & pixel-tau & pixel-any-tau\\\midrule\endhead']
    for kind in KINDS:
        for partition, label in (('YUNNAN_INSIDE', '云南内'), ('YUNNAN_OUTSIDE', '云南外')):
            for threshold in ('10', '50', '100', '500', '1000'):
                count = models[kind]['upper_tail_diagnostics'][partition]['threshold_exceedances'][threshold]
                cells = [labels[kind], label, threshold, str(count['scene_pixel_tau_exposure']),
                         str(count['scene_pixel_any_tau_exposure'])]
                lines.append(' & '.join(tex(x) for x in cells) + r'\\')
    lines += [r'\bottomrule\end{longtable}',
              '仅比较 qlog > log1p(阈值)，不执行 expm1。pixel-tau 按每个 scene、像元、tau 计数；'
              'pixel-any-tau 按该 scene-pixel 至少一个 tau 超过阈值计数。所有阈值仅作描述，'
              '不形成训练规则或新 QC。', r'\section{冻结来源与检查点登记}',
              r'\begin{longtable}{p{36mm}p{116mm}}\toprule 身份 & SHA / commit\\\midrule\endhead']
    for label, value in packet['frozen_identities'].items():
        lines.append(tex(label) + r' & {\footnotesize\ttfamily ' + tex(value) + r'}\\')
    lines += [r'\bottomrule\end{longtable}']
    for kind in KINDS:
        for name in ('BEST', 'LAST'):
            ref = models[kind][name]
            lines += [tex(labels[kind] + ' ' + name) + '：epoch=' + str(ref['epoch']) +
                      '，bytes=' + str(ref['bytes']) + r'，SHA256=\par',
                      r'{\footnotesize\ttfamily ' + tex(ref['sha256']) + r'}\par',
                      r'{\footnotesize\path{' + ref['absolute_local_path'].replace('\\', '/') + r'}}\par']
    lines += ['所有 checkpoint 文件和内部 model/optimizer/scheduler/RNG/permutation 身份经完整审计。'
              'GitHub 仅保存身份、SHA、大小、本地路径与轻量证据，不上传模型或优化器二进制。',
              '可机器核验的来源路径、SHA、完整历史、counter scopes 和 per-epoch audit 见本包 JSON/CSV '
              '及其 source evidence 索引。', r'\section{研究者审查事项}',
              '本包不自动接受实验，不转移 epoch budget，不启动 FinalFit、Phase-B 或 2025 推理。'
              '请研究者基于已冻结比较规则审查开发阶段结果，再单独决定后续授权。',
              r'\textbf{RESEARCHER\_PHASE\_A\_REVIEW\_REQUIRED=true；V2\_PHASE\_B\_AUTHORIZED=false。}',
              r'\end{document}']
    return '\n'.join(lines) + '\n'


def write_csv(path, rows):
    with path.open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--authorization-sha256', required=True)
    parser.add_argument('--review-root', type=Path, required=True)
    parser.add_argument('--b0-audit', type=Path, required=True)
    parser.add_argument('--b1-audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(identity(args.authorization)['sha256'] == args.authorization_sha256, 'Authorization SHA differs')
    gate = check_pair(args.authorization)
    if gate['status'] != 'METADATA_COMPLETION_GATE_PASS':
        print(json.dumps(gate, ensure_ascii=False)); return
    auth, _ = resolve_authority(args.authorization)
    public = Path(auth['publication_root'])
    paths = [args.authorization, args.review_root / 'paired_best_metrics.json']
    review = load(paths[-1])
    audits, early, counters, histories = {}, {}, {}, {}
    for kind, root in zip(KINDS, (args.b0_audit, args.b1_audit)):
        names = ('terminal_model_audit.json', 'early_stopping_reconciliation.json',
                 'formal_counter_reconciliation.json')
        paths.extend(root / name for name in names)
        audits[kind], early[kind], counters[kind] = (load(root / name) for name in names)
        for name in ('checkpoint_identity_audit.json', 'epoch_audit.json'):
            proof_path = root / name
            proof = load(proof_path)
            require(proof['status'] == 'PASS', 'Complete audit proof missing: ' + name)
            paths.append(proof_path)
        history_path = public / kind / 'training_validation_history.json'
        paths.append(history_path); histories[kind] = load(history_path)
    validate_inputs(review, audits, early, counters, histories)
    frozen = {**FROZEN, 'scientific_commit': auth['scientific_commit'],
              'execution_commit': auth['execution_commit'], 'authorization_sha256': args.authorization_sha256,
              'packet_generator_sha256': identity(Path(__file__))['sha256'],
              **{k + '_initial_state_sha256': v for k, v in auth['initial_state_sha256'].items()}}
    packet = {'status': 'PAIRED_DECISION_PACKET_PDF_AND_PUBLICATION_PENDING',
              'pair_id': auth['pair_id'], 'created_utc': datetime.now(timezone.utc).isoformat(),
              'frozen_identities': frozen, 'source_evidence': [identity(p) for p in paths],
              'models': {k: {'BEST': audits[k]['BEST'], 'LAST': audits[k]['LAST'],
                            'early_stopping': early[k], 'formal_counters': counters[k],
                            'metrics': review['models'][k]['metrics'],
                            'upper_tail_diagnostics': review['models'][k]['upper_tail_diagnostics']} for k in KINDS},
              'PAIR_PHASE_A_TRAINING_COMPLETE': True, 'FULL_2024_BEST_REVIEW_EXECUTED': True,
              'RESEARCHER_PHASE_A_REVIEW_REQUIRED': True, 'V2_PHASE_B_AUTHORIZED': False,
              '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
              'PACKET_GENERATION_FORWARD_CALLS': 0, 'PACKET_GENERATION_BACKWARD_CALLS': 0,
              'PACKET_GENERATION_OPTIMIZER_STEPS': 0, 'PACKET_GENERATION_RAW_SOURCE_OPENS': 0,
              'PDF_VISUALLY_VERIFIED': False, 'FINAL_GITHUB_PUBLICATION_VERIFIED': False}
    out = args.output.resolve()
    require(out.is_relative_to(REPO / 'docs/v2_phase_a_review/paired_packets'), 'Independent packet root required')
    out.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        with (out / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    save('paired_comparison_packet.json', packet)
    save('early_stopping_reconciliation.json', early)
    save('checkpoint_identity_registry.json', {k: {n: audits[k][n] for n in ('BEST', 'LAST')} for k in KINDS})
    training_rows, tail_rows = [], []
    for kind in KINDS:
        save(kind + '_COMPLETE_RUN_MANIFEST.json',
             {'model': kind, 'pair_id': auth['pair_id'], 'run_id': auth['run_ids'][kind],
              'absolute_checkpoint_root': str(Path(auth['checkpoint_roots'][kind]) / auth['run_ids'][kind]),
              'frozen_identities': frozen, 'audit': audits[kind], 'formal_counters': counters[kind],
              'source_evidence': packet['source_evidence'], 'V2_PHASE_B_AUTHORIZED': False,
              '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0})
        for row in histories[kind]:
            training_rows.append({'model': kind, 'epoch': row['epoch'],
                'train_core_loss': row['training']['global_core_loss'],
                'global_val_core_loss': row['validation']['global_val_core_loss'],
                'checkpoint_selected': row['decision']['checkpoint_selected'],
                'early_stop_improvement': row['decision']['early_stop_improvement'],
                'early_stop_counter': row['selection']['non_improvement_count'],
                'checkpoint_sha256': row['checkpoint']['sha256']})
            for phase in ('TRAIN', 'VALIDATION'):
                for partition in ('YUNNAN_INSIDE', 'YUNNAN_OUTSIDE'):
                    tail = row['diagnostics'][phase][partition]
                    for threshold, counts in tail['threshold_exceedances'].items():
                        tail_rows.append({'model': kind, 'epoch': row['epoch'], 'phase': phase,
                            'partition': partition, 'max_qlog': tail['max_qlog'],
                            'q32_per_forward_max_p99': tail['q32_per_forward_max_p99'],
                            'q32_per_forward_max_p99_9': tail['q32_per_forward_max_p99_9'],
                            'FP64_PHYSICAL_OVERFLOW_RISK': tail['FP64_PHYSICAL_OVERFLOW_RISK'],
                            'threshold_mm_h': threshold, **counts,
                            'total_scene_pixel_tau_exposure': tail['scene_pixel_tau_exposure'],
                            'total_scene_pixel_any_tau_exposure': tail['scene_pixel_any_tau_exposure']})
    write_csv(out / 'training_validation_history.csv', training_rows)
    write_csv(out / 'upper_tail_history.csv', tail_rows)
    (out / 'V2_PAIRED_PHASE_A_REVIEW.tex').write_text(render_tex(packet), encoding='utf-8', newline='\n')
    md = ['# v2 配对 Phase-A 开发实验决策包', '', '两模型完整终止审计与全量 2024 只读 BEST 评价已通过。',
          '样本集合：2023 Train=10,455；2024 Validation=10,501；2025 不访问；Phase-B 不授权。',
          '', '|模型|BEST epoch|完整 epoch|global_val_core_loss|Brier|AUROC|AP|conditional pinball|',
          '|---|---:|---:|---:|---:|---:|---:|---:|']
    for kind in KINDS:
        m = packet['models'][kind]
        values = [kind, str(m['early_stopping']['best_checkpoint_epoch']),
                  str(m['early_stopping']['completed_epoch'])]
        values.extend(number(m['metrics'][n]) for n in METRICS)
        md.append('|' + '|'.join(values) + '|')
    md += ['', '完整证据见 JSON/CSV；可编辑报告源为同目录 LaTeX。',
           'PDF 排版核验与最终 GitHub 发布仍待独立收尾，不将这些未运行项目标为 PASS。',
           'RESEARCHER_PHASE_A_REVIEW_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false。', '']
    (out / 'V2_PAIRED_PHASE_A_REVIEW.md').write_text('\n'.join(md), encoding='utf-8', newline='\n')
    save('packet_manifest.json', {'status': 'PDF_AND_PUBLICATION_PENDING', 'sources': packet['source_evidence'],
         'artifacts': [identity(p) for p in sorted(out.iterdir()) if p.is_file()],
         'PDF_VISUALLY_VERIFIED': False, 'FINAL_GITHUB_PUBLICATION_VERIFIED': False})
    print(json.dumps({'status': packet['status'], 'output': str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
