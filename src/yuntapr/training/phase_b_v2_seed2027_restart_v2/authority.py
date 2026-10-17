"""Bind the actual human reply; no program can extend this execution scope."""
EXECUTION_SCOPE='SEED2027_FRESH_RESTART_1127_PLUS_282312_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_938c2e4c47e647f5a837e672078b0a52",0]'
QUESTION='是否授权以原配置和资源上限从 seed2027 fresh 初态重启固定六组，保留旧账本及全部 1,127 次消耗，额外增加 741 次更新尝试，将累计上限调整为 283,439；仅启动一次，异常立即停止，不自动重试？'
ANSWER='授权重启及额外 741 次额度'

def execution_instruction() -> dict:
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=283439,new_attempt_cap=282312,prior_reserved=1127,
        additional_attempts=741,prior_authorized_cap=282698,epochs_per_run=9,other_seeds=[],
        automatic_retry=False,automatic_failure_recovery=False,restart_kind='FRESH_NO_LAST_NO_WARM_START')

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('RESTART_INSTRUCTION_COVERS_SEED2027_ONLY')
