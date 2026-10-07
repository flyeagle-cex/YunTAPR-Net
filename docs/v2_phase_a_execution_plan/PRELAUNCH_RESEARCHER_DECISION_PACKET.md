# 正式启动前研究者决策包

Scientific Freeze v2 已批准，不重新讨论冻结规则。当前实施 runner 和工程预检不代表批准正式训练。所有未运行门必须标 NOT_RUN/PENDING，不作为 PASS。

## 必须完成的门

1. 基线/科学配置/源代码/四份manifest/normalization/坐标及mask SHA，逐值样本身份，source存在/大小/全量SHA。
2. 两个独立进程 fresh same-name same-shape 配对初始化一致，参数量及状态SHA登记。
3. CUDA BF16、确定性环境、GPU与C/F容量核验。预留两个模型最多各50个checkpoint、逐步日志、staging、原子写入和20%额外余量。启动和每轮复核；不足不删除旧证据、不自动改参数。
4. 两模型独立 train batch2/u=1、singleton/u=5228；后者LR=1e-4，不执行之前5227步；另验validation batch8/tail5。使用冻结清单首批和尾批2023/2024样本，每训练case独立临时model/optimizer，合计4次ENGINEERING_ONLY更新、正式更新0。不得复用临时状态。
5. 全部已跟踪 regression tests + v2新测试：诊断非干预、精确统计、数值失败阻断、授权及2025拒绝、原子事务、连续/恢复零容差、BEST/early-stop边界、计数和发布隔离。报告实际suite counts，skip/NOT_RUN不视为PASS。
6. 独立readonly监控与发布队列；异常保存独立attempt，不覆盖此前失败。

## 2025 防火墙

父进程和worker均限制为冻结2023/2024白名单；hash/copy/open和native decode全链登记。仅允许当前经过源SHA核验的ASCII staging与冻结静态mask进入NetCDF。假2025路径在opener前拒绝，测试不打开真实2025文件。对账workers、raw opens、staging lineage、decode，缺日志时不能证明零访问。

## 下一次正式授权须绑定

实现commit及代码SHA、通过的preflight SHA、配对初始化SHA、数据manifest/normalization SHA、唯一checkpoint roots、pair/run IDs、publication checkout、研究者批准原文与SHA。运行checkout保持干净且固定commit，授权从publication checkout读取。恢复另绑origin authorization与具体LAST SHA。

本轮结束应保持：

```text
PLAN_READY_FOR_RESEARCHER_REVIEW=true
V2_SCIENTIFIC_FREEZE_APPROVED=true
FORMAL_TRAINING_AUTHORIZED=false
V2_PHASE_A_AUTHORIZED=false
V2_PHASE_A_STARTED=false
V2_PHASE_B_AUTHORIZED=false
B0_MATCHED_PHASE_B_RESUME_AUTHORIZED=false
B1_PHASE_B_STARTED=false
2025_RAW_ACCESS=0
2025_PIXELS_READ=0
RESEARCHER_DECISION_REQUIRED=true
```

具体工程门结果以独立run manifest为准，不由这份计划静态文字宣布通过。完成工程实施和证据发布后停止，等待正式启动审批。
