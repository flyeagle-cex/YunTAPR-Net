# Phase-B v2 隔离集成与合成验证 v1

基线 ca524b1accdcb30524cf106bf40d533d698e61e7；起始本地/远端main一致、已跟踪文件干净，无运行中的Python任务。本轮没有重跑旧177/3项测试，未改历史模型、loss、正式入口、冻结证据或旧候选实现；旧未跟踪文件保留。

当前 SYNTHETIC_INTEGRATION_PASS：CPU91、CUDA6通过，0失败/错误/跳过，静态15项通过。B0/B1完整501×501、batch2、BF16/FP32/FP64路径均完成三臂forward/backward。E0与原loss全部参数梯度最大绝对差为0。结论仅覆盖记录的人工张量和环境。

1. [架构](INTEGRATION_ARCHITECTURE.md)、[接口审计](MODEL_INTERFACE_AUDIT.md)、[合成数值和梯度](SYNTHETIC_NUMERICAL_AND_GRADIENT_RESULTS.md)。
2. [GPU实测](GPU_RESOURCE_MEASUREMENTS.md)、[fresh初始化与排列](INITIALIZATION_AND_ORDER_AUDIT.md)。
3. [执行与恢复门槛](EXECUTION_AND_RECOVERY_GATES.md)、[正式集成差异和缺口](FORMAL_INTEGRATION_DIFF_AND_GAPS.md)。
4. [逐文件学习](MODULE_STUDY_GUIDE.md)、[研究者审查](RESEARCHER_REVIEW_CHECKLIST.md)、[测试记录](tests/README.md)。
5. [可编辑LaTeX](ISOLATED_INTEGRATION_REVIEW.tex)、[中文PDF](ISOLATED_INTEGRATION_REVIEW.pdf)、[最终状态](final_status.json)、[manifest](manifest.json)。

新增源码 src/yuntapr/experimental/phase_b_v2_integration/；测试 tests/phase_b_v2_isolated_integration/；工具 scripts/phase_b_v2_isolated_integration/。实际发布SHA由追加publication_receipt.json绑定，commit不是批准。

V2_PHASE_B_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=2025_PIXELS_READ=0。无optimizer.step、真实2023/2024数据、2025数据或私有checkpoint访问。人工3430格点mask不是云南真实地理掩膜。
