"""Bind the actual human reply; no program can extend this execution scope."""
EXECUTION_SCOPE='SEED2027_FRESH_RESTART_2087_PLUS_282312_NO_RETRY'
QUESTION_ITEM='["ask_user_question","quota","stability","gitmode"]'
QUESTION='是否授权以原配置和资源上限从 seed2027 fresh 初态第三次重启固定六组，保留三次失败账本及全部 2,087 次消耗（核验 2,086，未核验 1），额外增加 2,087 次更新尝试，累计上限 284,399；仅已执行桌面 GPU 常驻应用清理，不修改驱动、分页文件、TDR 或科学配置；仅启动一次，异常立即停止，不自动重试？'
ANSWER='授权重新启动及额外 2,087 次额度，累计上限 284,399；仅已执行桌面 GPU 常驻应用清理'

def execution_instruction() -> dict:
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=284399,new_attempt_cap=282312,prior_reserved=2087,
        additional_attempts=2087,prior_authorized_cap=283439,epochs_per_run=9,other_seeds=[],
        automatic_retry=False,automatic_failure_recovery=False,restart_kind='FRESH_NO_LAST_NO_WARM_START')

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('RESTART_INSTRUCTION_COVERS_SEED2027_ONLY')
