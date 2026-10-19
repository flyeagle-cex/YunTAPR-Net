"""Bind the actual human reply; no program can extend this execution scope."""
EXECUTION_SCOPE='SEED2027_FRESH_RESTART_70099_PLUS_282312_NO_RETRY'
QUESTION_ITEM='["direct_human_reply","restart_v4"]'
QUESTION='是否在关闭内存占用应用后，授权以原配置和资源上限从 seed2027 fresh 初态第四次重启固定六组，保留四次失败账本及全部 70,099 次消耗（核验 70,098，未核验 1），额外增加 70,099 次更新尝试，累计上限 352,411；已有 LAST 不采用；仅启动一次，异常立即停止，不自动重试？'
ANSWER='我已经关闭，重启吧'

def execution_instruction() -> dict:
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=352411,new_attempt_cap=282312,prior_reserved=70099,
        additional_attempts=70099,prior_authorized_cap=284399,epochs_per_run=9,other_seeds=[],
        automatic_retry=False,automatic_failure_recovery=False,restart_kind='FRESH_RESTART_EXISTING_LAST_NOT_ADOPTED')

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('RESTART_INSTRUCTION_COVERS_SEED2027_ONLY')
