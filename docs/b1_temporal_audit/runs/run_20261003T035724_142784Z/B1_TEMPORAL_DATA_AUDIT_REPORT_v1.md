# B1 Six-Slot Temporal Data Audit v1

**真实当前源 B13 QC 已完成；集合为候选分类，不是正式 B1 监督资格政策。**

Run `run_20261003T035724_142784Z`；baseline `4286f8151fea2185c99b3cea0c8e532e8cd90070`；完整定义见 `config/b1/b1_six_slot_audit_definition_v1.json`，SHA `b6887a59900aa2f736cec4ab0d8727511e59eb9fc4e0418ebcb7d71778cd66d4`。

实际源读取在 `run_20261003T024550_523841Z` 完成。该 run 最终登记遭遇 CLI str/Path 错误，失败状态保留；当前 run 只复制已完成 QC/身份 metadata 并独立复算，不重读 raw。`source_run_snapshot.json` 绑定全部原文件 hash，`source_execution_code/` 保存原代码；`cli_registry_resolution.json` 记录修正与原 guard 终态 counter 未捕获，staging 实测 I/O 计数完整保留。

本轮仅 2023 Train / 2024 Validation March–October。预期 native slots=70560、targets=23520、scene-slots=141120。六个 offsets、channel order、tensor 已研究者批准；缺帧、normalization、fairness 尚待决定。所有 B13 缺测保留 NaN 解码语义；不插值、不代帧、不翻转坐标、不拟合统计。

## 年度集合

|角色|日历 targets|B0 原始 eligible|六槽 present|六槽 full-valid causal|B1 候选 eligible|交集候选|拒绝或未解决候选条件|
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023_TRAIN | 11760 | 11720 | 10502 | 10455 | 10455 | 10455 | 1305 |
| 2024_VALIDATION | 11760 | 11727 | 10545 | 10501 | 10501 | 10501 | 1259 |

候选 target 需要至少一个已冻结云南 mask 有效 target pixel；其有效性仅引用已签名的 2023/2024 历史证据，未打开 raw IMERG，也未计算降雨统计。原 B0 资格按冻结身份表完整保留。

## 原生 QC（月度）

|月|预期 native slots|实际 QC 状态计数|
|---|---:|---|
| 202303 | 4464 | ALL_FILL=5; FULL_VALID=4367; MISSING=81; PARTIAL=11 |
| 202304 | 4320 | ALL_FILL=4; FULL_VALID=4222; MISSING=79; PARTIAL=15 |
| 202305 | 4464 | FULL_VALID=4384; MISSING=80 |
| 202306 | 4320 | FULL_VALID=4242; MISSING=78 |
| 202307 | 4464 | CORRUPT_OR_UNREADABLE=1; FULL_VALID=4382; MISSING=81 |
| 202308 | 4464 | FULL_VALID=4385; MISSING=79 |
| 202309 | 4320 | ALL_FILL=9; FULL_VALID=4214; MISSING=78; PARTIAL=19 |
| 202310 | 4464 | FULL_VALID=4385; MISSING=79 |
| 202403 | 4464 | ALL_FILL=6; FULL_VALID=4370; MISSING=77; PARTIAL=11 |
| 202404 | 4320 | ALL_FILL=3; FULL_VALID=4228; MISSING=77; PARTIAL=12 |
| 202405 | 4464 | FULL_VALID=4384; MISSING=80 |
| 202406 | 4320 | FULL_VALID=4246; MISSING=74 |
| 202407 | 4464 | FULL_VALID=4390; MISSING=74 |
| 202408 | 4464 | FULL_VALID=4387; MISSING=77 |
| 202409 | 4320 | ALL_FILL=8; FULL_VALID=4218; MISSING=74; PARTIAL=20 |
| 202410 | 4464 | FULL_VALID=4385; MISSING=79 |

## 各槽独立原因


### 2023_TRAIN

| slot | lag min | missing | unreadable | partial | all-fill | metadata | noncausal | outside-scope | bucket deviation (diagnostic) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 66 | 1 | 17 | 7 | 0 | 0 | 1 | 0 |
| 1 | 50 | 543 | 0 | 14 | 11 | 0 | 0 | 1 | 0 |
| 2 | 40 | 26 | 0 | 14 | 0 | 0 | 0 | 1 | 0 |
| 3 | 30 | 66 | 1 | 17 | 7 | 0 | 0 | 0 | 0 |
| 4 | 20 | 543 | 0 | 14 | 11 | 0 | 0 | 0 | 0 |
| 5 | 10 | 26 | 0 | 14 | 0 | 0 | 0 | 0 | 0 |

### 2024_VALIDATION

