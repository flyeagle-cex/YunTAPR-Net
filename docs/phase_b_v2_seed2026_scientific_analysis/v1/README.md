# 首批 seed2026 科学结果分析

来源基线：`dbccf220e8e88178388433e3d69e4e0e9682d652`。分析范围为六组固定第九轮结果；2024 仍是开发集，只有一个 seed。

- [中文科研报告 PDF](paper/SEED2026_SCIENTIFIC_RESULTS.pdf) / [可编辑 LaTeX](paper/main.tex)
- [精简科学结论](SCIENTIFIC_RESULTS.md)
- [剩余十二组资源、备份和安全暂停方案](REPLICATION_RESOURCE_PLAN.md)
- [六份最终权重 SHA 及备份搜索审计](CHECKPOINT_PAYLOAD_AUDIT.json)
- [54 轮收据与四个配对 Bootstrap 对比复核](RECOMPUTATION_AUDIT.json)
- [全精度结果表](tables/) / [10 幅 SVG、PDF、600 dpi PNG 图](figures/)
- [失败、修复及限制](FAILURES_AND_LIMITATIONS.md) / [最终状态](final_status.json)

本轮新 optimizer 更新、模型推理、原始观测内容读取均为 0。只对登记的六份最终权重做只读 SHA，不反序列化，不打开其他历史权重。用户授权跨盘寻找备份，但 2025、系统/缓存、重解析点、权限拒绝及离线/压缩备份仍有覆盖限制。

## 复现

从仓库根目录运行，使用独立分析环境，**不要改动训练环境**：

```powershell
python -m venv .analysis-venv
.\.analysis-venv\Scripts\python.exe -m pip install -r docs/phase_b_v2_seed2026_scientific_analysis/v1/requirements-analysis.txt
.\.analysis-venv\Scripts\python.exe docs/phase_b_v2_seed2026_scientific_analysis/v1/analysis/analyze.py
.\.analysis-venv\Scripts\python.exe docs/phase_b_v2_seed2026_scientific_analysis/v1/analysis/plot.py
.\.analysis-venv\Scripts\python.exe docs/phase_b_v2_seed2026_scientific_analysis/v1/analysis/report.py
.\.analysis-venv\Scripts\python.exe docs/phase_b_v2_seed2026_scientific_analysis/v1/analysis/test_analysis.py
```

`analyze.py` 的资源核验需要原设备登记的 `.local` 资源日志；这些没有公开上传。科学图表只读取公开的 `ANALYSIS_DATA.json`，故其他设备无需原始数据即可执行 `plot.py`、`report.py`。测试 02 的完整私有来源 SHA 核对与资源日志复核只能在受控原设备复现；不伪装成公开可重建全部私有证据。

LaTeX：进入 `paper/`，用 XeLaTeX 编译 `main.tex` 两遍；本机使用 Windows 中文字体，其他系统可按字体环境调整 `fontset`，不改变图表数值。最终 PDF 名为 `SEED2026_SCIENTIFIC_RESULTS.pdf`。

`verify_storage.py` 是用户明确授权后的只读审计程序，默认会读取六份最终权重及搜索备份；**绘图和统计复现不应调用它**。不存在训练入口。

## 科学定义来源

|定义|原项目函数|
|---|---|
|E0/E1 Focal、FP32 标签|`phase_b_v2_ablations/focal.py`、`validation.py`|
|未加权分位数分子|`phase_b_v2_ablations/pinball.py`|
|训练分母及单次 lambda|`phase_b_v2_ablations/total.py:candidate_loss`、`combine_numerators`|
|统一 FP64 Core 与 CP|`phase_b_v2_ablations/metrics.py:common_validation_sums`|
|精确分数并列、十箱、覆盖、七雨强层、尾部|`phase_b_v2_formal_integration_candidate/metrics.py:Evaluator` 及正式子类|
|原四个比较与配对抽样|`training/phase_b_v2_seed2026_operator_v3/analysis.py`|

具体源码 SHA、输入 SHA 和本轮输出 SHA 见 `manifest.json`。原正式源码、冻结数据、历史结果和已存在的未提交状态文件均不在本轮改动范围。
