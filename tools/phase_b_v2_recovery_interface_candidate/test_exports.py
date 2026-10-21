"""Reproduce real missing imports using fake reports; no torch/data/model IO."""
from pathlib import Path
from contextlib import nullcontext
from types import ModuleType,SimpleNamespace
from unittest.mock import patch
import ast,difflib,hashlib,json,sys,unittest
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v5 import ancestor as failed
from yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v4 import ancestor as previous
from yuntapr.experimental.phase_b_v2_recovery_interface_candidate.exports import NAMES,inherited_exports,missing_imports,proposed_source

FOLDER=ROOT/'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v5'
OUT=ROOT/'docs/phase_b_v2_formal_execution/seed2027_b1_epoch7_recovery_v5/postmortem_20261021'
OUT.mkdir(exist_ok=True)
SOURCES={p.name:p.read_text(encoding='utf-8') for p in FOLDER.glob('*.py')}
BEFORE={k:hashlib.sha256(v.encode()).hexdigest() for k,v in SOURCES.items()}


def fixture_module():
    package=ModuleType('artificial_interface_fixture');package.__path__=[]
    module=ModuleType(package.__name__+'.ancestor');module.__dict__.update(vars(failed));module.__dict__.update(inherited_exports(previous))
    return package,module


class Tests(unittest.TestCase):
    def test_01_actual_failure_includes_three_missing_bindings(self):
        issues=missing_imports(SOURCES,vars(failed))
        self.assertEqual(issues,{'engine.py':['COMPLETE_PREFIX'],'recovery.py':['RECOVERY_PREFIX','SOURCE_CP']})
    def test_02_all_ancestor_imports_satisfied_in_candidate(self):
        _,module=fixture_module()
        self.assertEqual(missing_imports(SOURCES,vars(module)),{})
        for name in NAMES:self.assertEqual(getattr(module,name),getattr(previous,name))
    def test_03_real_completed_result_function_with_artificial_receipt(self):
        package,module=fixture_module();ident='B0_MATCHED_V2__E0__s2027'
        report={'run_id':ident,'status':'COMPLETE','artificial_fixture':True}
        module.Guard=lambda sha:nullcontext(SimpleNamespace(pool=SimpleNamespace(metadata={module.COMPLETE_PREFIX+ident+'.json':report})))
        function=next(node for node in ast.parse(SOURCES['engine.py']).body if isinstance(node,ast.FunctionDef) and node.name=='completed_result')
        env=dict(__package__=package.__name__,ORDER=(('B0_MATCHED_V2','E0'),),run_id=lambda *args:ident,
                 verify_release=lambda:{'failed_ancestor_sha256':'a'*64})
        with patch.dict(sys.modules,{package.__name__:package,package.__name__+'.ancestor':module}):
            exec(compile(ast.Module(body=[function],type_ignores=[]),'<actual-completed-result-artificial-input>','exec'),env)
            self.assertIs(env['completed_result'](ident),report)
    def test_04_real_recovery_import_statement_succeeds_without_weights(self):
        package,module=fixture_module()
        node=next(node for node in ast.walk(ast.parse(SOURCES['recovery.py'])) if isinstance(node,ast.ImportFrom) and node.module=='ancestor' and node.level==1)
        env={'__package__':package.__name__}
        with patch.dict(sys.modules,{package.__name__:package,package.__name__+'.ancestor':module}):
            exec(compile(ast.Module(body=[node],type_ignores=[]),'<actual-recovery-import>','exec'),env)
        self.assertEqual(env['PREFIX'],previous.RECOVERY_PREFIX);self.assertEqual(env['CP'],previous.SOURCE_CP)
    def test_05_only_three_alias_assignments_no_authority_change(self):
        old=ast.parse(SOURCES['ancestor.py']);new=ast.parse(proposed_source(SOURCES['ancestor.py']))
        self.assertEqual([ast.dump(n) for n in new.body[:-3]],[ast.dump(n) for n in old.body])
        self.assertEqual([n.targets[0].id for n in new.body[-3:]],list(NAMES))
    def test_06_formal_source_untouched_no_model(self):
        self.assertNotIn('torch',sys.modules)
        self.assertEqual(BEFORE,{k:hashlib.sha256((FOLDER/k).read_text(encoding='utf-8').encode()).hexdigest() for k in SOURCES})


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    diff=''.join(difflib.unified_diff(SOURCES['ancestor.py'].splitlines(True),proposed_source(SOURCES['ancestor.py']).splitlines(True),
        fromfile='a/src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v5/ancestor.py',
        tofile='b/FUTURE_SEPARATELY_RELEASED_ANCESTOR/ancestor.py'))
    with (OUT/'MINIMUM_INTERFACE_FIX.diff').open('x',encoding='utf-8',newline='\n') as f:f.write(diff)
    row=dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
             pass_all=result.wasSuccessful(),formal_sources_modified=False,new_optimizer_steps=0,
             checkpoint_payload_reads=0,new_raw_data_reads=0,launch_performed=False,missing_bindings=list(NAMES))
    with (OUT/'INTERFACE_REGRESSION_RESULT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(row,f,indent=2)
    raise SystemExit(not result.wasSuccessful())
