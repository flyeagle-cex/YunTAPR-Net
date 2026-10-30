"""New physical-control grant and dependency paths only; no torch or sources."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('physical_control_execution',ROOT/'tools/research_readiness/start_dote_physical_control.py')
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


class ExecutionTests(unittest.TestCase):
    def package(self):
        p=dict(execution_code_commit='c'*40,tasks=[dict(model=m.CONTROL,seed=2029)],
               scientific_choices=dict(negative_control=dict(rotation_matrix_east_north=[[0,-1],[1,0]])),
               budget=dict(total_source_bytes=477571953840,total_updates=4320,total_source_files=142813,
                           max_package_seconds=21600,replay_allowance=0,additional_retry_allowance=0))
        p['proposal_sha256']=m.digest(p);v=dict(output_root='NEW_UNUSED_OUTPUT')
        a=dict(approved_by_researcher=True,decision_id='synthetic_test_only',code_commit=p['execution_code_commit'],
               proposal_sha256=p['proposal_sha256'],tasks=p['tasks'],scientific_choices=p['scientific_choices'],budget=p['budget'],output_root=v['output_root'])
        return a,p,v
    def test_exact_bound_candidate(self):
        a,p,v=self.package();m.validate(a,p,v,'c'*40)
    def test_unapproved_or_wrong_commit_rejected(self):
        a,p,v=self.package();a['approved_by_researcher']=False
        with self.assertRaises(PermissionError):m.validate(a,p,v,'c'*40)
        a,p,v=self.package()
        with self.assertRaises(PermissionError):m.validate(a,p,v,'d'*40)
    def test_zero_control_cannot_consume_physical_grant(self):
        a,p,v=self.package();p['tasks'][0]['model']='B7_ZERO_DOTE';p['proposal_sha256']=m.digest({k:x for k,x in p.items() if k!='proposal_sha256'});a['proposal_sha256']=p['proposal_sha256']
        with self.assertRaises(PermissionError):m.validate(a,p,v,'c'*40)
    def test_no_changed_rotation_or_replay(self):
        for change in ('rotation','replay'):
            a,p,v=self.package()
            if change=='rotation':p['scientific_choices']['negative_control']['rotation_matrix_east_north']=[[1,0],[0,1]]
            else:p['budget']['replay_allowance']=1
            p['proposal_sha256']=m.digest({k:x for k,x in p.items() if k!='proposal_sha256'});a['proposal_sha256']=p['proposal_sha256']
            with self.assertRaises(ValueError):m.validate(a,p,v,'c'*40)


if __name__=='__main__':unittest.main()
