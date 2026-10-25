"""Targeted new-boundary tests; synthetic ledger only, no raw data or model."""
import ast,contextlib,copy,io,json,sqlite3,unittest,uuid
from pathlib import Path
from unittest.mock import patch
import operate
from yuntapr.training.phase_b_v2_seed2027_b1_e1_epoch6_recovery_v1 import protocol as p,accounting as a,ancestor as an,admission,control,authority,recovery,quota

def fixture(con):
    con.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE attempts(n,run,update_no,status);CREATE TABLE epochs(run,epoch,phase,train,validation,last_receipt);CREATE TABLE sessions(n,status);')
    con.execute('INSERT INTO campaign VALUES(?,?,?)',(an.SOURCE_CAMPAIGN,'FAILED_NO_RETRY','GUI_OWNER_FAILED_NO_RETRY'))
    con.execute("INSERT INTO sessions VALUES(1,'ACTIVE')")
    for i,(m,arm) in enumerate(p.ORDER):
        ident=p.run_id(m,arm)
        con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(ident,i,'COMPLETE' if i<3 else 'RUNNING' if i==3 else 'PENDING',9 if i<3 else 6 if i==3 else 0,47052 if i<3 else 36596 if i==3 else 0,an.COMPLETE_LAST.get(ident,p.LAST_SHA if i==3 else None)))
    rows=[(r,e,'LAST_COMMITTED',None,None,None) for r in an.COMPLETE_LAST for e in range(1,10)]
    rows.extend((p.SOURCE_RUN,e,'LAST_COMMITTED',None,None,None) for e in range(1,7))
    rows.append((p.SOURCE_RUN,7,'WAIT_VALIDATION',None,None,None))
    con.executemany('INSERT INTO epochs VALUES(?,?,?,?,?,?)',rows)
    con.executemany('INSERT INTO attempts VALUES(?,?,?,?)',[(i,'B0_MATCHED_V2__E1__s2027',5228+i,'RETURNED_VERIFIED') for i in range(1,41825)]+[(41824+i,p.SOURCE_RUN,i,'RETURNED_VERIFIED') for i in range(1,36597)])
    con.commit()

