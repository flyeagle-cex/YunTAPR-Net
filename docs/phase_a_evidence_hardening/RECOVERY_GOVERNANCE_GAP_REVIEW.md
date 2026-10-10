# 历史 B1 恢复治理偏差复核

原 [治理偏差报告](../v2_scientific_acceptance/runs/run_20261009T112710_013267Z/delivery_v2/RECOVERY_GOVERNANCE_DEVIATION.md)、9 个 source 文件和逻辑 chronology SHA 已核验；本轮没有新独立研究者 LAST-bound 恢复审批记录，状态仍为 NOT_EVIDENCED_IN_REGISTERED_RESUME_RECORDS。工程签名、JSON、远端发布或预检均不等同人类审批，本轮也不补签或追认。

冻结恢复规范要求“必须另有绑定具体 LAST SHA 和原授权祖先的研究者恢复批准。”实际恢复绑定使用原 Phase-A 授权和持续目标。绑定提交 f269272c821b49c5226ddf6d75eeb7108522cd34，LAST SHA=40f7f1204aba52815e1c8c2f3d2a5ce5d73da6b7b0297e1d79dc843cb3390649。上述身份有证据，缺失独立批准仍须研究者处置。

BEST Epoch 9/update 47,052 早于 LAST Epoch 14/update 73,192 和恢复 Epoch 15。BEST 参数未由受影响恢复段得到；后续完整训练历史、早停和无更好 checkpoint 的确认仍经历该恢复段。两个丢弃更新前缀 3,095/382 重放零差异；保留 88,876，全部尝试 92,353。技术可追溯性不能消除治理问题，也不能自行判定科研结果必然有效或无效。

研究者应独立决定偏差记录的处置、后续补救要求、BEST 科学审查是否可继续，以及正式验收。新增 synthetic 恢复检查器要求独立 LAST 批准、完成 epoch marker、原授权 SHA 和恢复状态核验，并永远返回 can_launch_formal_training=false；它不修补历史授权，也未接入正式 runner。

本轮仅诊断与工程准备；RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED=true；V2_PHASE_B_AUTHORIZED=false；2025_RAW_ACCESS=0；2025_PIXELS_READ=0。
