"""Transcription of this chat's exact researcher-approved LAST/replay question."""
EXECUTION_SCOPE='SEED2027_B0_E1_EPOCH1_ISOLATED_RECOVERY_V1_NO_RETRY'
QUESTION=('是否批准从 seed2027 B0/E1 第1轮 LAST（SHA：9bdd53f2544885abc6284aeccae65c7e0d2234af199a83f7ced22f241f38a55e）恢复，'
    '重放未封存的第2轮，并仅为此将累计更新尝试上限从 364,969 增加 5,228 至 370,197？'
    '模型、科学配置、资源阈值均不变，仅在资源余量充足后启动一次，异常不自动重试；seed2028、FinalFit、2025访问仍不授权。'
    '需要这次明确决定，是因为你之前要求新增预算及具体 LAST 恢复必须另行授权。')
ANSWER='批准这次限定恢复与5,228次重放额度'


def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question=QUESTION,answer=ANSWER,
        transcription_not_digital_signature=True,seed=2027,scope=EXECUTION_SCOPE,
        source_run='B0_MATCHED_V2__E1__s2027',source_epoch=1,source_update=5228,
        last_sha256='9bdd53f2544885abc6284aeccae65c7e0d2234af199a83f7ced22f241f38a55e',
        prior_reserved=187217,prior_returned_verified=187216,additional_replay_attempts=5228,
        previous_cap=364969,maximum_attempts=370197,new_attempt_cap=182980,
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        resource_limits_changed=False,seed2028_authorized=False,finalfit_authorized=False,
        test_2025_authorized=False,launch_only_after_sufficient_headroom=True)


def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:
        raise PermissionError('ONLY_DIRECTLY_APPROVED_SEED2027_B0_E1_EPOCH1_RECOVERY')
