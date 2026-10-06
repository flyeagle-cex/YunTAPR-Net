# 云南内外 quantile extrema：冻结轨迹工程诊断

本次仅重放 B0-Matched Phase-B epoch 5 的 8625 次成功更新及第 8626 次失败 forward；正式训练没有恢复。

FP64 physical boundary = `709.782712893384`。所有风险结论只针对此次冻结轨迹，不是未来保证。

|统计（成功更新 + 失败 forward）|云南内|云南外|
|---|---:|---:|
|per-forward max median|3.1486181433143265|265.00673990034193|
|per-forward max p90|4.0317368110117258|383.52663907603846|
|per-forward max p99|11.455380140747625|532.98350151326588|
|per-forward max p99_9|68.607976159822655|637.99104603068326|
|per-forward max max|226.39241802550987|721.21749662161892|

INSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED = False
OUTSIDE_PHYSICAL_OVERFLOW_RISK_OBSERVED = True

这些结果不能把‘溢出仅在省外’扩大为‘所有高 upper-tail 值仅在省外’。完整两区 extrema、计数及按暴露量归一化的比例见 JSON。

|描述性阈值 mm/h|云南内 pixel-tau|云南外 pixel-tau|云南内 any-tau pixel|云南外 any-tau pixel|
|---:|---:|---:|---:|---:|
|10|3222438|82429107|1863534|11146005|
|50|40054|50331882|13581|2840036|
|100|24924|46348920|7169|2471160|
|500|11561|40242562|2596|2038097|
|1000|9025|38337645|1865|1923489|

阈值仅作 descriptive diagnostics；不改变训练、loss、QC、expm1 或模型。any-tau 每个 scene-pixel 只计一次；pixel-tau 对 tau 分别计数。

两个 cohort、32 个 tau 分布、全部 forward 的两区 argmax 身份分别保存在 JSON、CSV 和 aggregate journal；不保存完整 tensor。

正式 optimizer steps=50537，新增正式 steps=0；B1 Phase-B 未启动；2025 raw access=0；正式恢复未授权，等待研究者决定。
