"""New grant and exact stopped-parent tests; no real tensors or optimizer."""
import ast
from pathlib import Path
import sqlite3
import unittest
from yuntapr.training.phase_b_v2_seed2026_operator_v2 import protocol as p
from yuntapr.training.phase_b_v2_seed2026_operator_v1 import protocol as old
from yuntapr.training.phase_b_v2_seed2026_operator_v2.recovery import verify_stopped_operator


class TestAncestry(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.executescript('CREATE TABLE attempts(status TEXT);CREATE TABLE campaign(status TEXT,reason TEXT);CREATE TABLE runs(id TEXT,epoch INT,updates INT,last_sha TEXT);CREATE TABLE epochs(run TEXT,epoch INT,phase TEXT);')
        self.con.executemany('INSERT INTO attempts VALUES(?)',[('RETURNED_VERIFIED',)]*5228)
        self.con.execute('INSERT INTO campaign VALUES(?,?)',('FAILED_NO_RETRY','RESEARCHER_EMERGENCY_STOP_NO_RETRY'))
        self.con.execute('INSERT INTO runs VALUES(?,?,?,?)',('B1_V2__E1__s2026',7,41824,p.LAST_SHA))
        self.con.execute('INSERT INTO epochs VALUES(?,?,?)',('B1_V2__E1__s2026',8,'WAIT_VALIDATION'))
    def tearDown(self):self.con.close()
    def test_exact_stopped_parent(self):verify_stopped_operator(self.con)
    def test_ambiguous_attempt_rejected(self):
        self.con.execute("UPDATE attempts SET status='RESERVED_BEFORE_CALL' WHERE rowid=1")
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_extra_attempt_rejected(self):
        self.con.execute("INSERT INTO attempts VALUES('RETURNED_VERIFIED')")
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_active_parent_rejected(self):
        self.con.execute("UPDATE campaign SET status='ACTIVE'")
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_wrong_sha_rejected(self):
        self.con.execute("UPDATE runs SET last_sha=?",('0'*64,))
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_unapproved_epoch8_last_rejected(self):
        self.con.execute("UPDATE epochs SET phase='LAST_COMMITTED'")
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_wrong_update_rejected(self):
        self.con.execute('UPDATE runs SET updates=41823')
        with self.assertRaises(ValueError):verify_stopped_operator(self.con)
    def test_budget_scope(self):
        self.assertEqual(p.OLD_RESERVED,192119);self.assertEqual(p.MAX_NEW,20*p.STEPS)
        self.assertEqual(p.OLD_RESERVED+p.MAX_NEW,p.TOTAL);self.assertEqual(p.TOTAL,296679)
        self.assertEqual(p.TOTAL-old.TOTAL,5228);self.assertEqual(p.TOTAL,282312+p.ABANDONED)
    def test_resources_and_matrix_unchanged(self):
        self.assertEqual(p.LIMITS,old.LIMITS);self.assertEqual(p.ORDER,old.ORDER)
        self.assertEqual(p.LAST_SHA,old.LAST_SHA)
    def test_math_and_same_bytes_reader_unchanged(self):
        directory=p.ROOT/'src/yuntapr/training'
        for file,names in [('engine.py',('train','validate')),('recovery.py',('apply_validated_state','restore_authorized')),('checkpoint.py',('_bytes','read'))]:
            a=ast.parse((directory/'phase_b_v2_seed2026_operator_v1'/file).read_text())
            b=ast.parse((directory/'phase_b_v2_seed2026_operator_v2'/file).read_text())
            for name in names:
                x=next(n for n in ast.walk(a) if isinstance(n,ast.FunctionDef) and n.name==name)
                y=next(n for n in ast.walk(b) if isinstance(n,ast.FunctionDef) and n.name==name)
                if name=='restore_authorized':
                    # Only the reported nonrefundable abandoned count changes.
                    for n in ast.walk(x):
                        if isinstance(n,ast.Constant) and n.value==9139:n.value=14367
                self.assertEqual(ast.dump(x,include_attributes=False),ast.dump(y,include_attributes=False))

if __name__=='__main__':unittest.main(verbosity=2)
