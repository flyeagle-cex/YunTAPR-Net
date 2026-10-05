"""Read-only synthesis after replay exits; proposals only, never resumes training."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
import argparse
import json
import math
import statistics

def describe(values):
    s=sorted(values);n=len(s);segment=max(1,n//4)
    return {'first':values[0],'last':values[-1],'min':s[0],'max':s[-1],
        'mean':statistics.fmean(values),'median':statistics.median(values),
        'p99':s[int(.99*(n-1))],'first_quarter_mean':statistics.fmean(values[:segment]),
        'last_quarter_mean':statistics.fmean(values[-segment:]),'all_finite':all(map(math.isfinite,values))}

def options():
    return {'implemented':False,'researcher_decision_required':True,'options':[
        {'option':'A','level':'ENGINEERING_PATH_DECOUPLING_PROPOSAL_ONLY',
         'proposal':'Separate log-domain training computation from eager physical materialization; retain expm1 and physical guards where physical outputs are required.',
         'scientific_semantics':'Objective/qlog/support/monotonicity can remain identical. The frozen eager B0Output and failure-contract semantics WOULD change; therefore this is not an automatically approved purely internal change.',
         'training_trajectory':'Can be identical before the previous overflow only after deterministic output/loss/gradient/state equivalence tests. There is no original successful trajectory beyond forward 50538 to compare.',
         'redo_Phase_A':'Not mathematically required by an exactly unchanged objective alone; researcher must review model-output contract, validation/selection path and physical diagnostics before accepting reuse of historical Phase-A evidence.',
         'redo_Phase_B_from_scratch':'Requires an explicit new execution decision. A clean new run from scratch is the conservative proposal; this audit grants no resume or restart authority.',
         'B0_vs_B1_fairness':'Use the same approved path and checks for both; never silently patch only one model.',
         '2025_Final_Test':'Still sealed. Physical overflow must have a predeclared validation/inference failure policy before any future evaluation; no outcome-guided changes.',
         'pros':['Preserves the established log-domain objective if equivalence is demonstrated','Avoids materializing unused physical quantities inside the optimization step'],
         'risks':['Does not bound physical quantiles or solve inference overflow','Removing an eager guard changes which updates can occur','threshold_censored_mean reduction can overflow even if individual quantiles are finite']},
        {'option':'B','level':'NUMERICAL_STABILITY_PROTOCOL_PROPOSAL_ONLY',
         'proposal':'Researcher-designed changes to optimization/stability controls; no specific LR, decay, clipping or regularization value selected in this audit.',
         'scientific_semantics':'Potentially unchanged model family, but the frozen training protocol changes; regularization would also change the objective.',
         'training_trajectory':'Expected to change; cannot be treated as continuation of the immutable trajectory.',
         'redo_Phase_A':'Yes for a revised paired development protocol and renewed epoch selection.',
         'redo_Phase_B_from_scratch':'Yes after revised Phase-A decisions and normalization/provenance verification.',
         'B0_vs_B1_fairness':'Apply a predeclared comparable protocol to both models and recompute paired evidence.',
         '2025_Final_Test':'No 2025 outcomes may guide this redesign; evaluation waits for renewed readiness.',
         'pros':['Can target activation/parameter/optimizer stability under development evidence'],
         'risks':['A stability setting may hide a mechanism rather than establish the cause','Requires renewed development and fair-comparison evidence']},
        {'option':'C','level':'SCIENTIFIC_PARAMETERIZATION_PROPOSAL_ONLY',
         'proposal':'Researcher-defined alternative positive monotonic quantile parameterization; no cap, distribution family or scientific parameter chosen here.',
         'scientific_semantics':'Yes: quantile representation/support/tail behavior or hypothesis class may change.',
         'training_trajectory':'Changes initialization, representation and gradients.',
         'redo_Phase_A':'Yes; requires independent scientific freeze and paired development.',
         'redo_Phase_B_from_scratch':'Yes; new model identities and protocol are required.',
         'B0_vs_B1_fairness':'Use an explicitly shared head family and matched information design; retain old baselines as history.',
         '2025_Final_Test':'Remain sealed until the redesigned model and protocol are frozen; no test-set adaptation.',
         'pros':['Can address physical tail behavior structurally'],
         'risks':['Introduces new scientific assumptions','An arbitrary bound can distort extreme precipitation','Requires full renewed scientific review']}]}

def finalize(run):
    run=run.resolve();reconciliation=c.read(run/'replay_reconciliation.json')
    closure=None
    if reconciliation['status']!='EXACT_FAILURE_REPRODUCED':
        closure_path=run/'readonly_closeout/readonly_reconciliation.json'
        if not closure_path.exists():raise PermissionError('Independent read-only numerical verification required')
        closure=c.read(closure_path)
        if (closure['status']!='EXACT_NUMERICAL_REPRODUCTION_VERIFIED_WITH_CLOSEOUT_ERROR'
            or not closure['numerical_reproduction_verified'] or closure['successful_updates']!=c.SUCCESS
            or closure['failed_forward_batch']!=c.FAIL_BATCH or closure['postprocessing_optimizer_steps']!=0):
            raise PermissionError('Do not synthesize a successful autopsy from incomplete numerical evidence')
        c.verify(closure['original_terminal_error_preserved']);c.verify(closure['original_terminal_progress_preserved'])
        for ref in c.read(run/'readonly_closeout/original_replay_evidence_manifest.json')['files']:c.verify(ref)
    if (run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.json').exists():raise FileExistsError('Immutable completed report')
    immutable=c.verify_snapshot(run);failure=c.read(run/'failing_tensor_diagnostics.json')
    metrics={};tau={t:{'max':[],'median':[]} for t in (1,8,16,24,32)}
    first=last=None;successful=0
    with (run/'replay_observations.jsonl').open(encoding='utf8') as f:
        for line in f:
            r=json.loads(line)
            if r['status']!='SUCCESS_EXACT_MATCH':continue
            successful+=1;first=first or r;last=r
            scalar={'feature_absmax':r['target_features']['absmax'],'raw_max':r['raw_head']['max'],
                    'qlog_max':r['qlog']['max'],'increment_max':r['increments']['max'],
                    'param_global':r['parameters_before_update']['global'],
                    'param_quantile_weight':r['parameters_before_update']['quantile_weight'],
                    'param_quantile_bias':r['parameters_before_update']['quantile_bias'],
                    'param_last_decoder':r['parameters_before_update']['last_decoder_block'],
                    'Adam_exp_avg':r['optimizer_before_update']['exp_avg'],
                    'Adam_exp_avg_sq':r['optimizer_before_update']['exp_avg_sq'],
                    'gradient_quantile':r['gradients_pre_clip']['quantile_head'],
                    'gradient_backbone':r['gradients_pre_clip']['backbone']}
            for k,v in scalar.items():metrics.setdefault(k,[]).append(v)
            for t in tau:
                tau[t]['max'].append(r['qlog_per_tau_max'][t-1]);tau[t]['median'].append(r['qlog_per_tau_median'][t-1])
    if successful!=c.SUCCESS:raise ValueError('Complete replay update collection required')
    descriptions={k:describe(v) for k,v in metrics.items()}
    failing_obs=failure['observation'];growth={str(t):{'successful_max':describe(v['max']),
        'successful_median':describe(v['median']),
        'failed_batch_global_max':failing_obs['qlog_per_tau_max'][t-1],
        'failed_max_pixel_qlog':failure['qlog_32_at_pixel'][t-1]} for t,v in tau.items()}
    pixel=failure['qlog_32_at_pixel'];increments=failure['increments_32_at_pixel']
    reconstructed=math.log1p(.1)+sum(increments[:failure['location']['tau_ordinal']])
    decomposition={'base':math.log1p(.1),'qlog_at_tau_1':pixel[0],'qlog_at_tau_8':pixel[7],
        'qlog_at_tau_16':pixel[15],'qlog_at_tau_24':pixel[23],'qlog_at_tau_32':pixel[31],
        'upper_31_increment_sum':sum(increments[1:]),'first_increment':increments[0],
        'reconstructed_max_pixel_qlog':reconstructed,'actual_max_qlog':failure['qlog_max'],
        'reconstruction_difference':reconstructed-failure['qlog_max'],
        'important_limit':'Per-update spatial maxima use changing batches. They are not fixed-input probes and cannot alone separate weight drift from input dependence.'}
    decomposition['first_overflowing_tau_ordinal_at_pixel']=next(i+1 for i,v in enumerate(pixel) if v>math.log1p(sys.float_info.max))
    decomposition['upper_31_fraction_of_total_increment_sum']=sum(increments[1:])/sum(increments)
    decomposition['pattern']='At the failure pixel q1 is elevated, with strong additional positive cumulative growth through q32. Only q32 crosses the FP64 physical boundary; this is not an equal additive shift of all quantiles.'
    classifications={
        'A_SINGLE_BATCH_INPUT_SOURCE_ANOMALY':{'status':'NOT_ESTABLISHED',
            'evidence':'Each actual staged input passed frozen size/SHA/CF causality/full-valid checks; failing input statistics and SHA identities are preserved.',
            'limit':'Identity/QC checks do not rule out a physically valid but unusual meteorological scene. No alternative sources or retrospective exclusions were used.'},
        'B_FEATURE_ACTIVATION_INSTABILITY':{'status':'QUANTIFIED_CAUSALITY_NOT_ESTABLISHED',
            'failure_absmax':failing_obs['target_features']['absmax'],'successful_distribution':descriptions['feature_absmax'],
            'limit':'A changing-batch feature excursion is not proof of independent causal activation instability.'},
        'C_QUANTILE_PARAMETER_DRIFT':{'status':'NORM_EVOLUTION_QUANTIFIED_CAUSALITY_NOT_ESTABLISHED',
            'weight':descriptions['param_quantile_weight'],'bias':descriptions['param_quantile_bias'],
            'limit':'Norm changes alone cannot identify harmful parameter drift; no frozen-point counterfactual intervention was executed.'},
        'D_CUMULATIVE_POSITIVE_INCREMENT_OVERFLOW':{'status':'DIRECT_MECHANISM_SUPPORTED',
            'evidence':decomposition,'limit':'This establishes how finite raw heads accumulate to an overflowing physical transform, not an independently identified optimizer/input cause.'},
        'E_OPTIMIZER_STATE_INSTABILITY':{'status':'NO_NONFINITE_OPTIMIZER_STATE_OBSERVED_CAUSAL_INSTABILITY_NOT_ESTABLISHED',
            'exp_avg':descriptions['Adam_exp_avg'],'exp_avg_sq':descriptions['Adam_exp_avg_sq'],
            'evidence':'Frozen update verifies every parameter and moment finite after all 8625 successful replay updates; failed forward performs no backward or optimizer step.'},
        'F_PHYSICAL_ONLY_OVERFLOW_WITH_FINITE_LOG_DOMAIN':{'status':'SUPPORTED_FOR_OBSERVED_FORWARD_AND_READONLY_LOG_OBJECTIVE',
            'qlog_finite':failure['qlog_all_finite'],'raw_finite':failure['raw_all_finite'],
            'physical_nonfinite_count':failure['qphysical_nonfinite_count'],
            'log_objective_diagnostic':failure['read_only_log_objective_diagnostic'],
            'limit':'Actual frozen core loss is not reached at the failed forward. No failed-batch backward was executed, so failed-batch gradient finiteness and future optimization stability are not established.'}}
    status={'B0_MATCHED_PHASE_B_COMPLETED':False,'B1_PHASE_B_STARTED':False,
        'FORMAL_OPTIMIZER_STEPS':c.FORMAL_STEPS,'FORMAL_OPTIMIZER_STEPS_ADDED':0,
        'ENGINEERING_OPTIMIZER_STEPS':c.SUCCESS,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
        'FORMAL_RESUME_AUTHORIZED':False,'RESEARCHER_DECISION_REQUIRED':True}
    status.update({'NUMERICAL_REPRODUCTION_VERIFIED':True,'ORIGINAL_REPLAY_CLOSEOUT_PASS':closure is None,
        'READ_ONLY_EVIDENCE_CLOSURE_PASS':True,'FINAL_CLONE_STATE_HASH_CAPTURED':closure is None,
        'POSTPROCESSING_OPTIMIZER_STEPS':0,'2025_MODEL_INFERENCE_SCENES':0})
    report={'utc':c.now(),'baseline':c.BASELINE,'scope':c.SCOPE,'status':status,
        'replay_reconciliation':reconciliation,'immutable_history':immutable,
        'readonly_closeout':closure,
        'overflow':failure['overflow_boundaries'],'failing_location':failure['location'],
        'maximum_pixel_Yunnan_mask':failure['Yunnan_mask'],'maximum_pixel_IMERG_valid':failure['IMERG_valid'],
        'mechanism_classification':classifications,'cumulative_decomposition':decomposition,
        'growth_by_tau':growth,'successful_update_distributions':descriptions,
        'growth_interpretation':decomposition['pattern']+' Changing-batch growth cannot establish a unique upstream cause or a new scientific instability threshold.',
        'solutions':options(),'fixes_implemented':False,
        'limitations':['Scalar norms and changing input batches do not establish unique causality.',
                       'Here the actual physical nonfinite count is exactly one and the captured maximum is outside Yunnan; no inference is made about unobserved batches.',
                       'Original post-replay closeout failed. Its status is immutable, and final disposable model/optimizer hashes were not captured; they are not reconstructed or inferred.',
                       'No hypothetical repaired run, future gradient or 2025 outcome was inspected.']}
    c.write(run/'solution_options.json',report['solutions'])
    c.write(run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.json',report)
    lines=['# QUANTILE OVERFLOW NUMERICAL AUTOPSY v1','',
        '本轮仅诊断。正式失败轨迹、科学合同、normalization 和历史 checkpoint 保持逐字节不变。',
        f'隔离重放从 epoch 4 / update {c.BOUNDARY} 开始，{c.SUCCESS} 次更新的 sample IDs / LR / loss / grad norms / clip / denominator 全部零容差匹配；第 {c.FAIL_BATCH} 次 forward 重现原始物理溢出。','',
        '## 执行状态与独立补证','',
        '原始 replay 在数值复现完成后的收尾哈希巡检中失败：LAST-only checkpoint 读取 guard 拦截了对较早已完成 checkpoint 的流式 SHA 检查。原 replay_reconciliation.json 的 REPRODUCTION_FAILURE 与 progress.json 均保留原始 bytes/SHA，未改成 PASS。',
        '独立 readonly_closeout 仅重新核验保存的日志、文件 bytes/SHA 与 staging 清理状态；没有再建立模型、反序列化 checkpoint、读取 raw source、执行 forward/backward/optimizer step。',
        '独立补证确认数值复现，但原始执行的收尾失败仍然存在。最终 disposable model/optimizer state SHA 未捕获，明确列为 NOT_CAPTURED；不反推这些身份，也不重跑以补齐。','',
        '## 数学边界与失败位置','',f"qlog_max = {failure['qlog_max']:.17g}；dtype = {failure['qlog_dtype']}。",
        f"float64 log1p(max) = {failure['overflow_boundaries']['float64']['log1p_finfo_max']:.17g}；margin = {failure['overflow_boundaries']['float64']['overflow_margin']:.17g}。",
        f"float32 log1p(max) = {failure['overflow_boundaries']['float32']['log1p_finfo_max']:.17g}。冻结 FP64 路径没有改变。",
        f"最大位置 = {json.dumps(failure['location'])}；IMERG valid = {failure['IMERG_valid']}；Yunnan mask = {failure['Yunnan_mask']}。",
        f"实际物理输出非有限值计数为 {failure['qphysical_nonfinite_count']}；捕获的最大位置位于云南评价 mask 外。该结论限于本次失败 forward。",
        f"失败样本为 {failure['sample_identities'][0]['sample_id']} 和 {failure['sample_identities'][1]['sample_id']}；前者为最大值所属 batch index 0。输入物理温度/标准化范围、真实 CF 因果信息和 source SHA 见 failing_batch_identity.json 与 failing_tensor_diagnostics.json。",'',
        '## 真实执行依赖','',
        'qlog 的有限性、support 和严格单调检查位于 expm1 前。core objective 使用 rain_logit 和 log-domain quantiles；物理量仍被 frozen forward 提前 materialize 并检查，因此本次异常发生在 actual core loss/backward 之前。',
        '只读数学诊断另行计算了失败 batch 的 log-domain objective；它不绕过原始 expm1、不产生 B0Output、不参与 backward 或 optimizer。失败 batch 的梯度有限性没有被证明。','',
        '## 累计结构','',
        '|同一最大像元的 quantile|qlog|','|---|---:|']
    lines += [f'|tau ordinal {t}|{pixel[t-1]:.17g}|' for t in (1,8,16,24,32)]
    lines += ['',f"first increment = {increments[0]:.17g}；upper 31 increments sum = {sum(increments[1:]):.17g}。",
        f"后续 31 个正增量占总增量 {decomposition['upper_31_fraction_of_total_increment_sum']:.4%}。q1 在该像元已经升高，但 q32 继续累计到 721.2175；只有第 32 个 quantile 跨过本次 FP64 物理变换边界。该形态是显著的高 tau 累计放大，不能解释为所有 quantiles 仅增加了同一偏移。",
        '逐步 per-tau max、median、increment 与 raw max 见 per_tau_growth_diagnostics.csv。不同 batch 的空间 maxima 不能当作同一输入的参数探针。','',
        '## 原因层级与证据限制','']
    for key,value in classifications.items():lines += [f"- {key}: {value['status']}。{value.get('limit','')}"]
    lines += ['', '## 候选解决方案：未实施','',
        'A 可保持 log-domain objective 和梯度方程，但会改变 frozen eager output/failure contract；需要研究者明确批准。它不会自动解决 validation/inference 的物理溢出，也不能据此授权 resume。',
        'B 改数值稳定性训练协议，C 改科学 quantile 参数化；二者需要重新冻结并重建 paired Phase-A / Phase-B 证据。逐项公平性、重跑要求与未来 Final Test 风险见 solution_options.json。','',
        '## 状态','', '```json',json.dumps(status,indent=2),'```','',
        f"{c.read(run/'observer_test_result.json')['counts']['passed']} 项前置隔离测试通过；CUDA 对照验证输出、loss、梯度、参数、optimizer 与 RNG 完全一致。另有 11 项只读补证测试通过，拒绝数值 mismatch、缺失更新、额外更新及正式计数增加；不导入 torch 或执行 optimizer。",
        '历史 dynamics 报告保留原始缺项，未把未记录数值当作零；没有依据诊断结果选择新参数。',
        '2025 保持封存，B1 不启动。研究者决策前停止；报告不授予任何修复或正式训练授权。']
    (run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    c.write(run/'immutability_after.json',immutable)
    original_progress=c.read(run/'progress.json')
    c.write(run/'audit_progress.json',{**original_progress,'utc':c.now(),
        'status':'AUTOPSY_COMPLETE_WITH_CLOSEOUT_ERROR','original_execution_status':original_progress['status'],
        'error':'原 replay 收尾 SHA 巡检受 LAST-only guard 拦截；原失败记录保留，独立只读补证已通过。',
        'numerical_reproduction_verified':True,'original_closeout_pass':False,
        'read_only_closure_pass':True,'formal_resume_authorized':False,
        'report_path':str(run/'QUANTILE_OVERFLOW_NUMERICAL_AUTOPSY_v1.md')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();finalize(args.run)
