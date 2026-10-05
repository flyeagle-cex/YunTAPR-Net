"""Append source-backed interpretation before publication; no new model execution."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
import argparse

def append(run):
    run=run.resolve();report_path=run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.json'
    report=c.read(report_path);failure=c.read(run/'failing_tensor_diagnostics.json')
    stats=report['successful_update_distributions'];growth=report['growth_by_tau']
    lines=['# 诊断证据解释','',
        '本附页只解释已保存的数值。分位数与范数比较是描述性证据，不设新的异常、剔除或科研阈值。完整精度以 JSON/CSV 为准。','',
        '## 空间极值与典型像元不同','',
        '|tau ordinal|成功更新：前四分段 max 均值|后四分段 max 均值|前四分段 spatial median 均值|后四分段 spatial median 均值|失败 batch max|',
        '|---|---:|---:|---:|---:|---:|']
    for t in ('1','8','16','24','32'):
        g=growth[t];mx=g['successful_max'];md=g['successful_median']
        lines.append(f"|{t}|{mx['first_quarter_mean']:.9g}|{mx['last_quarter_mean']:.9g}|{md['first_quarter_mean']:.9g}|{md['last_quarter_mean']:.9g}|{g['failed_batch_global_max']:.9g}|")
    lines += ['',
        '各 tau 的空间 maxima 随训练/批次出现升高；空间 median 并未同幅度升高。例如 q32 max 分段均值约从 241.43 到 302.91，而 median 分段均值从 1.3984 到 1.3744。失败 batch q32 median 约 1.4715，max 却为 721.2175。证据支持局部极值与高 tau 累计放大，不能把它称为整个场的所有 quantiles 共同平移或全部发散。',
        '同一失败像元 q1 已高达 24.8990，后续 31 个正增量又累计了 696.3184，占总增量约 96.56%；只有 q32 超过 FP64 物理变换边界。这里同时存在该像元低 tau 的升高与显著累计放大。',
        '这些统计采用变化的 batch，没有固定输入反事实探针，因此不能独立区分输入依赖与权重变化的上游因果贡献。','',
        '## Feature、参数与 Adam 状态','',
        '|观测量|成功更新起始值|最后成功更新前值|成功更新最大值|失败 forward 前值|',
        '|---|---:|---:|---:|---:|']
    failed_values={'feature_absmax':failure['observation']['target_features']['absmax'],
        'raw_max':failure['observation']['raw_head']['max'],'param_global':failure['observation']['parameters_before_update']['global'],
        'param_quantile_weight':failure['observation']['parameters_before_update']['quantile_weight'],
        'param_quantile_bias':failure['observation']['parameters_before_update']['quantile_bias'],
        'param_last_decoder':failure['observation']['parameters_before_update']['last_decoder_block'],
        'Adam_exp_avg':failure['observation']['optimizer_before_update']['exp_avg'],
        'Adam_exp_avg_sq':failure['observation']['optimizer_before_update']['exp_avg_sq']}
    for k,v in failed_values.items():
        s=stats[k];lines.append(f"|{k}|{s['first']:.9g}|{s['last']:.9g}|{s['max']:.9g}|{v:.9g}|")
    lines += ['',
        '失败 batch 的 feature absmax（34.1441）低于此前成功 batch 的最大值（34.6496）。因此不能单凭其激活幅度宣称出现此前未见的 feature 爆炸。raw max 则从成功记录上界 37.8662 提高到 40.1533，并通过 32 个正增量累积越过物理边界。',
        'quantile weight/bias 和 global/decoder 参数范数发生了可测变化，但变化本身不证明病理性漂移。Adam moments 均有限；exp_avg_sq 范数处于已保存成功记录范围内。没有证据证明 nonfinite optimizer state 是本次直接触发点。',
        '历史 epoch 4 后半段和 epoch 5 的成功更新没有 clipping；epoch 5 pre-clip 最大值为约 1.6944。失败 forward 在 loss/backward 之前终止，没有失败 batch 梯度，不能宣称其梯度也稳定。','',
        '## 直接触发点与尚未证明的根因','',
        '直接触发点为 D + F：有限的 FP32 raw head 经冻结 FP64 softplus/累计得到有限 qlog，随后 expm1 产生一个非有限物理 quantile。原始 global physical guard 检查整个输出 tensor，而 core loss 只监督 valid ∩ Yunnan。',
        '本次非有限计数恰好为 1，对应已捕获的 q32 最大位置（batch 0, row 99, column 3），其 Yunnan mask=False、IMERG valid=True、目标降水为 0。该事实解释了为何这个物理异常没有被有效监督域上的低 loss 明显反映；它不授权限制 guard 范围、删除该像元或修改评价 mask。',
        'A（源异常）未成立：实际 size/SHA/CF/full-valid 核验全部通过；仍不能由此排除物理上有效但少见的输入。B/C 有可量化的激活/范数变化，E 没有 nonfinite 状态证据；未执行因果干预，均不宣称为已证明的独立根因。',
        f"独立只读 log objective 诊断为 {failure['read_only_log_objective_diagnostic']['total']:.17g}，有限。actual frozen core loss 在该失败 forward 中未被执行，不把该诊断值当作新的正式 update loss。",'',
        '## 候选方案的研究者决策边界','',
        '|方案|科学/执行语义|训练轨迹|Phase-A / Phase-B|公平性及未来 Final Test|',
        '|---|---|---|---|---|',
        '|A：训练 log-domain 与物理 materialization 解耦|可保留 objective/qlog/support/monotonicity 方程，但改变 frozen eager output/failure contract，需要批准|溢出前必须重新证明输出/loss/gradient/state 等价；溢出后没有原成功轨迹可比|仅因目标方程不变不必然要求重跑 Phase-A；历史证据是否可复用、新 Phase-B 是否从 scratch 开始都由研究者决定，本轮无 resume 授权|两模型须采用同一批准路径；validation/inference 物理溢出仍需预声明规则；2025 继续封存|',
        '|B：数值稳定性训练协议修改|科学模型族可不变，训练协议会改变；加入 regularization 还会改变 objective|通常改变|需要重新冻结 paired development、重新选择 epoch budget，并从 scratch FinalFit|同等协议处理 B0-Matched/B1；不得根据 2025 调参|',
        '|C：quantile 科学参数化修改|改变表示、support/tail 行为或模型假设|改变|需要重新冻结模型并重跑 paired Phase-A / Phase-B|保留旧 baseline；新比较须明确共享 head 设计；2025 不参与设计|','',
        '本轮没有实施任何方案，没有选择新 LR、clipping、regularization、cap 或 tail 模型。A 可以避免训练过程中计算未被 objective 使用的物理量，但不解决其真实物理可表示性问题；也不能自动称为 frozen model semantics 不变。','',
        '## I/O 与补证限制','',
        '实际 replay 共读取 17,252 个 scene（8,626 个 batch），34,504 次 staging copy；来源均与冻结 manifest 的 SHA 一致，没有额外 prefetch scene。累计 temporary copy bytes 为 89,506,953,440（累计 I/O，非同时占用）；各 worker copy seconds 合计约 518.64，read seconds 合计约 502.65，不能相加当作并行运行 wall time。临时文件已清理，原始 H/F 数据未修改。',
        '原 replay 的收尾失败不可变。独立补证只读核验了 114 个历史文件/原始 checkpoint bytes，不反序列化它们。最终 disposable clone 的 model/optimizer logical hashes 未捕获；这项缺失保留，不伪造身份，不再次训练。']
    target=run/'DIAGNOSTIC_EVIDENCE_INTERPRETATION_v1.md'
    with target.open('x',encoding='utf8',newline='\n') as f:f.write('\n'.join(lines)+'\n')
    c.write(run/'interpretation_provenance.json',{'utc':c.now(),'generator':c.pin(Path(__file__)),
        'inputs':[c.pin(report_path),c.pin(run/'failing_tensor_diagnostics.json')],'output':c.pin(target),
        'new_model_calls':0,'new_optimizer_steps':0,'2025_raw_access':0})
    with (run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.md').open('a',encoding='utf8',newline='\n') as f:
        f.write('\n## 完整数值解释与证据\n\n[逐项诊断解释、分段趋势与候选方案对照](DIAGNOSTIC_EVIDENCE_INTERPRETATION_v1.md)。完整原始精度见 JSON、两个 CSV 与 replay_observations.jsonl；来源与原始收尾失败的独立补证见 readonly_closeout/readonly_reconciliation.json。\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);args=p.parse_args();append(args.run)
