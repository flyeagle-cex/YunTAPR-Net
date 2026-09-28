# Stage-0 provenance decision update

仅新 run 增量记录；旧 decision log、DRY_RUN_FAILED 及所有旧报告不覆盖。

## FROZEN_ENGINEERING_EVIDENCE
既有主库 24388、thermo 12960 的审计表复用；12960 一对一对应、研究期 8820/8820 T/RH complete。20 cases/40 raw 定向复核时间、坐标通过，完整保护结果见 logs/integrity_verification.json。本轮所有“冻结”仅指本次记录证据，不代表科学批准。

## PROVISIONAL
同一 operational GFS family 的解释获官方文档加强；local provenance 仍 SUPPORTED_WITH_CAVEATS。主库 NCAR/AWS 是 provider/archive/retrieval 的不同角色；旧模板继承解释待代码确认。旧索引大小对应 8820/8820 不等于内容校验。

## NOT_YET_FROZEN
vintage_rule、延迟 X、研究者批准的 main+thermo 组合、共同 bbox 全部未冻结。历史 processed whitelist 的 frozen_utc 与旧 init+5h 字段不自动继承科研批准。

## RESEARCHER_DECISION_REQUIRED
来源链最低可接受证据；历史 operational 可用性定义；A/B/C/D 选择；辅助 history 的科学解释；Stage-0 closeout。Q1 NEEDS_MORE_PROVENANCE；Q2 NOT_ESTABLISHED。
