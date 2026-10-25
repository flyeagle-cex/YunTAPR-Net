"""Recovery-only regressions; CPU fixtures, no weather sources or optimizer step."""
import hashlib,io,json,sqlite3,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.core_innovation.stage3.metered_io import SourceMeter,MeasuredReader,IdentityConflict,path_key


class MeterFailureTests(unittest.TestCase):
    def meter(self,raw=b'expected'):
        db=sqlite3.connect(':memory:');p=path_key(REPO_ROOT/'tests/core_stage4/.local/synthetic-read.bin')
        m=SourceMeter(db,{p:dict(bytes=len(raw),sha=hashlib.sha256(raw).hexdigest())},max_files=1,max_bytes=len(raw))
        db.execute('INSERT INTO file_io VALUES (?,?,?,?,?,?)',(p,'INTENT',len(raw),0,None,1));db.commit()
        return db,m,p

    def test_io_error_keeps_original_exception_and_partial_receipt(self):
        class Broken(io.BytesIO):
            def read(self,*args):raise OSError(22,'synthetic detached source')
        db,m,p=self.meter()
        try:
            with self.assertRaisesRegex(OSError,'synthetic detached source'):
                with MeasuredReader(m,p,Broken()) as f:f.read()
            state,actual=db.execute('SELECT state,actual_bytes FROM file_io').fetchone()
            self.assertEqual((state,actual),('PARTIAL_UNCERTAIN',0))
        finally:db.close()

    def test_complete_wrong_content_remains_sha_conflict(self):
        db,m,p=self.meter(b'expected')
        try:
            with self.assertRaisesRegex(IdentityConflict,'SHA_CONFLICT'):
                with MeasuredReader(m,p,io.BytesIO(b'changed!')) as f:f.read()
            self.assertEqual(db.execute('SELECT state FROM file_io').fetchone()[0],'SHA_CONFLICT')
        finally:db.close()


def folder():
    p=REPO_ROOT/'tests/core_stage4/.local'/uuid.uuid4().hex;p.mkdir(parents=True);return p


class RecoveryTests(unittest.TestCase):
    def test_resume_offsets_and_uncertainty_never_reset(self):
        from yuntapr.experimental.core_innovation.stage4.recovery import RecoveryLedger
        path=folder()/'updates.sqlite';l=RecoveryLedger(path,{'fixture':True})
        try:
            with self.assertRaises(PermissionError):l.reserve('B3',1)
            l.reserve('B3',1441)
            with self.assertRaises(PermissionError):l.reserve('B3',1442)
            with self.assertRaises(PermissionError):l.reserve('B4',1)
            l.returned('B3',1441);l.reserve('B3',1442);l.returned('B3',1442)
            l.reserve('B4',1);l.returned('B4',1)
            with l.db:
                l.db.executemany('INSERT INTO updates VALUES (?,?,?)',[(m,u,'RETURNED') for m,start in (('B3',1441),('B4',1)) for u in range(start,4321) if (m,u) not in (('B3',1441),('B3',1442),('B4',1))])
            self.assertEqual(l.db.execute('SELECT COUNT(*) FROM updates').fetchone()[0],7200)
            with self.assertRaises(PermissionError):l.reserve('B4',4321)
            self.assertEqual(1920+7200,9120)
        finally:l.close()
        with self.assertRaises(PermissionError):RecoveryLedger(path,{})

    def test_missing_explicit_caps_cannot_open_source_or_optimizer(self):
        from yuntapr.experimental.core_innovation.stage4.recovery import execute,AUTH,READ_CAP,FILE_CAP
        with patch('yuntapr.experimental.core_innovation.stage4.recovery.verify_source',side_effect=AssertionError('No source read')):
            with self.assertRaises(PermissionError):execute('does-not-exist','unused',authorization_id=AUTH,approved_update_cap=8640,approved_read_cap=READ_CAP,approved_file_cap=FILE_CAP,root=REPO_ROOT)

    def test_one_source_verification_is_metered_and_cannot_retry(self):
        from yuntapr.experimental.core_innovation.stage4.recovery import verify_source,read
        p=folder();source=p/'synthetic.bin';raw=b'synthetic only';source.write_bytes(raw)
        request=dict(source=dict(path=str(source),year=2024,bytes=len(raw),sha=hashlib.sha256(raw).hexdigest()))
        result=verify_source(request,p,'SYNTHETIC_FIXTURE')
        self.assertEqual(result['raw_bytes_read'],len(raw))
        receipt=read(p/'source_verification_receipt.json')
        self.assertEqual(receipt['states'],{'READ_COMPLETE':1});self.assertEqual(receipt['delivered_bytes'],len(raw))
        # The execution marker is the outer one-shot gate; source verification
        # itself also refuses to overwrite its immutable receipt.
        with self.assertRaises(FileExistsError):verify_source(request,p,'SYNTHETIC_FIXTURE')

    def test_model_adamw_and_rng_restore_without_optimizer_step(self):
        import random,numpy as np,torch
        from yuntapr.experimental.core_innovation.stage4.recovery import ResumeState,write
        from yuntapr.experimental.core_innovation.stage3.planning import digest
        from yuntapr.training.phase_a_protocol import state_digest
        p=folder();model=torch.nn.Linear(2,1);opt=torch.optim.AdamW(model.parameters(),lr=1e-4,foreach=False)
        for param in model.parameters():opt.state[param]=dict(step=torch.tensor(1440.),exp_avg=torch.full_like(param,.2),exp_avg_sq=torch.full_like(param,.3))
        rng=dict(python=random.getstate(),numpy=np.random.get_state(),torch_cpu=torch.get_rng_state(),torch_cuda=[])
        payload=dict(identity={'data':{'fixture':True}},optimizer_groups={'fixture':True},epoch=3,updates=1440,
            scheduler=dict(completed=1440,steps_per_epoch=480,original_horizon=24000),model=model.state_dict(),optimizer=opt.state_dict(),rng=rng)
        torch.save(payload,p/'B3_LAST_epoch_03.pt')
        for e in (1,2,3):
            report={'fixture_epoch':e};write(p/f'B3_development_{e:02d}.json',report);write(p/f'B3_LAST_epoch_{e:02d}.receipt.json',{'validation_receipt_sha256':digest(report)})
        restored=torch.nn.Linear(2,1);restored_opt=torch.optim.AdamW(restored.parameters(),lr=1e-4,foreach=False)
        state=ResumeState(dict(parent=str(p),data_identity={'fixture':True}))
        with patch('torch.cuda.set_rng_state_all') as cuda,patch.object(restored_opt,'step',side_effect=AssertionError('No optimizer update')):
            u,reports=state.restore('B3',restored,restored_opt,{'fixture':True})
        self.assertEqual((u,len(reports)),(1440,3));self.assertEqual(state_digest(model.state_dict()),state_digest(restored.state_dict()))
        self.assertEqual(state_digest(opt.state_dict()),state_digest(restored_opt.state_dict()));self.assertTrue(torch.equal(torch.get_rng_state(),rng['torch_cpu']));cuda.assert_called_once_with([])

