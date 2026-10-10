# 研究者代码与科学审查清单（未批准）

这是待审事项，不是审批记录；没有签名、批准token或已批准勾选。当前研究者已委托候选开发与合成验证，以下真实独立审查仍需后续发生。

1. 阅读闭合config，确认E0/E1/E2科学假设与唯一因素；代码PASS不能替代效应界限、副作用容忍、多重比较和功效判断。
2. 解释Focal为何用logit及BCEWithLogits；gamma0为何仍是.5BCE；理解focusing梯度不是只对BCE求导。
3. 解释FP32雨标签提升前比较、独立bool masks、N_valid/N_rain两个分母、invalid参考临时清理与输出NaN拒绝。
4. 解释32tau、FP64 log域、mean32后sum、q支撑与严格序；区分私有signed-error手算内核和公开qlog接口。
5. 核对total仅乘一次lambda、unweighted分子保留、无雨q梯度连接、零有效明确停止；接受或提出独立候选修订，不能直接改冻结定义。
6. 阅读E0对原函数及两头梯度的实际兼容证据、固定容差、gradcheck远离折点的原因；理解合成PASS不证明真实模型或物理性能。
7. 阅读全部失败attempt，尤其旧CUDA timeout、缺yaml/pytest及任务私有依赖路径；正式GPU资源与正式依赖锁定仍未测量或批准。
8. 理解metadata fresh/恢复检查不能证明真实权重来源，也不能验证人类批准真实性；BlockedRunner无启动能力。
9. 独立决定Phase-A接受范围与B1历史恢复治理处置，保留NOT_GRANTED；本候选不自动追认。
10. 独立批准正式集成范围后，在新版本工程化runner，开展另获授权的真实数据/模型preflight；再批准阶段1/2具体执行scope、SHA、资源和恢复规则。

现有2024开发验证已经用于BEST与反复诊断，不是全新确认集；q32欠覆盖、上尾异常与CPB改善未稳健确认的限制继续保留。2025、FinalFit、新架构、校准器均不纳入本候选开发的正式执行范围。
