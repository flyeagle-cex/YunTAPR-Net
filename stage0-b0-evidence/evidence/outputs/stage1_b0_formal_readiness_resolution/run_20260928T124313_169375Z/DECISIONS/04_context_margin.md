# Weather-system context

## Decision required

确定天气系统上下文尺度及对称/非对称依据。

## Current evidence

CSV四向角度margin可算；科学充分性未证实。 证据：SPATIAL/b0_input_domain_candidates.csv

## Options

对称角度候选、按可用覆盖非对称候选、提出物理距离/天气过程准则后重审。

## Consequences

角度相同不等于物理距离相同，context增加成本且可能影响泛化。

## What is already frozen

云南全境主评价，不以context改变评价区域。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
