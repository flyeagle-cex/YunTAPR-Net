# B0 missing / QC contract candidate

状态：工程语义已定义；完整正式接受/剔除与 loss mask 协议仍 RESEARCHER_DECISION_REQUIRED。

## FROZEN — 继承明确规则

- 输入为单时次 Himawari B13，原始文件永久只读；obs_end<=analysis_time 是硬因果约束，未来帧不允许进入。
- IMERG 真实 0 是无雨有效值，0 != missing；NaN、元数据 _FillValue/missing_value 和 masked pixels 保留独立布尔有效性语义。不得填成 0、插值、造值或以未来帧代替。
- 源 B13 按已有 packed metadata 解码，保留原 dtype、scale/add_offset、valid_min/max 与 missing_value。样本 int16 missing_value=-32768；scale≈0.01，offset≈273.15 K。元数据有效范围与新科研阈值不同；不能凭经验新增温度或雨量阈值。未来 metadata 改变须显式记录并审查。
- 冻结评价域为正式 center-in-polygon mask（3430），不是矩形全部 pixels。intersection 仅敏感性比较。

## PROVISIONAL — 整理工程状态，不新设阈值

|状态|工程含义|正式处置边界|
|---|---|---|
|B13 all_fill|解码后无有效 B13 观测|不能伪造为有效输入；保留拒绝/原因 metadata，计数分母与采样处置需批准|
|B13 partial|存在有效与无效像元|记录 invalid count/fraction；不得默认删整帧或默认填补|
|missing frame|已批准 nominal 位置无文件|记录缺帧；当前无授权 fallback，不静默替换帧|
|B13 invalid pixel|NaN/masked/declared fill或源 metadata 有效范围之外|保留 invalid mask；正式模型接收方式未定|
|IMERG target invalid|非有限数或 declared fill/missing|不得作真实 0；训练/评价不当作有效监督|
|IMERG target 0|有限且不等于 declared fill|保持有效，不因无雨被掩掉|

即使 B0 单帧，仍保留既有 sequence ID/slot availability、逐帧 QC、缺口/时间异常 metadata 以便溯源；不把六帧 completeness 当作 B0 接纳硬条件。creation_delay原值保留，date_created只记录。latency_tail_review 的 p99 只是分布尾部检查标记，不是排除条件、QC阈值或科学阈值；TEMPORAL_ORDER_ERROR 与 LATENCY_TAIL_REVIEW 分开，不删除/修改原始文件。

## RESEARCHER_DECISION_REQUIRED

partial-frame 可用比例/分布标准（本轮不提供新数值阈值）；无效输入的模型 mask 接口、是否整体拒绝、loss reduction 的有效分母；label validity 与 evaluation mask 的组合；重采样时缺测传播；训练域监督与主评价域的区分；missing-frame 的正式 causal fallback 是否允许；跨月 QC 扩展与严重时间异常接受策略。

若批准模型内部的 padding 或数值占位，必须保留有效性 mask，并明确占位不代表观测 0；当前未批准此策略。训练和评价的 target-invalid 像元不得进入有效监督/指标分母，但具体 normalization/loss reduction 未定。不能用 synthetic contract unit tests 冒充真实全月/全研究期 QC 已完成。

FROZEN 只表示明确继承的语义约束，不表示本候选文档整体已成为正式完整 QC 配置。
