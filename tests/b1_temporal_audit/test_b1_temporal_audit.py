"""Synthetic/read-only B1 audit tests; never opens original source payloads."""
from datetime import timedelta
import json
from pathlib import Path
import unittest
import tempfile
import shutil
import uuid
from unittest.mock import patch
import netCDF4
import numpy as np
from yuntapr.data import b1_temporal_audit as audit
from yuntapr.contracts.loader import sha256
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.spatial.sp04_mapping import load_sp04
from tests.final_test_catalogue.test_catalogue_gate import workspace_fixture

def full_frame(nominal):
    f=audit.empty_frame(nominal)
    f.update(present=True,readable=True,decoded=True,valid_count=251001,full_valid=True,metadata_valid=True,
        obs_start=(nominal+timedelta(seconds=40)).isoformat(),obs_end=(nominal+timedelta(seconds=578)).isoformat(),
        status='FULL_VALID',reasons='')
    return f

class B1DefinitionTests(unittest.TestCase):
    def test_exact_offsets_order_and_latest_equals_b0(self):
        t=audit.utc('2023-04-01T00:00:00Z');values=audit.slot_nominals(t);a=t+timedelta(minutes=30)
        self.assertEqual([int((a-n).total_seconds()/60) for n in values],[60,50,40,30,20,10])
        self.assertEqual(values,tuple(sorted(values)));self.assertEqual(values[-1],a-timedelta(minutes=10))

    def test_exact_calendar_population_no_2025_or_october_exclusion(self):
        for year in (2023,2024):
            target=audit.times(year,30);native=audit.times(year,10)
            self.assertEqual(len(target),11760);self.assertEqual(len(native),35280)
            self.assertEqual(target[-1],audit.utc(f'{year}-10-31T23:30:00Z'))
        with self.assertRaises(ValueError):audit.times(2025,30)

    def test_wrong_year_month_cadence_and_naive_timestamp_rejected(self):
        for value in ('2025-03-01T00:00:00Z','2024-02-29T00:00:00Z','2024-11-01T00:00:00Z',
                      '2024-04-01T00:10:00Z','2024-04-01T00:00:01Z','2024-04-01T00:00:00'):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):audit.slot_nominals(value)

    def test_first_target_outside_scope_is_distinct_from_missing(self):
        t=audit.utc('2024-03-01T00:00:00Z');nominals=audit.slot_nominals(t);a=t+timedelta(minutes=30)
        rows=[audit.slot_qc(t.isoformat(),i,n,full_frame(n) if audit.in_scope(n) else None,a) for i,n in enumerate(nominals)]
        self.assertEqual([r['frame_status'] for r in rows[:3]],['OUTSIDE_AUDIT_SCOPE']*3)
        self.assertEqual([r['causality_pass'] for r in rows[:3]],['UNKNOWN']*3)
        self.assertFalse(audit.temporal_decision(rows,True)[0])
        self.assertTrue(all('MISSING' not in r['reasons'] for r in rows))

    def test_authority_without_exact_researcher_confirmation_rejected(self):
        with workspace_fixture() as root:
            value=audit.definition_bindings();value.update(approved_utc=gate.now(),researcher_confirmation='approved')
            path=root/'definition.json';path.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(PermissionError):audit.load_definition(path,sha256(path))

    def test_definition_explicitly_keeps_other_decisions_unfrozen(self):
        with workspace_fixture() as root:
            value=audit.definition_bindings();value.update(approved_utc=gate.now(),researcher_confirmation='批准该时相与审计定义；其余决策保持待定（推荐）')
            path=root/'definition.json';path.write_text(json.dumps(value),encoding='utf-8')
            loaded=audit.load_definition(path,sha256(path));self.assertFalse(loaded['B1_DESIGN_FROZEN'])
            self.assertEqual(loaded['normalization'],'RESEARCHER_DECISION_REQUIRED')
            value['2025_ACCESS_AUTHORIZED']=True;path.write_text(json.dumps(value),encoding='utf-8')
            with self.assertRaises(PermissionError):audit.load_definition(path,sha256(path))

