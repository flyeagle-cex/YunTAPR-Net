"""Only the new E5 candidate recovery guards; no GPU, model or real data reads."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('physical_recovery',ROOT/'tools/research_readiness/start_dote_physical_recovery.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class RecoveryTests(unittest.TestCase):
    def package(self):
        scope=dict(Train=dict(bytes_per_pass=26424262556,file_count=7918),Development=dict(bytes_per_pass=26639253112,file_count=7950))
        caps=m.budget(scope,dict(reserved_logical_bytes=296916674513,delivered_logical_bytes=296911969264,opened_content_instances=88924),4705249)
        p=dict(tasks=[dict(model=m.CONTROL,seed=2029)],checkpoint=dict(epoch=5,updates=2400,sha256='a'*64),execution_code_commit='c'*40,scientific_choices={},budget=caps,proposal_sha256='d'*64)
        v=dict(output_root='UNUSED_SYNTHETIC_OUTPUT')
        a=dict(approved_by_researcher=True,code_commit='c'*40,decision_id='SYNTHETIC_ONLY',proposal_sha256=p['proposal_sha256'],tasks=copy.deepcopy(p['tasks']),scientific_choices={},budget=copy.deepcopy(caps),output_root=v['output_root'],approved_checkpoint_sha256='a'*64,approved_replay_updates=480)
        return a,p,v
    def test_budget_includes_four_epochs_static_verification_and_uncertainty(self):
        a,p,v=self.package();b=p['budget']
        self.assertEqual((b['total_source_bytes'],b['total_source_files'],b['cumulative_reserved_source_bytes']),(212259080749,63474,509175755262))
        self.assertEqual((b['new_updates'],b['replayed_updates'],b['cumulative_attempts']),(1920,480,4800))
        m.validate_approval(a,p,v,'c'*40)
    def test_missing_or_changed_grant_seed_checkpoint_replay_rejected(self):
        for change in ('missing','seed','checkpoint','replay','time','commit'):
            a,p,v=self.package()
            if change=='missing':a['approved_by_researcher']=False
            if change=='seed':p['tasks'][0]['seed']=2030
            if change=='checkpoint':p['checkpoint']['epoch']=6
            if change=='replay':a['approved_replay_updates']=0
            if change=='time':a['budget']['max_package_seconds']=21600
            if change=='commit':a['code_commit']='b'*40
            with self.subTest(change=change),self.assertRaises(PermissionError):m.validate_approval(a,p,v,'c'*40)
    def test_wall_pause_expires_even_when_monotonic_has_not_advanced(self):
        deadline=m.Deadline(100,200,10800)
        with patch.object(m.time,'time',return_value=10901),patch.object(m.time,'monotonic',return_value=201):
            with self.assertRaisesRegex(RuntimeError,'deadline'):deadline()
        with patch.object(m.time,'time',return_value=99),patch.object(m.time,'monotonic',return_value=201):
            with self.assertRaisesRegex(RuntimeError,'rollback'):deadline()
    def test_wait_checks_wall_every_two_seconds_without_retrying_process(self):
        class Child:
            calls=[]
            def wait(self,timeout):
                self.calls.append(timeout)
                if len(self.calls)==1:raise m.subprocess.TimeoutExpired('SYNTHETIC',timeout)
                return 1
        child=Child()
        with patch.object(m.time,'time',return_value=100),patch.object(m.time,'monotonic',return_value=200):
            self.assertEqual(m.wait_bounded(child,m.Deadline(100,200,10800)),1)
        self.assertEqual(child.calls,[2,2])
    def test_reader_scope_before_any_source_open(self):
        for role,e,name in [('Final',6,'B7_dev_reads_06'),('Train',5,'B7_train_reads_05'),('Train',10,'B7_train_reads_10'),('Train',6,'B8_train_reads_06')]:
            with self.subTest(role=role,e=e,name=name),self.assertRaises(PermissionError):m.validate_pass(role,e,name)
        m.validate_pass('Train',6,'B7_train_reads_06');m.validate_pass('Development',9,'B7_dev_reads_09')
    def test_restore_targets_E5_and_reuses_full_optimizer_scheduler_rng_loader(self):
        from yuntapr.experimental.core_innovation.stage4 import recovery as base
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp);weight=parent/'B7_LAST_epoch_05.pt';weight.write_bytes(b'SYNTHETIC_NOT_MODEL')
            for e in range(1,6):m.write(parent/f'B7_development_{e:02d}.json',dict(epoch=e))
            state=m.PhysicalResume(dict(parent=str(parent),checkpoint_sha256=m.sha(weight),data_identity={'data':'fixture'}))
            with patch.object(base,'restore_last') as restore:
                u,reports=state.restore('B7',object(),object(),{})
            self.assertEqual((u,len(reports)),(2400,5));restore.assert_called_once()
            self.assertEqual(restore.call_args.kwargs,dict(data_identity={'data':'fixture'},epoch=5,updates=2400,kind='B7',seed=2029))
            with self.assertRaises(PermissionError):state.completed_epochs('B8')
    def test_recovery_ledger_offset_cap_and_uncertain_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=m.PhysicalResume(dict(parent=tmp));ledger=state.ledger(Path(tmp)/'updates.sqlite',{})
            with self.assertRaises(PermissionError):ledger.reserve('B7',2881)
            for u in range(2401,4321):ledger.reserve('B7',u);ledger.returned('B7',u)
            with self.assertRaises(PermissionError):ledger.reserve('B7',4321)
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM updates').fetchone()[0],1920);ledger.close()
    def test_E9_closeout_inherits_five_epochs_and_rejects_partial_new_pass(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);old=base/'old';old.mkdir();new=base/'new';new.mkdir();_,p,_=self.package();p['data']={'fixture':'2024_ONLY'};p['checkpoint']['parent_commit']='b'*40
            with sqlite3.connect(new/'updates.sqlite') as db:
                db.execute('CREATE TABLE updates(model TEXT,state TEXT,u INTEGER)')
                db.executemany('INSERT INTO updates VALUES (?,?,?)',[('B7','RETURNED',u) for u in range(2401,4321)])
            db.close()
            for e in range(1,6):m.write(old/f'B7_LAST_epoch_{e:02d}.receipt.json',dict(epoch=e))
            for e in range(6,10):
                dev=dict(source_identity=p['data']);seal=dict(epoch=e,updates=e*480,code_commit='c'*40,validation_receipt_sha256=m.digest(dev))
                for name,value in [(f'B7_train_{e:02d}.json',dict(updates=e*480)),(f'B7_development_{e:02d}.json',dev),(f'B7_LAST_epoch_{e:02d}.receipt.json',seal),(f'B7_tail_{e:02d}.json',{})]:m.write(new/name,value)
                (new/f'B7_LAST_epoch_{e:02d}.pt').write_bytes(b'SYNTHETIC_ONLY')
                for role,n,b in [('train',7918,26424262556),('dev',7950,26639253112)]:
                    sub=new/f'B7_{role}_reads_{e:02d}';sub.mkdir()
                    m.write(sub/'pass_receipt.json',dict(during_failure=False,expected_files=n,expected_bytes=b,actual_reads=dict(opened_files=n,delivered_bytes=b,reserved_bytes=b,states={'READ_COMPLETE':n})))
            result=m.close_segment(new,old,p,'c'*40)
            self.assertEqual((result['epochs'],len(result['checkpoints']),result['segment_updates'],result['replay_updates']),(9,9,1920,480))
            path=new/'B7_dev_reads_09/pass_receipt.json';r=m.read(path);r['during_failure']=True;path.write_text(m.json.dumps(r))
            with self.assertRaisesRegex(RuntimeError,'pass incomplete'):m.close_segment(new,old,p,'c'*40)

if __name__=='__main__':unittest.main()
