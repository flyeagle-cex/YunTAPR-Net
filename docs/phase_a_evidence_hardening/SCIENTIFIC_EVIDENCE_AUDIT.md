# Phase-A 科学证据一致性审计

独立核验结果为 25 项通过、0 项失败。机器结果：[audit_results.json](tests/audit_attempt_002/audit_results.json)。128 个历史 acceptance manifest 条目的字节数和 SHA256 一致；历史报告、源代码、图表和失败记录未修改。该结论是证据一致性核验，不构成科学验收。

## 身份和适用范围

基线及本次读取时 GitHub main：92687641e59c256a9443b8bfb420b6c947fdcb3a。主仓库为 YunTAPR-Net-push-chunks；另有旧 upload 和 v2 execution checkout，不同步、不清理。主仓库原已跟踪文件无改动；大量旧未跟踪文件仍保留。最初 cwd 是项目容器目录而非 Git 根目录。使用 Get-Process 未见训练 Python；CIM 详细命令行查询因系统权限失败，不宣称查清全部进程命令行。未停止任何进程。

Phase-A 配对训练与科学审查材料已完成，本轮目录在检查时尚不存在。历史 final_status 的 publication pending 是提交前快照，后续 publication_verification 收据确认 bb7c25a8 已发布；不能将旧快照字段误判为推理未完成，更不能改写快照。

2023 训练场景 10,455；2024 共同验证场景 10,501。两模型 scene_ids 全序列逐项相等且唯一，全部为 2024 年 3–10 月。云南有效暴露 N=36,018,430，参考有雨暴露 R=4,496,600；标签在源 float32 上取 IMERG>0.1 mm/h。两个 BEST 均为 Epoch 9/update 47,052，未重新选择。B0 最新卫星槽为分析时刻 T−10 分钟；B1 为 T−60 至 T−10 的六个因果槽，不能写成含 T 时刻未来观测。

## 指标及分母

S_occ 为 alpha=0.5、gamma=2 的 focal BCE 分子；S_qr 为真实有雨且有效云南像元的 32 tau 平均 Pinball 之和。Core=(S_occ+S_qr)/N。训练量化损失分量和科学 global_core_L_qr 使用 S_qr/N；科学 Conditional Pinball 使用 S_qr/R，单位为 log1p(mm/h)。二者不可直接互换，也不能把 minibatch 平均损失平均当作全局量。

Brier=有效云南像元上 (p−标签)^2 的平均，包含真实干像元。AUROC 使用精确 BF16 概率同分组排序、并列半分；AP 使用同分组末端非插值 precision 增量加权。固定概率分箱只用于可靠性诊断，不用于近似 AUROC/AP。单类别分层 AUROC 保持缺失，真实雨分层 AP=1 是条件化后的平凡值，不能作为发生识别证据。POD/FAR/CSI 因概率决策阈值未冻结保持不可估计。

|指标|B0|B1|B1−B0|95% 配对探索区间|
|---|---|---|---|---|
|Core_loss|0.048759608|0.047816404|-0.000943203|[-0.001439666, -0.000484232]|
|Brier|0.096867626|0.095253471|-0.001614156|[-0.002899451, -0.000368153]|
|AUROC|0.886357037|0.893468822|0.007111785|[0.003879209, 0.010605683]|
|AP|0.567232691|0.585904924|0.018672233|[0.010226829, 0.028673455]|
|conditional_pinball|0.124885458|0.124113223|-0.000772235|[-0.001698889, 0.000235028]|

## 重建与对照

全部 22 分层点指标由 daily 分子/分母及精确 score counts 重建；月、季节、民用昼夜、真实雨强四种分区均守恒。对全部 110 个比较逐项核对 CSV/JSON 点值、绝对/相对差异、区间和有效重采样次数。32 tau 覆盖率、每 tau Pinball 及其探索区间逐项重建。可靠性所有分箱的计数、平均概率、雨频率及区间重建。旧 Markdown、LaTeX、PDF、SVG/PNG 与 manifest 字节身份一致；其中科学定义人工对照实际 loss/head 源码。文件哈希证明身份，不能单独证明文稿中每一句科学解释正确。

35 个非重叠七日 UTC 块覆盖 2024-03-01 至 2024-10-31，seed=2026，2,000 次，每次抽 35 块，B0/B1 共用次数矩阵。完整矩阵零差异重建；66 个 Core/Brier/Conditional Pinball 差异区间独立按池化分子分母重建。排名指标仅对固定 5 个重采样索引执行精确池化 smoke；全量排名 CI 复用已发表结果和绑定，未重复全部分析。训练相关性、跨周天气过程、季节非平稳、单一年份、单一种子和 BEST 选择偏差仍在。

## 未执行与异常

未读取卫星或 IMERG 原始像元、未打开模型 checkpoint、未新增模型推理。外部冻结静态 mask 仅引用已发表 SHA，未重新读文件；10 项其余冻结协议输入 SHA 已核对。本轮未运行旧训练全套或含 optimizer/backward 的 fixture。初次审计 24 pass/1 fail 保留：将文稿四舍五入的 20.24 错当源 float32 精确值；第二次改为严格对照 float32(20.24)，没有放宽其他指标容差。

本轮仅诊断与工程准备；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
