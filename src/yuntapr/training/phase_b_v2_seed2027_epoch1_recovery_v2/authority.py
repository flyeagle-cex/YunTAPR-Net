"""Actual independent human decision, bound to one LAST and unchanged total cap."""
EXECUTION_SCOPE='SEED2027_EPOCH1_RECOVERY_V2_75327_PLUS_277084_NO_RETRY'
QUESTION_ITEM='["request_user_input_async","call_fd66931c3bf749569bb0c077efdbe873",0]'
QUESTION='元数据修复已通过 8 项测试，本次失败新增预留与执行均为 0。是否授权保留失败版本和账本，按已验证的规范化 SHA 对照重新发布并启动一次，仍从同一 B0/E0 第 1 轮 LAST 恢复，累计 75,327／上限 352,411 不变，异常停止且不自动再重试？'
ANSWER='授权零更新修复后重新发布启动'

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
