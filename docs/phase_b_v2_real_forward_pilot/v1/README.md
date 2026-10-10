# Phase-B v2 限额真实数据前向 pilot v1

状态：`BOUNDED_REAL_FORWARD_PILOT_PASS`。范围：`BOUNDED_REAL_FORWARD_ENGINEERING_ONLY`，来源基线 `edf883b55dd01dbf397b52224db58be85550c42a`。

复用首次只读预检的固定 48 场景及顺序，冻结 seed 2026 配对 fresh 初始化，不加载历史权重。真实完成 48 场景，B0/B1 batch 前向分别 24/24 次，batch 固定为 2。

导航：[适配实现](REAL_ADAPTER_IMPLEMENTATION.md)、[前向检查](REAL_FORWARD_VALIDATION.md)、[同字节与访问审计](BYTE_IDENTITY_AND_ACCESS_AUDIT.md)、[资源](RESOURCE_AND_LATENCY_REPORT.md)、[失败与阻塞](BLOCKERS_AND_FAILURES.md)、[最终机器状态](final_status.json)。

`run_pilot.py` 默认只允许新建本地 `attempt_001`。本轮另保留一次明确的访问前 PyTorch 包装冲突修复续接 attempt_002，继承原始时间和字节额度；任何真实场景/forward 已开始的失败都不能走该入口，既存尝试不覆盖。`test_pilot.py` 仅作新保护逻辑的合成单元测试，不构建模型。公开 JSON 不含真实像元数组、权重或私有路径。

本轮通过仅证明随机初态下受控接口可用。Phase-B、科学接受、历史恢复和业务近实时能力仍未获批准或未验证；历史 2025 路径属性访问继续为 `NOT_INSTRUMENTED`。
