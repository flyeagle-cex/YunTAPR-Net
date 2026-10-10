# 2023/2024 冻结 payload SHA 专项 v1

本轮状态：**FULL_PAYLOAD_SHA_PASS**。本地与远端起始基线 5da0a6081f9d3953cf59f7c6d71aedaf74e951f2；仅对冻结引用进行完整文件 SHA-256 校验，没有解码、模型推理或训练。

本次匹配 67,006 / 67,006 文件；应用层 payload 返回 274.592686 GiB，监督进程耗时 6520.968 秒。原 294 个已核验文件也在统一新证据中重新读取，不复用旧 SHA 通过记录。

payload 只读句柄成功 67,006 次，文件属性句柄成功 67,006 次，父目录属性句柄 510 个。峰值工作集 1.576836 GiB；实际物理磁盘字节和 CPU 时间没有测量，不能用应用返回字节代替物理 I/O。

- [完整性报告](FROZEN_PAYLOAD_SHA_AUDIT.md)、[异常及未解决项](INTEGRITY_FAILURES_AND_BLOCKERS.md)。
- [读取与资源账本](READ_SCOPE_AND_RESOURCE_LEDGER.json)、[逐文件脱敏收据](PAYLOAD_SHA_RECEIPTS.csv.gz)。
- [快照及 TOCTOU 风险](SNAPSHOT_AND_TOCTOU_RISKS.md)、[来源](source_identity.json)、[状态](final_status.json)、[清单](manifest.json)。

脚本仅使用标准库，未导入 PyTorch、netCDF4 或原始数据 decoder。数据文件均使用只读 Windows 句柄；准确引用诱导的父目录句柄在本次审计期间持有，拒绝重解析点、写入和删除共享。没有遍历原始目录、下载、替换文件、修改 cache/scaler/mask 或数据划分。

历史 2025 路径属性访问仍 NOT_INSTRUMENTED。专项 SHA 通过不升级整体真实预检，不证明业务近实时可用性或未来训练消费字节不变。本包完成后停止；不自动启动 preflight、Runner、训练或恢复。
