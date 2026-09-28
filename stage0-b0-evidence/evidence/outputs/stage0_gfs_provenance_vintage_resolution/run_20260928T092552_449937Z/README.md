# GFS provenance / vintage evidence resolution

本轮目录：`F:\pytorch\Research\outputs\stage0_gfs_provenance_vintage_resolution\run_20260928T092552_449937Z`。固定解释器：`F:\pytorch\Research\.venv\Scripts\python.exe`。只读旧日志、manifest、审计表和 40 个预先登记的定向原始文件。没有全库重扫、合并、训练或依赖升级。

- 入口结论：FINAL_GFS_PROVENANCE_VINTAGE_REPORT.md、audit_final_status.json。
- 证据：PROVENANCE/、TIME_LINEAGE/、TIME_AVAILABILITY/；来源和行号保留在表中，所有表提供 CSV/pyarrow Parquet，写入/回读检查见 logs/parquet_validation.csv。
- 准入：NEEDS_MORE_PROVENANCE；historical operational vintage NOT_ESTABLISHED。工程测试通过也不替代科研批准。
- 执行源：src/discover_artifacts.py → src/trace_cases.py → src/extract_evidence.py → src/resolve_evidence.py → src/verify_integrity.py → scoped pytest → src/finalize.py。脚本使用独占新建输出，不能盲目重跑覆盖；新执行应复制到新 run 并更新 config。
- 原始文件只读。英文 staging 上限 32 MiB、单文件逐次复制，校验大小与 SHA256，使用 netCDF4 只读，随后仅清理本轮拥有的临时副本。copy/read 秒数与 bytes 保留 logs/staging_io.jsonl。历史诊断缓存未清理。
- 无 release 推算；未知字段明确 UNKNOWN/NOT_ESTABLISHED，不用 0、空时间或 NOT_RUN 冒充 PASS。缺失时间在表中留空并提供状态列。
- 旧 run 为历史证据，未重写；本轮有限 SHA256 核查不宣称全盘逐文件哈希验证。output_manifest.csv 记录最终产物哈希，自身不自引用。
