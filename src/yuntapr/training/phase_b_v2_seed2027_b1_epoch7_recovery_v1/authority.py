"""Actual independent human decision, bound to one LAST and unchanged total cap."""
EXECUTION_SCOPE='SEED2027_B1_EPOCH7_RECOVERY_164835_PLUS_198664_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_ae5eb6cd0e9c4446b24dabd1295d98c9",0]'
QUESTION='原 H: 数据盘当前未挂载。请先接回原盘；是否授权在盘身份检查通过后，保留旧账本及累计 164,835 次消耗，从 B1/E0 第 7 轮 LAST（SHA：bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a）恢复，重跑第 8 轮并完成既定 seed2027 剩余任务；额外增加 5,228 次额度，将累计上限从 358,271 调整为 363,499？保留已完成的 B0/E0，其他配置和资源上限不变，仅启动一次，异常停止且不自动重试。'
ANSWER='已接回原 H: 盘，授权恢复及额外 5,228 次额度'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=363499,new_attempt_cap=198664,prior_reserved=164835,
        additional_attempts=5228,source_epoch=7,source_update=36596,source_run='B1_V2__E0__s2027',
        last_sha256='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_B1_COMPLETE_EPOCH7_LAST_WITH_NONREFUNDABLE_EPOCH8_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_B1_EPOCH7_RECOVERY')
