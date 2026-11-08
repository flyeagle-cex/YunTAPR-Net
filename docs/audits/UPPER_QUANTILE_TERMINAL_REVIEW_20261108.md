# UPPER-QUANTILE-PAIR-20261108｜终态与 7 项 gate 只读复核

- 审核者：Harness（独立于 Codex）
- 范围：只读 `TERMINAL_VERIFICATION.json`、`RESULTS.json` 及保存的 JSON/SQLite 元数据；未读权重/数据，未训练/推理/测试，未使用 2025，未生成批准
- 结论：**工程收据 PASS；DEVELOPMENT SCREEN FAIL；科学 NOT_VERIFIED**

## 0. 内容结论先行

候选 `UQ_MILD_V1` **没有通过预注册筛查**：

- **通过 3/7 项**：`all_physical_pinball`、`strong_log_pinball`、`strong_physical_pinball`；
- **失败 4/7 项**：`all_log_pinball`、`brier`、`occurrence_ap`、`occurrence_auroc`；
- 两个强雨诊断有小幅改善，但四项护栏失败，因此 `RESULTS.screen_passed=false`，`TERMINAL.status=ENGINEERING_COMPLETE_SCREEN_FAILED`。

这是内容结论，先于 Git 操作报告。

## 1. 终态与总量

- `TERMINAL_VERIFICATION.json`：`code_commit=f43b4225fef462a31035d59a06b85f31e5b257dc`，`exit.return_code=0`，`automatic_retry=false`，`target_elapsed_seconds=34920.439852 < 43200`。
- 包 completion：`COMPLETE_TRAIN_AND_DEV_EVALUATION`，`updates=8640`，`source_bytes=955143907680`，`source_files=285626`。
- 两臂 completion 均为 4320 更新、477,571,953,840 B、142,813 次；两臂合计 **8640 / 955,143,907,680 / 285,626**，与终态一致。
- 每臂 `updates.sqlite`：**4320 行全部 RETURNED，范围 1–4320**。
- 每臂 9 个 Train pass + 9 个 Dev pass；实测 receipts 合计：
  - Train：71,262 打开 / 237,818,363,004 B
  - Dev：71,550 打开 / 239,753,278,008 B
  - 加 static 1 次 / 312,828 B
  - 合计 **142,813 次 / 477,571,953,840 B**，与单臂 completion 一致。
- 两臂 `replay=0`；无 failure/自动重试。

## 2. 7 项 gate 复核

按预注册 tolerance `1e-10`，直接从 `RESULTS.metrics` 的 delta 重算：

| gate | control | candidate | delta | 判定 |
|---|---:|---:|---:|---|
| all_log_pinball | .12740129422354954 | .12753815183063594 | +.00013685760708639916 | **FAIL（上升）** |
| all_physical_pinball | .019610600071569055 | .019599873546433805 | −.000010726525135250353 | PASS |
| strong_log_pinball | .8982487808534173 | .8973089050661304 | −.0009398757872869368 | PASS |
| strong_physical_pinball | .5409483556362883 | .5404426720236376 | −.000505683612650687 | PASS |
| brier | .09673163538839748 | .09701111768999805 | +.0002794823016005754 | **FAIL（上升）** |
| occurrence_ap | .5934546324623617 | .5920422686238742 | −.0014123638384875292 | **FAIL（下降）** |
| occurrence_auroc | .8959240618810312 | .8958980523000758 | −.000026009580955443923 | **FAIL（下降）** |

结论：**3/7 通过，`screen_passed=false`**；与 `TERMINAL.development_screen=FAIL` 一致。强雨项虽改善：

- strong log −0.10463424023731711%；
- strong physical −0.09348094090347657%；

但 all-log +0.1074%、Brier +0.2889%、AP −0.2380%、AUROC −0.0029%，四项护栏失败，不能把强雨小幅改善当作筛查通过。

## 3. E9 身份与人口

两臂 E9 人口完全一致：

- scenes **963**
- valid **3,303,090**
- wet **407,820**
- strong R>20 **717**

六个 group 的 `scenes / valid / wet`、`ids_sha`、`source_sha`、`source_identity` 均一致；population/partition 摘要一致。

两臂 `paired_initial_identity.json` 内容相同：B7 full state = `ab749c88283399a8fe839e872b7dfdc64904aa80bd4d1bc560c399dbeb9a6326`；`paired_orders.json` 字节 SHA 均为 `193fcbc6eab5fa3b29b02ecc3419ab7a01b45a143f08f0a7464fbcc1f4067502`。故 **same initial state / same nine orders** 成立。

E9 收据：

- CONTROL_E0：checkpoint SHA `a3f9208a...5565f`；report SHA `ff46da36...dc060`；tail SHA `84652e83...d27df`；
- CANDIDATE：checkpoint SHA `06c384b9...12635`；report SHA `15838165...6a63b`；tail SHA `3889d02a...bd0a77`。

两臂 completion、report、tail、paired initial/orders、receipt 的实际字节+SHA 与 `TERMINAL`/`RESULTS` 一致；`paired_loss_summary.json` 2321 B / `ef81dd7c...f687437` 与 `RESULTS.pair_summary_identity` 一致。

## 4. 限制

1. 只核 JSON/SQLite 元数据，未重读两个 E9 checkpoint 权重，也未读原始数据；checkpoint SHA 来自收据/该终态记录。
2. 单 seed 2029、重复使用 2024 Development；717 个 R>20 像元时次不是独立天气事件，R>50 仅 6 个像元时次。
3. q32 覆盖率仅辅助：候选 all q32 = 384,737/407,820（约 .943399），strong q32 仍 39/717；不能作为成功 gate 或概率校准。
4. 无显著性、机制或最终模型选择结论；2025 未访问；`scientific_acceptance=NOT_VERIFIED`，研究者掌握 NOT_ASSESSED。
5. 工程终态 PASS 只表示收据/总量/身份可核对；不改变 development screen FAIL。

## 5. 结论

**工程量：PASS（终态收据、总量、E9 身份与人口可核对）。**  
**候选筛查：FAIL（3/7 gate，四项护栏失败）。**  
**科学：NOT_VERIFIED；研究者掌握：NOT_ASSESSED。**

本轮未训练/推理/重评，未读权重/数据/缓存/2025，未生成批准，未修改 Codex。
