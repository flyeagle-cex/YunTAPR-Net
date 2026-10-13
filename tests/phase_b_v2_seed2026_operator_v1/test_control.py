"""Synthetic metadata only: no real data, model, or optimizer calls."""
import ast
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import uuid
from yuntapr.training.phase_b_v2_seed2026_operator_v1 import quota as q
from yuntapr.training.phase_b_v2_seed2026_operator_v1 import protocol as p


class TestControl(unittest.TestCase):
    def setUp(self):
        self.root=p.ROOT/'tests/phase_b_v2_seed2026_operator_v1/.local'/uuid.uuid4().hex
        (self.root/'.git').mkdir(parents=True);self.out=self.root/'out';self.local=self.out/'.local';self.local.mkdir(parents=True)
        self.db=self.root/'.git/ledger.sqlite'
        (self.out/'release.json').write_text(json.dumps({'ancestor_receipt_sha256':'a'*64}))
        old=self.root/'docs/phase_b_v2_formal_execution/seed2026_v2';old.mkdir(parents=True)
        for model,arm in p.ORDER[:3]:(old/(p.run_id(model,arm)+'.json')).write_text(json.dumps({'epochs':[{'checkpoint':{'payload_sha256':'f'*64}}]}))
        self.patches=[patch.object(q,'ROOT',self.root),patch.object(q,'OUT',self.out),patch.object(q,'LOCAL',self.local),
            patch.object(q,'DB',self.db),patch.object(q,'session_root',lambda n:self.local/f's{n}'),
            patch.object(q,'owned_json',lambda path:json.loads(path.read_bytes()))]
        for m in self.patches:m.start()
        self.ledger=q.Ledger.initialize({'source':'SYNTHETIC_METADATA_ONLY'})
    def tearDown(self):
        self.ledger.close()
        for m in reversed(self.patches):m.stop()
    def active(self):
        n,nonce=self.ledger.claim_session();self.ledger.activate_session(n,nonce);return n,nonce
    def ident(self):return p.run_id('B1_V2','E1')
    def commit_boundary(self):
        ident=self.ident();self.ledger.start_run(ident);self.ledger.begin_epoch(ident,8)
        # Logical full-epoch fixture; there is NO optimizer call here.
        self.ledger.con.execute('UPDATE runs SET updates=? WHERE id=?',(8*p.STEPS,ident))
        self.ledger.finish_train(ident,8,dict(scenes=10455,batches=p.STEPS))
        self.ledger.validated(ident,8,dict(complete=True,summary=dict(scenes=10501,n_valid=10501*3430),receipt_sha='a'*64))
        self.ledger.last(ident,8,dict(payload_sha256='b'*64))
    def paused(self,n,nonce):
        row=self.ledger.pause_boundary(n,nonce,dict(elapsed_seconds=123,content_bytes=456))
        folder=self.local/f's{n}';folder.mkdir()
        (folder/'paused.json').write_text(json.dumps(row));(folder/'termination.json').write_text(json.dumps(dict(status='PAUSED',job_empty_and_handles_signaled=True,elapsed_seconds=124)))
        return row
    def test_base_quota_and_epoch7(self):
        self.assertEqual(self.ledger.snapshot()['reserved'],186891);self.assertEqual(self.ledger.run_row(self.ident())['epoch'],7)
    def test_duplicate_start_rejected(self):
        self.active()
        with self.assertRaises(PermissionError):self.ledger.claim_session()
    def test_wrong_nonce_rejected(self):
        n,_=self.active()
        with self.assertRaises(PermissionError):self.ledger.verify_session(n,'wrong')
    def test_failed_rejects_restart(self):
        self.active();self.ledger.fail('SYNTHETIC_FAILURE')
        with self.assertRaises(PermissionError):self.ledger.claim_session()
    def test_complete_rejects_restart(self):
        self.ledger.con.execute("UPDATE campaign SET status='COMPLETE'")
        with self.assertRaises(PermissionError):self.ledger.claim_session()
    def test_pause_request_blocks_next_run(self):
        self.active();self.ledger.request_pause()
        with self.assertRaises(q.PauseAtBoundary):self.ledger.start_run(self.ident())
    def test_pause_request_blocks_next_epoch(self):
        self.active();self.ledger.start_run(self.ident());self.ledger.request_pause()
        with self.assertRaises(q.PauseAtBoundary):self.ledger.begin_epoch(self.ident(),8)
    def test_pause_does_not_block_current_update(self):
        self.active();self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),8);self.ledger.request_pause()
        self.ledger.reserve(self.ident(),36597);self.ledger.returned(self.ident(),36597)
        self.assertEqual(self.ledger.snapshot()['new_reserved'],1)
    def test_ambiguous_attempt_rejects_pause(self):
        n,nonce=self.active();self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),8);self.ledger.reserve(self.ident(),36597)
        with self.assertRaises(ValueError):self.ledger.pause_boundary(n,nonce,{})
    def test_unfinished_validation_rejects_pause(self):
        n,nonce=self.active();self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),8)
        self.ledger.con.execute("UPDATE epochs SET phase='WAIT_VALIDATION'")
        with self.assertRaises(ValueError):self.ledger.pause_boundary(n,nonce,{})
    def test_clean_pause_continues_same_lifetime_quota(self):
        n,nonce=self.active();self.commit_boundary();self.paused(n,nonce)
        n2,nonce2=self.ledger.claim_session();self.assertEqual(n2,2);self.assertNotEqual(nonce,nonce2)
        self.ledger.activate_session(n2,nonce2);self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),9)
        self.assertEqual(self.ledger.snapshot()['reserved'],186891)
    def test_pause_not_closed_rejects_start(self):
        n,nonce=self.active();self.commit_boundary();self.paused(n,nonce)
        (self.local/f's{n}'/'termination.json').write_text(json.dumps(dict(status='PAUSED',job_empty_and_handles_signaled=False)))
        with self.assertRaises(PermissionError):self.ledger.claim_session()
    def test_pause_receipt_mutation_rejected(self):
        n,nonce=self.active();self.commit_boundary();row=self.paused(n,nonce);row['quota']['reserved']-=1
        (self.local/f's{n}'/'paused.json').write_text(json.dumps(row))
        with self.assertRaises(PermissionError):self.ledger.claim_session()
    def test_initialize_never_resets_quota(self):
        self.active();self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),8);self.ledger.reserve(self.ident(),36597)
        other=q.Ledger.initialize({'other':'identity'})
        try:self.assertEqual(other.snapshot()['reserved'],186892)
        finally:other.close()
    def test_fixed_cap_no_refund(self):
        self.active();self.ledger.start_run(self.ident());self.ledger.begin_epoch(self.ident(),8)
        with patch.object(q,'MAX_NEW',1):
            self.ledger.reserve(self.ident(),36597);self.ledger.returned(self.ident(),36597)
            with self.assertRaises(PermissionError):self.ledger.reserve(self.ident(),36598)
    def test_original_completed_groups_not_rerun(self):
        self.active()
        with self.assertRaises(PermissionError):self.ledger.start_run(p.run_id(*p.ORDER[0]))
    def test_training_and_validation_math_unchanged(self):
        base=ast.parse((p.ROOT/'src/yuntapr/training/phase_b_v2_seed2026_resume_v2/engine.py').read_text())
        new=ast.parse((p.ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v1/engine.py').read_text())
        for name in ('train','validate'):
            a=next(n for n in ast.walk(base) if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in ast.walk(new) if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))
    def test_only_scope_budget_arithmetic(self):
        self.assertEqual(p.OLD_RESERVED+p.MAX_NEW,p.TOTAL);self.assertEqual(p.MAX_NEW,20*p.STEPS)
        self.assertEqual(p.TOTAL,282312+5228+3911)


if __name__=='__main__':unittest.main(verbosity=2)
