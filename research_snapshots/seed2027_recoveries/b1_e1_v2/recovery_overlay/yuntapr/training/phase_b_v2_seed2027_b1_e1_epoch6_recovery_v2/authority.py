"""Exact direct human approval for the B1/E1 epoch6 LAST and 5,228 replay."""
EXECUTION_SCOPE='SEED2027_B1_E1_EPOCH6_ISOLATED_RECOVERY_V2_NO_RETRY'
QUESTION=('是否批准从 seed2027 B1/E1 第6轮 LAST（SHA：245619dbc66e60c677c2288660286a88748c9bf3121200610d3e7b13ebe4bc2b）恢复，'
    '重放未封存的第7轮，并仅为此将累计尝试上限从 370,197 增加 5,228 至 375,425？'
    '仅在资源余量达标后启动一次，科学配置和资源阈值不变，异常不自动重试；seed2028、FinalFit、2025访问仍不授权。'
    '需要这次决定，是因为上次批准仅绑定 B0/E1 第1轮 LAST 及当次重放，未涵盖这个新断点和新增额度。')
ANSWER='批准本次限定恢复与 5,228 次重放'
REISSUE='继续训练，后台只保留chrom，其他全部可以关闭'

def execution_instruction():
    return dict(origin='DIRECT_HUMAN_REPLY_IN_THIS_CONVERSATION',question=QUESTION,answer=ANSWER,
        transcription_not_digital_signature=True,seed=2027,scope=EXECUTION_SCOPE,
        zero_update_reissue_instruction=REISSUE,zero_update_failed_previous_launch=True,new_additional_attempt_budget=0,
        source_run='B1_V2__E1__s2027',source_epoch=6,source_update=31368,
        last_sha256='245619dbc66e60c677c2288660286a88748c9bf3121200610d3e7b13ebe4bc2b',
        prior_reserved=265637,prior_returned_verified=265636,additional_replay_attempts=5228,
        previous_cap=370197,maximum_attempts=375425,new_attempt_cap=109788,
        epochs_per_run=9,other_seeds=[],automatic_retry=False,automatic_failure_recovery=False,
        resource_limits_changed=False,seed2028_authorized=False,finalfit_authorized=False,
        test_2025_authorized=False,launch_only_after_sufficient_headroom=True)

def require_execution_authority(seed):
    if type(seed) is not int or seed!=2027:raise PermissionError('ONLY_DIRECTLY_APPROVED_SEED2027_B1_E1_EPOCH6_RECOVERY')
