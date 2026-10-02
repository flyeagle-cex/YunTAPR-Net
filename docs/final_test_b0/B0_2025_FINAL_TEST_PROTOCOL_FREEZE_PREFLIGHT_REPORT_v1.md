# YunTAPR-Net B0 2025 Final Test 协议冻结与 runner preflight v1

本轮完成评价协议冻结、独立 Final Test runner 和零 2025 读取 preflight。最终版本实际执行 **60 项测试，全部通过，failure/error/skip 均为 0**。只对已冻结 FINAL 做只读身份核验及 synthetic 输入的 CUDA forward，没有执行正式 Final Test。

## 身份、基线与执行证据

- baseline：`ddbb69ccca6c806973a89a91127ea02c9af42afd`；基线 1,711 个文件逐文件 Git blob / SHA256 核验，均保持原样。
- 最新有效 preflight：`run_20261002T152029_621524Z`；完成 UTC：`2026-10-02T15:20:36.330304+00:00`。
- 协议：`config/evaluation/b0_2025_final_test_protocol_v1.yaml`。
- 协议 SHA256：`6d08def2602dda3d931937c68cadeae86b5c16b60f9f7132c9e134b962cdbe3b`。
- FINAL：`F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit\run_20261002T035929_487644Z\epoch_011.pt`；52,071,595 bytes；epoch 11；global update 128,964。
- FINAL SHA256：`05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65`。读取前后完全相同。
- Phase-B normalization：mean 270.5900486586461 K，std 20.368583874067266 K。
- normalization SHA256：`c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327`；不 refit。
- 模型逻辑 state SHA256：`d6e64fe6f3e38eb421806858fc0f484ebfb2ec0fcc952604813fa448f8e49944`；加载后与推理后逐值身份相同。

## FROZEN：评价时期、资格规则与指标

测试窗口起点仅允许 UTC `[2025-03-01 00:00, 2025-10-01 00:00)`，间隔 30 分钟，即日历上 10,272 个候选槽位。该数来自日期运算，**不是读取 2025 数据得到的 eligible scene 数**；实际 eligible population 当前 `NOT_INSPECTED`。未来正式授权后的 catalogue 必须逐一登记全部槽位、固定资格结论及拒绝原因，再冻结 population identity。

沿用 V1.1 正式 B0 规则：IMERG V07 Final provenance、精确网格/时间、501×501 B13 全场 valid/finite、预期最新 nominal=T+20min、obs_start≤obs_end≤analysis_time=T+30min、无 older-frame fallback，以及冻结云南 mask 中有效监督像元数>0。保留 IMERG 部分有效场，不新增每场 3,430 像元全部有效的要求；缺测继续 masked，绝不当 0。固定时间顺序、每个 eligible identity 一次，batch=2、drop_last=false、worker=0。population 冻结后任一 SHA/size/QC/因果/cleanup 问题必须停止，不跳过、不替代。

9 月 30 日 23:30 起始窗口允许，其结束时刻 10 月 1 日 00:00 是窗口边界；所用卫星 nominal 为 9 月 30 日 23:50。10 月源文件与 10 月起始窗口在打开前拒绝。拒绝规则同时检查目录和文件名的日期，覆盖错放在 9 月目录的 10 月文件。

预声明主要指标：global core loss、occurrence loss、quantile loss、Brier、AUROC、Average Precision、conditional mean pinball、每个 tau 的 pinball、32 tau conditional coverage、coverage error、crossing/nonfinite/support violation。`S_occ/N_valid`、`S_qr/N_valid` 和 `(S_occ+S_qr)/N_valid` 使用全人口原始分子与真实 valid 分母；conditional pinball 和 coverage 使用 `N_rain`，不得平均 batch loss。rainy 判定沿用 float32 target > float32(0.1)，在 float64 提升前判断。tau=(i-0.5)/32。AUROC/AP 继承 exact equal-score ties 与 non-interpolated grouped AP，禁止排名分箱近似。空组、无雨 conditional 指标或单类别 AUROC 记录 null 与原因，不造 0。

POD/FAR/CSI 保持 `THRESHOLD_NOT_FROZEN`。不得在查看 2025 结果后增删主要指标、挑阈值、校准或更换 epoch/checkpoint。

## 2024 诊断定义的原样继承

`docs/scientific_review/b0_phase_a/runs/run_20261002T005448_798068Z/case_selection_rules.json` 的完整解析对象在协议 `inherited_diagnostics` 中逐值一致，并绑定原文件与旧实现 SHA256。未改动旧 Scientific Review 代码或结果。新协议仅声明测试时期、授权/schema 和现有统计量在本测试人口上的应用。

- monthly：相同统计量应用于 3–9 月，空月明确无 eligible scenes。
- spatial：相同 per-cell valid/rain count、频率、概率、Brier、conditional pinball 与 proxy；conditional pinball 展示门槛仍为 30 个 rainy observation，仅影响展示；使用已冻结精确坐标、mask，禁止重造坐标、transpose/flip。
- reliability：原 0.1 固定 edges，边界右归、最后 bin 包括 1；仅诊断，不 recalibration。
- rain-rate：原 `(0.1,1]`、`(1,5]`、`(5,10]`、`(10,20]`、`(20,30]`、`(30,50]`、`(50,inf)`；descriptive only。
- quantile groups：原 low tau<0.2、middle 0.2≤tau≤0.8、high tau>0.8。
- exceedances：原 10/20/30/50 mm/h，descriptive only，extreme definition 未冻结。
- probability histogram：原 0.01 固定 edges；三类 top-10 case 与 tie 顺序全部沿用。
- DIAGNOSTIC_PROXY：p_rain×32 个 physical conditional quantile 的平均，报告 MAE/RMSE/Bias；不称为精确期望降水，遗漏 drizzle 分量。

