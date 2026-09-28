# Vintage rule candidates — researcher review only

没有候选被选择；vintage_rule_frozen=false；X 未指定。旧文件中的 init+5h 只保留为历史假设。所有回放规则还必须约束 forecast 身份、输入数据完整性、决策时刻及 endpoint 的含义。

| 候选 | 所需证据 | 优点 | 局限 / 历史回放 | 泄漏风险 | 可复现性 |
|---|---|---|---|---|---|
| A 真实 operational release | 2023–2025 每个 init/lead 对应的可验证首发/完整可获取时间，发布端及重发语义 | 最接近当时可获得信息 | 当前 NOT_ESTABLISHED；有完整历史记录才可回放 | 用重传/入库/最后修改替代首发会错判；需完整变量可用时间 | 保存原始日志、签名/校验和、UTC 与事件语义 |
| B 历史本地 download/availability | 同时段真实本地成功接收记录、内容哈希、机器时区、文件身份 | 能重放特定本地系统当时可见内容 | 现有是 2026 回溯获取，不能倒推 2023–2025 的近实时可用性 | 把 2026 获得的数据回填至旧 forecast 时间会泄漏假设 | 完整留存收件记录可复现本地获取史；本轮大小/路径关联仍不闭环 |
| C 官方 documented release latency | 对应产品、端点、年代、cycle/lead 的官方延迟定义与异常处理，研究者批准保守界限 | 可形成文档依据一致规则 | 当前页面只有产品/周期说明，无历史 latency 保证；规则回放不是逐文件观测 | 常规发布计划忽略延迟、故障和重发 | 保存文档版本、适用年代、端点与选用理由 |
| D 固定 init+X fallback | 研究者明确 X、适用范围、依据、敏感性与异常策略 | 简单，可复现 | 仅假设情景回放，不建立真实 operational availability；本轮不指定 X | 延迟过短可能使用当时未完成文件；过长改变输入可用性 | 版本化参数和假设，明确标注为假设 |

日志 download time 仅可说明其事件时刻的本地获取；skipped 只证明程序报告跳过，failed 不能记作成功。mtime、conversion、CF init/valid、History 与 archive date 均不得自动当 release。AWS NewGFSObject 服务存在不代表已拿到历史消息。
