"""Only the new read-only pipeline display; no training or inference fixtures."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('pipeline_monitor',ROOT/'tools/b2_monitor/server.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class PipelineMonitorTests(unittest.TestCase):
    def setUp(self):
        self.out=ROOT/'tests/research_readiness/.local'/('pipeline_'+uuid.uuid4().hex)
        self.out.mkdir(parents=True)
        self.write('binding.json',dict(at='2026-10-30T05:41:12+00:00'))
        runs=[dict(run_id=f'run{i}',model='B7',seed=2000+i,checkpoint_sha256='a'*64) for i in range(19)]
        self.write('registry.json',dict(runs=runs))
        self.write('private.json',dict(new_output_root=str(self.out),registry=str(self.out/'registry.json'),inherited={}))
        self.write('training.json',dict(output_root=str(self.out/'NOT_STARTED_CANDIDATE')))
        self.write('proposal.json',dict(tasks=[dict(model='B7_PERP_GRADIENT',seed=2029)],execution_code_commit='b'*40))
        self.write('config.json',dict(metric_private=str(self.out/'private.json'),training_private=str(self.out/'training.json'),training_proposal=str(self.out/'proposal.json'),metric_service_dir=str(self.out/'service')))

    def write(self,name,value):
        p=self.out/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_text(json.dumps(value),encoding='utf-8')

    def result(self,i,passed=True,actual=None):
        self.write(f'runs/run{i}/result.json',dict(status='COMPLETE' if passed else 'GATE_FAILED',checkpoint_identity=dict(sha256_actual=actual or 'a'*64,expected_sha256='a'*64),gate=dict(passed=passed,metrics={} if passed else dict(conditional_pinball=dict(passed=False,stored=.1,recomputed=.2)))))

    def snapshot(self):
        with patch.object(m.base,'process_token',return_value=None),patch.object(m.base,'resources',side_effect=AssertionError('Resources not requested')),patch.object(m.base,'query',side_effect=AssertionError('No candidate ledger exists')):
            return m.PipelineReader(self.out,123,self.out/'config.json').snapshot(include_resources=False)

    def test_failed_gate_blocks_unstarted_candidate_and_keeps_completed(self):
        self.result(0);self.result(1,False)
        self.write('failure.json',dict(at='2026-10-30T08:32:11+00:00',error='stop'))
        s=self.snapshot()
        self.assertEqual(s['metric_completed'],1);self.assertEqual(s['state'],'FAILED')
        self.assertEqual(s['metric_runs'][1]['state'],'GATE_FAILED')
        self.assertEqual(s['metric_runs'][1]['gate_failures'][0]['metric'],'conditional_pinball')
        self.assertEqual(s['candidate']['state'],'BLOCKED');self.assertEqual(s['candidate']['returned'],0)
        self.assertFalse((self.out/'NOT_STARTED_CANDIDATE').exists())

    def test_wrong_checkpoint_cannot_be_displayed_complete(self):
        self.result(0,actual='c'*64)
        self.assertEqual(self.snapshot()['metric_completed'],0)

    def test_metric_completion_is_not_training_completion_or_launch(self):
        for i in range(19):self.result(i)
        self.write('completion.json',dict(status='COMPLETE_19_E9_DEV_METRIC_BACKFILL'))
        s=self.snapshot()
        self.assertEqual(s['metric_state'],'COMPLETE');self.assertEqual(s['metric_completed'],19)
        self.assertEqual(s['candidate']['state'],'PENDING');self.assertEqual(s['candidate']['epochs'],[])
        self.assertNotEqual(s['state'],'COMPLETE')
        self.assertFalse((self.out/'NOT_STARTED_CANDIDATE').exists())

    def test_log_events_are_never_added_as_content_file_instances(self):
        self.result(0)
        p=self.out/'runs/run0/result.json';x=json.loads(p.read_text(encoding='utf-8'))
        x['read_scope_actual']=dict(read_events=900,content_bytes_read=123,meter_totals=dict(opened_files=4))
        p.write_text(json.dumps(x),encoding='utf-8')
        s=self.snapshot();self.assertEqual(s['recorded_metric_io']['files'],4)
        self.assertEqual(s['recorded_metric_io']['legacy_log_events'],900)


if __name__=='__main__':unittest.main()
