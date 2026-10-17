"""Only the new activation delta: no model, CUDA, optimizer or raw data."""
from pathlib import Path
import ast,copy,hashlib,json,os,subprocess,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
os.environ['YUNTAPR_REPLICATION_SEED']='2027'
from yuntapr.training.phase_b_v2_seed2027 import protocol as p
from yuntapr.training.phase_b_v2_seed2027.authority import execution_instruction,EXECUTION_SCOPE,require_execution_authority

def fn(raw,name,cls=None):
    nodes=ast.parse(raw).body
    if cls:nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls)
    return ast.dump(next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.raw=(p.OUT/'config.json').read_bytes()
        self.actual=dict(sha256='1'*64,pins={'fixture.py':'2'*64})
        self.record=dict(schema='SEED2027_HUMAN_AUTHORIZED_EXECUTION_v1',seed=2027,campaign=p.CAMPAIGN,
            human_instruction=execution_instruction(),human_instruction_sha256=p.digest(execution_instruction()),
            execution_scope=EXECUTION_SCOPE,launch_authorized=True,planned_attempt_cap=p.TOTAL,
            original_resource_limits=p.LIMITS,source_sha256=self.actual['sha256'],source_pins=self.actual['pins'],
            held_publication_commit='ed45c6c817b9c5ab47b1e3f30ce30e99ddb9e38c',
            dependency_manifest_sha256='2d02c5757f9da5fc1fef8b82168ffd689b96c07056d1cc13acf354a3fd88e780',
            config_sha256=hashlib.sha256(self.raw).hexdigest())
    def test_01_actual_instruction_and_seed_scope(self):
        self.assertEqual(execution_instruction()['answer'],'授权激活并启动 seed2027')
        require_execution_authority(2027)
        for seed in (2026,2028,'2027',True):
            with self.assertRaises(PermissionError):require_execution_authority(seed)
    def test_02_unchanged_frozen_config(self):
        self.assertEqual(self.raw,(ROOT/'docs/phase_b_v2_formal_execution/seed2027_release_v1/config.json').read_bytes())
        p.validate_plan(json.loads(self.raw))
    def test_03_exact_activation_scope(self):
        self.assertIs(p.validate_record(self.record,self.actual,self.raw),self.record)
    def test_04_boolean_or_json_alone_insufficient(self):
        for record in ({'APPROVED':True},{'launch_authorized':True},dict(self.record,human_instruction={} )):
            with self.assertRaises(ValueError):p.validate_record(record,self.actual,self.raw)
    def test_05_scope_budget_resources_dependencies_reject(self):
        for key,value in [('seed',2028),('planned_attempt_cap',282313),('execution_scope','ALL_SEEDS'),
            ('original_resource_limits',{}),('human_instruction_sha256','0'*64),
            ('dependency_manifest_sha256','0'*64),('source_sha256','0'*64)]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):p.validate_record(dict(self.record,**{key:value}),self.actual,self.raw)
    def test_06_configuration_bytes_tamper(self):
        with self.assertRaises(ValueError):p.validate_record(self.record,self.actual,self.raw+b' ')
    def test_07_historical_hold_cannot_be_active_release(self):
        old=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2027_release_v1/release.json').read_bytes())
        with self.assertRaises(ValueError):p.validate_record(old,self.actual,self.raw)
        self.assertFalse(old['launch_authorized'])
    def test_08_numerical_loops_unchanged(self):
        name='src/yuntapr/training/phase_b_v2_seed2027/engine.py'
        old=subprocess.check_output(['git','show','ed45c6c:'+name],cwd=ROOT)
        for method in ('train','validate','run_one','run'):
            self.assertEqual(fn(old,method,'Engine'),fn((ROOT/name).read_bytes(),method,'Engine'))
    def test_09_existing_quota_name_and_cap(self):
        self.assertEqual(p.DB.name,'phase_b_v2_seed2027_fresh_v1.sqlite')
        self.assertEqual(p.TOTAL,6*9*5228)
        self.assertEqual((p.OLD_RESERVED,p.ABANDONED),(0,0))
    def test_10_check_has_no_training_import_or_side_effect(self):
        self.assertNotIn('torch',sys.modules)
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
        self.assertFalse((p.LOCAL/'sessions').exists())
if __name__=='__main__':unittest.main(verbosity=2)
