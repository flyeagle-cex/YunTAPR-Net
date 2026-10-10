"""Synthetic files/metadata only; never query any actual raw-data path."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

HERE=Path(__file__).absolute().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_full_payload_integrity import audit
from yuntapr.experimental.phase_b_v2_full_payload_integrity.winio import ReadHandle

class ScopeTests(unittest.TestCase):
    def scope(self):return audit.Scope({'B13':r'H:\synthetic_202303_202510','IMERG':r'F:\synthetic_imerg'})
    def test_accepted_years(self):
        s=self.scope()
        for y in (2023,2024):self.assertTrue(s.lexical(fr'H:\synthetic_202303_202510\{y}03\01\file.nc','B13',y).endswith('file.nc'))
    def test_forbidden_before_all_filesystem_apis(self):
        s=self.scope()
        with patch('pathlib.Path.resolve',side_effect=AssertionError('resolve')),patch('os.stat',side_effect=AssertionError('stat')),patch('builtins.open',side_effect=AssertionError('open')),patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',side_effect=AssertionError('backend')):
            for path,kind,year in ((r'H:\synthetic_202303_202510\202503\x.nc','B13',2025),
                                  (r'H:\synthetic_202303_202510\202503\x.nc','B13',2023),
                                  (r'F:\synthetic_imerg\2025\imerg_20250301.nc','IMERG',2024)):
                with self.assertRaises(PermissionError):s.register(path,kind,year,'0'*64,1)
    def test_root_escape(self):
        for text in (r'H:\other\202303\x.nc',r'H:\synthetic_202303_202510\..\202303\x.nc','202303/x.nc',r'\\?\H:\synthetic_202303_202510\202303\x.nc'):
            with self.assertRaises(PermissionError):self.scope().lexical(text,'B13',2023)
    def test_extension_stream_month(self):
        for rel in ('202303/x.pt','202303/x.nc:stream','202302/x.nc'):
            with self.assertRaises(PermissionError):self.scope().lexical('H:/synthetic_202303_202510/'+rel,'B13',2023)
    def test_missing_sha(self):
        for sha in ('','0'*63,'G'*64):
            with self.assertRaises(ValueError):self.scope().register(r'H:\synthetic_202303_202510\202303\x.nc','B13',2023,sha,1)
    def test_conflict_and_dedup(self):
        s=self.scope();path=r'H:\synthetic_202303_202510\202303\x.nc';s.register(path,'B13',2023,'0'*64,1);s.register(path,'B13',2023,'0'*64,1)
        self.assertEqual(len(s.entries),1)
        with self.assertRaises(ValueError):s.register(path,'B13',2023,'1'*64,1)
    def test_exact_reference(self):
        with self.assertRaises(PermissionError):self.scope().authorized(r'H:\synthetic_202303_202510\202303\unregistered.nc')
    def test_target_mismatch(self):
        with self.assertRaises(PermissionError):self.scope().authenticate_final('H:/a','H:/b')

class HandleTests(unittest.TestCase):
    def test_native_readonly_and_identity(self):
        private=HERE/'.local'/'unit';private.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private) as folder:
            path=Path(folder)/'artificial.bin';path.write_bytes(b'only artificial bytes')
            with ReadHandle(str(path),payload=True) as handle:
                self.assertEqual(handle.before['size'],21);b=bytearray(21);self.assertEqual(handle.readinto(b),21)
                self.assertEqual(bytes(b),b'only artificial bytes');self.assertEqual(handle.snapshot(),handle.before)
                with self.assertRaises(PermissionError):path.open('wb')
    def test_directory_kind(self):
        private=HERE/'.local'/'unit';private.mkdir(parents=True,exist_ok=True)
        with ReadHandle(str(private),directory=True) as handle:self.assertTrue(handle.before['attributes']&0x10)
        with self.assertRaises((ValueError,PermissionError)):ReadHandle(str(private),directory=False)

class StreamTests(unittest.TestCase):
    def make(self,data=b'abcdef',expected=None):
        private=HERE/'.local'/'unit';private.mkdir(parents=True,exist_ok=True)
        directory=Path(tempfile.mkdtemp(dir=private));a=audit.Audit(directory);self.addCleanup(a.j.con.close)
        a.scope=audit.Scope({'B13':r'H:\synthetic_202303_202510','IMERG':r'F:\synthetic_imerg'})
        path=a.scope.register(r'H:\synthetic_202303_202510\202303\x.nc','B13',2023,expected or audit.sha(data),len(data))
        signature={'size':len(data),'attributes':0,'volume':1,'file_index':1,'mtime_100ns':1}
        a.j.con.execute('INSERT INTO files(i,path,kind,year,file_key,expected_sha,frozen_size,size,signature,status) VALUES(0,?,?,?,?,?,?,?,?,?)',(path,'B13',2023,'opaque',expected or audit.sha(data),len(data),len(data),json.dumps(signature),'NOT_READ'))
        class Fake:
            def __init__(self,*args,**kwargs):self.before=signature.copy();self.final_path=path;self.position=0
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def readinto(self,buf):
                value=data[self.position:self.position+len(buf)];buf[:len(value)]=value;self.position+=len(value);return len(value)
            def snapshot(self):return self.before.copy()
        a.check=lambda:None;a.progress=lambda *args:None
        return a,Fake
    def test_stream_matches(self):
        a,fake=self.make()
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',fake),patch.object(audit,'CHUNK',2):a.hash_all()
        self.assertEqual(a.j.con.execute('SELECT status,read_bytes FROM files').fetchone(),('SHA_PASS',6))
        self.assertEqual(a.raw_bytes,6);self.assertEqual(a.j.get('inflight_requested_bytes'),0)
    def test_mismatch_records_actual_and_stops(self):
        a,fake=self.make(expected='0'*64)
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',fake):
            with self.assertRaises(ValueError):a.hash_all()
        self.assertEqual(a.j.con.execute('SELECT status,actual_sha FROM files').fetchone(),('FAILED',audit.sha(b'abcdef')))
    def test_content_budget_never_overruns(self):
        a,fake=self.make()
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',fake),patch.object(audit,'LIMIT_BYTES',4),patch.object(audit,'CHUNK',2):
            with self.assertRaises(MemoryError):a.hash_all()
        self.assertEqual(a.raw_bytes,4)
    def test_metadata_content_included_in_budget(self):
        a,fake=self.make();a.j.set('public_metadata_bytes',4)
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',fake),patch.object(audit,'LIMIT_BYTES',8),patch.object(audit,'CHUNK',2):
            with self.assertRaises(MemoryError):a.hash_all()
        self.assertEqual(a.raw_bytes,4)
    def test_changed_object_stops_before_read(self):
        a,fake=self.make()
        class Changed(fake):
            def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);self.before['file_index']=2
            def readinto(self,b):raise AssertionError('Content read after identity change')
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',Changed):
            with self.assertRaises(ValueError):a.hash_all()
        self.assertEqual(a.raw_bytes,0)
    def test_changed_during_read(self):
        a,fake=self.make()
        class Changed(fake):
            def snapshot(self):return {**self.before,'mtime_100ns':2}
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',Changed):
            with self.assertRaises(ValueError):a.hash_all()
        self.assertEqual(a.j.con.execute('SELECT status FROM files').fetchone()[0],'FAILED')
    def test_permission_stops(self):
        a,_=self.make()
        with patch('yuntapr.experimental.phase_b_v2_full_payload_integrity.winio.ReadHandle',side_effect=PermissionError('synthetic denied')):
            with self.assertRaises(PermissionError):a.hash_all()
        self.assertEqual(a.raw_bytes,0);self.assertEqual(a.j.con.execute('SELECT payload_success FROM files').fetchone()[0],0)
    def test_time_cap(self):
        a,_=self.make();a.start=-audit.LIMIT_SECONDS
        with self.assertRaises(TimeoutError):audit.Audit.check(a)
    def test_no_decoder_model_imports(self):
        self.assertNotIn('torch',sys.modules);self.assertNotIn('netCDF4',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
