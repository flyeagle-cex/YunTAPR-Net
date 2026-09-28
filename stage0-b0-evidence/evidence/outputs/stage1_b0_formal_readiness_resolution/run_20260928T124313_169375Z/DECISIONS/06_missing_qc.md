# Missing and QC

## Decision required

批准partial-frame/invalid-input策略、target有效性与loss/metric分母。

## Current evidence

元数据解码、0!=missing等工程语义已确定；无新阈值。 证据：DATA_CONTRACT/b0_missing_qc_contract_candidate.md

## Options

显式mask接口或经批准的样本拒绝策略；新QC阈值须另有科学依据。

## Consequences

改变样本组成及有效监督面积；不可用隐式填零影响无雨频率。

## What is already frozen

0为有效无雨；missing不造值；原始数据只读；物理因果约束。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
