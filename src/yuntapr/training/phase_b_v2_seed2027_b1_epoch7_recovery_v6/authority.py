"""Direct human zero-update repair/reissue instruction, with no new budget."""
EXECUTION_SCOPE='SEED2027_B1_EPOCH7_CONSOLE_FREE_RECOVERY_V6_NO_RETRY'
MESSAGE='授权零更新修复后重新发布并启动一次'
QUESTION=('三项祖先接口遗漏的最小修复候选已通过 6 项回归测试，本次失败新增预留和执行均为 0。'
    '是否授权保留 v4/v5 全部失败记录，完成独立修复发布并启动一次，仍从 seed2027 B1/E0 第 7 轮 LAST'
    '（SHA：bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a）恢复既定剩余训练？'
    '累计消耗 166,305、上限 364,969 均不变，不增加额度；其他科学配置和资源上限不变，异常停止且不自动重试。')

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',message=MESSAGE,question=QUESTION,
        seed=2027,scope=EXECUTION_SCOPE,maximum_attempts=364969,new_attempt_cap=198664,
        prior_reserved=166305,prior_returned_verified=166304,additional_attempts=0,inherited_replay_attempts=922,
        source_epoch=7,source_update=36596,source_run='B1_V2__E0__s2027',
        last_sha256='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a',
        failed_release_source_commit='0a8574792a22b7d545d5a981b44d95d689e0dfda',
        repair_review_commit='a32dc88fdbe128801d456f7f8a59a7f3256c5e4a',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='ZERO_UPDATE_INTERFACE_REPAIR_REISSUE_SAME_AUTHORIZED_EPOCH7_LAST')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:
        raise PermissionError('ONLY_DIRECTLY_APPROVED_SEED2027_ZERO_UPDATE_REISSUE_V6')
