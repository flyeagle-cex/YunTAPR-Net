"""Exercise actual consumers without model construction, data reads or updates."""
from pathlib import Path
from types import ModuleType,SimpleNamespace
from contextlib import nullcontext
from unittest.mock import patch
import ast,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6 import ancestor as a,protocol as p
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v6'

def names(target):
    if isinstance(target,ast.Name):return {target.id}
    if isinstance(target,(ast.Tuple,ast.List)):return set().union(*(names(x) for x in target.elts))
    return set()

def exports(tree):
    result=set()
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):result.add(node.name)
        elif isinstance(node,ast.Import):result.update(n.asname or n.name.split('.')[0] for n in node.names)
        elif isinstance(node,ast.ImportFrom):result.update(n.asname or n.name for n in node.names)
        elif isinstance(node,ast.Assign):
            for target in node.targets:result.update(names(target))
        elif isinstance(node,ast.AnnAssign):result.update(names(node.target))
    return result

class Tests(unittest.TestCase):
    def test_01_all_function_local_relative_imports_have_actual_source_bindings(self):
        trees={f.stem:ast.parse(f.read_text(encoding='utf-8')) for f in NEW.glob('*.py')}
        supplied={name:exports(tree) for name,tree in trees.items()}
        for file,tree in trees.items():
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom) and node.level==1 and node.module in supplied:
                    for item in node.names:self.assertIn(item.name,supplied[node.module],file+' -> '+node.module+'.'+item.name)
    def test_02_completed_result_uses_the_original_pinned_namespace(self):
        ident=p.run_id(*p.ORDER[0]);report=dict(run_id=ident,status='COMPLETE',artificial_only=True)
        pkg=ModuleType('artificial_v6_consumer');pkg.__path__=[]
        fake=ModuleType(pkg.__name__+'.ancestor');fake.__dict__.update(vars(a))
        fake.Guard=lambda value:nullcontext(SimpleNamespace(pool=SimpleNamespace(metadata={a.COMPLETE_PREFIX+ident+'.json':report})))
        function=next(x for x in ast.parse((NEW/'engine.py').read_text(encoding='utf-8')).body if isinstance(x,ast.FunctionDef) and x.name=='completed_result')
        env=dict(__package__=pkg.__name__,run_id=p.run_id,ORDER=p.ORDER,verify_release=lambda:{'failed_ancestor_sha256':'a'*64})
        with patch.dict(sys.modules,{pkg.__name__:pkg,pkg.__name__+'.ancestor':fake}):
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual-v6-completed-result>','exec'),env)
            self.assertIs(env['completed_result'](ident),report)
    def test_03_actual_recovery_imports_resolve_before_opening_any_checkpoint(self):
        tree=ast.parse((NEW/'recovery.py').read_text(encoding='utf-8'))
        statement=next(x for x in ast.walk(tree) if isinstance(x,ast.ImportFrom) and x.level==1 and x.module=='ancestor')
        env={'__package__':'yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v6'}
        exec(compile(ast.Module(body=[statement],type_ignores=[]),'<actual-v6-recovery-import>','exec'),env)
        self.assertEqual(env['PREFIX'],a.RECOVERY_PREFIX);self.assertEqual(env['CP'],a.SOURCE_CP);self.assertEqual(env['RUN'],p.SOURCE_RUN)
    def test_04_monitor_has_a_real_fixed_gui_entry_and_current_commands(self):
        folder=ROOT/'scripts/phase_b_v2_live_monitor_b1_epoch7_v6'
        self.assertTrue((folder/'Task-View.py').is_file())
        self.assertIn('53087',(folder/'server.py').read_text(encoding='utf-8'))
        self.assertIn('phase_b_v2_seed2027_b1_epoch7_recovery_v6',(folder/'app.html').read_text(encoding='utf-8'))
        self.assertNotIn('phase_b_v2_live_monitor_b1_epoch7_v5',(folder/'app.html').read_text(encoding='utf-8'))
    def test_05_no_model_data_or_training_call(self):
        self.assertNotIn('torch',sys.modules);self.assertFalse(p.DB.exists())

if __name__=='__main__':unittest.main(verbosity=2)
