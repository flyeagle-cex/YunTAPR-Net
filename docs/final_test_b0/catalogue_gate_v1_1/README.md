# B0 2025 catalogue gate v1.1

独立协议修正与 fixture 验证。真实 catalogue 和 Final Test 均未授权、未执行。

- [协议](../B0_2025_FINAL_TEST_PROTOCOL_v1.1.md)
- [完成报告](preflight/run_20261003T012656_856180Z/B0_2025_CATALOGUE_GATE_PREFLIGHT_REPORT_v1.1.md)
- [可编辑 LaTeX](preflight/run_20261003T012656_856180Z/B0_2025_CATALOGUE_GATE_PREFLIGHT_REPORT_v1.1.tex)
- [PDF](preflight/run_20261003T012656_856180Z/B0_2025_CATALOGUE_GATE_PREFLIGHT_REPORT_v1.1.pdf)
- [最终状态](preflight/run_20261003T012656_856180Z/final_status.json)
- [完整测试记录](preflight/run_20261003T012656_856180Z/test_results.txt)

实际 98 项测试通过。保留失败预检：run_20261003T012450_839209Z。所有既有 v1 证据和术语修订均保持 immutable。未来授权 schema 由 CatalogueAuthority.load / FinalAuthority.load 严格定义；仓库没有实际生产授权或真实 2025 CSV。

`delivery_artifact_sha256.json` 登记此发布新文件和两个退役 gate 的 bytes/SHA。当前 Python 为既有 F:/pytorch/Research/.venv-cuda/Scripts/python.exe；不变更环境包。完成本轮 GitHub main 发布后停止。
