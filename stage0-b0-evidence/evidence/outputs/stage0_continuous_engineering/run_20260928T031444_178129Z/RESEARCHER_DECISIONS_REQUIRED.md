# Researcher decisions required

工程总状态 NEEDS_REVIEW：独立审计已完成，以下科学/来源问题未代替研究者决定。

| 事项 | 实际证据 | 需要研究者复核的内容 |

|---|---|---|

| GFS 核心 T/RH 缺口 | 主目录 2023–2025 全年 13,152 文件均没有所需 T/RH；PWAT/CAPE/U/V/PS 存在 | 是否批准审计 GFS_thermo、验证同源 cycle/lead/grid/units 后设计显式补充方案；本轮未合并 |
| GFS 辅助时间来源冲突 | 17,665 个 udunits/history 冲突；其中 3,628 个 History token 冲突；当前 CF 算术均一致 | 追溯转换代码/原始 archive，确认数组真实 forecast 身份；不要仅靠索引算术判定科学可用 |
| GFS operational availability/vintage | 无直接业务发布证据；11,968 个 +5h 字段明确是上游假设 | 明确来源证据和可用性规则；不自动采用 +5h、mtime 或 init_time |
| IMERG native window 语义 | converted CF 坐标严格半小时；native 窗口对应关系仍 PROVISIONAL | 确认 [T,T+30min) 与 analysis_time=T+30min 绑定 |
| Himawari availability | date_created 是 product/file creation；obs_end 是物理结束 | 如采用 proxy 需明确其证据及适用范围，不能写成真实 availability |
| model_input_bbox/上下文 | 数值共同包络 lat20–30、lon97–107，仅候选 | 决定云南全境与省界外上下文；covers_yunnan_context 保持待确认 |
| IMERG 2025-10 | 定向检查 0 文件；先前全库止于 2025-09-30 | 补齐同版本数据或另行科学决策；本轮不缩短研究期 |
| SRTM/云南 mask | 237 瓦片目录与云南 polygon 存在；raster values/grid mask 未验证 | DEM 有效性与 mask 栅格化/边界规范待后续授权工程 |
| 独立外部验证 | NOT_AUDITED | 指定已准备的数据与独立性证据，不能把未审计写成 READY/MISSING |
| split/quantiles | 正式精确划分块、32 quantile levels 尚未冻结 | 由研究者决定；未执行 split、统计或训练 |

没有必须先回答才能完成的剩余独立工程任务；本文件是统一复核清单，不是本轮暂停请求。
下一阶段仅建议：先复核来源时间冲突与核心变量补充方案，再冻结 availability/vintage 和窗口语义；确认后另行执行配对工程。不得直接跳到模型实验。
