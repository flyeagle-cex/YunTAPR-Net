# Multi-month data qualification

## Decision required

正式规则明确后，批准后续多月数据资格验证范围和缺口处置。

## Current evidence

2024-07 Himawari审计完成但有缺帧；其他研究月NOT_AUDITED。 证据：F:\pytorch\Research\outputs\stage0_continuous_engineering\run_20260928T041855_828904Z\CROSS_SOURCE\research_period_data_matrix.csv

## Options

按正式规则分月只读验证；根据真实缺口再提交决策；不预先认定丢失。

## Consequences

名义calendar槽位不是实际可训练样本。

## What is already frozen

本轮不启动全量处理或训练，不把NOT_AUDITED当PASS。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
