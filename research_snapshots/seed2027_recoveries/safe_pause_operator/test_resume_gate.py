"""Synthetic operator transitions only: no model, observations or optimizer."""
import ast
import copy
import hashlib
import inspect
import json
import sqlite3
import textwrap
import unittest
from unittest.mock import patch
import bootstrap as b
import resume_gate as fixed

OLD_GUARD = "if state!='READY' or self.con.execute('SELECT count(*) FROM sessions').fetchone()[0]:"
NEW_GUARD = "if state not in ('READY','PAUSED') or (state=='READY' and self.con.execute('SELECT count(*) FROM sessions').fetchone()[0]):"
QUOTA_SHA = '6efa3a291de72f2bbd3768a63b30fb94c3bebfb8902147d2304ca193705d8577'


def fixture(cls):
    ledger = object.__new__(cls)
    ledger.con = sqlite3.connect(':memory:', isolation_level=None)
    ledger.ancestor_sha = 'f' * 64
    ledger.con.executescript('''
    CREATE TABLE campaign(id,status,reason);
    CREATE TABLE sessions(n PRIMARY KEY,status,nonce,receipt);
    CREATE TABLE control(id,pause_requested);
    CREATE TABLE attempts(n,run,update_no,status);
    CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);
    INSERT INTO control VALUES(1,1);
    ''')
    ledger.con.execute('INSERT INTO campaign VALUES(?,?,NULL)', (b.protocol.CAMPAIGN,'PAUSED'))
    row = {'status':'PAUSED_VERIFIED','campaign':b.protocol.CAMPAIGN,'session':1,'nonce':'a'*32,'quota':ledger.snapshot()}
    ledger.con.execute('INSERT INTO sessions VALUES(?,?,?,?)',(1,'PAUSED','a'*32,json.dumps(row)))
    receipts = {
        'paused.json':copy.deepcopy(row),
        'termination.json':{'status':'PAUSED','job_empty_and_handles_signaled':True},
        'gui_termination.json':{'nonce':'a'*32,'session':1,'campaign':b.protocol.CAMPAIGN,'supervisor_exit_code':0,'job_empty_and_handles_signaled':True}
    }
    return ledger, receipts


class ResumeTests(unittest.TestCase):
    def test_original_failure_reproduced_without_mutation(self):
        ledger, receipts = fixture(b.quota.Ledger)
        before = '\n'.join(ledger.con.iterdump())
        try:
            with self.assertRaisesRegex(PermissionError,'ONE_HUMAN_APPROVED_LAUNCH_ONLY'):
                ledger.claim_session()
            self.assertEqual(before, '\n'.join(ledger.con.iterdump()))
        finally: ledger.close()

    def test_only_one_original_guard_expression_changes(self):
        self.assertEqual(hashlib.sha256(b.protocol.ROOT.joinpath('recovery_overlay/yuntapr/training/phase_b_v2_seed2027_b1_e1_epoch6_recovery_v2/quota.py').read_bytes()).hexdigest(),QUOTA_SHA)
        original=textwrap.dedent(inspect.getsource(b.quota.Ledger.claim_session))
        self.assertEqual(original.count(OLD_GUARD),1)
        expected=original.replace(OLD_GUARD,NEW_GUARD)
        actual=textwrap.dedent(inspect.getsource(fixed.ResumeLedger.claim_session))
        self.assertEqual(ast.dump(ast.parse(expected)),ast.dump(ast.parse(actual)))

    def test_verified_pause_claims_next_session_preserves_quota(self):
        ledger, receipts = fixture(fixed.ResumeLedger)
        before=ledger.snapshot()
        try:
            with patch.object(fixed,'owned_json',side_effect=lambda path:receipts[path.name]):
                n,nonce=ledger.claim_session()
                self.assertEqual(n,2);self.assertEqual(len(nonce),32)
                self.assertEqual(ledger.snapshot(),before)
                self.assertEqual(ledger.con.execute('SELECT status FROM sessions WHERE n=1').fetchone(),('PAUSED',))
                self.assertEqual(ledger.con.execute('SELECT pause_requested FROM control').fetchone(),(0,))
                with self.assertRaisesRegex(PermissionError,'ALREADY_RUNNING'):
                    ledger.claim_session()
        finally: ledger.close()

    def test_failed_active_and_invalid_ready_states_rejected(self):
        for state in ('FAILED_NO_RETRY','COMPLETE','ACTIVE','READY'):
            with self.subTest(state=state):
                ledger,receipts=fixture(fixed.ResumeLedger)
                try:
                    ledger.con.execute('UPDATE campaign SET status=?',(state,))
                    before='\n'.join(ledger.con.iterdump())
                    with self.assertRaises(PermissionError):ledger.claim_session()
                    self.assertEqual(before,'\n'.join(ledger.con.iterdump()))
                finally:ledger.close()

    def test_pause_evidence_or_quota_drift_rejected_atomically(self):
        for case in ('receipt','job','gui_exit','gui_nonce','quota'):
            with self.subTest(case=case):
                ledger,receipts=fixture(fixed.ResumeLedger)
                try:
                    if case=='receipt':receipts['paused.json']['status']='OTHER'
                    if case=='job':receipts['termination.json']['job_empty_and_handles_signaled']=False
                    if case=='gui_exit':receipts['gui_termination.json']['supervisor_exit_code']=1
                    if case=='gui_nonce':receipts['gui_termination.json']['nonce']='b'*32
                    if case=='quota':ledger.con.execute("INSERT INTO attempts VALUES(1,'synthetic',1,'RETURNED_VERIFIED')")
                    before='\n'.join(ledger.con.iterdump())
                    with patch.object(fixed,'owned_json',side_effect=lambda path:receipts[path.name]):
                        with self.assertRaises(PermissionError):ledger.claim_session()
                    self.assertEqual(before,'\n'.join(ledger.con.iterdump()))
                finally:ledger.close()


if __name__=='__main__':unittest.main(verbosity=2)
