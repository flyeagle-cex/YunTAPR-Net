"""Real human instruction for one fresh restart; not a signing service."""
EXECUTION_SCOPE='SEED2027_FRESH_RESTART_386_PLUS_282312_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_9f4c33c6b6bc471b84527429307a4e4a",0]'
QUESTION='是否授权保留旧账本和失败证据，以原科学配置及资源上限从 seed2027 fresh 初态重新启动六组，额外增加 386 次更新尝试，将累计上限从 282,312 调整为 282,698 次；本次异常仍立即停止、不自动重试或恢复？'
ANSWER='授权重新启动及额外 386 次额度'

def execution_instruction() -> dict:
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=282698,new_attempt_cap=282312,prior_reserved=386,
        epochs_per_run=9,other_seeds=[],automatic_retry=False,
        automatic_failure_recovery=False,restart_kind='FRESH_NO_LAST_NO_WARM_START')

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('RESTART_INSTRUCTION_COVERS_SEED2027_ONLY')
