# Phase-A Scientific Evidence Hardening & Phase-B Engineering Readiness

已完成本轮授权的聚合审计、诊断、候选数学实现、合成测试和下一阶段准备；正式科学审批待决。未新建项目或重复训练/推理。

- [科学证据审计](SCIENTIFIC_EVIDENCE_AUDIT.md)：128 个历史文件 SHA、22 分层、32 tau 和探索区间。
- [概率及上尾诊断](PROBABILITY_AND_TAIL_DIAGNOSTICS.md)：稀疏空箱、条件覆盖不足、强雨层损失。
- [事件候选](EVENT_CATALOGUE_CANDIDATES.md) / [地形候选](TERRAIN_STRATIFICATION_CANDIDATES.md)：仅数学/合成，不是正式目录。
- [历史恢复治理复核](RECOVERY_GOVERNANCE_GAP_REVIEW.md)。
- [Phase-B 入口准备](PHASE_B_ENTRY_READINESS_CHECKLIST.md) / [研究者待决](RESEARCHER_DECISION_REQUIRED.md)。
- [可编辑 LaTeX](PHASE_A_HARDENING_REVIEW.tex) / [PDF](PHASE_A_HARDENING_REVIEW.pdf)。
- [机器审计](tests/audit_attempt_002/audit_results.json)、[合成测试](tests/synthetic_attempt_002.xml)、[测试说明](tests/README.md)。
- [既有图表及身份](figures/README.md)、[manifest](manifest.json)、[状态](final_status.json)。

实现沿现有 src/yuntapr 布局新增 diagnostics/candidates.py、diagnostics/readiness.py；审计 scripts/phase_a_evidence_hardening/audit.py。代码无正式入口，所有候选参数显式传入。原论文/源代码/权重/数据/旧失败证据均保留。

复现只读审计：python scripts/phase_a_evidence_hardening/audit.py --output 一个尚不存在的目录。合成测试：设置 PYTHONPATH=src 后 python -m pytest -q tests/phase_a_evidence_hardening -p no:cacheprovider。完整历史排名 bootstrap 不重跑，原报告审查限制见审计文档。

实际当前通过记录是第二次审计 25 pass/0 fail，第二次 synthetic 48 pass/0 fail；首次失败分别保留，不混算为最终失败。冻结 mask、checkpoint 原始字节、原始数据、站点雷达、真实事件和地形目录均未访问/执行。本轮仅诊断与工程准备；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
