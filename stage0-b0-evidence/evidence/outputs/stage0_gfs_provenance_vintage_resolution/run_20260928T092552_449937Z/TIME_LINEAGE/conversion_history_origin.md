# conversion history origin

DIRECT_EVIDENCE：旧分类为 17665 个 auxiliary metadata conflict，其中 14037 为 ALTERNATIVE_REFERENCE_TIME、3628 为 STALE_HISTORY_TOKEN;ALTERNATIVE_REFERENCE_TIME，真实 forecast time conflict 为 0。原分类表保持不变。

DIRECT_EVIDENCE：本轮将所有含 history 的字段（含 legacy_history_before_20260925）纳入文本 token 对照，已有主库证据表中 11805 行含非当前 token；其中已匹配 thermo 的范围为 9385 行。这与旧 3628 的分类口径不同，不能当作新增原始时间冲突。详细逐行映射见 history_token_scope_reconciliation.csv。

DIRECT_EVIDENCE：17 条 AWS templates 日志明确记录模板文件。其中 gfs_aws_primary_20260726_103206.log 第 2 行的 instant 模板为 2023062212_f000；在当前文件 legacy_history 中可见相同上游 token。扩展 stale 行中 11803 行至少有一个 token 与日志模板命名相符。该 token 描述另一个 forecast，Translation Date 描述转换时间，二者都不是 operational release。

NOT_ESTABLISHED：模板属性复制可以解释部分旧 token，但未定位到转换脚本，不能证明具体哪条赋值语句写入 History/udunits，不能把“模板复用”确认为已闭环成因。udunits 原始参考值、CF units 及主时间保持原状；未 flip、重写、修补或回填。

DIRECT_EVIDENCE：metadata 中 legacy_history_before_20260925 与 provenance normalized History 并存，能证明当前属性内容；NOT_ESTABLISHED：2026-09-25 标准化的具体代码版本与逐文件执行记录。
