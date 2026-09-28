# Normalization

## Decision required

批准Train-only范围内的方法、统计域、权重与版本规范。

## Current evidence

范围规则已定义；没有任何真实拟合统计。 证据：DATA_CONTRACT/b0_normalization_contract.md

## Options

经批准后采用标准化/稳健方法或物理固定尺度；当前无选择。

## Consequences

统计域和无效像元处理会改变模型输入分布。

## What is already frozen

Val/Test不参与拟合，Test不能反向调参；invalid排除且版本化。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