class B1SlotQcTests(unittest.TestCase):
    def rows(self):
        t=audit.utc('2023-04-01T00:00:00Z');a=t+timedelta(minutes=30)
        return [audit.slot_qc(t.isoformat(),i,n,full_frame(n),a) for i,n in enumerate(audit.slot_nominals(t))]
    def test_complete_valid_causal_candidate_not_a_formal_policy(self):
        rows=self.rows();self.assertEqual(audit.temporal_decision(rows,True),(True,()))
        self.assertEqual(audit.definition_bindings()['missing_policy'],'RESEARCHER_DECISION_REQUIRED')
    def test_partial_all_fill_and_missing_collect_multiple_slot_reasons(self):
        rows=self.rows()
        for i,reason in enumerate(('PARTIAL','ALL_FILL','MISSING')):rows[i]['reasons']=reason
        result,reasons=audit.temporal_decision(rows,True)
        self.assertFalse(result);self.assertEqual(reasons,('S0_PARTIAL','S1_ALL_FILL','S2_MISSING'))
    def test_real_observation_end_controls_causality(self):
        t=audit.utc('2024-04-01T00:00:00Z');a=t+timedelta(minutes=30);n=a-timedelta(minutes=10)
        frame=full_frame(n);frame['obs_end']=(a+timedelta(microseconds=1)).isoformat()
        row=audit.slot_qc(t.isoformat(),5,n,frame,a)
        self.assertEqual(row['causality_pass'],'False');self.assertIn('NONCAUSAL_FRAME',row['reasons'])
    def test_scan_bucket_deviation_is_diagnostic_only(self):
        t=audit.utc('2023-04-01T00:00:00Z');a=t+timedelta(minutes=30);n=a-timedelta(minutes=60)
        frame=full_frame(n);frame['obs_start']=(n-timedelta(seconds=1)).isoformat()
        row=audit.slot_qc(t.isoformat(),0,n,frame,a)
        self.assertEqual(row['scan_bucket_conforms'],'False');self.assertEqual(row['causality_pass'],'True');self.assertEqual(row['reasons'],'')
    def test_valid_target_required_but_partial_imerg_mask_retained(self):
        self.assertFalse(audit.temporal_decision(self.rows(),False)[0])
        self.assertTrue(audit.temporal_decision(self.rows(),1>0)[0])
    def test_no_slot_drop_duplicate_or_reorder(self):
        rows=self.rows()
        for bad in (rows[:5],list(reversed(rows)),rows[:5]+[rows[4]]):
            with self.assertRaises(ValueError):audit.temporal_decision(bad,True)

class B1GuardTests(unittest.TestCase):
    def test_2025_all_months_raw_and_imerg_checkpoint_never_opened(self):
        guard=audit.AuditGuard()
        for p in (audit.HROOT/'202503'/'01'/'NC_H09_20250301_0000_R21_FLDK.06001_06001.nc',
            audit.HROOT/'202510'/'01'/'NC_H09_20251001_0000_R21_FLDK.06001_06001.nc',
            audit.IROOT/'2023'/'imerg_20230301.nc',audit.IROOT/'2025'/'imerg_20250301.nc',audit.CHECKPOINT_ROOT/'epoch_011.pt'):
            with self.subTest(p=str(p)):
                with self.assertRaises(PermissionError):guard.check(str(p),'rb')
        self.assertEqual(guard.source_open_events,0)
    def test_readonly_correct_development_path_and_no_february(self):
        guard=audit.AuditGuard();p=audit.HROOT/'202310'/'31'/'NC_H09_20231031_2350_R21_FLDK.06001_06001.nc'
        guard.check(str(p),'rb');self.assertEqual(guard.source_open_events,1)
        with self.assertRaises(PermissionError):guard.check(str(p),'wb')
        with self.assertRaises(PermissionError):guard.check(str(audit.HROOT/'202402'/'29'/'NC_H09_20240229_2350_R21_FLDK.06001_06001.nc'),'rb')
    def test_direct_backend_original_path_rejected_before_netcdf_io(self):
        with audit.AuditGuard(),patch.object(netCDF4,'num2date') as times:
            with self.assertRaises(PermissionError):
                netCDF4.Dataset(str(audit.HROOT/'202403'/'01'/'NC_H09_20240301_0000_R21_FLDK.06001_06001.nc'))
            times.assert_not_called()
    def test_model_forward_torch_load_backward_optimizer_rejected(self):
        import torch
        with audit.AuditGuard():
            for fn in (lambda:torch.nn.Identity()(torch.ones(1)),lambda:torch.load('fixture.pt'),
                       lambda:torch.ones(1,requires_grad=True).sum().backward(),
                       lambda:torch.optim.AdamW([torch.nn.Parameter(torch.ones(1))])):
                with self.assertRaises((PermissionError,RuntimeError)):fn()

