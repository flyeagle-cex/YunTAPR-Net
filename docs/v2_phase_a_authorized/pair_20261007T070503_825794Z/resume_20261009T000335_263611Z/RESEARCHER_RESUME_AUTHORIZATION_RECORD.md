# B1-v2 Phase-A：既有授权的 epoch 14 LAST 恢复绑定

授权来源是研究者原始 paired Phase-A 正式授权及当前持续目标：完成两个已批准 Phase-A，并在中断后仅从最后一个完整 LAST 恢复。本记录登记现有授权的执行绑定，不宣称研究者在本记录生成时间另行作出了新的科学决策。

B0-Matched-v2 已完成 epoch 17 早停，不重训。B1-v2 从 SHA256 40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649 的完整 epoch 14 LAST 恢复。保留 73,192 次更新，丢弃失败 epoch 15 的 3,095 次未 checkpoint 更新，重跑 epoch 15。只允许既有冻结 Phase-A 到 early stopping 或 50 epoch。

科学、代码、数据、normalization、model/optimizer/scheduler/RNG/permutation 身份已通过当前只读预检；远端 main 包含本记录及绑定提交后才允许执行。冻结 runner 未修改。独立监控只读追加日志与不可变轮次报告，不打开可替换状态文件。原 WinError 5 的历史锁持有者未知，任何后续失败仍保留独立证据并停止。

不允许 Phase-B、FinalFit、2025、自动调参或静默修复。旧正式授权、失败记录、完整 epoch/checkpoint 与原更正证据保持不可变。
