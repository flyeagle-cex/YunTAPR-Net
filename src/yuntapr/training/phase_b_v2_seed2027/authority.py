"""Narrow execution scope of the new direct human instruction.

The old publication decision is preserved below and in its immutable release.
Authority comes from the human reply, not from a JSON flag or this module.
This is no signing service and grants no other seed or failure recovery.
"""
PUBLICATION_DECISION='只发布执行版本，暂不启动'
PUBLICATION_SCOPE='SEED2027_EXECUTION_RELEASE_ONLY_NO_START'
ACTIVATION_DECISION='授权激活并启动 seed2027'
ACTIVATION_QUESTION_ITEM='["request_user_input_async","call_5019595a04f04337bb72541fce4505c7",0]'
ACTIVATION_QUESTION='是否现在撤销暂缓，授权我完成 seed2027 激活发布，并在原定数据与资源检查通过后直接启动固定六组训练（每组9轮、合计最多282,312次更新尝试），保持科学配置与资源上限不变，不含seed2028，异常时停止且不自动重试或恢复？'
EXECUTION_SCOPE='SEED2027_SIX_FRESH_RUNS_282312_ATTEMPTS_NO_FAILURE_RETRY'

def execution_instruction() -> dict:
    """Verbatim provenance of the actual human reply; not a fake signature."""
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',
        question_item_id=ACTIVATION_QUESTION_ITEM,question=ACTIVATION_QUESTION,
        answer=ACTIVATION_DECISION,seed=2027,scope=EXECUTION_SCOPE,
        maximum_attempts=282312,epochs_per_run=9,other_seeds=[],
        automatic_retry=False,automatic_failure_recovery=False)

def require_execution_authority(seed: int) -> None:
    if type(seed) is not int or seed!=2027:
        raise PermissionError('THIS_HUMAN_INSTRUCTION_DOES_NOT_COVER_OTHER_SEEDS')
    # No caller-supplied approved flag, environment variable or JSON grant.
    # verify_release additionally binds the fixed scope, code and dependencies.