| slot | lag min | missing | unreadable | partial | all-fill | metadata | noncausal | outside-scope | bucket deviation (diagnostic) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 60 | 51 | 0 | 16 | 7 | 0 | 0 | 1 | 0 |
| 1 | 50 | 541 | 0 | 14 | 10 | 0 | 0 | 1 | 0 |
| 2 | 40 | 20 | 0 | 13 | 0 | 0 | 0 | 1 | 0 |
| 3 | 30 | 51 | 0 | 16 | 7 | 0 | 0 | 0 | 0 |
| 4 | 20 | 541 | 0 | 14 | 10 | 0 | 0 | 0 | 0 |
| 5 | 10 | 20 | 0 | 13 | 0 | 0 | 0 | 0 | 0 |


metadata 表含 grid/packing 和 time metadata 错误；单独原因见 native/slot rows。noncausal 使用真实 CF 时间，而 scan bucket 只对照、不剔除。outside-scope 共六槽，两年各首 target 三槽，绝不混入 missing。

## 完整 multi-reason 与 incidence


### 2023_TRAIN 全部 multi-reason 组合

| 完整原因组合（槽位不合并） | target 数 |
|---|---:|
| `S0_ALL_FILL;S4_MISSING` | 7 |
| `S0_CORRUPT_OR_UNREADABLE` | 1 |
| `S0_MISSING` | 63 |
| `S0_MISSING;S1_MISSING` | 2 |
| `S0_MISSING;S2_MISSING` | 1 |
| `S0_OUTSIDE_AUDIT_SCOPE;S1_OUTSIDE_AUDIT_SCOPE;S2_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S0_PARTIAL;S1_ALL_FILL;S4_MISSING` | 11 |
| `S0_PARTIAL;S1_MISSING` | 1 |
| `S0_PARTIAL;S1_PARTIAL;S3_MISSING;S4_MISSING` | 1 |
| `S0_PARTIAL;S1_PARTIAL;S4_MISSING` | 3 |
| `S0_PARTIAL;S4_MISSING` | 1 |
| `S1_MISSING` | 536 |
| `S1_MISSING;S2_MISSING` | 1 |
| `S1_MISSING;S2_MISSING;S3_MISSING` | 1 |
| `S1_MISSING;S4_MISSING` | 2 |
| `S1_PARTIAL;S2_PARTIAL;S3_PARTIAL;S4_MISSING` | 1 |
| `S1_PARTIAL;S2_PARTIAL;S4_MISSING` | 5 |
| `S1_PARTIAL;S4_MISSING` | 4 |
| `S2_MISSING` | 23 |
| `S2_PARTIAL` | 4 |
| `S2_PARTIAL;S3_ALL_FILL` | 3 |
| `S2_PARTIAL;S3_PARTIAL` | 1 |
| `S3_ALL_FILL` | 4 |
| `S3_CORRUPT_OR_UNREADABLE` | 1 |
| `S3_MISSING` | 62 |
| `S3_MISSING;S4_MISSING` | 1 |
| `S3_MISSING;S5_MISSING` | 1 |
| `S3_PARTIAL;S4_ALL_FILL` | 11 |
| `S3_PARTIAL;S4_PARTIAL` | 4 |
| `S4_MISSING` | 505 |
| `S4_MISSING;S5_MISSING` | 2 |
| `S4_PARTIAL` | 4 |
| `S4_PARTIAL;S5_PARTIAL` | 6 |
| `S5_MISSING` | 23 |
| `S5_PARTIAL` | 8 |

原因 incidence（一个 target 可计多个，不可相加当作拒绝 target 数）：

| 独立原因 | incidence |
|---|---:|
| `S0_ALL_FILL` | 7 |
| `S0_CORRUPT_OR_UNREADABLE` | 1 |
| `S0_MISSING` | 66 |
| `S0_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S0_PARTIAL` | 17 |
| `S1_ALL_FILL` | 11 |
| `S1_MISSING` | 543 |
| `S1_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S1_PARTIAL` | 14 |
| `S2_MISSING` | 26 |
| `S2_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S2_PARTIAL` | 14 |
| `S3_ALL_FILL` | 7 |
| `S3_CORRUPT_OR_UNREADABLE` | 1 |
| `S3_MISSING` | 66 |
| `S3_PARTIAL` | 17 |
| `S4_ALL_FILL` | 11 |
| `S4_MISSING` | 543 |
| `S4_PARTIAL` | 14 |
| `S5_MISSING` | 26 |
| `S5_PARTIAL` | 14 |

### 2024_VALIDATION 全部 multi-reason 组合