class B1PhysicalReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.mapping=load_sp04()

    def fixture(self,path,kind='full'):
        with netCDF4.Dataset(str(path),'w') as ds:
            for name,size in (('latitude',501),('longitude',501),('time',1)):ds.createDimension(name,size)
            for name,axis in (('latitude','native_lat'),('longitude','native_lon')):
                values=self.mapping.axes[axis].copy()
                if kind=='flip' and name=='latitude':values=values[::-1]
                ds.createVariable(name,'f4',(name,))[:]=values
            variable=ds.createVariable('tbb_13','i2',('latitude','longitude'),fill_value=-9999)
            variable.setncatts(dict(units='K',scale_factor=np.float32(.01),add_offset=np.float32(0),
                valid_min=np.int16(0),valid_max=np.int16(32767)))
            variable.set_auto_maskandscale(False);values=np.full((501,501),27000,dtype=np.int16)
            if kind=='partial':values[0,0]=-9999
            elif kind=='all_fill':values[:]=-9999
            variable[:]=values
            for name,value in (('start_time',20),('end_time',19 if kind=='reversed_time' else 29)):
                tv=ds.createVariable(name,'f8',('time',));tv.units='minutes since 2024-07-01 00:00:00';tv[:]=[value]
            ds.date_created='2024-07-01T01:00:00Z'

    def check_fixture(self,kind):
        parent=Path(tempfile.gettempdir())/'yuntapr_b1_reader_fixtures'
        parent.mkdir(parents=True,exist_ok=True)
        directory=parent/('source_'+uuid.uuid4().hex);directory.mkdir()
        try:
            path=directory/'synthetic_b13.nc';self.fixture(path,kind)
            telemetry={'b13_pixel_values_read':0}
            with audit.AuditGuard():result=audit.frame_qc(path,self.mapping,audit.utc('2024-07-01T00:20:00Z'),telemetry)
            self.assertFalse(any(isinstance(v,np.ndarray) for v in result.values()))
            return result,telemetry
        finally:
            if directory.resolve().parent!=parent.resolve():raise ValueError('Unsafe fixture cleanup')
            shutil.rmtree(directory)

    def test_actual_reader_preserves_cf_and_only_b13_pixel_counter(self):
        result,telemetry=self.check_fixture('full')
        self.assertEqual(result['status'],'FULL_VALID');self.assertEqual(result['valid_count'],251001)
        self.assertEqual(result['obs_end'],'2024-07-01T00:29:00+00:00')
        self.assertEqual(result['date_created'],'2024-07-01T01:00:00Z')
        self.assertEqual(telemetry,{'b13_pixel_values_read':251001})

    def test_missing_values_never_zero_and_multireason_time_error(self):
        for kind,count in (('partial',251000),('all_fill',0)):
            result,_=self.check_fixture(kind)
            self.assertFalse(result['full_valid']);self.assertEqual(result['valid_count'],count)
            self.assertEqual(result['status'],kind.upper())
        result,_=self.check_fixture('reversed_time')
        self.assertFalse(result['metadata_valid']);self.assertIn('TIME_METADATA_ERROR',result['reasons'])

    def test_native_latitude_flip_is_rejected_before_pixels(self):
        result,telemetry=self.check_fixture('flip')
        self.assertEqual(result['status'],'B13_GRID_OR_PACKING_METADATA_ERROR')
        self.assertEqual(telemetry['b13_pixel_values_read'],0)
