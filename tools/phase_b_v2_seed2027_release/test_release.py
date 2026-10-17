"""New publication/hold tests only; no model, observation or GPU imports."""
from pathlib import Path
import ast,copy,hashlib,json,os,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
os.environ['YUNTAPR_REPLICATION_SEED']='2027'
from yuntapr.training.phase_b_v2_seed2027 import protocol as p
from yuntapr.training.phase_b_v2_seed2027.authority import require_execution_authority,PUBLICATION_DECISION,PUBLICATION_SCOPE
OLD=ROOT/'src/yuntapr/experimental/phase_b_v2_multiseed_candidate'
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027'
def fn(path,name,cls=None):
    tree=ast.parse(path.read_bytes());nodes=tree.body
    if cls:nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls)
    return ast.dump(next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.raw=(p.OUT/'config.json').read_bytes()
        self.actual={'sha256':'1'*64,'pins':{'fixture.py':'2'*64}}
        self.record=dict(schema='SEED2027_EXECUTION_PUBLICATION_WITHOUT_LAUNCH_v1',campaign=p.CAMPAIGN,seed=2027,
            publication_decision=PUBLICATION_DECISION,publication_scope=PUBLICATION_SCOPE,launch_authorized=False,
            planned_attempt_cap=282312,original_resource_limits=p.LIMITS,source_sha256=self.actual['sha256'],
            source_pins=self.actual['pins'],config_sha256=hashlib.sha256(self.raw).hexdigest())
    def test_01_science_config_byte_identical(self):
        self.assertEqual(self.raw,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_v1/config.json').read_bytes())
    def test_02_hold_is_actual_human_decision(self):
        self.assertEqual(PUBLICATION_DECISION,'只发布执行版本，暂不启动')
        with self.assertRaisesRegex(PermissionError,'LAUNCH_WITHHELD'):require_execution_authority(2027)
    def test_03_no_other_seed_permission(self):
        for seed in (2026,2028,'2027',True):
            with self.assertRaises(PermissionError):require_execution_authority(seed)
    def test_04_boolean_does_not_grant_launch(self):
        self.record['launch_authorized']=True
        with self.assertRaises(ValueError):p.validate_record(self.record,self.actual,self.raw)
        with self.assertRaisesRegex(PermissionError,'LAUNCH_WITHHELD'):p.verify_release()
    def test_05_source_tamper_rejected(self):
        self.record['source_sha256']='0'*64
        with self.assertRaises(ValueError):p.validate_record(self.record,self.actual,self.raw)
    def test_06_config_tamper_rejected(self):
        with self.assertRaises(ValueError):p.validate_record(self.record,self.actual,self.raw+b' ')
    def test_07_budget_and_scope_tamper_rejected(self):
        for key,value in [('seed',2028),('planned_attempt_cap',282313),('publication_scope','APPROVED')]:
            changed=dict(self.record);changed[key]=value
            with self.assertRaises(ValueError):p.validate_record(changed,self.actual,self.raw)
    def test_08_published_not_launched_schema(self):
        self.assertIs(p.validate_record(self.record,self.actual,self.raw),self.record)
    def test_09_numerical_loops_unchanged(self):
        for name in ('train','validate'):self.assertEqual(fn(OLD/'engine.py',name,'Engine'),fn(NEW/'engine.py',name,'Engine'))
    def test_10_checkpoint_bytes_code_unchanged(self):
        self.assertEqual((OLD/'checkpoint.py').read_bytes(),(NEW/'checkpoint.py').read_bytes())
    def test_11_pause_job_and_resource_logic_unchanged(self):
        for name in ('pause','open_owned_job','emergency_stop'):
            self.assertEqual(fn(OLD/'control.py',name),fn(NEW/'control.py',name))
        self.assertEqual((OLD/'resources.py').read_bytes(),(NEW/'resources.py').read_bytes())
    def test_12_new_launcher_routes_to_published_worker(self):
        self.assertIn('yuntapr.training.phase_b_v2_seed2027.supervisor',(NEW/'control.py').read_text())
        self.assertIn('yuntapr.training.phase_b_v2_seed2027.worker',(NEW/'supervisor.py').read_text())
        self.assertNotIn('phase_b_v2_multiseed_candidate.worker',(NEW/'supervisor.py').read_text())
    def test_13_direct_ledger_cannot_create_quota(self):
        from yuntapr.training.phase_b_v2_seed2027.quota import Ledger
        with self.assertRaisesRegex(PermissionError,'LAUNCH_WITHHELD'):Ledger.initialize({'APPROVED':True})
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
    def test_14_no_session_or_heavy_import(self):
        self.assertFalse((p.LOCAL/'sessions').exists());self.assertNotIn('torch',sys.modules)
        self.assertEqual(p.DB.name,'phase_b_v2_seed2027_fresh_v1.sqlite')
if __name__=='__main__':unittest.main(verbosity=2)