class Contracts(unittest.TestCase):
    def test_exact_budget_and_no_refund(self):
        self.assertEqual(a.PRIOR_RESERVED+a.FRESH_CAP,375425)
        self.assertEqual(a.ADOPTED+a.FRESH_CAP,282312)
        self.assertEqual(a.PRIOR_RESERVED-a.ADOPTED,93113)
        self.assertEqual(a.COMBINED_CAP-370197,5228)
        a.validate(a.fields(109788,109788),complete_transaction=True)
        for n,v in ((109789,109789),(True,0),(-1,0),(1,2)):
            with self.assertRaises(ValueError):a.fields(n,v)
        q=a.fields(1,1);q['old_unverified_attempts']=0
        with self.assertRaises(ValueError):a.validate(q,complete_transaction=True)

    def test_insufficient_headroom_never_claims_session(self):
        with patch.object(admission,'launch_headroom',return_value={'ready':False}),patch.object(control,'verify_release') as release,patch.object(quota.Ledger,'initialize') as initialize:
            with self.assertRaisesRegex(MemoryError,'NO_SESSION_CLAIMED'):control.start()
            release.assert_not_called();initialize.assert_not_called()

    def test_explicit_authority_and_root_isolation(self):
        authority.require_execution_authority(2027)
        for seed in (2028,2026,True,'2027'):
            with self.assertRaises(PermissionError):authority.require_execution_authority(seed)
        for name in ('../x','2025/data.nc','previous/.git/unknown.sqlite'):
            with self.assertRaises(PermissionError):an.lexical(name)
        self.assertNotEqual(p.ROOT,p.PREVIOUS_ROOT);self.assertNotEqual(p.ROOT,p.LIVE_ROOT)
        self.assertTrue(p.DB.is_relative_to(p.ROOT));self.assertTrue(p.LOCAL.is_relative_to(p.ROOT))
        self.assertEqual(authority.execution_instruction()['last_sha256'],p.LAST_SHA)
        self.assertEqual(authority.execution_instruction()['source_update'],31368)
        self.assertFalse(authority.execution_instruction()['test_2025_authorized'])

    def test_unchanged_numerical_and_resource_algorithms(self):
        old=p.PREVIOUS_ROOT/'recovery_overlay/yuntapr/training/phase_b_v2_seed2027_b0_e1_recovery_v1'
        new=Path(p.__file__).parent
        def node(path,name):return next(n for n in ast.walk(ast.parse(path.read_text(encoding='utf-8'))) if isinstance(n,ast.FunctionDef) and n.name==name)
        for file,names in {'engine.py':['train','validate','cpu_tree','checked_output'],'evaluation.py':['__init__','finish'],
            'checkpoint.py':['validate','save','read','_bytes','reopen_owned'],'analysis.py':['compare'],
            'monitor.py':['monitor'],'resources.py':['check','cuda_admission','host_admission'],'admission.py':['launch_headroom']}.items():
            for name in names:self.assertEqual(ast.dump(node(old/file,name)),ast.dump(node(new/file,name)),(file,name))
        from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.protocol import LIMITS
        self.assertEqual(p.LIMITS,LIMITS)

    def test_exact_failed_source_and_unsealed_epoch_rejected(self):
        con=sqlite3.connect(':memory:')
        try:
            fixture(con);an.verify_source(con)
            con.execute("UPDATE epochs SET phase='LAST_COMMITTED' WHERE run=? AND epoch=7",(p.SOURCE_RUN,))
            with self.assertRaises(ValueError):an.verify_source(con)
        finally:con.close()

    def test_adopt_33_epochs_and_first_replay_update_only_once(self):
        # Inherit the workspace ACL; Windows tempfile's mode 0700 denies the sandbox token.
        with contextlib.nullcontext(p.LOCAL/('artificial_'+uuid.uuid4().hex)) as root:
            root.mkdir()
            if not root.resolve().is_relative_to(p.LOCAL.resolve()):raise PermissionError('ARTIFICIAL_TEST_DIRECTORY_SCOPE')
            source=root/'artificial_source.sqlite';db=root/'artificial_new.sqlite'
            con=sqlite3.connect(source);fixture(con);con.close()
            release={'failed_ancestor_sha256':'f'*64,'completed_last_sha256':an.COMPLETE_LAST}
            with patch.object(p,'verify_release',return_value=release),patch.object(an,'Guard',side_effect=lambda _:contextlib.nullcontext()),patch.object(an,'source_database',return_value=source),patch.object(quota,'DB',db):
                ledger=quota.Ledger.initialize(release)
                try:
                    self.assertEqual(ledger.con.execute('SELECT count(*) FROM epochs').fetchone()[0],33)
                    self.assertEqual(ledger.run_row(p.SOURCE_RUN)['updates'],31368)
                    self.assertEqual(ledger.snapshot()['new_reserved'],0)
                    number,nonce=ledger.claim_session();self.assertEqual(number,1)
                    with self.assertRaises(PermissionError):ledger.claim_session()
                    ledger.begin_epoch(p.SOURCE_RUN,7)
                    self.assertEqual(ledger.reserve(p.SOURCE_RUN,31369),1)
                    ledger.returned(p.SOURCE_RUN,31369)
                    self.assertEqual(ledger.snapshot()['reserved'],265638)
                    ledger.fail('ARTIFICIAL_FAILURE')
                    with self.assertRaises(PermissionError):ledger.reserve(p.SOURCE_RUN,31370)
                    with self.assertRaises(PermissionError):ledger.claim_session()
                finally:ledger.close()

    def test_history_metric_order_and_exports(self):
        history={'train':{'v':[1,2]},'development':{'v':[3,4]}}
        payload={'train':copy.deepcopy(history['train']),'validation':copy.deepcopy(history['development'])}
        recovery.validate_history_metrics(history,payload)
        payload['train']['v'].reverse()
        with self.assertRaises(ValueError):recovery.validate_history_metrics(history,payload)
        self.assertTrue(callable(recovery.apply_validated_state))

if __name__=='__main__':unittest.main(verbosity=2)
