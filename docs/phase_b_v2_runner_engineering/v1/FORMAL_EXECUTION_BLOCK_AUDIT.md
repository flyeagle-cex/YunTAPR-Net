# 正式执行阻断审查

- 仅 SyntheticRunner 内部 make_synthetic_pair；无外部 batch、真实路径、DataLoader 或训练 epoch loop。
- start_formal/reject_formal_execution 无条件抛 PermissionError；bool、APPROVED 字符串、JSON 与 Git commit 均不起作用。
- 真实历史 checkpoint 及原始数据扩展名、含 2025 的访问、未登记 CSV 被进程审计拒绝。唯一 CSV 例外是 SHA 已核验的已发表元数据；合成 .pt/.part 只允许当前专用 store 上下文。
- 标准 optimizer 的直接 step 被阻断；只有账本预留成功的当前 AdamW 事务调用原始实现；6 个闭合模型×臂各≤2，任务总数≤12。
- formal 训练源码未导入候选 namespace；333 个冻结/历史来源全部 SHA 不变。
- step/checkpoint 失败不自动重试、换 seed、改参；恢复 apply 异常使 runner 停用。

保护范围是合作式候选 Python 进程的工程防误用，不是抵御任意恶意 Python/系统管理员的安全沙箱。发布此代码并未产生任何真实训练能力或授权。真实接入必须另建正式集成版本，进行本人审查与独立许可，不能靠修改一个布尔值启动。

V2_PHASE_B_AUTHORIZED=false；FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=false；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；HISTORICAL_RECOVERY_RATIFICATION=NOT_GRANTED；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
