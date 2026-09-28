# Formal architecture

## Decision required

批准正式U-Net/GPROF-IR-style配置，明确第一版概率头。

## Current evidence

small U-Net smoke PASS仅工程证据，无正式架构批准。 证据：MODEL/B0_FORMAL_ARCHITECTURE_DECISION.md

## Options

概率B0第一版（表示待选）；或明确批准确定性对照角色；层宽/深度/padding一并记录。

## Consequences

输出定义影响loss、概率评价与总体方案对照关系。

## What is already frozen

single B13, single time, target-grid aligned；不引入GFS/DEM等后续模块。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
