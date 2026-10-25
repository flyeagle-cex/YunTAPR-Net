# B2正式启动说明

科学协议已在52060ce5dd349a59907db7c70f6996b9a6ebc361冻结：t−10分钟、sqrt(6)槽位映射、其余72张量相同、seed2029/E0/九轮/batch2/固定E9 LAST、959/963共同人口、B13原训练统计。

最小真实缓存检查已通过（evidence/b2_cached_real_check.json），新增原始读取和更新均为0。129来源、126逐轮摘要及未变化合成检查直接继承；不要重新运行旧检查命令。B2正式训练仍NOT_STARTED，仅待一次最终启动批准。

固定额度：4,320更新、477,571,641,012逻辑源字节、142,812源读取实例、最长21,600秒、零replay、工作空间至少24GiB。失败即停，保留原始数据与历史权重；2025持续冻结。

批准后，Codex将明确批准决定与本分支最终提交写入既有私有授权JSON（当前approved_by_researcher=False），随即执行下列唯一训练入口，不再重复科学选择或无变化审查。使用现有CUDA Python环境，先在启动环境设置PYTHONHASHSEED=2029；入口内部设置cuBLAS和线程参数。

```text
python tools/research_readiness/train_b2.py --execute --proposal docs/research_readiness/20261025/evidence/b2_proposal_v4.json --private-preparation docs/research_readiness/.local/b2_preparation_20261025_v4.json --researcher-approval docs/research_readiness/.local/B2_final_start_approval.json --output docs/research_readiness/.local/B2_s2029_formal_20261025_v1
```

当前False授权模板不能启动。最终运行时的资源/源SHA/掩膜/顺序检查是已有执行机制的一部分，不能以此另起重复预检查。训练结束后在当前工作分支提交并推送代码和脱敏实验收据，继续使用PR #1审查，不直接更新main。
