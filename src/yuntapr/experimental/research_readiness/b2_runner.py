"""One future B2 run, requiring a researcher-reviewed immutable proposal.

This module grants no authorization. The delivered approval template is false.
The formal real-data path remains NOT_VERIFIED until an approved run is made.
"""
from pathlib import Path
import gc
import json
import os
import random
import sqlite3
import time
import numpy as np
import torch
from yuntapr.training.phase_a_protocol import state_digest, lr_for_update
from yuntapr.experimental.phase_b_v2_runner_candidate.optimizer import new_adamw, clip_and_check, check_finite
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.core_innovation.stage4.data import PopulationPlan, BatchReader, read, sha
from yuntapr.experimental.core_innovation.stage4.engine import resources, epoch_order, cpu_tree, write
from yuntapr.experimental.core_innovation.stage4.evaluation import Evaluation
from yuntapr.experimental.core_innovation.stage4.launch import PassReader
from .b2 import STEM_RULE, fresh_b2, forward_b2
from .tail_diagnostics import TailDiagnostics


def validate_authorization(approval, proposal, *, current_commit):
    b = proposal['budget']
    required = dict(approved_by_researcher=True, model='B2', seed=2029,
                    proposal_sha256=proposal['proposal_sha256'], code_commit=current_commit,
                    optimizer_update_cap=4320, source_read_byte_cap=b['logical_source_bytes'],
                    source_read_file_cap=b['logical_source_read_instances'], replay_allowance=0,
                    approved_stem_rule=STEM_RULE)
    if any(approval.get(k) != v for k, v in required.items()):
        raise PermissionError('No exact researcher approval for this B2 proposal/code/budget')
    if (not isinstance(approval.get('decision_id'), str) or not approval['decision_id'].strip()
            or type(approval.get('max_wall_seconds')) != int or not 0 < approval['max_wall_seconds'] <= 43200):
        raise PermissionError('Explicit researcher decision ID and reviewed wall-time cap <=12h required')


class B2Ledger:
    def __init__(self, path, identity):
        if Path(path).exists():
            raise PermissionError('No overwrite/resume/retry')
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE identity(value TEXT)')
        self.db.execute('INSERT INTO identity VALUES (?)', (json.dumps(identity, sort_keys=True),))
        self.db.execute('CREATE TABLE updates(u INTEGER PRIMARY KEY,state TEXT)')
        self.db.commit()

    def reserve(self, u):
        with self.db:
            n, good = self.db.execute("SELECT COUNT(*),COALESCE(SUM(state='RETURNED'),0) FROM updates").fetchone()
            if type(u) != int or u != n+1 or n != good or u > 4320:
                raise PermissionError('B2 cap/order/uncertain-update boundary')
            self.db.execute("INSERT INTO updates VALUES (?,'INTENT')", (u,))

    def returned(self, u):
        with self.db:
            c = self.db.execute("UPDATE updates SET state='RETURNED' WHERE u=? AND state='INTENT'", (u,))
            if c.rowcount != 1:
                raise RuntimeError('Missing B2 durable update intent')


def difference(b3, b2):
    def metric(summary, key):
        # Raw historical receipts store the full coverage vector; the public
        # extract additionally names its final entry q32_coverage.
        if key == 'q32_coverage' and key not in summary:
            return summary['coverage'][-1]
        return summary[key]
    for key in ('source_identity', 'population_ids_sha256', 'partition_sha256'):
        if b3[key] != b2[key]:
            raise ValueError('B2/B3 evaluation identity differs')
    if b3['groups'].keys() != b2['groups'].keys():
        raise ValueError('Different evaluation groups')
    groups = {}
    for name, a in b3['groups'].items():
        b = b2['groups'][name]
        if a['ids_sha'] != b['ids_sha'] or a['summary']['n_valid'] != b['summary']['n_valid']:
            raise ValueError('Unpaired group')
        groups[name] = {k: metric(b['summary'], k)-metric(a['summary'], k) if metric(a['summary'], k) is not None and metric(b['summary'], k) is not None else None
                        for k in ('brier', 'auroc', 'average_precision', 'conditional_pinball', 'q32_coverage', 'q32_signed_bias')}
    return dict(direction='B2_MINUS_B3', descriptive_only=True, groups=groups,
                tail_coverage_comparison='B3_REAL_RAIN_STRATUM_COVERED_COUNTS_NOT_AVAILABLE')


