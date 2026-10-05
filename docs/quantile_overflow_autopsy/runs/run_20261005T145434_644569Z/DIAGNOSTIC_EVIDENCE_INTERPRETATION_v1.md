# 诊断证据解释

本附页只解释已保存的数值。分位数与范数比较是描述性证据，不设新的异常、剔除或科研阈值。完整精度以 JSON/CSV 为准。

## 空间极值与典型像元不同

|tau ordinal|成功更新：前四分段 max 均值|后四分段 max 均值|前四分段 spatial median 均值|后四分段 spatial median 均值|失败 batch max|
|---|---:|---:|---:|---:|---:|
|1|8.07103466|10.3838684|0.0981961458|0.0980630246|24.8990467|
|8|55.7673952|69.8820564|0.169234879|0.170001959|166.868058|
|16|115.636163|143.717304|0.281187007|0.280382107|343.236223|
|24|178.946785|222.92705|0.484430765|0.477715302|531.723008|
|32|241.426659|302.907746|1.39842757|1.37440356|721.217497|

各 tau 的空间 maxima 随训练/批次出现升高；空间 median 并未同幅度升高。例如 q32 max 分段均值约从 241.43 到 302.91，而 median 分段均值从 1.3984 到 1.3744。失败 batch q32 median 约 1.4715，max 却为 721.2175。证据支持局部极值与高 tau 累计放大，不能把它称为整个场的所有 quantiles 共同平移或全部发散。
同一失败像元 q1 已高达 24.8990，后续 31 个正增量又累计了 696.3184，占总增量约 96.56%；只有 q32 超过 FP64 物理变换边界。这里同时存在该像元低 tau 的升高与显著累计放大。
这些统计采用变化的 batch，没有固定输入反事实探针，因此不能独立区分输入依赖与权重变化的上游因果贡献。

## Feature、参数与 Adam 状态

|观测量|成功更新起始值|最后成功更新前值|成功更新最大值|失败 forward 前值|
|---|---:|---:|---:|---:|
|feature_absmax|9.40334702|19.8837643|34.6495514|34.1440582|
|raw_max|5.79272461|23.4471416|37.8662186|40.1533089|
|param_global|64.4282729|67.5615635|67.5615635|67.5623709|
|param_quantile_weight|4.14450796|4.27096473|4.27362079|4.27033536|
|param_quantile_bias|0.597133748|0.614192718|0.614938743|0.614089251|
|param_last_decoder|13.6998852|14.1434538|14.1435284|14.1434427|
|Adam_exp_avg|0.00334270628|0.00406946171|0.014946412|0.00455144573|
|Adam_exp_avg_sq|1.93136375e-05|1.99133513e-05|2.42446562e-05|1.9899518e-05|

失败 batch 的 feature absmax（34.1441）低于此前成功 batch 的最大值（34.6496）。因此不能单凭其激活幅度宣称出现此前未见的 feature 爆炸。raw max 则从成功记录上界 37.8662 提高到 40.1533，并通过 32 个正增量累积越过物理边界。
quantile weight/bias 和 global/decoder 参数范数发生了可测变化，但变化本身不证明病理性漂移。Adam moments 均有限；exp_avg_sq 范数处于已保存成功记录范围内。没有证据证明 nonfinite optimizer state 是本次直接触发点。
历史 epoch 4 后半段和 epoch 5 的成功更新没有 clipping；epoch 5 pre-clip 最大值为约 1.6944。失败 forward 在 loss/backward 之前终止，没有失败 batch 梯度，不能宣称其梯度也稳定。

## 直接触发点与尚未证明的根因

直接触发点为 D + F：有限的 FP32 raw head 经冻结 FP64 softplus/累计得到有限 qlog，随后 expm1 产生一个非有限物理 quantile。原始 global physical guard 检查整个输出 tensor，而 core loss 只监督 valid ∩ Yunnan。
本次非有限计数恰好为 1，对应已捕获的 q32 最大位置（batch 0, row 99, column 3），其 Yunnan mask=False、IMERG valid=True、目标降水为 0。该事实解释了为何这个物理异常没有被有效监督域上的低 loss 明显反映；它不授权限制 guard 范围、删除该像元或修改评价 mask。
A（源异常）未成立：实际 size/SHA/CF/full-valid 核验全部通过；仍不能由此排除物理上有效但少见的输入。B/C 有可量化的激活/范数变化，E 没有 nonfinite 状态证据；未执行因果干预，均不宣称为已证明的独立根因。
独立只读 log objective 诊断为 0.037468508452172894，有限。actual frozen core loss 在该失败 forward 中未被执行，不把该诊断值当作新的正式 update loss。

## 候选方案的研究者决策边界

|方案|科学/执行语义|训练轨迹|Phase-A / Phase-B|公平性及未来 Final Test|
|---|---|---|---|---|
|A：训练 log-domain 与物理 materialization 解耦|可保留 objective/qlog/support/monotonicity 方程，但改变 frozen eager output/failure contract，需要批准|溢出前必须重新证明输出/loss/gradient/state 等价；溢出后没有原成功轨迹可比|仅因目标方程不变不必然要求重跑 Phase-A；历史证据是否可复用、新 Phase-B 是否从 scratch 开始都由研究者决定，本轮无 resume 授权|两模型须采用同一批准路径；validation/inference 物理溢出仍需预声明规则；2025 继续封存|
|B：数值稳定性训练协议修改|科学模型族可不变，训练协议会改变；加入 regularization 还会改变 objective|通常改变|需要重新冻结 paired development、重新选择 epoch budget，并从 scratch FinalFit|同等协议处理 B0-Matched/B1；不得根据 2025 调参|
|C：quantile 科学参数化修改|改变表示、support/tail 行为或模型假设|改变|需要重新冻结模型并重跑 paired Phase-A / Phase-B|保留旧 baseline；新比较须明确共享 head 设计；2025 不参与设计|

本轮没有实施任何方案，没有选择新 LR、clipping、regularization、cap 或 tail 模型。A 可以避免训练过程中计算未被 objective 使用的物理量，但不解决其真实物理可表示性问题；也不能自动称为 frozen model semantics 不变。

## I/O 与补证限制

实际 replay 共读取 17,252 个 scene（8,626 个 batch），34,504 次 staging copy；来源均与冻结 manifest 的 SHA 一致，没有额外 prefetch scene。累计 temporary copy bytes 为 89,506,953,440（累计 I/O，非同时占用）；各 worker copy seconds 合计约 518.64，read seconds 合计约 502.65，不能相加当作并行运行 wall time。临时文件已清理，原始 H/F 数据未修改。
原 replay 的收尾失败不可变。独立补证只读核验了 114 个历史文件/原始 checkpoint bytes，不反序列化它们。最终 disposable clone 的 model/optimizer logical hashes 未捕获；这项缺失保留，不伪造身份，不再次训练。