## 实现与未来正式入口

入口 `scripts/test_b0_2025_final_v1.py`，模块 `src/yuntapr/evaluation/final_test_b0.py`，测试 `tests/final_test_b0/`。preflight 和 run 为独立 action。本轮只调用 preflight；run 缺少新的研究者 authorization 时，在读取 population、源文件及 FINAL 前拒绝。未来授权必须绑定协议、实现、FINAL、normalization 与完整候选 catalogue 的 SHA256；当前 release 不提供该授权。

FINAL 全文件 SHA、size、原 training provenance、模型 schema 在模型 state application 前核验；只应用 model state，未实例化/应用 optimizer，也未应用 RNG state。加载后的 model eval/requires_grad=false，在 inference_mode 下前向。历史 checkpoint payload 内 optimizer 字典的反序列化不等于创建或恢复 optimizer；该字典未用于推理。绑定既有训练依赖的冻结清单，并独立记录新增 evaluation 实现 hash，未重定义旧 training 清单。

runtime guards 禁止所有 torch optimizer 构造/step、backward、train(True)、正式 checkpoint 写入和任何其它正式 checkpoint 读取；preflight 禁止整个 H/IMERG raw root 的 open（含直接 netCDF4 backend open）。未来授权读取仍只允许原始只读 source 与受控英文 staging，copy size/SHA 校验并仅清理自建副本。

## 实际测试范围与证据

|实际 suite|tests|结果|
|---|---:|---|
|新增 ProtocolTests|14|PASS|
|新增 GuardTests|12|PASS|
|新增 AccumulatorTests|18|PASS|
|既有 tied AUROC/AP metric test|1|PASS|
|既有 unequal-partition full-population metric test|1|PASS|
|既有 Scientific Review inference-only units|8|PASS|
|新增 preflight artifact tests|6|PASS|
|合计|60|0 failure / 0 error / 0 skip|

即 50 项新增测试 + 10 项既有 inference-only regression。测试覆盖冻结 provenance、错误授权/日期/目录拒绝、部分 IMERG valid mask、缺失/重复/乱序人口、variable-size 分母、ties、无雨/单类/空 bin、完整诊断 count reconciliation、数值异常停止、readonly FINAL 与 baseline 身份。

既有包含真实 optimizer/backward 的整套 254 项 training/resume regression **本轮 NOT_RUN**，因为本轮明确禁止这些操作；未将其计为本轮 PASS。此前的训练任务测试记录保持不变。guard tests 中仅有被入口拒绝的操作尝试，没有实际 optimizer 创建、参数更新或 backward。

只读真实 FINAL CUDA smoke：synthetic 270 K 常量 B13、历史 2024 时间标签 normalization fixture、四个 synthetic target cells `[0, float32(0.1), 1, 20]`；schema 中 2025 日期仅为 synthetic 标签。valid=4/rain=2，**不是 2025 Final Test 结果**。FP32 raw quantiles、FP64 log/physical quantiles，CUDA 峰值 allocated=448,776,192 bytes、reserved=685,768,704 bytes；wall 0.583057 s 为 smoke 整段记录，非全人口性能预测。模型 state/FINAL 文件 hash 前后不变；no grad/no optimizer/no training。

日志：最新 run 的 `unit_test_results.txt`、`unit_test_summary.json`、`artifact_test_results.txt`、`preflight_manifest.json`、`final_identity_verification.json`、`synthetic_FINAL_forward_smoke.json`、`final_status.json`。raw source opened=0；3 次 Python raw-open probe 均被 guard 在 I/O 前拒绝。

## 保留历史与清理

两个早期 unit probe 错误均保留为失败记录：Windows tempfile ACL 和 optimizer rejection fixture 的 subclass signature 路径。工程修复仅限自建测试 fixture/guard。两个失败后遗留的自建临时目录在绝对路径/身份核验后清理成功，未触碰源数据、正式 checkpoint 或旧 cache。

独立先前成功 run `run_20261002T151525_945067Z`（57 项）保持历史原样；最终 guard 增强后的最新 run 为本报告的 60 项版本，未覆盖旧记录。1,711 个 baseline 文件原样。未安装、升级任何 Python/环境包。

## 最终状态与停止点

```text
FINAL_TEST_PROTOCOL_FROZEN=true
FINAL_TEST_RUNNER_READY=true
FINAL_TEST_2025_AUTHORIZED=false
FINAL_TEST_2025_EXECUTED=false
2025_PIXELS_READ=0
MODEL_PARAMETERS_UPDATED=false
OPTIMIZER_STEPS=0
BACKWARD_CALLS=0
```

`FINAL_TEST_RUNNER_READY=true` 仅表示本轮 fixture/schema/只读 synthetic preflight 闭环，不等于实际 2025 源数据可用性或全人口 reinference 已被验证。2025 catalogue、真实 eligible count、正式推理和测试结果均 `NOT_RUN / NOT_INSPECTED`，留待单独授权。完成报告、源码与日志的 GitHub main 提交后停止；不进入 B1–B8。