def execute(proposal_path, private_path, approval_path, output, *, root, current_commit):
    proposal, private, approval = map(read, (proposal_path, private_path, approval_path))
    body = dict(proposal)
    expected = body.pop('proposal_sha256')
    if digest(body) != expected or private['proposal_sha256'] != expected:
        raise ValueError('Proposal identity differs')
    validate_authorization(approval, proposal, current_commit=current_commit)
    for name, h in proposal['code_sha256'].items():
        if sha(root/name) != h:
            raise ValueError('Reviewed code changed: '+name)
    output = Path(output)
    if not output.resolve().is_relative_to(root/'docs/research_readiness/.local') or output.exists():
        raise PermissionError('Fresh ignored experiment output required')
    p = private['prepared']
    inputs = p['private_inputs']
    plan = PopulationPlan(inputs['stage3_run'], inputs['request'], root=root)
    if plan.identity != proposal['data']:
        raise ValueError('Pinned data identity changed')
    pbody = dict(p)
    phash = pbody.pop('preparation_sha256')
    if digest(pbody) != phash:
        raise ValueError('Private preparation digest differs')
    for name, h in p['code_sha256'].items():
        if sha(root/name) != h:
            raise ValueError('Inherited reviewed Stage4 code changed')
    for role, scope in p['roles'].items():
        expected_scope = proposal['budget']['scopes'][role]
        if (digest(scope['files']) != scope['source_manifest_sha256'] or set(scope['ids']) != set(plan.ids(role))
                or any(scope[k] != expected_scope[k] for k in expected_scope)
                or len(scope['files']) != scope['file_count']
                or sum(f['bytes'] for f in scope['files'].values()) != scope['bytes_per_pass']):
            raise ValueError('Private read scope changed')
    if (9*sum(s['bytes_per_pass'] for s in p['roles'].values()) != proposal['budget']['logical_source_bytes']
            or 9*sum(s['file_count'] for s in p['roles'].values()) != proposal['budget']['logical_source_read_instances']):
        raise ValueError('Read budget changed')
    admission = resources()
    if admission['workspace_free_bytes'] < 24*1024**3:
        raise RuntimeError('Reserve >=24GiB workspace before formal B2')
    model, init = fresh_b2(2029, stem_rule=approval['approved_stem_rule'], root=root)
    if init != proposal['input_dimension_difference']:
        raise ValueError('Reviewed B2 initialization differs')
    baseline = read(Path(private['historical_b3_run'])/'B3_development_09.json')
    output.mkdir(parents=True, exist_ok=False)
    write(output/'authorization_binding.json', dict(approval=approval, proposal_sha256=expected, admission=admission))
    write(output/'initialization.json', init)
    orders = {e: epoch_order(plan.ids('Train'), 2029, e) for e in range(1, 10)}
    write(output/'train_orders.json', {str(e): dict(ids=o, sha256=digest(o)) for e, o in orders.items()})
    ledger = B2Ledger(output/'updates.sqlite', dict(approval=approval, data=plan.identity))
    start = time.monotonic()
    def deadline():
        if time.monotonic()-start > approval['max_wall_seconds']:
            raise RuntimeError('Reviewed wall-time cap reached; no retry/resume')
    def reader(role, epoch, ids):
        scope = p['roles'][role]
        inner = BatchReader(plan, {role: ids}, output/f'B2_{role}_reads_{epoch:02d}',
                            decision_id=approval['decision_id'], max_files=scope['file_count'],
                            max_bytes=scope['bytes_per_pass'], source_bytes={q:f['bytes'] for q,f in scope['files'].items()})
        actual = {q:{k:f[k] for k in ('bytes','sha')} for q,f in inner.meter.files.items()}
        if actual != {q:{k:f[k] for k in ('bytes','sha')} for q,f in scope['files'].items()}:
            inner.close()
            raise PermissionError('Actual loader differs from reviewed source scope')
        return PassReader(inner, scope)
    try:
        model = model.cuda()
        optimizer, groups = new_adamw(model)
        buffer_sha = state_digest(dict(model.named_buffers()))
        u = 0
        for epoch, order in orders.items():
            deadline()
            resources(backward=False)
            r = reader('Train', epoch, order)
            visited = []
            model.train()
            nvalid = nrain = 0
            socc = sqr = 0.
            try:
                for pos in range(0, 959, 2):
                    deadline()
                    b = r.batch('Train', order[pos:pos+2]).to('cuda')
                    if b.identity != plan.identity or b.ids != order[pos:pos+2] or b.role != 'Train':
                        raise ValueError('Train identity/order drift')
                    optimizer.zero_grad(set_to_none=True)
                    for g in optimizer.param_groups:
                        g['lr'] = lr_for_update(u+1, steps_per_epoch=480)
                    with torch.autocast('cuda', dtype=torch.bfloat16):
                        out, loss = forward_b2(model, b)
                    loss.training_objective.backward()
                    clip_and_check(model)
                    ledger.reserve(u+1)
                    optimizer.step()
                    u += 1
                    ledger.returned(u)
                    check_finite(model.state_dict())
                    check_finite(optimizer.state_dict())
                    visited.extend(b.ids)
                    nvalid += loss.n_valid
                    nrain += loss.n_rain
                    socc += float(loss.s_occ.detach())
                    sqr += float(loss.s_qr.detach())
                    del b, out, loss
            finally:
                r.close()
            if tuple(visited) != order or u != epoch*480 or nvalid != 959*3430 or state_digest(dict(model.named_buffers())) != buffer_sha:
                raise RuntimeError('Incomplete B2 epoch or changed buffers')
            training = dict(scenes=959, batches=480, updates=u, n_valid=nvalid, n_rain=nrain,
                            s_occ_unweighted=socc, s_qr_unweighted=sqr, weighted_mean=(socc+sqr)/nvalid,
                            loss_arm='E0', train_order_sha256=digest(order))
            write(output/f'B2_train_{epoch:02d}.json', training)
            optimizer.zero_grad(set_to_none=True)
            gc.collect()
            torch.cuda.empty_cache()
            ids = plan.ids('Development')
            r = reader('Development', epoch, ids)
            ev = Evaluation(ids, [plan.rows['Development'][s]['analysis_time'] for s in ids], plan.identity,
                            output/f'B2_evaluation_{epoch:02d}', strong_scene_ids=plan.strong_scene_ids)
            tail = TailDiagnostics()
            model.eval()
            try:
                with torch.no_grad():
                    for pos in range(0, 963, 8):
                        deadline()
                        b = r.batch('Development', ids[pos:pos+8]).to('cuda')
                        if b.identity != plan.identity or b.ids != ids[pos:pos+8] or b.role != 'Development':
                            raise ValueError('Development identity/order drift')
                        with torch.autocast('cuda', dtype=torch.bfloat16):
                            out, _ = forward_b2(model, b)
                        ev.add(out, b)
                        for i, sid in enumerate(b.ids):
                            tail.add(sid, b.rate[i, 0].cpu().numpy(), out.conditional_quantiles_log[i].cpu().numpy(),
                                     (b.valid[i, 0]&b.region[i, 0]).cpu().numpy())
                        del b, out
                report = ev.finish()
            finally:
                ev.close()
                r.close()
            write(output/f'B2_development_{epoch:02d}.json', report)
            write(output/f'B2_tail_diagnostics_{epoch:02d}.json', tail.finish())
            payload = dict(identity=dict(data=plan.identity, approval=approval, model='B2'), epoch=epoch, updates=u,
                           model=cpu_tree(model.state_dict()), optimizer=cpu_tree(optimizer.state_dict()), optimizer_groups=groups,
                           scheduler=dict(completed=u, steps_per_epoch=480, original_horizon=24000),
                           rng=dict(python=random.getstate(), numpy=np.random.get_state(), torch_cpu=torch.get_rng_state(), torch_cuda=torch.cuda.get_rng_state_all()),
                           training=training, validation=report, train_order_sha256=digest(order))
            checkpoint = output/f'B2_LAST_epoch_{epoch:02d}.pt'
            with checkpoint.open('xb') as f:
                torch.save(payload, f)
                f.flush()
                os.fsync(f.fileno())
            write(checkpoint.with_suffix('.receipt.json'), dict(model='B2', epoch=epoch, updates=u,
                  checkpoint_sha256=sha(checkpoint), validation_receipt_sha256=digest(report), population_sha256=plan.identity['population_sha256']))
            del payload
        if ledger.db.execute("SELECT COUNT(*) FROM updates WHERE state='RETURNED'").fetchone()[0] != 4320:
            raise RuntimeError('B2 update ledger incomplete')
        write(output/'B2_minus_B3_E09.json', difference(baseline, report))
        result = dict(status='COMPLETE_TRAIN_AND_DEV_EVALUATION', model='B2', seed=2029, updates=4320, epochs=9,
                      scientific_acceptance='NOT_IMPLIED_BY_RUN_COMPLETION', proposal_sha256=expected)
        write(output/'completion.json', result)
        return result
    except BaseException as exc:
        write(output/'failure.json', dict(status='STOP_NO_AUTOMATIC_RETRY', error=type(exc).__name__+': '+str(exc)))
        raise
    finally:
        ledger.db.close()
