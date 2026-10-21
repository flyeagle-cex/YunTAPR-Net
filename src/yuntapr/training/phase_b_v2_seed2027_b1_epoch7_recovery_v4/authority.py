"""Direct human LAST-bound recovery grant; no inference from test success."""
EXECUTION_SCOPE='SEED2027_B1_EPOCH7_CONSOLE_FREE_RECOVERY_V4_NO_RETRY'
MESSAGE='授权修复集成、恢复及额外922次额度'
QUESTION=('是否授权将已通过 5 项人工测试的无控制台启动修复接入独立恢复版本，保留旧账本及累计 166,305 次消耗，'
    '从 seed2027 B1/E0 第 7 轮 LAST（SHA：bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a）恢复，'
    '重跑第 8 轮并完成既定剩余训练；额外批准 922 次重放，将累计上限从 364,047 调整为 364,969？'
    '其他科学配置和资源上限不变，仅启动一次，异常停止且不自动重试，不含 seed2028。')

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',message=MESSAGE,question=QUESTION,
        seed=2027,scope=EXECUTION_SCOPE,maximum_attempts=364969,new_attempt_cap=198664,
        prior_reserved=166305,prior_returned_verified=166304,additional_attempts=922,
        source_epoch=7,source_update=36596,source_run='B1_V2__E0__s2027',
        last_sha256='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a',
        stopped_source_commit='cbf90bec71cfb4e1f2ac41ca0051fb9e9e6e198e',
        prior_running_source_commit='3c9953f44fa3e000cc8e49f3a99e132c72e6efe2',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_B1_COMPLETE_EPOCH7_LAST_WITH_NONREFUNDABLE_EPOCH8_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:
        raise PermissionError('ONLY_DIRECTLY_APPROVED_SEED2027_EPOCH7_RECOVERY_V4')
