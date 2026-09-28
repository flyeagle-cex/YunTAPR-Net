# Stage-0 Final Gate Package

先读 FINAL_STAGE0_GATE_REPORT.md，再看 B0_ENTRY_REQUIREMENTS.md 和 DECISIONS/cards。STAGE0_MASTER_STATUS 是唯一汇总入口；旧 run 保持其原时点结论。

CSV/JSON 是机器可核验状态，Markdown 为研究者阅读版本。evidence_registry.csv 提供 source run/file/section/SHA；EVIDENCE/evidence_fingerprint_check.csv 是定向检查结果。DECISIONS/gate_assessment.json 是本包的结构化依赖评估，不是新科研定义。

使用固定 Python：F:/pytorch/Research/.venv/Scripts/python.exe；无安装/升级。源码在 src；重现必须新建独立 run，不能对旧 run 执行 collect 或覆盖报告。pytest 仅校验决策包及只读证据，不运行旧任务、不生成数据或模型。

NOT_RUN、NOT_AUDITED、NOT_ESTABLISHED 不会因为工程测试通过而升级。完整性证据限登记关键输入；无全 raw 内容 hash 声明。
