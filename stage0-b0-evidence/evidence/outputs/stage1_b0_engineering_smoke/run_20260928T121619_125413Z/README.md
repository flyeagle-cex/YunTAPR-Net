# B0 offline engineering smoke

入口：FINAL_B0_ENGINEERING_SMOKE_REPORT.md；机器状态：b0_smoke_status.json。独立 run `F:\pytorch\Research\outputs\stage1_b0_engineering_smoke\run_20260928T121619_125413Z`。工程源码在 src，pytest 在 tests，真实小样本追溯表/读取 metadata/梯度/checkpoint/诊断在 B0_SMOKE。

使用固定 Python `F:\pytorch\Research\.venv\Scripts\python.exe`。代码可在新 run 重现；命令顺序如下（prepare 返回新路径，用它替换 NEW_RUN）：

```powershell
& 'F:\pytorch\Research\.venv\Scripts\python.exe' 'src/scripts/run_b0_smoke.py' prepare
& 'F:\pytorch\Research\.venv\Scripts\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' unit --run 'NEW_RUN'
& 'F:\pytorch\Research\.venv\Scripts\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' execute --run 'NEW_RUN'
& 'F:\pytorch\Research\.venv\Scripts\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' final_tests --run 'NEW_RUN'
& 'F:\pytorch\Research\.venv\Scripts\python.exe' 'NEW_RUN/src/scripts/run_b0_smoke.py' finalize --run 'NEW_RUN'
```

只有明确授权时才开始另一轮。写文件使用独占创建；不能原路径覆盖执行。单位/时间/missing 合约见 B0_SMOKE 的独立说明。模型调用仅接受 B13 一帧；不导入 GFS/DEM/ERA5/DOTE/DTFM/MEE。七通道旧源码仅用于提取既有纯解码函数，其他通道数组未读取。pyarrow CSV/Parquet 双格式保持表格原字符串表示，JSON 保存类型化记录。

checkpoint 为 SMOKE CHECKPOINT / NOT SCIENTIFIC CHECKPOINT。诊断使用参与过 smoke updates 的 4 个真实样本，不是 held-out validation/test。没有论文图表或科研结论。下一阶段不自动启动。
