"""Actual independent human decision, bound to one LAST and unchanged total cap."""
EXECUTION_SCOPE='SEED2027_EPOCH1_RECOVERY_75327_PLUS_277084_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_3246fe0ef37240efa9a3f30f11170862",0]'
QUESTION='是否授权修复日志校验后，从 seed2027 B0/E0 第1轮 LAST（SHA：e4c0162492ab10bfe3136fa8117c0f5e111078957fa35832e0a88cb5dc1ab0ff）恢复，从第2轮继续既定六组；保留累计75,327次消耗，上限仍为352,411，不增加额度，异常停止且不自动重试？'
ANSWER='授权从此 LAST 恢复，额度不变（推荐）'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question_item_id=QUESTION_ITEM,
        question=QUESTION,answer=ANSWER,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=352411,new_attempt_cap=277084,prior_reserved=75327,
        additional_attempts=0,source_epoch=1,source_update=5228,
        last_sha256='e4c0162492ab10bfe3136fa8117c0f5e111078957fa35832e0a88cb5dc1ab0ff',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_COMPLETE_LAST_RECOVERY_NO_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_EPOCH1_RECOVERY')
