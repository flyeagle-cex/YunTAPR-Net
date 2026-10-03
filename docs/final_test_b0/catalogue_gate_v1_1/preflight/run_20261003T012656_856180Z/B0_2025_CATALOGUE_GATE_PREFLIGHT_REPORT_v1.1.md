# B0 2025 catalogue gate / protocol v1.1 closure report

本轮完成协议 v1.1、catalogue-only builder、两阶段授权、future formal runner 改接和 fixture preflight。**没有构建真实 2025 catalogue，没有执行 Final Test。**

科学基线：299d3f1080840b24db3ba6fe39684a1e6bca530a。研究者批准的工程起点：65e1086bc2f0d830a6f45e01253b4ccffcae1130。当前 run：`run_20261003T012656_856180Z`，UTC。v1 文档、YAML 和全部原有审计证据保持原字节；1745 个起点文件无变化。仅两个已有代码文件加入 v1 formal 授权/入口永久拒绝，防止旧单 manifest gate 被绕过。

## 实际验证

98 tests PASS，0 failures/errors/skips：catalogue gate 80，synthetic NetCDF backend 18。这是本轮新增目录工程测试；没有宣称重新运行全项目训练/优化器 regression suite。外层固定原始 roots 的 source guard 与 catalogue-only model/metric guard 全程有效。fixture 临时模型、checkpoint、optimizer 从未创建；CSV/NetCDF/staging 临时目录经 ownership 检查后清理。

测试覆盖严格字段/值/CSV header、所有结果字段别名、rain-invariant eligibility、全部 10272 UTC slots、October hard reject、缺失/重复/重排、12 列身份投影、FINAL/model/forward/loss/metrics aliases 阻断、guard 复用/回滚、protected path、双 CSV 与 freeze SHA、freeze 后独立授权、不可变授权与 byte snapshot。positive authorization 测试仅验证 synthetic metadata，所有身份/SHA 来源为 fixture，绝不是真实 2025 freeze 或授权。

先前独立预检失败 run 保留：run_20261003T012450_839209Z。失败项为 outer guard 下的 staticmethod fixture 假设，改用不能执行真实计算的独立静态 fixture descriptor 后重新创建 run 并通过；没有覆盖失败记录。

## 防泄漏与访问语义

28 列候选目录禁止 rainy count、雨强/频率/bin/exceedance、预测和全部性能统计；12 列 eligible manifest 只包含身份。IMERG 日 QC 返回 48 个 valid-mask counts，保留原解码 validity 语义，删除局部解码值，不计算 rain occurrence/intensity summary。B13 保留 date_created 可解析性检查，但不输出、不作为 availability。

catalogue-only scope 在 source preflight 前独立核验 protocol/implementation/roots/completion manifest pins；checkpoint、模型、forward、loss 和 metric 被阻断。任何 raw NC 均不能充当 completion manifest。English staging 单文件复制，size/SHA 验证，自有副本清理；真实未来 QC 的像元计数、hash/copy bytes、copy/read seconds 和 cleanup 单独登记。失败 artifact 不携带原异常文本，不写入旧目录。

第二阶段只能在真实 catalogue freeze 后获研究者另行授权，绑定协议、实现、FINAL、normalization、candidate/eligible CSV SHA 及 freeze record SHA。同一已核验字节用于解析，授权与样本 snapshots 只读，正式 dataset 必须等于授权样本集合。rainy count 只允许在真正获授权的 inference runtime 内动态计算并写 runtime ledger，不能回填 catalogue。

本轮 2025_CATALOGUE_QC_ACCESS=false，FINAL_TEST_2025_EXECUTED=false，2025_MODEL_INFERENCE_SCENES=0，2025_FINAL_TEST_METRICS_COMPUTED=false，2025_TARGET_OUTCOME_SUMMARIES_EXPOSED=false，2025_PIXELS_READ=0，raw opens=0，checkpoint loads=0，model forward=0，backward=0，optimizer steps=0，MODEL_PARAMETERS_UPDATED=false。pixel 计数只是 raw-access telemetry，不是 Final Test 执行判据。未来 formal partial failure 报告 source-open 事实与 completed-sample 下界，不能误写 exact read=0。

## 冻结与未执行

FROZEN：v1 的十个科学定义子树逐项一致；v1.1 catalogue schema、授权顺序、防泄漏规则、全部原 primary/diagnostic 定义。v1.1 SHA：`b1be82d5bc03293c35ddc793faa1187e97fa48c537039181c0eb68a689f15eb8`。

NOT_EXECUTED：真实 2025 candidate catalogue、真实 eligible manifest、真实 eligible/rejected/reason counts、FINAL loading、2025 inference 和 metrics。10272 只代表已冻结计划窗口数；真实资格数量为 NOT_INSPECTED。

RESEARCHER_AUTHORIZATION_REQUIRED：先授权 `B0_2025_FINAL_TEST_CATALOGUE_ONLY`；真实 QC/freeze 完成后，再单独授权 Final Test。当前没有任何生产授权文件，本发布不是授权。

## 交付与运行

协议说明：`docs/final_test_b0/B0_2025_FINAL_TEST_PROTOCOL_v1.1.md`。本 run 保存 manifest、完整 test_results、test_summary、final_status、此 Markdown、LaTeX、PDF 和 PDF render verification。delivery_artifact_sha256.json 对新文件及两个退役 gate 文件登记 SHA/bytes，不改写旧索引。GitHub 发布 commit 以 main 历史及独立 publication receipt 为准。

本轮实际执行：`F:\pytorch\Research\.venv-cuda\Scripts\python.exe scripts/build_b0_2025_final_test_catalogue_v1.py preflight`。未安装或升级依赖。

最终：FINAL_TEST_PROTOCOL_V1_1_FROZEN=true；FINAL_TEST_CATALOGUE_RUNNER_READY=true；FINAL_TEST_CATALOGUE_AUTHORIZED=false；FINAL_TEST_2025_AUTHORIZED=false；FINAL_TEST_2025_EXECUTED=false。提交 GitHub main 后 STOP。
