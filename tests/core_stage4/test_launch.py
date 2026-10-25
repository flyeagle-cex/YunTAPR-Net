import contextlib,importlib.util,io,json,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import torch
from yuntapr.contracts.loader import REPO_ROOT
from yuntapr.experimental.core_innovation.stage4 import launch
from yuntapr.experimental.core_innovation.stage4.data import BatchReader,read
from yuntapr.experimental.core_innovation.stage3.metered_io import path_key


def tiny_plan(root):
    plan=SimpleNamespace(root=root,rows={},sat={},gfs={},sources={})
    for role,dates in (('Train',('2023-05-01T05:30:00+00:00','2023-05-01T11:30:00+00:00')),('Development',('2024-05-01T05:30:00+00:00','2024-05-02T05:30:00+00:00'))):
        plan.rows[role]={}
        for j,sid in enumerate(dates):
            year=int(sid[:4]);analysis=sid.replace('05:30','06:00').replace('11:30','12:00');row=dict(analysis_time=analysis,imerg_sha256='1'*64)
            for i in range(6):
                nominal=f'{role}_{j}_{i}';p=str(root/f'{nominal}.nc');row[f'slot_{i}_nominal']=nominal
                plan.sat[nominal]=(p,{});plan.sources[p]=dict(bytes=100,sha='0'*64,year=year)
            plan.gfs[analysis]={k:str(root/f'{role}_{j}_{k}.nc') for k in ('main','thermo')}
            for p in plan.gfs[analysis].values():plan.sources[p]=dict(bytes=20,sha='2'*64,year=year)
            plan.rows[role][sid]=row
    plan.ids=lambda role:tuple(plan.rows[role]);return plan


class LaunchTests(unittest.TestCase):
    def test_inventory_and_pair_budget_no_raw_access(self):
        folder=REPO_ROOT/'tests/core_stage4/.local'/uuid.uuid4().hex;folder.mkdir(parents=True)
        (folder/'inventory.csv').write_text('relative_path,date,year,size_bytes\n2023\\imerg_20230501.nc,2023-05-01,2023,300\n2024\\imerg_20240501.nc,2024-05-01,2024,400\n2024\\imerg_20240502.nc,2024-05-02,2024,500\n',encoding='utf-8')
        plan=tiny_plan(folder);mask=(str(folder/'mask.nc'),dict(bytes=40,sha='3'*64,year=2023,kind='static_mask'))
        original=Path.open
        def no_raw(p,*a,**k):
            if p.suffix=='.nc':raise AssertionError('Budget calculation opened raw source')
            return original(p,*a,**k)
        with patch.object(launch,'INVENTORY','inventory.csv'),patch.object(Path,'open',no_raw):
            index=launch.target_index(plan);roles={r:launch.source_scope(plan,r,index,mask) for r in plan.rows}
            b=launch.summarize_scopes(roles)
        self.assertEqual(roles['Train']['file_count'],18);self.assertEqual(roles['Development']['file_count'],19)
        self.assertEqual(roles['Train']['bytes_per_pass'],1620);self.assertEqual(roles['Development']['bytes_per_pass'],2220)
        self.assertEqual(b['logical_raw_bytes'],69120);self.assertEqual(b['logical_source_read_instances'],666)
        self.assertEqual(b['unique_source_files'],36);self.assertFalse(b['cache_over_limit'])

    def test_reader_uses_indexed_sizes_without_raw_stat(self):
        plan=tiny_plan(REPO_ROOT);ids=plan.ids('Train')[:1]
        ref=read(REPO_ROOT/'config/science_v2/phase_a_protocol_frozen_v1.json')['identity']['yunnan_mask']
        mask=(ref['path'],dict(bytes=40,sha=ref['sha256'],year=2023,kind='static_mask'))
        full=launch.source_scope(plan,'Train',{'2023-05-01':300},mask)
        sizes={p:f['bytes'] for p,f in full['files'].items()};old=Path.stat
        def no_raw_stat(p,*a,**k):
            if p.suffix=='.nc':raise AssertionError('Reader construction statted a raw source instead of indexed size')
            return old(p,*a,**k)
        folder=REPO_ROOT/'tests/core_stage4/.local'/uuid.uuid4().hex
        with patch.object(Path,'stat',no_raw_stat):
            reader=BatchReader(plan,{'Train':ids},folder,decision_id='SYNTHETIC_INDEX_ONLY',max_files=100,max_bytes=10000,source_bytes=sizes)
            try:self.assertEqual(reader.meter.totals()['opened_files'],0)
            finally:reader.close()

    def test_default_entry_prepares_without_execute(self):
        spec=importlib.util.spec_from_file_location('start_pair',REPO_ROOT/'tools/core_stage4/start_pair.py');entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
        out=REPO_ROOT/'docs/core_stage4/.local'/uuid.uuid4().hex/'synthetic_preparation.json'
        fake=dict(status='SYNTHETIC_PREPARATION_ONLY',config={},budget={},preparation_sha256='0'*64,raw_source_opens_during_preparation=0,optimizer_updates=0,final_start_authorized=False)
        with patch.object(launch,'execute',side_effect=AssertionError('Default entry must not execute')),patch.object(launch,'preparation',return_value=fake),patch('yuntapr.experimental.core_innovation.stage4.data.PopulationPlan',return_value=object()),contextlib.redirect_stdout(io.StringIO()):
            entry.main(['--preparation',str(out),'--stage3-run','metadata','--request','request.json','--mask-read-ledger','ledger.sqlite'])
        self.assertFalse(read(out)['final_start_authorized'])

    def test_execute_guard_precedes_gpu_optimizer_and_inputs(self):
        with patch.object(torch.cuda,'is_available',side_effect=AssertionError('GPU must not be inspected')),patch.object(torch.optim.Optimizer,'__init__',side_effect=AssertionError('Optimizer must not be constructed')):
            with self.assertRaises(PermissionError):launch.execute('missing.json','never_created',start_authorization_id='')
