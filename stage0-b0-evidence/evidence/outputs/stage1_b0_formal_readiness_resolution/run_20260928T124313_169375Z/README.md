# YunTAPR-Net B0 Formal Readiness Resolution

结果：**B0_FORMAL_NOT_READY**，证据/候选/决策包已完成。科学入口仍有 12 项 blocker；没有启动训练。旧 B0 smoke PASS 保持原样。此目录为独立新 run，不能将此包完成等同于科学约定冻结或模型可正式训练。

## 导航

- [最终报告](FINAL_B0_FORMAL_READINESS_REPORT.md)
- [状态 JSON](b0_formal_readiness_status.json)、[入口矩阵](B0_FORMAL_ENTRY_MATRIX.csv)
- [研究者决策清单](RESEARCHER_DECISIONS_REQUIRED.md)、DECISIONS/ 下 10 张卡
- TIME/：原生/转换 metadata、四种时间候选、来源链、官方出处
- GAPS/：Final October 缺口，Late 身份和搜索覆盖限制
- SPATIAL/：4 个实际坐标候选、形状/margin/padding/索引与冻结 hash 校验
- SPLIT/：3 个连续块候选，数量仅未扣 QC/buffer 的名义上界
- DATA_CONTRACT/、MODEL/：machine-readable候选契约与科学待决项
- evidence_registry.csv/.parquet、PROVENANCE/：输入与生成脚本 hash
- tests/：首轮失败及修复后结果均保留；logs/：搜索、环境、临时缓存和完整性

## 运行和复核

固定 Python：`F:\pytorch\Research\.venv\Scripts\python.exe`。包版本实测记录于 logs/environment.json；没有安装或升级包。h5py 未安装，使用 netCDF4 读取 HDF5 metadata 成功；不因可选包缺失改环境。

本轮顺序：已授权文件名发现 → probe.py 只读 metadata/坐标及哈希保护 → build_package.py 分阶段断言 → run_checks.py 定向 pytest → finalize.py 校验旧证据、整理状态/报告。脚本历史按 hash 后缀保留，实际最终源文件 hash 在 PROVENANCE/generator_script_hashes.csv。第一次 build 因原 discovery 脚本换行编码字节差异中止，在归档各版本后继续。详情 logs/recovery_notes.json。

在完成包上复核测试可使用以下**只读**命令（不写回原测试日志）：

```powershell
& 'F:\pytorch\Research\.venv\Scripts\python.exe' -X utf8 -B -m pytest 'F:\pytorch\Research\outputs\stage1_b0_formal_readiness_resolution\run_20260928T124313_169375Z\tests\test_readiness.py' -q -p no:cacheprovider
```

不要在完成目录重跑写入构建脚本；写入函数采用排他创建，防止覆盖。要重建，应另建 run 并显式更新 probe.py 的 RUN，登记复用的 discovery 证据路径/hash，而非假装搜索当时状态仍代表新时点。旧 smoke 与 Stage0 目录始终作为只读依赖。测试覆盖契约和元数据，未重复 ML pipeline，也不是全月/全期 QC。

## 双格式与坐标

主要候选、矩阵及 registry 同时 CSV + Parquet，Parquet engine=pyarrow。CSV 使用 pandas 读取精确坐标应指定 `float_precision='round_trip'`，否则默认 C parser 可能产生一个 ULP 舍入差异；本轮首次一致性测试正是由此失败，源 CSV 与真实坐标未改动，修复读取后严格一致性通过。Parquet 无写入失败，也未更换依赖。坐标权威源为真实采样/冻结 NPZ/NetCDF + SHA，不用 arange 重建。

## 中文路径 bounded staging

只在本 run `cache/staging/` 创建随机英文名、单文件临时副本，每次验证 size 和 SHA256，用英文路径交给 netCDF4，仅读取 header/time/坐标。共 18 次，临时峰值 8,248,250 bytes，总复制 59,873,882 bytes，copy 0.051280s，metadata read 0.082704s，全部 cleanup 成功，当前临时数据为 0 bytes。没有删除 H 盘或任何已有诊断缓存。

源/副本 SHA 会增加读取 I/O，copy_seconds 与 read_seconds 不包含全部 hash 时间；本次数据是小规模 metadata probe 成本，**不是**重新做 Zarr/NetCDF 存储性能结论，也不能与旧 full-array benchmark 直接比较。唯一不可读的是 Late 的一个11月临时文件，错误已归档；科学 Final 证据不使用它。

## 完整性与限度

最终重新校验 135 条保护证据及全部新增只读输入，合并 162 个文件全部大小/mtime/SHA不变。没有对整个原始库重新逐文件 hash，raw_data_modified=false 来源于只读操作边界和这些实测保护记录。全盘搜索是名称发现，有跳过/访问拒绝，未解包旧 archive；不是不存在任何备用数据的绝对证明。

没有正式 mean/std、Train/Val/Test 实例分配、数据重采样、GFS/DEM特征、B0训练或下一阶段执行。输出按用户明确要求为可编辑 Markdown/CSV/JSON，而非另生成未要求的 PDF 或图表。
