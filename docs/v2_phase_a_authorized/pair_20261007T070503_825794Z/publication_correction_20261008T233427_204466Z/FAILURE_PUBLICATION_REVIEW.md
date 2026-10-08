# B1-v2 失败证据发布与恢复核验更正

B1-v2 在 Epoch 15 / Step 3095 写入监控 progress.json 时发生 WinError 5，runner 随后停止。模型数值失败未被该异常记录证明；锁持有者或杀毒/同步干扰等具体根因尚未确定。

只读核验结果：

- 74 个绑定代码文件、冻结 protocol/head/normalization、预检与测试总清单 SHA 一致。
- 两模型共 31 个已登记完整 epoch checkpoint 的文件大小/SHA 一致。
- B1 Epoch 14 LAST 保存的 model、optimizer、scheduler、RNG 与 epoch permutation 身份核验通过；没有应用状态。
- B1 retained trajectory = 73,192 updates；attempt completed = 76,287；未来恢复必须丢弃 3,095 个未 checkpoint updates。原监控快照仅为 76,286，滞后一次更新。
- B0-Matched-v2 已在 Epoch 17 早停；B1 尚未完成，不能输出完整配对实验已完成。

此前本地恢复草稿的 PASS 和特定恢复批准表述已更正，原始字节完整归档。当前恢复文件为不可执行的发布证据，已测试 pinned runner 会在模型构造前拒绝该文件。此前实际失败原件、已完成 epoch 产物、正式启动授权和冻结科学规则未修改。

2025_RAW_ACCESS=0 / 2025_PIXELS_READ=0 指本次审计，受进程审计 hook 强制禁止全部 raw-source open；历史训练的零访问声明引用原 failure 与完整 epoch markers。本次没有重扫全部历史 raw-access logs，不声称新增了该范围的独立验证。

后续恢复所需：查明并验证监控写入问题的处理方式，执行数据/GPU/存储恢复预检，并形成完整 LAST-bound 执行记录与远端核验。本次只发布证据，没有恢复训练或进入 Phase-B。
