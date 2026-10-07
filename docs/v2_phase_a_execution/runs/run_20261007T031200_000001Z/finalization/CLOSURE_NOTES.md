# v2 paired Phase-A preflight 最终归档

工程预检 PASS，run 已关闭。正式训练未获授权、未启动。

- 源 SHA 收据与冻结白名单逐项对账：67,006 / 67,006；本次收尾未重新打开任何 raw source。
- GPU smoke：8 / 8 PASS；完整测试：770 / 770 PASS。沿用已完成执行证据，不重新 forward/backward。
- 隔离工程 optimizer steps：4；正式 optimizer steps：0；本次收尾新增 optimizer steps：0。
- 2025_RAW_ACCESS=0；2025_PIXELS_READ=0。证明范围为受控预检父进程及 worker，非所有系统进程。
- 54 个历史正式 checkpoint 共约 2.82 GB，重新流式计算文件 SHA256 和大小，与历史登记逐项一致。未反序列化或应用状态。
- Git 跟踪的历史科学文件相对 Scientific Freeze v2 基线无修改或删除；配置、runner、manifest、normalization、两次配对初始化身份均核验一致。具体证明范围及身份见 JSON。
- 两个 v2 正式 checkpoint 根目录尚未创建。publication checkout 为当前仓库 main，远端为 flyeagle-cex/YunTAPR-Net。

原始 `../preflight_manifest.json` 及执行日志保持原字节；本目录 `preflight_manifest.json` 是独立收尾清单，绑定原清单、核验脚本及最终 JSON，不覆盖历史结果。运行完成时的存储容量和收尾时容量分别保留；不保证未来启动时的可用空间，正式启动前仍应复核。

收尾脚本首次检查把 `FROZEN_STATIC_MASK` 标记误解为源路径，第二次检查只搜索 formal_training 登记而未纳入配对阶段的完整 checkpoint inventory；两次均在创建本目录之前停止，没有生成 PASS 文件。核实已有日志 schema 和历史清单后修正收尾适配，第三次全部通过。原 runner、模型、科学配置和执行证据未修改。

发布后停止，等待研究者审查。此归档不构成正式训练授权。
