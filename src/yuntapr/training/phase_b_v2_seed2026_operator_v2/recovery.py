"""One exact researcher-approved LAST; immutable ancestor and no quota refund.

The legacy P1 reader is reused with an explicit, SHA-pinned durable registration.
This does not relax the old runner's authority or export a general restore API.
"""
from __future__ import annotations
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle
from .protocol import ROOT, OUT, OLD_OUT, LAST_SHA, OLD_RESERVED, digest

OLD_DATABASE = ROOT / '.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite'
RECOVER_RUN = 'B1_V2__E1__s2026'
COMPLETE_RUNS = ('B0_MATCHED_V2__E0__s2026', 'B1_V2__E0__s2026', 'B0_MATCHED_V2__E1__s2026')
PREVIOUS_OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2026_resume_v2'
CHECKPOINT_ROOT = PREVIOUS_OUT / '.local' / RECOVER_RUN / 'checkpoints'
REFERENCE = CHECKPOINT_ROOT / 'LAST_epoch_07.ref.json'
REGISTRATION = CHECKPOINT_ROOT / 'LAST_epoch_07.registration.json'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def ancestor() -> dict:
    return json.loads((OUT / 'ancestor.json').read_bytes())


class Guard:
    """Retain read-only no-write/delete handles to every pinned ancestor witness."""
    def __init__(self, expected_sha: str):
        self.handles = []
        try:
            raw = (OUT / 'ancestor.json').read_bytes()
            if sha(raw) != expected_sha:
                raise ValueError('RECOVERY_ANCESTOR_RECEIPT_SHA')
            self.receipt = json.loads(raw)
            if (self.receipt['reserved'] != OLD_RESERVED or self.receipt['verified'] != OLD_RESERVED
                    or self.receipt['last_sha256'] != LAST_SHA or self.receipt['source_epoch'] != 7
                    or self.receipt['source_update'] != 36596 or self.receipt['abandoned_updates'] != 14367):
                raise ValueError('EXACT_RECOVERY_SCOPE_AND_NONREFUNDABLE_ANCESTRY')
            allowed = {'.git/phase_b_v2_seed2026_a1863dc_republish_v2.once',
                       '.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite',
                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.once',
                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite',
                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.once',
                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite',
                       '.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite',
                       '.git/phase_b_v2_seed2026_epoch7_operator_v1.once'}
            for relative, expected in self.receipt['pins'].items():
                text = relative.replace('\\', '/')
                if ('2025' in text or ':' in text or text.startswith('/') or '..' in text.split('/')
                        or text.endswith(('.pt', '.pth', '.ckpt'))
                        or not (text.startswith(('docs/phase_b_v2_formal_execution/seed2026_v2/',
                            'docs/phase_b_v2_formal_execution/seed2026_resume_v1/',
                            'docs/phase_b_v2_formal_execution/seed2026_resume_v2/',
                            'docs/phase_b_v2_formal_execution/seed2026_operator_v1/')) or text in allowed)):
                    raise PermissionError('ONLY_FIXED_ANCESTOR_METADATA_BEFORE_NATIVE_ACCESS')
                path = ROOT / text
                handle = ReadHandle(str(path), payload=True)
                self.handles.append(handle)
                if os.path.normcase(handle.final_path) != os.path.normcase(str(path)):
                    raise ValueError('ANCESTOR_NATIVE_PATH')
                h = hashlib.sha256(); count = 0; buf = bytearray(1024**2)
                while n := handle.readinto(buf):
                    count += n; h.update(memoryview(buf)[:n])
                if count != handle.before['size'] or handle.snapshot() != handle.before or h.hexdigest() != expected:
                    raise ValueError('ANCESTOR_BYTES_CHANGED')
            with sqlite3.connect(OLD_DATABASE.as_uri() + '?mode=ro', uri=True) as con:
                con.execute('PRAGMA query_only=ON')
                reserved = con.execute('SELECT count(*) FROM attempts').fetchone()[0]
                verified = con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]
                if reserved != 162068 or verified != 162068:
                    raise ValueError('ANCESTOR_QUOTA_CHANGED_OR_AMBIGUOUS')
                if con.execute('SELECT status FROM campaign').fetchone() != ('FAILED_NO_RETRY',):
                    raise ValueError('ANCESTOR_NOT_STOPPED')
                row = con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?', (RECOVER_RUN,)).fetchone()
                if row != (3, 20912, '64bb7c2158cabfb90bc3aa4f0bb454b80129dfa4ee6c4c8e4e8b5582a457ffdf'):
                    raise ValueError('ANCESTOR_RUN_BOUNDARY_CHANGED')
                if con.execute('SELECT phase FROM epochs WHERE run=? AND epoch=4', (RECOVER_RUN,)).fetchone() != ('WAIT_VALIDATION',):
                    raise ValueError('UNFINISHED_EPOCH4_EVIDENCE_CHANGED')
            zero=self.receipt['zero_update_predecessor']
            if zero['reserved']!=0 or zero['returned']!=0 or zero['job_empty'] is not True:
                raise ValueError('FAILED_RECOVERY_NOT_ZERO_AND_STOPPED')
            db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'
            with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_zero_predecessor(con)
            with sqlite3.connect((ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite').as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON')
                if con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=24823 or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=24823:
                    raise ValueError('STOPPED_RECOVERY_QUOTA_AMBIGUOUS')
                if con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',(RECOVER_RUN,)).fetchone()!=(7,40507,LAST_SHA) or con.execute('SELECT status FROM campaign').fetchone()!=('FAILED_NO_RETRY',):
                    raise ValueError('STOPPED_EPOCH7_SOURCE_CHANGED')
            with sqlite3.connect((ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite').as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_stopped_operator(con)
            # Hold parent directory objects against rename/reparse replacement.
            chain = []; parent = CHECKPOINT_ROOT
            while True:
                chain.append(parent)
                if parent == ROOT: break
                parent = parent.parent
            for path in reversed(chain):
                handle = ReadHandle(str(path), directory=True); self.handles.append(handle)
                if os.path.normcase(handle.final_path) != os.path.normcase(str(path)):
                    raise ValueError('ANCESTOR_CHECKPOINT_PARENT_IDENTITY')
        except BaseException:
            self.close(); raise

    def close(self):
        for handle in reversed(self.handles): handle.close()
        self.handles.clear()


def history() -> list:
    row = json.loads((PREVIOUS_OUT / '.local' / RECOVER_RUN / 'progress.json').read_bytes())
    if row['complete_epoch'] != 7 or row['updates'] != 36596 or len(row['epochs']) != 7:
        raise ValueError('EXACT_COMMITTED_THREE_EPOCH_HISTORY')
    for i, record in enumerate(row['epochs'], 1):
        report = dict(record['development']); receipt = report.pop('receipt_sha')
        if record['epoch'] != i or receipt != digest(report) or not report['complete']:
            raise ValueError('ANCESTOR_COMPLETED_VALIDATION_HISTORY')
    return row['epochs']


def completed_results() -> list:
    result = []
    for run in COMPLETE_RUNS:
        row = json.loads((OLD_OUT / (run + '.json')).read_bytes())
        if row['run_id'] != run or row['status'] != 'COMPLETE' or row['updates'] != 47052 or len(row['epochs']) != 9:
            raise ValueError('ONLY_ALREADY_COMPLETE_ANCESTOR_RESULTS')
        for i, entry in enumerate(row['epochs'], 1):
            report = dict(entry['development']); receipt = report.pop('receipt_sha')
            if entry['epoch'] != i or not report['complete'] or digest(report) != receipt:
                raise ValueError('ANCESTOR_RESULT_RECEIPT')
        result.append(row)
    return result


def apply_validated_state(model, optimizer, schedule, payload) -> dict:
    """Called only AFTER full contract validation; no update or RNG reseeding."""
    from yuntapr.experimental.phase_b_v2_runner_candidate import rng
    from yuntapr.training.phase_a_protocol import state_digest
    from .engine import cpu_tree
    rng.validate(payload['rng'])
    model.load_state_dict(payload['model'], strict=True)
    optimizer.load_state_dict(payload['optimizer'])
    schedule.load_state_dict(payload['scheduler'])
    if state_digest(model.state_dict()) != state_digest(payload['model']):
        raise ValueError('MODEL_RESTORE_NOT_BIT_IDENTICAL')
    if state_digest(cpu_tree(optimizer.state_dict())) != state_digest(payload['optimizer']):
        raise ValueError('ADAMW_RESTORE_NOT_BIT_IDENTICAL')
    if schedule.state_dict() != payload['scheduler']:
        raise ValueError('SCHEDULER_RESTORE_NOT_EXACT')
    rng.restore(payload['rng'])
    if state_digest(cpu_tree(rng.capture())) != state_digest(payload['rng']):
        raise ValueError('RNG_RESTORE_NOT_EXACT')
    return dict(model_sha256=state_digest(payload['model']), optimizer_sha256=state_digest(payload['optimizer']),
                rng_sha256=state_digest(payload['rng']), scheduler=payload['scheduler'],
                all_state_verified_before_first_resumed_step=True)


def restore_authorized(model, optimizer, schedule, initial_sha, plan) -> dict:
    from yuntapr.training.phase_b_v2_seed2026_resume_v2.checkpoint import Contract as OldContract, Store as OldStore
    from yuntapr.experimental.phase_b_v2_formal_runner_candidate.checkpoint import optimizer_template
    identity = json.loads((PREVIOUS_OUT / '.local' / RECOVER_RUN / 'identity.json').read_bytes())
    if (identity['run_id'] != RECOVER_RUN or identity['arm'] != 'E1' or identity['seed'] != 2026
            or identity['data'] != plan.identity or identity['initial_sha256'] != initial_sha):
        raise ValueError('RECOVERY_FROZEN_DATA_FRESH_TEMPLATE_OR_RUN_IDENTITY')
    registration = json.loads(REGISTRATION.read_bytes())
    contract = OldContract(identity, {k: (tuple(v.shape), str(v.dtype)) for k,v in model.state_dict().items()},
                           optimizer_template(optimizer), initial_sha, plan.ids(2023), plan.ids(2024))
    if (registration['payload_name'] != 'LAST_epoch_07.pt' or registration['reference_name'] != REFERENCE.name
            or registration['payload_sha256'] != LAST_SHA or registration['contract_sha'] != contract.key
            or contract.key != '22dee715eeefeedc6b8bdf1c7df3a9e9dfb2f504f29a4e15c3d9c8340f093d28'
            or registration['receipt_sha256'] != '467102b5a24e6458d588c5f342498ef50ad26109318d73d5520d55cd0445b35d'):
        raise ValueError('ONLY_EXPLICIT_SHA_BOUND_LAST_REGISTRATION')
    # Explicit adoption factory, not OldStore.__init__ (which creates NEW stores).
    # Reader's native-object/SHA/BytesIO/weights_only and full contract remain intact.
    store = object.__new__(OldStore)
    store.root, store.contract, store.failed, store.directories = CHECKPOINT_ROOT, contract, False, []
    store.registered = {str(REFERENCE): dict(reference=REFERENCE, payload=CHECKPOINT_ROOT / 'LAST_epoch_07.pt',
        receipt_sha=registration['receipt_sha256'], payload_sha=LAST_SHA,
        receipt_object=registration['receipt_object'], payload_object=registration['payload_object'])}
    payload = store.read(REFERENCE)
    if payload['epoch'] != 7 or payload['update'] != 36596:
        raise ValueError('APPROVED_LAST_EPOCH_UPDATE')
    proof = apply_validated_state(model, optimizer, schedule, payload)
    return dict(**proof, source_last_sha256=LAST_SHA, source_epoch=7, source_update=36596,
                same_bytes_deserialized=True, weights_only=True, old_reserved_not_refunded=OLD_RESERVED,
                abandoned_updates_total=14367, exact_stop_point_state_available=False,
                restores_complete_epoch7_state=True)


def verify_zero_predecessor(con):
    """Readonly SQL proof: no attempted update or adopted epoch in failed v1."""
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=0
            or con.execute('SELECT count(*) FROM epochs').fetchone()[0]!=0
            or con.execute('SELECT status FROM campaign').fetchone()!=('FAILED_NO_RETRY',)
            or con.execute('SELECT status,epoch,updates,last_sha FROM runs WHERE id=?',
                           (RECOVER_RUN,)).fetchone()!=('PENDING',3,15684,'64bb7c2158cabfb90bc3aa4f0bb454b80129dfa4ee6c4c8e4e8b5582a457ffdf')):
        raise ValueError('ZERO_UPDATE_FAILED_RECOVERY_ANCESTOR_CHANGED')


def verify_stopped_operator(con):
    """Exact emergency ancestor; no epoch8 LAST and no ambiguous update."""
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=5228
        or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=5228
        or con.execute('SELECT status,reason FROM campaign').fetchone()!=('FAILED_NO_RETRY','RESEARCHER_EMERGENCY_STOP_NO_RETRY')
        or con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',(RECOVER_RUN,)).fetchone()!=(7,41824,LAST_SHA)
        or con.execute('SELECT epoch,phase FROM epochs WHERE run=?',(RECOVER_RUN,)).fetchall()!=[(8,'WAIT_VALIDATION')]):
        raise ValueError('EXACT_EMERGENCY_STOPPED_OPERATOR_ANCESTRY')
