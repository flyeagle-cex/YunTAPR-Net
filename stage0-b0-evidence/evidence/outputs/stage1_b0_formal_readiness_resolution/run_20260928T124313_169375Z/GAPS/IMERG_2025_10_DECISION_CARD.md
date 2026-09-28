# IMERG 2025-10 decision card

**IMERG V07 Final 2025-10 = MISSING，未补齐。** 研究期仍为 2023–2025 March–October，2025 Final Test 不变。

## Current evidence

用户追加授权扩大全盘搜索。C、D、E、F、G、H 盘共检查 179970 个目录、1432706 个文件名，登记 552 条候选名称；251 个访问错误、1959 个主动跳过目录。完整错误与跳过目录在 logs/volume_*.json，规则见 src/discover.py；跳过系统/环境目录、链接和本轮输出目录。它不是所有字节/任意命名/压缩包内容的穷尽搜索；**未找到不等于全盘绝对不存在**。

对已知 Final root 的 2025 年目录进行 October 名称定向检查，0 个文件。发现 `raw/IMERG_LATE/2025` 的 31 个 October 日文件和 1 个 smoke 同名文件。抽查 2025-10-01 global title/source 明确为 Late / GPM_3IMERGHHL_07；它们不满足 V07 Final 要求，不替代、不合并、不重新命名。

已登记备份 archive 为 2021–2024 年 IMERG tar.gz，备份 manifest 未指向 2025 Final archive。本轮未打开压缩包成员，也未读取全库降水数组。未识别任意改名或嵌套压缩包中的可能数据，这项搜索范围限制明确保留。

原 completion manifest 记录 2026-09-25 的 2025-10-01 Final 请求失败，错误为 No matching granules found；这是当时请求历史，**不能推出官方永久无该数据或现在无法下载**。本轮未联网请求数据、未修复旧下载任务。

## Options

- **A**：研究者批准后补齐同版本 IMERG V07 Final 2025-10，再审计产品身份、48-slot完整性、native bounds、坐标和QC；保持原研究期。
- **B**：研究者显式修改正式时间范围，记录新版本与比较公平性影响；绝不自动缩至 March–September。
- **C**：其他研究者提出的科研方案，先说明目标、可比性和产品一致性，再显式批准；不默认允许 Late/Early 替换。

## Consequences

当前完整 2025 Final Test 有 31 天 / 1488 名义槽位缺口。科学处理方案必须在正式入口前明确。本轮不下载、不改变研究期、不采用产品替代。
