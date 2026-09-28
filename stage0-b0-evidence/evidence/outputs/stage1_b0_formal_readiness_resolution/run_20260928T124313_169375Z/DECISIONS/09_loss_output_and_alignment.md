# Loss/output and spatial alignment

## Decision required

批准正式loss/output、native-target对齐、missing传播、指标、概率校准和重复实验方案。

## Current evidence

smoke对齐与单输出仅工程候选，无正式批准。 证据：MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md

## Options

随架构科学目标联合选择，不指定默认loss/插值/阈值。

## Consequences

决定学习目标、网格支持和可比性，不能据2025挑选。

## What is already frozen

目标真坐标与主mask不改变；Test不调参；不以未来信息输入。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
