# QUANTILE OVERFLOW NUMERICAL AUTOPSY v1

本轮仅诊断。正式失败轨迹、科学合同、normalization 和历史 checkpoint 保持逐字节不变。
隔离重放从 epoch 4 / update 41912 开始，8625 次更新的 sample IDs / LR / loss / grad norms / clip / denominator 全部零容差匹配；第 8626 次 forward 重现原始物理溢出。

## 执行状态与独立补证

原始 replay 在数值复现完成后的收尾哈希巡检中失败：LAST-only checkpoint 读取 guard 拦截了对较早已完成 checkpoint 的流式 SHA 检查。原 replay_reconciliation.json 的 REPRODUCTION_FAILURE 与 progress.json 均保留原始 bytes/SHA，未改成 PASS。
独立 readonly_closeout 仅重新核验保存的日志、文件 bytes/SHA 与 staging 清理状态；没有再建立模型、反序列化 checkpoint、读取 raw source、执行 forward/backward/optimizer step。
独立补证确认数值复现，但原始执行的收尾失败仍然存在。最终 disposable model/optimizer state SHA 未捕获，明确列为 NOT_CAPTURED；不反推这些身份，也不重跑以补齐。

## 数学边界与失败位置

qlog_max = 721.21749662161892；dtype = torch.float64。
float64 log1p(max) = 709.78271289338397；margin = 11.434783728234947。
float32 log1p(max) = 88.722839052068352。冻结 FP64 路径没有改变。
最大位置 = {"batch_index": 0, "tau_index_zero_based": 31, "tau_ordinal": 32, "tau": 0.984375, "row": 99, "column": 3}；IMERG valid = True；Yunnan mask = False。
实际物理输出非有限值计数为 1；捕获的最大位置位于云南评价 mask 外。该结论限于本次失败 forward。
失败样本为 2023-08-16T04:30:00+00:00 和 2024-09-04T01:00:00+00:00；前者为最大值所属 batch index 0。输入物理温度/标准化范围、真实 CF 因果信息和 source SHA 见 failing_batch_identity.json 与 failing_tensor_diagnostics.json。

## 真实执行依赖

qlog 的有限性、support 和严格单调检查位于 expm1 前。core objective 使用 rain_logit 和 log-domain quantiles；物理量仍被 frozen forward 提前 materialize 并检查，因此本次异常发生在 actual core loss/backward 之前。
只读数学诊断另行计算了失败 batch 的 log-domain objective；它不绕过原始 expm1、不产生 B0Output、不参与 backward 或 optimizer。失败 batch 的梯度有限性没有被证明。

## 累计结构

|同一最大像元的 quantile|qlog|
|---|---:|
|tau ordinal 1|24.899046730707646|
|tau ordinal 8|166.86805794533964|
|tau ordinal 16|343.23622339397315|
|tau ordinal 24|531.72300773086147|
|tau ordinal 32|721.21749662161892|

first increment = 24.80373655090332；upper 31 increments sum = 696.31844989091167。
后续 31 个正增量占总增量 96.5604%。q1 在该像元已经升高，但 q32 继续累计到 721.2175；只有第 32 个 quantile 跨过本次 FP64 物理变换边界。该形态是显著的高 tau 累计放大，不能解释为所有 quantiles 仅增加了同一偏移。
逐步 per-tau max、median、increment 与 raw max 见 per_tau_growth_diagnostics.csv。不同 batch 的空间 maxima 不能当作同一输入的参数探针。

## 原因层级与证据限制

- A_SINGLE_BATCH_INPUT_SOURCE_ANOMALY: NOT_ESTABLISHED。Identity/QC checks do not rule out a physically valid but unusual meteorological scene. No alternative sources or retrospective exclusions were used.
- B_FEATURE_ACTIVATION_INSTABILITY: QUANTIFIED_CAUSALITY_NOT_ESTABLISHED。A changing-batch feature excursion is not proof of independent causal activation instability.
- C_QUANTILE_PARAMETER_DRIFT: NORM_EVOLUTION_QUANTIFIED_CAUSALITY_NOT_ESTABLISHED。Norm changes alone cannot identify harmful parameter drift; no frozen-point counterfactual intervention was executed.
- D_CUMULATIVE_POSITIVE_INCREMENT_OVERFLOW: DIRECT_MECHANISM_SUPPORTED。This establishes how finite raw heads accumulate to an overflowing physical transform, not an independently identified optimizer/input cause.
- E_OPTIMIZER_STATE_INSTABILITY: NO_NONFINITE_OPTIMIZER_STATE_OBSERVED_CAUSAL_INSTABILITY_NOT_ESTABLISHED。
- F_PHYSICAL_ONLY_OVERFLOW_WITH_FINITE_LOG_DOMAIN: SUPPORTED_FOR_OBSERVED_FORWARD_AND_READONLY_LOG_OBJECTIVE。Actual frozen core loss is not reached at the failed forward. No failed-batch backward was executed, so failed-batch gradient finiteness and future optimization stability are not established.

## 候选解决方案：未实施

A 可保持 log-domain objective 和梯度方程，但会改变 frozen eager output/failure contract；需要研究者明确批准。它不会自动解决 validation/inference 的物理溢出，也不能据此授权 resume。
B 改数值稳定性训练协议，C 改科学 quantile 参数化；二者需要重新冻结并重建 paired Phase-A / Phase-B 证据。逐项公平性、重跑要求与未来 Final Test 风险见 solution_options.json。

## 状态

```json
{
  "B0_MATCHED_PHASE_B_COMPLETED": false,
  "B1_PHASE_B_STARTED": false,
  "FORMAL_OPTIMIZER_STEPS": 50537,
  "FORMAL_OPTIMIZER_STEPS_ADDED": 0,
  "ENGINEERING_OPTIMIZER_STEPS": 8625,
  "2025_RAW_ACCESS": 0,
  "2025_PIXELS_READ": 0,
  "FORMAL_RESUME_AUTHORIZED": false,
  "RESEARCHER_DECISION_REQUIRED": true,
  "NUMERICAL_REPRODUCTION_VERIFIED": true,
  "ORIGINAL_REPLAY_CLOSEOUT_PASS": false,
  "READ_ONLY_EVIDENCE_CLOSURE_PASS": true,
  "FINAL_CLONE_STATE_HASH_CAPTURED": false,
  "POSTPROCESSING_OPTIMIZER_STEPS": 0,
  "2025_MODEL_INFERENCE_SCENES": 0
}
```

19 项前置隔离测试通过；CUDA 对照验证输出、loss、梯度、参数、optimizer 与 RNG 完全一致。另有 11 项只读补证测试通过，拒绝数值 mismatch、缺失更新、额外更新及正式计数增加；不导入 torch 或执行 optimizer。
历史 dynamics 报告保留原始缺项，未把未记录数值当作零；没有依据诊断结果选择新参数。
2025 保持封存，B1 不启动。研究者决策前停止；报告不授予任何修复或正式训练授权。

## 完整数值解释与证据

[逐项诊断解释、分段趋势与候选方案对照](DIAGNOSTIC_EVIDENCE_INTERPRETATION_v1.md)。完整原始精度见 JSON、两个 CSV 与 replay_observations.jsonl；来源与原始收尾失败的独立补证见 readonly_closeout/readonly_reconciliation.json。
