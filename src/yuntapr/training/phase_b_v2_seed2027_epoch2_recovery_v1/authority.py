"""Actual independent human decision, bound to one LAST and unchanged total cap."""
EXECUTION_SCOPE='SEED2027_EPOCH2_RECOVERY_85783_PLUS_271856_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_58c59391589e449e9fc2c62f3bef31fb",0]'
QUESTION='是否授权保留旧账本及全部 85,783 次消耗，从 B0/E0 第 2 轮 LAST（SHA：b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce）恢复，重跑第 3 轮并完成既定 seed2027 六组；额外批准 5,228 次重放，将累计上限从 352,411 调整为 357,639，其他配置和资源上限不变，异常停止且不自动重试？'
ANSWER='授权从第2轮 LAST 恢复及额外5228次额度'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=357639,new_attempt_cap=271856,prior_reserved=85783,
        additional_attempts=5228,source_epoch=2,source_update=10456,
        last_sha256='b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_COMPLETE_LAST_RECOVERY_WITH_NONREFUNDABLE_EPOCH3_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_EPOCH2_RECOVERY')
