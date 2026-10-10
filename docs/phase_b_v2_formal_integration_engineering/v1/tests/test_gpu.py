"""EXPLICIT campaign: four updates maximum, two fresh replays per model."""
import gc
import json
import time
import unittest
import torch
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec
from yuntapr.experimental.phase_b_v2_integration.initialization import seeded_environment
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.engine import IntegratedEngine
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.protocol import OUT, FLAGS, SCOPE
from yuntapr.experimental.phase_b_v2_formal_integration_candidate.state import ActualQuota

class GPUIntegration(unittest.TestCase):
    def exercise(self,model):
        records=[]
        # B0's first update is already consumed by the recorded save/read failure.
        # Its exact synthetic state was inspected without restoring or updating.
        first_failure=json.loads((OUT/'tests'/'first_failure_state.json').read_text()) if model=='B0_MATCHED_V2' else None
        for replay in ((1,) if first_failure else range(2)):
            with seeded_environment(2026):
                torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats();start=time.perf_counter()
                engine=IntegratedEngine(RunSpec('E0',model,2026))
                train=engine.train_epoch();report,reference=engine.validate_and_commit()
                before=engine.state_identity();sha=json.loads(reference.read_text())['sha256']
                restored=engine.restore_completed_last(reference,sha)
                self.assertEqual(before,restored)
                self.assertEqual(report['summary']['scenes'],2);self.assertEqual(report['summary']['n_valid'],6860)
                self.assertEqual(engine.schedule.completed,1);self.assertIsNone(engine.selected_endpoint()['selected_synthetic_epoch'])
                torch.cuda.synchronize()
                records.append(dict(replay=replay,state=before,initial_sha=engine.initial_sha,train=train,
                    seconds=time.perf_counter()-start,peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                    peak_reserved_bytes=torch.cuda.max_memory_reserved(),resources=engine.resources,
                    last_sha=sha,validation_receipt=report['receipt_sha'],synthetic_summary=report['summary'],quota=engine.quota.report()))
                # Persist each completed update/test path before continuing, no retry.
                (OUT/'tests'/f'gpu_{model}.json').write_bytes((json.dumps({'scope':SCOPE,'records':records,**FLAGS},indent=2)+'\n').encode())
                engine.state.close();engine.quota.con.close();del engine;gc.collect();torch.cuda.empty_cache()
        baseline=first_failure or records[0]
        self.assertEqual(baseline['state'],records[-1]['state'])
        self.assertEqual(baseline['initial_sha'],records[-1]['initial_sha'])
        if not first_failure:self.assertEqual(records[0]['train'],records[1]['train'])
    def test_b0_replay(self):self.exercise('B0_MATCHED_V2')
    def test_b1_replay(self):self.exercise('B1_V2')

if __name__=='__main__':unittest.main(failfast=True)
