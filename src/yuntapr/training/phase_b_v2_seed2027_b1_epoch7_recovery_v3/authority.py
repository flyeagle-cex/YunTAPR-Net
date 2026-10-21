"""New direct human restart after zero-update failure; prior cap unchanged."""
EXECUTION_SCOPE='SEED2027_B1_EPOCH7_ZERO_UPDATE_REISSUE_OS_TASK_V3_NO_RETRY'
MESSAGE='给我恢复然后继续进程，需要退出codex也能继续'
CLARIFICATION='是，仅脱离 Codex 运行'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_MESSAGE_IN_THIS_CONVERSATION',message=MESSAGE,
        clarification=CLARIFICATION,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=364047,new_attempt_cap=198664,prior_reserved=165383,
        additional_attempts=0,prior_548_replay_approval_preserved=True,
        source_epoch=7,source_update=36596,source_run='B1_V2__E0__s2027',
        last_sha256='bd2e12c38551e1356add16990a8edd17fa3c20a8594863005c90461b27b6931a',
        prior_failed_release_commit='c61b05f792ee6861a3b9f3b9bca5025e4e626758',
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        restart_kind='EXPLICIT_B1_COMPLETE_EPOCH7_LAST_WITH_NONREFUNDABLE_EPOCH8_REPLAY')

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_APPROVED_SEED2027_ZERO_UPDATE_REISSUE_OS_TASK')
