# Phase-B v2 隔离正式集成工程候选 v1

状态：**SYNTHETIC_INTEGRATION_PASS**；正式训练仍不可执行。本包基于 `c92eb1910c4bb94a27b250917f86ba82f6e16406`，仅新增隔离代码与公开工程证据，没有修改冻结模型、损失、训练入口、协议或历史报告。

本次完成 55 项新增 CPU 检查、2 项 CUDA 集成检查。累计实际合成 AdamW 更新 **4 次**，正式更新 **0 次**。首次 CUDA 检查出现一次 checkpoint 序列化错误，发生在第 1 次更新之后；计数没有退款，修复后仅执行余下 3 次。[失败与修复记录](TEST_AND_FIX_RECORD.md)保留完整经过。

- [代码及接口](IMPLEMENTATION_AND_GAPS.md)：B9 控制器、精确指标、checkpoint、拒绝式真实数据入口。
- [指标口径与资源](METRIC_AND_RESOURCE_EVIDENCE.md)：只含合成工程判断。
- [正式版本差异及审批边界](FORMAL_INTEGRATION_DIFF.md)：已实现功能与仍未验证功能分开。
- [研究者待决定事项](RESEARCHER_DECISION_REQUIRED.md)：未填写批准结果。
- [最终状态](final_status.json)、[来源身份](source_identity.json)、[文件清单](manifest.json)。

代码目录：`src/yuntapr/experimental/phase_b_v2_formal_integration_candidate/`。CPU 检查命令：在仓库根目录、可用 PyTorch 环境下执行 `python docs/phase_b_v2_formal_integration_engineering/v1/run_checks.py`。CUDA 检查属于本次已消耗完毕的独立四步预算；**不要删除 `.local/actual_campaign.sqlite` 后重跑**。其额度为本机审计约束，不是抗恶意篡改的授权服务。

本轮未再次访问真实 2023/2024 原始观测、scaler、云南 mask 或私有 checkpoint；没有重跑旧合成套件。合成人工 mask 不代表云南地理位置。2025 像元读取为零；历史 2025 路径属性查询仍为 **NOT_INSTRUMENTED**，不追溯宣称系统级访问为零。M-C 与论文定位 A 仍为推荐候选，科学成功判定不可用。
