# 正式工程就绪度与最小待审差异

**新隔离 P1 人工路径 PASS；正式 NOT_READY / NOT_AUTHORIZED。** 旧文件未应用差异，不能把新路径通过当作旧 reader 已替换。

下表模块默认在 src/yuntapr/experimental/ 下，行号适用于未改基线。

| 精确接口 | 结论 | 正式最小待审批差异 |
|---|---|---|
| runner_candidate/checkpoint.py:SyntheticStore.read；formal_integration_candidate/checkpoint.py:Store.read | FAIL（旧风险仍在） | 正式 reader 改可信注册+同句柄 SHA+BytesIO；禁止委托旧 read |
| p1_integration_candidate/checkpoint.py:Store.read/save | PASS（人工） | 正式已授权 LAST 可信登记，审查实际 payload/内存/磁盘预算 |
| formal_integration_candidate/engine.py:validate_and_commit（77）、restore_completed_last（106） | NOT_VERIFIED（未运行） | 注入新 transport，不再 reference.read_text() 二次信任路径；使用已验收据 SHA |
| 同文件 restore_completed_last（114–115） | NOT_VERIFIED（真实安装原子性） | 完整准备/校验后安装；任一 load/RNG 失败永久失败，不继续；恢复独立审批 |
| state.py:B9State.check_restore（86） | PASS（人工调用原方法） | READY/COMPLETE、非pending、LAST/epoch/update精确匹配继续保留；未构造DB/epoch |
| state.py:ActualQuota.perform（104） | PASS（静态）；正式额度未验证 | 不调用/重置旧四次合成与两次smoke；新正式持久额度绑定原执行授权 |
| metrics.py:Evaluator（36） | PASS（静态来源未变） | 精确binary64并列/磁盘累计保留；未重跑指标，正式全量容量仍未验证 |
| access.py:RealDataAdapter/RejectingAuthority | PASS（拒绝测试） | 真实来源、权限、审批服务关闭，不能用bool/JSON/commit启用 |
| p1 launcher.py:run / winjob.py:Job.spawn | PASS（人工） | 正式命令、资源、生命周期与审计身份另批；当前无任意argv |
| p1 integration.py:ArtificialRunner | PASS（人工） | 聚合reader/Job，无factory/epoch/optimizer；没有接入真实IntegratedEngine |

路径前缀全名分别为 phase_b_v2_runner_candidate、phase_b_v2_formal_integration_candidate、phase_b_v2_p1_integration_candidate、phase_b_v2_execution_watchdog_candidate，参见 manifest.json。

新 Contract 在独立 globals 中用 CPU RNG 适配复用原 envelope，无 CUDA RNG 或 live optimizer.load_state_dict；不偷换为正式恢复通过。新 BoundaryProbe 调用原 check_restore，仅人工 dict，不构造旧 DB 或消费旧 ActualQuota。

科学接口不变：

$$L_{\rm train}=(S_{\rm occ,\gamma}+\lambda_q S_{\rm qr})/N_{\rm valid},\quad
C_{\rm common}=(S_{\rm occ,2}^{64}+S_{\rm qr}^{64})/N_{\rm valid},\quad
P_{\rm conditional}=S_{\rm qr}^{64}/N_{\rm rain}.$$

本轮没有改 loss、FP64共同评价、fresh、B9终点或E0/E1/E2，没有调用fresh模型。此式仅标接口，不是科研结果。保护审计：3,692个旧跟踪文件SHA、封存额度anchor SHA与SQLite只读行均一致；旧smoke payload未打开；其他未跟踪任务未动。
