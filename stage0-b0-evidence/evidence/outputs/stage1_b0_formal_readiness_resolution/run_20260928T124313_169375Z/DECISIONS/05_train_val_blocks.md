# Train / Validation design

## Decision required

选择完整块、边界buffer/事件隔离和Validation调参协议。

## Current evidence

3候选无重叠且仅2023/24；样本数是未扣QC/buffer上界。 证据：SPLIT/B0_TRAIN_VAL_DECISION.md

## Options

TV01跨年；TV02晚季；TV03双October；或批准完整天气过程方案。

## Consequences

各有年份/季节代表性风险；无事件目录不能声称事件隔离已完成。

## What is already frozen

Development2023/24 March–October；FinalTest2025不调参；不随机拆相邻样本。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
