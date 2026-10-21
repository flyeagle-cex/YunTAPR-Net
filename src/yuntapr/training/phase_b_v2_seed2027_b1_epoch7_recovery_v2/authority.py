"""Exact direct human reply; no machine-generated grant or automatic recovery."""
EXECUTION_SCOPE='SEED2027_B1_EPOCH7_RECOVERY_165383_PLUS_198664_OS_TASK_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_b1552a3bb56f4b7792a75b411e1075df",0]'
QUESTION='是否授权将已通过 8 项测试的系统任务启动机制接入新恢复版本，保留旧账本及累计 165,383 次消耗，从 seed2027 B1/E0 第 7 轮 LAST（SHA：bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a）恢复，重跑第 8 轮并完成既定剩余训练；额外增加 548 次重放额度，将累计上限从 363,499 调整为 364,047？其他配置及资源上限不变，仅启动一次，异常停止且不自动重试。'
ANSWER='授权修复集成、恢复及额外548次额度'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=364047,new_attempt_cap=198664,prior_reserved=165383,
        additional_attempts=548,source_epoch=7,source_update=36596,source_run='B1_V2__E0__s2027',
        last_sha256='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_B1_COMPLETE_EPOCH7_LAST_WITH_NONREFUNDABLE_EPOCH8_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_B1_EPOCH7_OS_TASK_RECOVERY')
