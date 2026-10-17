"""Only new seed wiring/configuration checks. No torch/GPU/data/model tests."""
from pathlib import Path
import ast,copy,hashlib,importlib,json,os,subprocess,sys,unittest
ROOT=Path(__file__).absolute().parents[2]
DOC=ROOT/'docs/phase_b_v2_multiseed_preparation/v1'
NEW=ROOT/'src/yuntapr/experimental/phase_b_v2_multiseed_candidate'
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v3'
sys.path.insert(0,str(ROOT/'src'));os.environ['YUNTAPR_REPLICATION_SEED']='2027'
from yuntapr.experimental.phase_b_v2_multiseed_candidate import protocol as p
def method(path,cls,name):
    tree=ast.parse(path.read_bytes());parent=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return ast.dump(next(n for n in parent.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name),include_attributes=False)
class PreparationTests(unittest.TestCase):
    def setUp(self):self.plan=json.loads((p.OUT/'config.json').read_bytes())
    def test_01_six_runs(self):self.assertEqual(len(p.validate_plan(self.plan)['runs']),6)
    def test_02_seed_identity_reject(self):
        self.plan['seed']=2026
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_03_arm_drift_reject(self):
        self.plan['runs'][2]['gamma']=2
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_04_order_drift_reject(self):
        self.plan['runs'].reverse()
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_05_budget_drift_reject(self):
        self.plan['attempt_cap']+=1
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_06_resource_drift_reject(self):
        self.plan['limits']['max_cuda_reserved_bytes']+=1
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_07_no_boolean_authority(self):
        self.plan['execution_authorized']=True
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
        with self.assertRaisesRegex(PermissionError,'NOT_AUTHORIZED'):p.verify_release()
    def test_08_no_warm_start(self):
        self.plan['initial_checkpoint']='invented_LAST.pt'
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_09_no_2025_role(self):
        self.plan['data_roles']['2025']='Test'
        with self.assertRaises(ValueError):p.validate_plan(self.plan)
    def test_10_seed_scope_separation(self):
        a=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2027_v1/config.json').read_bytes())
        b=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2028_v1/config.json').read_bytes())
        self.assertNotEqual(a['campaign'],b['campaign']);self.assertNotEqual(a['quota_namespace'],b['quota_namespace'])
        self.assertEqual(a['frozen_identity'],b['frozen_identity']);self.assertEqual(a['limits'],b['limits'])
        self.assertEqual(a['attempt_cap']+b['attempt_cap'],564624)
    def test_11_numerical_loops_unchanged(self):
        for name in ('train','validate'):self.assertEqual(method(OLD/'engine.py','Engine',name),method(NEW/'engine.py','Engine',name))
    def test_12_checkpoint_same_bytes_methods_unchanged(self):
        for name in ('_bytes','read','save','receipt','reopen_owned'):
            self.assertEqual(method(OLD/'checkpoint.py','Store',name),method(NEW/'checkpoint.py','Store',name))
    def test_13_safe_pause_and_stop_unchanged(self):
        for name in ('claim_session','request_pause','pause_boundary'):
            self.assertEqual(method(OLD/'quota.py','Ledger',name),method(NEW/'quota.py','Ledger',name))
        treeold=ast.parse((OLD/'control.py').read_bytes());treenew=ast.parse((NEW/'control.py').read_bytes())
        for name in ('pause','open_owned_job','emergency_stop'):
            find=lambda t:ast.dump(next(n for n in t.body if isinstance(n,ast.FunctionDef) and n.name==name),include_attributes=False)
            self.assertEqual(find(treeold),find(treenew))
    def test_14_resource_logic_unchanged(self):
        self.assertEqual((OLD/'resources.py').read_bytes(),(NEW/'resources.py').read_bytes())
    def test_15_fixed_hash_and_bootstrap_seeds(self):
        self.assertIn("PYTHONHASHSEED='2026'",(NEW/'control.py').read_text())
        self.assertIn('default_rng(2026)',(NEW/'analysis.py').read_text())
        self.assertIn('manual_seed(SEED+epoch-1)',(NEW/'protocol.py').read_text())
    def test_16_no_historical_recovery_path(self):
        text=(NEW/'engine.py').read_text()
        self.assertNotIn('restore_authorized',text);self.assertNotIn('ORDER[3:]',text)
        self.assertIn('fresh_paired_models(SEED)',text)
        self.assertNotIn('Guard(', (NEW/'worker.py').read_text())
    def test_17_direct_ledger_creation_refused(self):
        from yuntapr.experimental.phase_b_v2_multiseed_candidate.quota import Ledger
        self.assertFalse(p.DB.exists())
        with self.assertRaisesRegex(PermissionError,'NOT_AUTHORIZED'):Ledger.initialize({'APPROVED':True})
        self.assertFalse(p.DB.exists());self.assertFalse(p.DB.with_suffix('.once').exists())
    def test_18_backup_covers_all_six_on_other_disk(self):
        r=json.loads((DOC/'BACKUP_VERIFICATION.json').read_bytes())
        self.assertEqual(r['status'],'SIX_FINAL_LAST_PHYSICAL_BACKUP_SHA_PASS')
        self.assertNotEqual(r['source_disk_number'],r['backup_disk_number'])
        self.assertEqual(len([f for f in r['files'] if f['payload']]),6)
        self.assertEqual(sum(f['bytes'] for f in r['files']),383597262)
    def test_19_reuse_source_hashes(self):
        for key,h in json.loads((DOC/'SOURCE_REUSE_INPUTS.json').read_bytes()).items():self.assertEqual(hashlib.sha256((ROOT/key).read_bytes()).hexdigest(),h)
    def test_20_no_heavy_import_or_execution(self):
        self.assertNotIn('torch',sys.modules)
        for seed in (2027,2028):
            db=ROOT/f'.git/phase_b_v2_seed{seed}_fresh_v1.sqlite'
            self.assertFalse(db.exists());self.assertFalse(db.with_suffix('.once').exists())
if __name__=='__main__':unittest.main(verbosity=2)
