"""Actual independent human decision, bound to one LAST and unchanged total cap."""
EXECUTION_SCOPE='SEED2027_EPOCH2_MUTEX_RECOVERY_86415_PLUS_271856_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_c510a8d27c8146bebdf86a096d93c34a",0]'
QUESTION='是否授权将已通过人工测试的状态文件互斥修复接入新恢复版本，保留旧任务和全部 86,415 次消耗，仍从 B0/E0 第 2 轮 LAST（SHA：b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce）恢复，额外批准 632 次重放，将累计上限从 357,639 调整为 358,271；其他配置和资源上限不变，启动一次，异常停止且不自动重试？'
ANSWER='授权修复集成、恢复及额外632次额度'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=358271,new_attempt_cap=271856,prior_reserved=86415,
        additional_attempts=632,source_epoch=2,source_update=10456,
        last_sha256='b6062fe5b747924cc7cdf6cfce38f43f9f71fa9a1ad8ee10065cc987e875c3ce',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_COMPLETE_LAST_RECOVERY_WITH_NONREFUNDABLE_EPOCH3_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_EPOCH2_RECOVERY')
