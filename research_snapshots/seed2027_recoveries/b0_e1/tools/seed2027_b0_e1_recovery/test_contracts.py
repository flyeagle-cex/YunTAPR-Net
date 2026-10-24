"""Bounded stdlib regressions; no training, GPU, data or original ledger writes."""
import ast, copy, io, json, sqlite3, unittest
from pathlib import Path
from unittest.mock import patch
import operate
from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1 import accounting as a,protocol as p,ancestor as an,admission,control,authority,recovery

class Contracts(unittest.TestCase):
    def test_accounting_and_refusal(self):
        self.assertEqual(a.PRIOR_RESERVED+a.FRESH_CAP,370197)
        self.assertEqual(a.ADOPTED+a.FRESH_CAP,282312)
        self.assertEqual(a.COMBINED_CAP-364969,5228)
        a.validate(a.fields(a.FRESH_CAP,a.FRESH_CAP),complete_transaction=True)
        for n,v in ((a.FRESH_CAP+1,a.FRESH_CAP+1),(True,0),(1,2),(-1,0)):
            with self.assertRaises(ValueError):a.fields(n,v)
        q=a.fields(1,1);q['old_unverified_attempts']=0
        with self.assertRaises(ValueError):a.validate(q,complete_transaction=True)

    def test_headroom_blocks_before_claim(self):
        with patch.object(admission,'launch_headroom',return_value={'ready':False}),patch.object(control,'verify_release') as verify,patch.object(control.Ledger,'initialize') as initialize:
            with self.assertRaisesRegex(MemoryError,'NO_SESSION_CLAIMED'):control.start()
            verify.assert_not_called();initialize.assert_not_called()

    def test_human_and_path_scope(self):
        authority.require_execution_authority(2027)
        for seed in (2028,2026,True,'2027'):
            with self.assertRaises(PermissionError):authority.require_execution_authority(seed)
        for path in ('../x','2025/test.nc',str(p.LIVE_ROOT),'docs/x'):
            with self.assertRaises(PermissionError):an.lexical(path)
        self.assertNotEqual(p.ROOT,p.LIVE_ROOT)
        self.assertTrue(p.DB.is_relative_to(p.ROOT));self.assertTrue(p.LOCAL.is_relative_to(p.ROOT))
        self.assertNotIn(str(p.ROOT/'src'),p.BOOTSTRAP_PATH)
        self.assertFalse(authority.execution_instruction()['test_2025_authorized'])

    def test_metric_receipt_order_and_export(self):
        row={'train':{'x':[1,2]},'development':{'x':[3,4]}}
        payload={'train':copy.deepcopy(row['train']),'validation':copy.deepcopy(row['development'])}
        recovery.validate_history_metrics(row,payload)
        payload['train']['x'].reverse()
        with self.assertRaises(ValueError):recovery.validate_history_metrics(row,payload)
        self.assertTrue(callable(recovery.apply_validated_state))

    def test_unchanged_scientific_algorithms(self):
        old=p.LIVE_ROOT/'src/yuntapr/training/phase_b_v2_seed2027_b1_epoch7_recovery_v7'
        new=Path(an.__file__).parent
        def nodes(path):return ast.parse(path.read_text(encoding='utf-8'))
        def find(tree,name):return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
        for file,names in {'engine.py':['train','validate','cpu_tree','checked_output'],'evaluation.py':['__init__','finish'],
            'checkpoint.py':['validate','save','read','_bytes','reopen_owned'],'analysis.py':['compare'],
            'monitor.py':['monitor'],'resources.py':['check','cuda_admission','host_admission']}.items():
            for name in names:self.assertEqual(ast.dump(find(nodes(old/file),name)),ast.dump(find(nodes(new/file),name)),(file,name))
        self.assertEqual(p.LIMITS,__import__('yuntapr.training.phase_b_v2_seed2027_b1_epoch7_recovery_v7.protocol',fromlist=['LIMITS']).LIMITS)

    def test_source_ledger_exact_and_negative(self):
        con=sqlite3.connect(':memory:')
        try:
            con.executescript('CREATE TABLE campaign(id,status,reason);CREATE TABLE runs(id,ordinal,status,epoch,updates,last_sha);CREATE TABLE attempts(n,run,update_no,status);CREATE TABLE epochs(run,epoch,phase);CREATE TABLE sessions(n,status);')
            con.execute('INSERT INTO campaign VALUES(?,?,?)',(an.SOURCE_CAMPAIGN,'FAILED_NO_RETRY','GUI_OWNER_FAILED_NO_RETRY'))
            con.execute("INSERT INTO sessions VALUES(1,'ACTIVE')")
            for i,(m,arm) in enumerate(p.ORDER):
                ident=p.run_id(m,arm)
                con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(ident,i,'COMPLETE' if i<2 else 'RUNNING' if i==2 else 'PENDING',9 if i<2 else 1 if i==2 else 0,47052 if i<2 else 10456 if i==2 else 0,an.COMPLETE_LAST.get(ident,p.LAST_SHA if i==2 else None)))
            for r in an.COMPLETE_LAST:
                con.executemany('INSERT INTO epochs VALUES(?,?,?)',[(r,e,'LAST_COMMITTED') for e in range(1,10)])
            con.executemany('INSERT INTO epochs VALUES(?,?,?)',[(p.SOURCE_RUN,1,'LAST_COMMITTED'),(p.SOURCE_RUN,2,'WAIT_VALIDATION')])
            con.executemany('INSERT INTO attempts VALUES(?,?,?,?)',[(i,'B1_V2__E0__s2027',36596+i,'RETURNED_VERIFIED') for i in range(1,10457)]+[(10456+i,p.SOURCE_RUN,i,'RETURNED_VERIFIED') for i in range(1,10457)])
            an.verify_source(con)
            con.execute("UPDATE epochs SET phase='LAST_COMMITTED' WHERE run=? AND epoch=2",(p.SOURCE_RUN,))
            with self.assertRaises(ValueError):an.verify_source(con)
            con.execute("UPDATE epochs SET phase='WAIT_VALIDATION' WHERE run=? AND epoch=2",(p.SOURCE_RUN,))
            con.execute("UPDATE attempts SET status='RESERVED_BEFORE_CALL' WHERE n=20912")
            with self.assertRaises(ValueError):an.verify_source(con)
        finally:con.close()

    def test_streamed_read_accounting_and_truncation(self):
        from yuntapr.training.phase_b_v2_seed2027_b0_e1_recovery_v1.evidence import scan
        events=[dict(event='PUBLIC_METADATA_READ',bytes=7),dict(event='READ_RESERVED',file_key='x',opened_utc='z'),dict(event='READ_FINISHED',file_key='x',opened_utc='z',bytes=11)]
        raw=b''.join(json.dumps(e).encode()+b'\n' for e in events)
        row,_=scan(io.BytesIO(raw),event_log=True)
        self.assertEqual(row['content_bytes'],18);self.assertIsNone(row['trailing_read_reservation'])
        with self.assertRaises(ValueError):scan(io.BytesIO(raw[:-1]),event_log=True)

if __name__=='__main__':unittest.main(verbosity=2)
