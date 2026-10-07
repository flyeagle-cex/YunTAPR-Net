# Scientific Freeze v2 配对 Phase-A 执行计划

科学基线：`d049f7ab7b8a382f47a5fe54384ea9416a22cde9`。研究者已批准科学规则；本轮实施授权仅包括独立 runner、文档、测试和工程预检，不授权正式训练。

## 冻结身份

|对象|SHA256|
|---|---|
|Quantile Head v2|`3a865a6e4ab180f61d7ab6e2f684ab6b814bfe6b2e59a34d127ddf1d772fc97e`|
|Phase-A protocol|`a0141f21cfa997d5adb72dff5afb32b17dc7edcf5f3397fc9c4bfe2ea42048be`|
|Shared normalization|`656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31`|

其他源身份从上述协议和既有数据合同读取，不重写历史候选和审计文件。mean=271.60515414265217 K，std=19.93959597783802 K，仅复用已冻结 2023 Train scaler，不 refit。

## 执行顺序

1. 实现、隔离测试、工程 preflight；完整保存失败尝试。
2. 提交实现与证据，研究者另行批准绑定代码 SHA、preflight SHA 和实际运行身份的正式启动授权。
3. B0-Matched-v2 完整结束并通过审计，随后 B1-v2。单 GPU 串行；正常早停是正常结束，异常则暂停整个配对流程。
4. 完成配对复核及 GitHub 发布后停止。不得自动进入 Phase-B、2025 Final Test 或其他 baseline。

两模型共用 optimizer、scheduler、loss、batch、normalization、验证、数值保护、诊断和 checkpoint 政策。唯一模型输入差异是 latest B13 与六因果 B13 槽，以及由此导致的最前端权重 shape 差异。

## 数据预检

先验证四份 manifest SHA，再验证逐行 sample_id/索引/时间/IMERG 源 SHA/时间索引/3430 有效目标数。2023 Train=10455、2024 Validation=10501，无重复；两个模型的共同身份及顺序逐值相同。B0 使用 B1 槽 5，六槽 offsets=[60,50,40,30,20,10]，最旧至最新；逐帧检查 obs_start≤obs_end≤analysis_time、完整有效性、文件大小与 SHA。

只从冻结 manifest 生成精确源白名单，不全盘扫描。H 盘永久只读；沿用 ASCII bounded staging，每 worker 上限 734003200 bytes、每次一文件，核验源/副本 SHA 与大小后解码，仅清理本进程创建的临时副本。任何缺失、变化或失效均停止，不缩小样本集合或补帧。

## 发布与运行隔离

正式执行用干净独立 checkout 固定在已批准实现 commit；授权和运行报告位于另一个 publication checkout。原始科学冻结的授权 false 保留历史含义，正式运行必须另有明确授权文件，不能把科学批准当训练批准。

启动前提交代码、规范、测试、preflight、初始化身份与研究者授权。每 epoch 后持久化完整本地证据，独立 publisher 尝试提交 epoch 摘要、选择历史、诊断摘要、checkpoint registry/BEST/LAST、SHA/大小/绝对路径。网络失败排队，不影响模型轨迹；最终需远端 SHA 核验。只提交文本白名单，不提交 checkpoint、optimizer/RNG/model binary、raw 或完整 tensor。

完整逐 forward/step 日志保存在对应正式根目录下的 `audit/run_<attempt UTC>/`；提交摘要时登记其身份，不静默删除旧尝试。GitHub 发布失败不能标为成功。

## 预检与最终状态

实际工程执行证据在 `../v2_phase_a_execution/`，单次 preflight 输出 `preflight_manifest.json` 才表示该次成功；`failure.json` 表示失败，缺失项不能记 PASS。实施完成不自动改变正式授权。

`V2_SCIENTIFIC_FREEZE_APPROVED=true`；`FORMAL_TRAINING_AUTHORIZED=false`；`V2_PHASE_A_AUTHORIZED=false`；`V2_PHASE_A_STARTED=false`；`V2_PHASE_B_AUTHORIZED=false`；`B0_MATCHED_PHASE_B_RESUME_AUTHORIZED=false`；`B1_PHASE_B_STARTED=false`；`2025_RAW_ACCESS=0`；`RESEARCHER_DECISION_REQUIRED=true`。
