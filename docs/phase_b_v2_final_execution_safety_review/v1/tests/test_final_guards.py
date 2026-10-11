"""New stdlib-only guard checks plus ONE additional abrupt-monitor-exit case."""
import ast
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).absolute().parents[4]
sys.path.insert(0, str(ROOT/'src'))
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate import start_formal
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.watchdog import run_case, interpreter_keys, persist
from yuntapr.experimental.phase_b_v2_execution_watchdog_candidate.winjob import Job, native_identity, K
from ctypes import wintypes as W
K.GetCurrentProcess.restype = W.HANDLE
OUT = ROOT/'docs/phase_b_v2_final_execution_safety_review/v1'


class Guards(unittest.TestCase):
    def test_folder_scope_before_mkdir(self):
        with patch.object(Path,'mkdir',side_effect=AssertionError('Filesystem reached')):
            with self.assertRaises(PermissionError): run_case('success',OUT/'arbitrary')

    def test_forbidden_year_lexical_only(self):
        with patch.object(Path,'mkdir',side_effect=AssertionError('Filesystem reached')):
            with self.assertRaises(PermissionError): run_case('success',OUT/'.local/2025_FORBIDDEN_SYNTHETIC')

    def test_folder_type_rejected(self):
        with self.assertRaises(TypeError): run_case('success','APPROVED')

    def test_sql_json_row_normalization(self):
        sql_rows=[('COMPLETE_SEALED',2)]
        saved=json.loads(json.dumps(sql_rows))
        self.assertNotEqual(saved,sql_rows)
        self.assertEqual(saved,[list(row) for row in sql_rows])

    def test_abrupt_monitor_exit(self):
        con = sqlite3.connect(OUT/'.local/synthetic_launch_budget.sqlite')
        con.execute('PRAGMA synchronous=FULL')
        with con:
            self.assertLess(con.execute('SELECT COUNT(*) FROM launches').fetchone()[0],40)
            con.execute('INSERT INTO launches(case_name,utc) VALUES(?,julianday(\'now\'))',('driver_crash',))
        con.close()
        r = run_case('driver_crash', OUT/'.local'/('crash_'+uuid.uuid4().hex[:12]))
        persist(OUT/'tests'/('abrupt_exit_'+uuid.uuid4().hex[:12]+'.json'), r)
        self.assertEqual(r['violation'],'WORKER_UNEXPECTED_EXIT')
        self.assertTrue(r['child_dead_before_outer_job_termination'])
        self.assertTrue(r['cleanup_verified'])
        self.assertLess(r['elapsed_seconds'],15)

    def test_fake_authority_rejected(self):
        for v in (True,'APPROVED',{'signature':'self-issued'}):
            with self.assertRaises(PermissionError): start_formal(approved=v)

    def test_bad_case_before_directory_creation(self):
        path = OUT/'.local/unknown_case_never_created'
        with self.assertRaises(ValueError): run_case('real_train',path)
        self.assertFalse(path.exists())

    def test_bad_pid_before_open(self):
        j=Job()
        try:
            for pid in (True,0,-1,'123',2**32):
                with self.assertRaises(ValueError): j.bind(pid)
        finally: j.close()

    def test_parent_identity_rejected(self):
        j=Job()
        try:
            with self.assertRaises(PermissionError): j.bind(os.getpid())
            self.assertEqual(j.pids(),[])
        finally: j.close()

    def test_image_family_not_json(self):
        identity=native_identity(K.GetCurrentProcess())
        self.assertIn(identity['image_path_key'],interpreter_keys())
        self.assertGreater(identity['creation_filetime'],0)

    def test_no_science_imports(self):
        self.assertFalse({k.split('.')[0] for k in sys.modules}&{'torch','numpy','netCDF4','h5py','cupy'})

    def test_source_closed_imports(self):
        namespace=ROOT/'src/yuntapr/experimental/phase_b_v2_execution_watchdog_candidate'
        for file in namespace.glob('*.py'):
            tree=ast.parse(file.read_text(encoding='utf-8'))
            for n in ast.walk(tree):
                if isinstance(n,(ast.Import,ast.ImportFrom)):
                    names=[a.name for a in n.names] if isinstance(n,ast.Import) else [n.module or '']
                    self.assertFalse(any(x.split('.')[0] in {'torch','numpy','netCDF4','h5py','cupy'} for x in names))
                if isinstance(n,ast.Attribute): self.assertNotIn(n.attr,{'backward','optimizer','cuda'})


if __name__=='__main__': unittest.main(verbosity=2)
