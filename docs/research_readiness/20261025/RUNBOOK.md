# 运行与审查说明

状态：仅完成准备与合成核查；本轮没有正式训练许可。建议先审查[B2协议](B2_TRAINING_AND_EVALUATION_REPORT.md)，再决定是否批准B2单项，不将多seed或B5–B8自动捆绑启动。

工作目录为本轮独立准备副本根目录。使用历史CUDA Python环境，启动前设置 `PYTHONHASHSEED=2029`、`CUBLAS_WORKSPACE_CONFIG=:4096:8`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`。本机环境绝对位置保留在私有记录；这里不复制个人数据根路径。

元数据准备命令（只读取已存在清单/统计/SQLite；每次使用新输出名）：

```text
python tools/research_readiness/prepare_b2.py --historical-preparation <历史seed2029/preparation.json> --historical-b3-run <历史恢复运行目录> --output docs/research_readiness/20261025/evidence/b2_proposal_NEXT.json --private-output docs/research_readiness/.local/b2_preparation_NEXT.json
```

本轮最终提案：`evidence/b2_proposal_v3.json`；私有输入：`docs/research_readiness/.local/b2_preparation_20261025_v3.json`（相对于仓库根目录），包含原清单/统计定位与受限源范围。私有准备文件、气象数据及权重不公开。

针对性合成检查：

```text
python tools/research_readiness/run_checks.py test_candidates
python docs/research_progress/scripts/verify_public.py
python tools/research_readiness/verify_delivery.py
```

以下仅为**未来获批后**的命令模板，本轮未执行：研究者审核最终代码提交、最新提案SHA、首层映射及明确额度后，将批准决定登记到新的私有JSON，不能直接使用False模板；不得把AI自行改True当成批准。

```text
python tools/research_readiness/train_b2.py --execute --proposal docs/research_readiness/20261025/evidence/b2_proposal_v3.json --private-preparation docs/research_readiness/.local/b2_preparation_20261025_v3.json --researcher-approval <研究者明确批准记录.json> --output docs/research_readiness/.local/B2_s2029_NEW_RUN
```

执行器要求干净的已跟踪代码与批准commit一致、提案/代码/源范围哈希不变、新输出目录、4,320更新及精确读取额度、0重放；至少24GiB空闲磁盘和既定GPU/RAM入场条件。到时限或任何不一致就停止并留失败收据，不自动恢复、不改batch/精度/人口、不覆盖旧LAST。

真实数据端到端执行仍NOT_VERIFIED，不能因存在启动命令而称为已经完成；未来审批也不免除开始时的资源及源完整性检查。
