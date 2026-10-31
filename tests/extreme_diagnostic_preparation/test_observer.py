"""Saved-output-only observer: no scientific source or model fixture."""
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from tools.research_readiness import observe_extreme_diagnostic as observer


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.local=self.root/'docs/research_readiness/.local';self.local.mkdir(parents=True)
        self.public=self.root/'docs/research_readiness/proposal';self.public.mkdir()
        self.folder=self.local/'package';self.folder.mkdir();self.service=self.local/'observer';self.service.mkdir()
        self.p=dict(tasks=list(observer.TASKS),final_2025_access=False,execution_code_commit='a'*40,
            budget=dict(prior_metadata_archive_charge_bytes=64,metadata_archive_cap_bytes=1216,cumulative_source_reservation_cap_bytes=5000))
        self.p['proposal_sha256']=observer.digest(self.p)
        self.proposal=self.public/'proposal.json';self.write(self.proposal,self.p)
        self.private=self.local/'private.json';self.write(self.private,dict(output_root=str(self.folder),proposal_sha256=self.p['proposal_sha256']))
        self.approval=self.local/'approval.json';self.write(self.approval,dict(approved_by_researcher=True,scope='SYNTHETIC_OBSERVER_ONLY'))
        self.write(self.folder/'binding.json',dict(proposal_sha256=self.p['proposal_sha256'],code_commit='a'*40,approval_sha256=observer.sha(self.approval),controller_pid=0,absolute_wall_deadline=time.time()+60))
        self.config=self.local/'observer.json';self.write(self.config,dict(proposal=str(self.proposal),private_preparation=str(self.private),approval=str(self.approval),service_dir=str(self.service),executor_service_dir=str(self.local/'executor_service'),receipt_relative_path='docs/research_readiness/proposal/launch/completion_observation.json'))
        self.reader=observer.Reader(self.config,root=self.root,process_token=lambda pid:1)

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

    def test_only_sealed_task_counts_as_complete(self):
        self.write(self.folder/'TRAIN_LABELS/task_complete.json',dict(verified_sha256='wrong',accounting={}))
        self.assertEqual(self.reader.snapshot()['tasks_complete'],0)
        path=self.folder/'TRAIN_LABELS/verified.json';self.write(path,dict(status='SYNTHETIC'))
        self.write(path.parent/'task_complete.json',dict(verified_sha256=observer.sha(path),accounting=dict(payload_reserved_bytes={'labels':3},metadata_archive_reserved_bytes=4,metadata_open_instances=1)))
        status=self.reader.snapshot();self.assertEqual(status['tasks_complete'],1);self.assertEqual(status['models_complete'],0)
        self.assertEqual(status['known_sealed_or_failed_reservations']['cumulative_known_archive_bytes'],71)
        self.assertNotIn(str(self.root),json.dumps(status))

    def test_incomplete_chunk_is_not_counted_and_array_is_never_opened(self):
        folder=self.folder/'B7_s2029/joint';folder.mkdir(parents=True)
        (folder/'chunk_0000.npz').write_bytes(b'NOT_A_REAL_ARRAY_DO_NOT_READ')
        (folder/'chunks.jsonl').write_text(json.dumps(dict(state='COMPLETE',scenes=8))+chr(10)+'{"state":',encoding='utf-8')
        self.assertEqual(self.reader.chunks('B7_s2029'),(8,True))
        with self.assertRaises(PermissionError):self.reader.document(folder/'chunk_0000.npz')
        with self.assertRaises(PermissionError):self.reader.document(self.root/'outside.json')

    def test_wrong_binding_and_outside_namespace_are_rejected(self):
        binding=json.loads((self.folder/'binding.json').read_text());binding['approval_sha256']='changed'
        self.write(self.folder/'binding.json',binding)
        with self.assertRaises(PermissionError):observer.Reader(self.config,root=self.root,process_token=lambda pid:1)
        self.write(self.private,dict(output_root=str(self.root/'outside'),proposal_sha256=self.p['proposal_sha256']))
        with self.assertRaises(PermissionError):observer.Reader(self.config,root=self.root,process_token=lambda pid:1)

    def test_failure_is_terminal_without_scientific_acceptance(self):
        self.write(self.folder/'failure.json',dict(error_type='SyntheticError',details='PRIVATE_DETAIL_NOT_PUBLIC'))
        status=self.reader.snapshot();self.assertEqual(status['state'],'FAILED_NO_RETRY')
        self.assertEqual(status['scientific_acceptance'],'PENDING_RESEARCHER_REVIEW')
        self.assertNotIn('PRIVATE_DETAIL_NOT_PUBLIC',json.dumps(status))

    def test_unknown_process_query_is_not_evidence_of_exit(self):
        self.reader.process_token=lambda pid:None
        self.assertEqual(self.reader.snapshot()['state'],'UNKNOWN_PROCESS_STATE')
        self.write(self.local/'executor_service/target_exit.json',dict(return_code=1))
        self.assertEqual(self.reader.snapshot()['state'],'STOPPED_WITHOUT_TERMINAL_RECEIPT')

    def test_publication_state_does_not_expose_private_errors(self):
        self.write(self.service/'terminal_sync_failure.json',dict(details='PRIVATE_ERROR_PATH'))
        snapshot=self.reader.snapshot();self.assertEqual(snapshot['publication']['state'],'STOP_PUBLICATION_NO_RETRY')
        self.assertNotIn('PRIVATE_ERROR_PATH',json.dumps(snapshot))

    def test_http_methods_are_read_only(self):
        with ThreadingHTTPServer(('127.0.0.1',0),observer.handler(self.reader)) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url=f'http://127.0.0.1:{server.server_port}'
                with urlopen(url+'/api/status',timeout=2) as response:self.assertTrue(json.load(response)['read_only'])
                with urlopen(url+'/',timeout=2) as response:
                    html=response.read().decode('utf-8');self.assertIn('YunTAPR-Net',html);self.assertNotIn(str(self.root),html)
                for method in ('POST','PUT','DELETE','PATCH'):
                    with self.subTest(method=method),self.assertRaises(HTTPError) as context:urlopen(Request(url+'/',method=method),timeout=2)
                    self.assertEqual(context.exception.code,405)
            finally:server.shutdown();thread.join(timeout=2)

    def test_terminal_publication_refuses_a_changed_branch_and_keeps_receipt(self):
        self.write(self.folder/'failure.json',dict(error_type='SyntheticError'))
        (self.public/'launch').mkdir()
        with patch.object(observer,'git',return_value='different-branch'):
            with self.assertRaises(PermissionError):observer.publish_terminal(self.reader,self.reader.snapshot())
        receipt=json.loads((self.public/'launch/completion_observation.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['state'],'FAILED_NO_RETRY');self.assertNotIn(str(self.root),json.dumps(receipt))


if __name__=='__main__':unittest.main()
