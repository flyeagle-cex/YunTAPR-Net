# Formal time binding

## Decision required

批准 T/native window/analysis_time 的科学关系及单帧选择规则。

## Current evidence

9 个 Final 原生时间坐标等于 bounds 下界，日文件时刻相等；原 converter 缺失；smoke 仍 provisional。 证据：TIME/B0_FORMAL_TIME_SEMANTICS_EVIDENCE.md

## Options

T=start 并经证据补强后批准；T=center 需新增证据；从独立 native bounds 映射；证据不足保持 NOT_ESTABLISHED。

## Consequences

改变标签窗、可用卫星槽和问题定义；不能把时间一致性等同在线可用性。

## What is already frozen

obs_end<=analysis_time；不得未来帧；date_created 不作 availability。

## What must not be changed automatically

不自动选择候选，不改旧Stage-0/smoke证据，不修改原始数据；不新增科学阈值，不据Test调参，不运行正式训练。任何新科研约定需研究者显式批准并新建可追溯版本。
