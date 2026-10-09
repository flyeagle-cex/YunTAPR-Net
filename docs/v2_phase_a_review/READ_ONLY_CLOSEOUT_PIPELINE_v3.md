# v2 paired Phase-A：训练后只读收尾

两模型的实际 final_report 均为 COMPLETE：completed epoch=17，BEST epoch=9，early-stop counter=8。最新恢复 wrapper 正常退出，pair completion marker 存在，正式 GPU lock 已释放。这些事实由 completion_gate 实际核验；不是 fixture 或预计完成状态。

B0 全部完整 epoch 的既有终止审计继续保留。新增独立收尾程序只按以下顺序执行：

1. B1 完整 17 epoch CPU 审计：逐轮样本身份、顺序、LR、损失、梯度、分母、diagnostics、counter 和 checkpoint 内部状态 SHA。
2. 两个 BEST 的全量 2024 只读推理：共同固定的 10,501 场景；仅应用 model state；禁止 optimizer 构造与 backward；按原始分子全局累计，并与 BEST 原验证值零容差对账。Brier/AUROC/AP/conditional pinball 只作开发比较。
3. 生成配对决策包 JSON、CSV、Markdown 和可编辑 LaTeX。真正的 PDF 编译、逐页视觉核验、最终 GitHub 发布及 Goal completion audit 仍由后续收尾完成，程序不会把它们标为 PASS。

入口：run_read_only_closeout_v2.py。默认只核验 completion metadata，不启动子进程。显式 --execute 才执行上述只读链路；代码须与指定已发布 commit 的字节相符，远端 main 须包含该 commit。每个子任务执行前重新验证所有收尾代码 SHA。

GPU 推理使用冻结 F:/pytorch/Research/.venv-cuda/Scripts/python.exe 与 PYTHONHASHSEED=2026、CUBLAS_WORKSPACE_CONFIG=:4096:8。CPU checkpoint 审计单独设置 CUDA_VISIBLE_DEVICES=-1。正式 execution checkout 不修改。

每次执行创建独立 UTC run 目录，保存 launch manifest、子进程命令/PID、stdout/stderr、exit code 和 append-only 进度。失败形成独立 FAILED_STOP，不自动重试、恢复训练、修复或跳 batch。2025 与 Phase-B 保持禁止。

同一 localhost 8771 只读页面显示本次审计/推理进度；POST 拒绝，API 不提供控制训练功能。页面只读内存状态，不打开正式 live journal 或 mutable runner JSON。旧监控源码和其 hash 绑定记录保留。

测试：本次 13 项 metadata/mock fixtures 实际 PASS。初次 fixture 共享对象错误和 sandbox 临时目录权限错误记录于 closeout_packet_fixture_tests_20261009_v1.json；不计为训练失败。既有 770 项 preflight 证据不覆盖，也不宣称本次重跑了该 suite。

两模型正式保留轨迹分别为 88,876 updates。B0 all-attempt=89,175–89,176、discarded=299–300；B1 all-attempt=92,353、discarded=3,477。历史不确定区间原样保留，不填造精确计数。

所有生成报告采用“样本集合”与 scene-pixel exposure 等准确术语。上尾风险、p99/p99.9 和描述性阈值不得反向影响冻结协议或选择。

最终仍须：RESEARCHER_PHASE_A_REVIEW_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
