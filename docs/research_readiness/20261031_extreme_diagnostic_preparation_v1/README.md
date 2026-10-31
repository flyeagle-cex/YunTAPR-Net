# 极端降水诊断准备 V1

已完成保存证据核对、候选概率界工具和14项独立合成检查。没有新增真实模型评价、原始气象读取、权重访问、训练或2025访问。

研究者要求直接推进准备，不再中途展示草稿。准备授权不伪造为新科学方法已冻结、真实推理预算已批准或论文结论获准。此目录的 `proposal.json` 明确将这些状态保持为 false；没有真实数据适配器、训练启动器、批准文件或自动化。

- [六页可编辑方案源文件](latex/main.tex)
- [PDF](../../../output/pdf/YunTAPR-Net_极端降水诊断准备与预注册候选方案_20261031.pdf)
- [候选规则与九模型身份](proposal.json)
- [已有证据诊断及追溯缺陷](saved_evidence_audit.json)
- [提交对象字节来源清单](source_manifest.json)
- [交付质量检查](delivery_verification.json)

## 已核验范围

基线工作分支提交 `7c19b9d36bc73b998fcf72b9cc630989f7e3b324`。178项总体源值、5,737项普通配对及其参考值、65项B7减PERP配对、27组A/B/C严格大于20 mm/h分类、九份已有E9身份和19份已完成补算门槛均通过。没有再次哈希或加载权重。

PERP的65条配对行把目标ID和参考ID都写成PERP；本次按明确B7与PERP源值相减，数值一致，但不能沿用该错误关联。旧索引仍有PERP未训练的表格行。问题单独登记，所有历史文件保持原字节。

## 候选工具的识别边界

`tools/research_readiness/extreme_diagnostic_candidates.py`只提供与有限条件分位数相容的超阈概率、Brier、AUROC区间和决策可识别状态。它们不是实际风险置信区间；未知尾部不填零，AP不伪造精确值。工具目前只经过合成检查，没有应用于真实模型输出。

准备与针对性检查命令：

```text
python -B -m unittest discover -s tests/extreme_diagnostic_preparation -p "test_*.py" -v
python -B tools/research_readiness/prepare_extreme_diagnostic_v1.py --output docs/research_readiness/<NEW_PREPARATION_DIRECTORY>
```

第二条只读取显式白名单中的已提交统计对象，拒绝已有输出目录，不能执行模型推理或训练。源哈希按指定Git提交对象字节计算，不混用Windows工作副本换行。

LaTeX可使用XeLaTeX编译；默认字体Arial和Microsoft YaHei可由研究者替换。内置编辑器预览编译受Windows运行环境限制，本轮以本机XeLaTeX导出、Poppler逐页渲染、文本／链接和数值检查验收。没有生成科研图或图表。

## 真实计算前的缺口

九次开发、静态包及一次训练标签的逻辑内容参考为239,935,204,070字节／71,802实例；检查点归档长度单列。该数字不是已批准额度。硬时间、存储／内存门槛、具体适配器提交及准确新授权尚未闭合，G2真实诊断保持NOT_STARTED。独立事件／观测、额外训练、多尺度与2025均需另行决策。

本轮只新增本目录、两个独立准备工具、一份合成测试及PDF。没有更改模型、损失、正式训练协议、根入口或历史收据。提交到工作分支，不更新main或合并PR。
