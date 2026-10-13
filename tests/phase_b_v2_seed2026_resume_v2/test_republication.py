"""Only the new zero-update ancestor gate; no model or optimizer."""
import ast
from pathlib import Path
import sqlite3
import unittest
from yuntapr.training.phase_b_v2_seed2026_resume_v2.recovery import verify_zero_predecessor,RECOVER_RUN,LAST_SHA

class Tests(unittest.TestCase):
    def fixture(self):
        c=sqlite3.connect(':memory:')
        c.executescript('CREATE TABLE attempts(n);CREATE TABLE epochs(n);CREATE TABLE campaign(status);'
                       'CREATE TABLE runs(id,status,epoch,updates,last_sha);')
        c.execute('INSERT INTO campaign VALUES(?)',('FAILED_NO_RETRY',))
        c.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(RECOVER_RUN,'PENDING',3,15684,LAST_SHA))
        self.addCleanup(c.close);return c
    def test_zero_update_predecessor_accepted(self):verify_zero_predecessor(self.fixture())
    def test_nonzero_attempt_predecessor_rejected(self):
        c=self.fixture();c.execute('INSERT INTO attempts VALUES(1)')
        with self.assertRaises(ValueError):verify_zero_predecessor(c)
    def test_adopted_epoch_predecessor_rejected(self):
        c=self.fixture();c.execute('INSERT INTO epochs VALUES(1)')
        with self.assertRaises(ValueError):verify_zero_predecessor(c)
    def test_training_evaluation_restore_and_resource_code_unchanged(self):
        root=Path(__file__).absolute().parents[2]/'src/yuntapr/training'
        for name in ('engine.py','checkpoint.py','resources.py','evaluation.py','analysis.py'):
            old=ast.parse((root/'phase_b_v2_seed2026_resume_v1'/name).read_text(encoding='utf-8'))
            new=ast.parse((root/'phase_b_v2_seed2026_resume_v2'/name).read_text(encoding='utf-8'))
            self.assertEqual(ast.dump(old,include_attributes=False),ast.dump(new,include_attributes=False))

if __name__=='__main__':unittest.main(verbosity=2)
