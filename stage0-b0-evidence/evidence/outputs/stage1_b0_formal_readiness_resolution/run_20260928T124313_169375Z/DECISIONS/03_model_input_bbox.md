# Model input bbox

## Decision required

在 SP01–SP04 或另行论证范围中选正式输入域，并批准坐标对齐。

## Current evidence

4 候选均在实际坐标共同范围并覆盖3430主评价中心。 证据：SPATIAL/B0_INPUT_DOMAIN_DECISION.md

## Options

polygon包络附近、0.25°/0.50°请求margin、全共同坐标范围，或提出新候选重新检查。

## Consequences

形状、计算量和边界输入支持不同；全范围不是自动默认。

## What is already frozen

主评价 mask 和真实目标网格不改变。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