| 完整原因组合（槽位不合并） | target 数 |
|---|---:|
| `S0_ALL_FILL;S4_MISSING` | 7 |
| `S0_MISSING` | 50 |
| `S0_MISSING;S1_MISSING;S2_MISSING;S3_MISSING` | 1 |
| `S0_OUTSIDE_AUDIT_SCOPE;S1_OUTSIDE_AUDIT_SCOPE;S2_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S0_PARTIAL;S1_ALL_FILL;S4_MISSING` | 10 |
| `S0_PARTIAL;S1_PARTIAL;S4_MISSING` | 5 |
| `S0_PARTIAL;S4_MISSING` | 1 |
| `S1_MISSING` | 537 |
| `S1_MISSING;S3_MISSING` | 1 |
| `S1_MISSING;S4_MISSING` | 1 |
| `S1_MISSING;S5_MISSING` | 1 |
| `S1_PARTIAL;S2_PARTIAL;S4_MISSING` | 5 |
| `S1_PARTIAL;S4_MISSING` | 4 |
| `S2_MISSING` | 17 |
| `S2_MISSING;S4_MISSING` | 2 |
| `S2_PARTIAL` | 4 |
| `S2_PARTIAL;S3_ALL_FILL` | 3 |
| `S2_PARTIAL;S3_PARTIAL` | 1 |
| `S3_ALL_FILL` | 4 |
| `S3_MISSING` | 48 |
| `S3_MISSING;S4_MISSING;S5_MISSING` | 1 |
| `S3_PARTIAL;S4_ALL_FILL` | 10 |
| `S3_PARTIAL;S4_PARTIAL` | 5 |
| `S4_MISSING` | 505 |
| `S4_PARTIAL` | 4 |
| `S4_PARTIAL;S5_PARTIAL` | 5 |
| `S5_MISSING` | 18 |
| `S5_PARTIAL` | 8 |

原因 incidence（一个 target 可计多个，不可相加当作拒绝 target 数）：

| 独立原因 | incidence |
|---|---:|
| `S0_ALL_FILL` | 7 |
| `S0_MISSING` | 51 |
| `S0_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S0_PARTIAL` | 16 |
| `S1_ALL_FILL` | 10 |
| `S1_MISSING` | 541 |
| `S1_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S1_PARTIAL` | 14 |
| `S2_MISSING` | 20 |
| `S2_OUTSIDE_AUDIT_SCOPE` | 1 |
| `S2_PARTIAL` | 13 |
| `S3_ALL_FILL` | 7 |
| `S3_MISSING` | 51 |
| `S3_PARTIAL` | 16 |
| `S4_ALL_FILL` | 10 |
| `S4_MISSING` | 541 |
| `S4_PARTIAL` | 14 |
| `S5_MISSING` | 20 |
| `S5_PARTIAL` | 13 |


## 来源、工程成本与测试

全部 present B13 的原始和 staging SHA256/bytes 逐文件一致；读目标是 ASCII staging；原盘只读。当前 native frame index SHA：`a5054200d6bde11f2342c292ca72428d0558d5b5c5c640017844f0b4ed8c540e`。final_status 保存全部 16 native / 16 slot / 6 population CSV 的 SHA。

源码/定义 SHA 在开始和结束均核验一致，1802 个历史文件原字节保留。源文件 copy read / temporary write 各 306,101,365,884 bytes，原盘额外 hash read 306,101,365,884 bytes。copy 967.487s，read/QC 649.401s，总 elapsed 2250.931s；单文件暂存峰值 636,106,619 bytes；清理均成功。

closure 40 tests 全通过、零 skip；失败 probe 历史保留。closure 原始源读取=0，2025 像元=0。当前审计 MODEL_FORWARD/CHECKPOINT_LOAD/BACKWARD/OPTIMIZER 全为 0。

## 文件联结

- `native_frames/YYYYMM.csv`：原生 nominal、精确 relative_path、bytes/SHA、validity、CF 时间、全部 QC 原因。
- `six_slots/YYYYMM.csv`：sample_id + slot → expected_nominal → native row；保留 causality、diagnostic bucket、全部 slot 原因。
- `b0_original_eligible_YYYY.csv` / `b1_candidate_eligible_YYYY.csv` / `intersection_candidate_YYYY.csv`：identity-only，显式候选标签，绑定 frame index SHA。
- `frame_identity_index.json` / `audit_start.json` / `final_status.json`：来源、定义、源码、集合哈希与真实零操作状态。
- `history_before.json` / `closure_test_summary.json` / `closure_test_results.txt`：不可变历史和测试证据。
- 设计决策、editable LaTeX/PDF：`docs/b1_scientific_design/B1_SCIENTIFIC_DESIGN_DECISION_PACKET_v1.*`。

```text
B1_DESIGN_FROZEN=false
B1_SLOT_DEFINITION_FROZEN=true
B1_TENSOR_CONTRACT_FROZEN=true
B1_TEMPORAL_AUDIT_EXECUTED=true
B1_MISSING_POLICY_FROZEN=false
B1_NORMALIZATION_FROZEN=false
B1_FAIRNESS_PRIMARY_POPULATION_FROZEN=false
B1_FORMAL_MODEL_IMPLEMENTED=false
B1_TRAINING_STARTED=false
B1_NORMALIZATION_FITTED=false
2025_FINAL_TEST_EXECUTED=false
2025_MODEL_INFERENCE_SCENES=0
2025_RAW_PIXELS_READ=0
MODEL_CHECKPOINT_LOADS=0
MODEL_FORWARD_CALLS=0
OPTIMIZER_STEPS=0
BACKWARD_CALLS=0
```

本轮完成后 STOP。未来正式资格规则、normalization 或比较集合不允许被这份候选审计静默决定。
