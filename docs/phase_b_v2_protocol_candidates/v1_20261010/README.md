# Phase-B v2 科学协议候选与独立物理验证资料准备 v1

状态：RESEARCHER_DECISION_REQUIRED。本目录是方案交付，不是冻结协议、批准文件或训练入口。基线 main=6e692625ebdd9bdaeff65e22d0ce59af349d98c5；本地与远端首次核对相同。核对时已跟踪文件无改动，旧未跟踪日志、恢复文件和临时目录保留；未发现 Python 训练进程。旧 v1 Phase-B 成果已有，但本轮 v2 候选目录此前不存在。

1. [协议候选](PROTOCOL_CANDIDATES.md)：目的、初始化、资格、normalization、预算与验证组合。
2. [最小假设与消融矩阵](HYPOTHESES_AND_ABLATIONS.md)：新增实验范围、控制变量与可否证条件。
3. [独立资料清单](INDEPENDENT_REFERENCE_INVENTORY.md)：9 类资料及许可、时间、尺度、共享来源风险。
4. [物理验证准备](PHYSICAL_VERIFICATION_DESIGN.md)：配准、时间支撑、质量控制、独立性登记和未发送的资料询问提纲。
5. [Methods / Experimental Design 初稿](METHODS_AND_EXPERIMENTAL_DESIGN.md)：已完成与拟议研究明确分开。
6. [研究者决策材料](RESEARCHER_DECISION_REQUIRED.md)：逐项取舍、依赖与停止边界。
7. [来源](REFERENCES.md)、[机器来源登记](source_registry.json)、[机器候选](candidate_design.json)、[预算](budget_candidates.csv)。
8. [完整可编辑 LaTeX](PHASE_B_V2_CANDIDATE_REVIEW.tex) / [PDF](PHASE_B_V2_CANDIDATE_REVIEW.pdf)、[检查记录](tests/README.md)、[身份清单](manifest.json)、[最终状态](final_status.json)。提交与远端核验见后续追加的 publication_receipt.json。

既有 [Phase-A 补强包](../../phase_a_evidence_hardening/README.md) 和 [科学验收证据](../../v2_scientific_acceptance/README.md) 继续作为历史来源。本轮没有重复 87 项检查，没有重新推理，也没有修改既有文档、冻结配置、正式源码或参数。所有数值结果仍来自 2024 开发验证证据。

唯一新增计算是发表样本数的整数预算、候选角色约束的合成单元测试，以及文档构建/完整性交付检查；不导入 torch，不加载 checkpoint，不访问原始数据。所有新训练、校准拟合、数据申请/获取、真实站点或雷达验证均未执行。2025_RAW_ACCESS=0；2025_PIXELS_READ=0；V2_PHASE_B_AUTHORIZED=false；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED。

本轮无新增科学图表；沿用已发表表格与引用，不生成示意图。报告面向研究者审阅，目标期刊、英文翻译与正式 Results 待后续决定。公开网页调查日为 2026-10-10；页面可见的产品时间范围不是本项目已取得的资料范围。
