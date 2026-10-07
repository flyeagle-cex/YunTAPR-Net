"""Independent metadata-only review gate; never imports torch or opens raw data."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from quantile_head_v2 import common as c
import argparse,ast


def audit(run):
    run=run.resolve();gate=c.read(run/'test_gate_result.json')
    attempt=run/'test_attempts'/gate['attempt'];checks=[]
    for name in ('v2_numerical_tests.json','v1_regression_tests.json'):
        result=c.read(attempt/name)
        assert result['status']=='PASS' and result['counts']['run']==result['planned_tests']
        assert result['counts']['failed']==result['counts']['errors']==result['counts']['skipped']==0
    checks.append('all_planned_related_tests_executed_without_skip')
    n=c.read(attempt/'numerical_verification.json')
    for device,mode in (('cpu','DISABLED_FP32'),('cuda','BF16')):
        r=n['a_path_equivalence_'+device]
        assert r['comparison_tolerance']==0 and r['qlog_loss_gradients_optimizer_model_RNG_exact']
        assert r['autocast']==mode and len(r['paths'])==2
        assert r['paths'][0]==r['paths'][1]
    checks.append('A_path_outputs_gradients_optimizer_model_RNG_zero_tolerance')
    stress=n['v2_extreme_stress'];assert stress['all_required_cases_pass']
    assert len(stress['cases'])==2
    assert all(r['mixed_scene_pixels']==50000 and r['constant_cases']==81 and r['gradient_finite'] for r in stress['cases'])
    assert all(len(r['per_tau_qlog_range'])==32 for r in stress['cases'])
    checks.append('requested_extreme_ranges_both_raw_precisions_measured')
    assert n['native_fp32_counterexample']['adjacent_equal_count']==31
    assert n['fp64_finite_raw_counterexample']['guard_rejects']
    assert all(r['FP64_PHYSICAL_OVERFLOW_RISK'] and r['FP32_PHYSICAL_OVERFLOW_RISK'] for r in stress['cases'])
    checks.append('floating_point_limits_and_uncapped_physical_risk_not_hidden')
    cfg=c.read(ROOT/'config/science_v2/quantile_head_v2_candidate.json')
    for k in ('FORMAL_TRAINING_AUTHORIZED','V2_SCIENTIFIC_FREEZE_APPROVED','V2_PHASE_A_AUTHORIZED',
              'V2_PHASE_A_STARTED','V2_PHASE_B_AUTHORIZED','B0_MATCHED_PHASE_B_RESUME_AUTHORIZED','B1_PHASE_B_STARTED'):
        assert cfg['authorization'][k] is False
    assert cfg['authorization']['2025_RAW_ACCESS']==0 and cfg['authorization']['RESEARCHER_DECISION_REQUIRED'] is True
    checks.append('scientific_acceptance_and_formal_training_authority_remain_false')
    data=c.read(run/'candidate_data_reuse_audit.json')
    assert data['normalization_sha256']=='656fe7a929cbd8617b08427e8d1fa7029b26512253efb44faa576796137d4a31'
    assert data['training_scenes']==10455 and data['validation_scenes']==10501
    assert data['paired_target_identities_exact'] and not data['normalization_refit']
    assert data['RESEARCHER_APPROVAL_REQUIRED'] and not data['V2_DATA_REUSE_APPROVED']
    checks.append('Phase_A_train_only_scaler_and_matched_identities_candidate_only')
    counters=c.read(attempt/'governance_counters.json')
    assert all(counters[k]==0 for k in ('RAW_SOURCE_OPENS','2025_RAW_ACCESS','FORMAL_CHECKPOINT_STATE_APPLICATIONS_TO_V2','FORMAL_OPTIMIZER_STEPS_ADDED'))
    scope=c.read(attempt/'legacy_regression_scope.json')
    assert not scope['historical_state_applied_to_v2'] and not scope['old_source_files_modified']
    assert counters['FORMAL_CHECKPOINT_DESERIALIZATIONS']==len(scope['readonly_Phase_A_checkpoints'])
    checks.append('no_raw_source_or_v2_inheritance_readonly_historical_state_checks_reported')
    authority=c.read(run/'authority.json')
    assert authority['bound_commit']==c.BASELINE
    assert c.digest(Path(authority['task_copy']['path']))==authority['task_source']['sha256']
    assert authority['epsilon_confirmation']=='批准候选数值，仅用于工程验证'
    assert authority['floating_point_confirmation']=='批准区分数学与浮点保证'
    checks.append('original_task_and_two_researcher_confirmations_bound_to_baseline')
    for path in (ROOT/'docs/scientific_freeze_v2').glob('*.md'):
        content=path.read_text(encoding='utf8')
        assert not any(ord(ch)<32 and ch not in '\n\t\r' for ch in content)
        assert '人口' not in content
    packet=(ROOT/'docs/scientific_freeze_v2/YUNTAPR_QUANTILE_HEAD_V2_DECISION_PACKET.md').read_text(encoding='utf8')
    assert '\\frac' in packet and all('## '+str(i)+'.' in packet for i in range(1,17))
    assert 'v2 不保证永远没有物理溢出' in packet
    checks.append('review_packet_complete_math_rendering_and_sample_terminology')
    for p in (ROOT/'src/yuntapr/models/quantile_v2').glob('*.py'):
        tree=ast.parse(p.read_text(encoding='utf8'))
        calls={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
        assert not calls & {'clamp','clamp_min','clamp_max','sort','argsort','nan_to_num','nextafter'}
        if p.name in ('heads.py','models.py','parameterization.py'):
            assert 'expm1' not in calls
    checks.append('no_physical_transform_in_training_and_no_hidden_output_repairs')
    fail=c.read(run/'test_attempts/attempt_001/v2_numerical_tests.json')
    assert fail['status']=='FAIL' and 'DNNL does not support' in fail['console']
    old=c.read(run/'test_attempts/attempt_001/executed_code_identity.json')
    for leaf,source in (('verification.py.txt','scripts/quantile_head_v2/verification.py'),
                        ('test_v2.py.txt','tests/quantile_head_v2/test_v2.py')):
        assert c.digest(run/'test_attempts/attempt_001/executed_sources'/leaf)==old[source]
    checks.append('failed_CPU_BF16_attempt_and_original_source_bytes_preserved')
    manifest=c.read(run/'final_manifest.json')
    for ref in manifest['identities'].values():
        assert c.digest(Path(ref['path']))==ref['sha256']
    immutable=c.verify_history(run)
    assert immutable==manifest['historical_immutability']
    checks.append('all_final_code_config_packet_hashes_and_historical_bytes_verified')
    assert 'torch' not in sys.modules
    result={'utc':c.now(),'status':'PASS','checks_run':len(checks),'checks_passed':checks,
            'FORWARD_CALLS':0,'BACKWARD_CALLS':0,'OPTIMIZER_STEPS':0,'RAW_SOURCE_OPENS':0,
            '2025_RAW_ACCESS':0,
            'readonly_historical_Phase_A_checkpoint_deserializations':counters['FORMAL_CHECKPOINT_DESERIALIZATIONS'],
            'historical_checkpoint_state_applications_to_v2':0,'historical_immutability':immutable}
    c.write(run/'artifact_audit.json',result)
    print(__import__('json').dumps({'status':'PASS','artifact_checks':len(checks)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True,type=Path);args=parser.parse_args();audit(args.run)
