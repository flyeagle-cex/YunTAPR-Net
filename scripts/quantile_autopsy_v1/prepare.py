"""Read-only static and historical autopsy; no torch import or raw access."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quantile_autopsy_v1 import common as c
import argparse
import ast
import csv
import json
import math
import statistics
import subprocess
from datetime import datetime, timezone

def static_graph(run):
    files = sorted((c.ROOT / 'src/yuntapr').rglob('*.py')) + sorted((c.ROOT / 'scripts').glob('*.py'))
    uses = []
    for p in files:
        for number, line in enumerate(p.read_text(encoding='utf8').splitlines(), 1):
            if 'conditional_quantiles_physical' in line or 'threshold_censored_mean' in line:
                uses.append({'file': p.relative_to(c.ROOT).as_posix(), 'line': number,
                             'source': line.strip(), 'classification':
                             'INFERENCE_OUTPUT_REQUIRED' if '/models/' in p.as_posix() or '/metrics/' in p.as_posix()
                             else 'DIAGNOSTIC_REQUIRED'})
    monotonic = (c.ROOT / 'src/yuntapr/models/monotonic_quantiles.py').read_text(encoding='utf8')
    heads = (c.ROOT / 'src/yuntapr/models/probability_heads.py').read_text(encoding='utf8')
    loss = (c.ROOT / 'src/yuntapr/losses/total_loss.py').read_text(encoding='utf8')
    assert 'torch.isfinite(quantiles)' in monotonic or 'torch.isfinite(q)' in monotonic
    assert heads.index('qlog = monotonic_quantiles') < heads.index('torch.expm1(qlog)')
    attrs = {n.attr for n in ast.walk(ast.parse(loss)) if isinstance(n, ast.Attribute)}
    assert {'rain_logit', 'conditional_quantiles_log'} <= attrs
    assert 'conditional_quantiles_physical' not in attrs and 'threshold_censored_mean' not in attrs
    graph = {'baseline': c.BASELINE, 'production_code_modified': False,
        'qlog_finite_guard_before_physical_transform': True,
        'objective_inputs': {'TRAINING_OBJECTIVE_REQUIRED': ['rain_logit', 'conditional_quantiles_log',
            'IMERG target', 'IMERG validity mask', 'Yunnan evaluation mask']},
        'objective_has_physical_dependency': False,
        'execution_has_eager_physical_dependency': True,
        'edges': [['raw FP32 head', 'FP64 softplus increments'], ['FP64 softplus increments', 'FP64 monotonic qlog'],
                  ['FP64 monotonic qlog', 'finite/support/strict-order guards'],
                  ['finite/support/strict-order guards', 'FP64 expm1'],
                  ['FP64 expm1', 'physical finite guard'], ['physical finite guard', 'B0Output'],
                  ['B0Output.rain_logit', 'core focal loss'], ['B0Output.conditional_quantiles_log', 'core pinball loss'],
                  ['physical quantiles', 'threshold_censored_mean']],
        'physical_consumers': uses,
        'active_finalfit_path': 'execute_update -> forward_loss -> model -> heads -> expm1 -> physical guard -> core loss -> backward',
        'censored_mean_extra_risk': 'mean reduces physical quantiles; finite expm1 values alone do not guarantee a finite mean reduction',
        'limitations': 'Static dependency classification is not a proposal to change the frozen B0Output contract.'}
    c.write(run / 'quantile_execution_dependency_graph.json', graph)

def quantile(values, q):
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo = math.floor(pos); hi = math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

def summary(rows):
    result = {'updates': len(rows), 'clip_count': sum(r['clipped'] for r in rows)}
    result['clip_fraction'] = result['clip_count'] / len(rows)
    for key in ('loss', 'pre_clip_norm', 'post_clip_norm', 'LR', 'wall_seconds'):
        vals = [r[key] for r in rows]
        changes = [abs(b-a) for a,b in zip(vals, vals[1:])]
        segment = max(1, len(vals)//4)
        result[key] = {'min': min(vals), 'max': max(vals), 'mean': statistics.fmean(vals),
                       'p50': quantile(vals,.5), 'p99': quantile(vals,.99),
                       'first_quarter_mean': statistics.fmean(vals[:segment]),
                       'last_quarter_mean': statistics.fmean(vals[-segment:]),
                       'largest_adjacent_change': max(changes, default=0),
                       'all_finite': all(math.isfinite(x) for x in vals)}
    longest = current = 0
    for r in rows:
        current = current + 1 if r['clipped'] else 0
        longest = max(longest, current)
    result['longest_consecutive_clipped_updates'] = longest
    vals = [r['loss'] for r in rows]; mu = statistics.fmean(vals)
    denom = sum((x-mu)**2 for x in vals)
    result['loss_autocorrelation_descriptive'] = {str(lag):
        sum((a-mu)*(b-mu) for a,b in zip(vals[:-lag], vals[lag:]))/denom if denom and len(vals)>lag else None
        for lag in (1,2,10,50,100)}
    # Rankings are descriptive reviews, never exclusion or scientific thresholds.
    result['largest_loss_updates'] = [{'update': r['update'], 'loss': r['loss'], 'sample_ids': r['sample_ids']}
                                     for r in sorted(rows, key=lambda r:r['loss'], reverse=True)[:5]]
    result['largest_gradient_updates'] = [{'update': r['update'], 'pre_clip_norm': r['pre_clip_norm'],
                                           'sample_ids': r['sample_ids']}
                                         for r in sorted(rows, key=lambda r:r['pre_clip_norm'], reverse=True)[:5]]
    return result

def history(run):
    allrows = []; results = {}
    fields = ['epoch','update','sample_ids','loss','L_occ','L_qr','LR','pre_clip_norm','post_clip_norm',
              'clipped','rainy_count','actual_denominator','wall_seconds','utc']
    with (run/'pre_failure_training_dynamics.csv').open('x',encoding='utf8',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for epoch in range(1,6):
            rows = list(c.historical_updates(epoch))
            assert len(rows) == (10478 if epoch<5 else c.SUCCESS)
            assert [r['update'] for r in rows] == list(range((epoch-1)*10478+1, (epoch-1)*10478+len(rows)+1))
            for r in rows:
                vals = {k:r.get(k,'') for k in fields};vals['sample_ids']=json.dumps(r['sample_ids'],separators=(',',':'))
                writer.writerow(vals)
            results[f'epoch_{epoch}']=summary(rows);allrows.extend(rows)
            if epoch == 4: results['epoch_4_second_half']=summary(rows[len(rows)//2:])
    assert len(allrows)==c.FORMAL_STEPS
    results['missing_existing_per_update_fields']=['L_occ','L_qr','rainy_count']
    results['epoch_aggregates']=c.read(c.FAILED/'training_history.json')
    c.write(run/'pre_failure_training_dynamics_summary.json',results)
    lines=['# 失败前训练动态：只读分析','',
           '统计来自原始 TRAIN_UPDATE_AUDITED 事件；没有重新推算不存在的逐步 L_occ、L_qr 或 rainy count。空 CSV 字段表示未记录，不表示零。',
           '分位数、相邻跳变排序与 autocorrelation 都是描述性检查，不是科研异常阈值。未记录的 qlog/activation 不能由 loss 日志反推。','',
           '|区段|updates|loss mean|loss max|pre-clip max|clip fraction|连续 clip 最大长度|','|---|---:|---:|---:|---:|---:|---:|']
    for k,s in results.items():
        if not k.startswith('epoch_') or not isinstance(s,dict):continue
        lines.append(f"|{k}|{s['updates']}|{s['loss']['mean']:.9g}|{s['loss']['max']:.9g}|{s['pre_clip_norm']['max']:.9g}|{s['clip_fraction']:.6g}|{s['longest_consecutive_clipped_updates']}|")
    lines += ['', '完整逐步值、首末四分段均值、最大相邻跳变、滞后相关与单 batch 排名见 CSV 和 summary JSON。',
              '历史日志有限性只能证明成功更新时 loss/grad 有限，不能证明未记录的物理量未接近溢出。原因分类等待独立 replay。']
    (run/'pre_failure_training_dynamics_report.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path);args=p.parse_args()
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=c.ROOT,text=True).strip()
    if head!=c.BASELINE:raise ValueError('Exact task baseline required')
    run=args.run or c.ROOT/'docs/quantile_overflow_autopsy/runs'/('run_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ'))
    run.mkdir(parents=True,exist_ok=False)
    source=run/'researcher_autopsy_authorization.txt';source.write_bytes(c.ATTACHMENT.read_bytes())
    identity=c.read(c.FAILED/'last_checkpoint_identity.json')
    assert identity['sha256']==c.CHECKPOINT_SHA and identity['model_state_sha256']==c.MODEL_SHA
    assert identity['epoch']==4 and identity['global_update']==c.BOUNDARY
    c.write(run/'execution_scope.json',{'utc':c.now(),'operation':c.SCOPE,'model':'B0_MATCHED','AUTHORIZED':True,
        'baseline':head,'researcher_authorization':c.pin(source),'2025_raw_access':False,
        'formal_resume_authorized':False,'B1_authorized':False,'production_changes_allowed':False,
        'checkpoint_writes_allowed':False,'exact_successful_updates':c.SUCCESS,'exact_failure_batch':c.FAIL_BATCH,
        'checkpoint_identity':identity,'formal_optimizer_steps_immutable':c.FORMAL_STEPS})
    c.snapshot(run);static_graph(run);history(run)
    c.progress(run,{'status':'STATIC_AND_HISTORY_READY','run':str(run),'engineering_updates':0,
        'expected_successful_updates':c.SUCCESS,'failure_batch':c.FAIL_BATCH,'formal_optimizer_steps':c.FORMAL_STEPS,
        '2025_raw_access':0,'B1_phase_b_started':False})
    print(json.dumps({'run':str(run),'status':'STATIC_AND_HISTORY_READY'}))

if __name__=='__main__':main()
