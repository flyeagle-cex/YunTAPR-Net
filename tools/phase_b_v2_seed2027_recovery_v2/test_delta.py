"""Small re-publication delta only; no training, data, model or CUDA imports."""
from pathlib import Path
import ast,importlib.util,sqlite3,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v2.recovery import validate_history_metrics
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v2 import protocol as p,ancestor as a
from yuntapr.training.phase_b_v2_seed2027_epoch1_recovery_v2.authority import execution_instruction
spec=importlib.util.spec_from_file_location('prior_metadata_tests',ROOT/'tools/phase_b_v2_seed2027_recovery/test_metadata_fix.py')
sys.path.insert(0,str(ROOT/'tools/phase_b_v2_seed2027_recovery'))
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
prior.validate_history_metrics=validate_history_metrics

def method(path,cls,name):
    rows=ast.parse(path.read_bytes()).body
    if cls:rows=next(x.body for x in rows if isinstance(x,ast.ClassDef) and x.name==cls)
    return ast.dump(next(x for x in rows if getattr(x,'name',None)==name),include_attributes=False)

class Delta(unittest.TestCase):
    def test_01_same_budget_science_and_resources(self):
        old=ROOT/'docs/phase_b_v2_formal_execution/seed2027_epoch1_recovery_v1/config.json'
        self.assertEqual((p.OUT/'config.json').read_bytes(),old.read_bytes())
        self.assertEqual((p.OLD_RESERVED,p.OLD_VERIFIED,p.MAX_NEW,p.TOTAL),(75327,75326,277084,352411))
        p.validate_plan(__import__('json').loads(old.read_bytes()))
    def test_02_exact_new_human_reply(self):
        r=execution_instruction();self.assertEqual(r['answer'],'授权零更新修复后重新发布启动')
        self.assertEqual(r['additional_attempts'],0);self.assertEqual(r['last_sha256'],p.LAST_SHA)
    def test_03_no_training_algorithm_changes(self):
        old=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_epoch1_recovery_v1'
        new=old.with_name('phase_b_v2_seed2027_epoch1_recovery_v2')
        for file,cls,names in [('engine.py','Engine',('run_one','train','validate')),('supervisor.py',None,('main',)),('checkpoint.py',None,('Store',))]:
            for name in names:
                self.assertEqual(method(old/file,cls,name).replace('epoch1_recovery_v1','epoch1_recovery_v2'),method(new/file,cls,name))
    def test_04_zero_predecessor_fixture(self):
        with sqlite3.connect(':memory:') as con:
            con.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE attempts(status);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE epochs(run,epoch,phase);')
            con.execute('INSERT INTO campaign VALUES(?,?,?)',(a.ZERO_CAMPAIGN,'FAILED_NO_RETRY','AUTHORIZED_LAST_METRICS'))
            for i,(m,arm) in enumerate(p.ORDER):
                con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(p.run_id(m,arm),i,'RUNNING' if i==0 else 'PENDING',1 if i==0 else 0,5228 if i==0 else 0,p.LAST_SHA if i==0 else None))
            con.execute('INSERT INTO epochs VALUES(?,?,?)',(a.RUN,1,'LAST_COMMITTED'));a.verify_zero(con)
            con.execute("INSERT INTO attempts VALUES('RESERVED_BEFORE_CALL')")
            with self.assertRaises(ValueError):a.verify_zero(con)
    def test_05_no_launch_side_effects(self):
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
        self.assertFalse((p.LOCAL/'sessions').exists());self.assertNotIn('torch',sys.modules)

if __name__=='__main__':
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(prior.Tests),unittest.defaultTestLoader.loadTestsFromTestCase(Delta)])
    result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
