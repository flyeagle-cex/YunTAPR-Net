"""Regression for the actual blocked loader entrance, without any raw reads."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from yuntapr.experimental.core_innovation.stage4.launch import ReaderFactory
from yuntapr.experimental.core_innovation.stage4 import data

class StaticReaderTests(unittest.TestCase):
    def setUp(self):
        self.ids=('SYNTHETIC_A','SYNTHETIC_B')
        self.files={'SYNTHETIC_SOURCE':dict(bytes=123,sha='a'*64)}
        scope=dict(ids=list(self.ids),file_count=1,bytes_per_pass=123,files=self.files)
        self.prepared={'roles':{'Train':scope,'Development':scope}}
    def test_real_factory_accepts_explicit_B5_B6_both_roles_only_once(self):
        def fake(*args,**kwargs):return SimpleNamespace(meter=SimpleNamespace(files=self.files),close=lambda:None)
        with patch.object(data,'BatchReader',side_effect=fake) as construct:
            for kind in ('B5','B6'):
                factory=ReaderFactory(None,self.prepared,'SYNTHETIC_NO_AUTHORIZATION',allowed_models=(kind,))
                for role in ('Train','Development'):
                    factory(role,1,self.ids,Path(f'{kind}_{role}_reads_01'))
                    with self.assertRaises(PermissionError):factory(role,1,self.ids,Path(f'{kind}_{role}_reads_01'))
            self.assertEqual(construct.call_count,4)
    def test_defaults_population_and_arm_guards_reject_before_source_open(self):
        with patch.object(data,'BatchReader',side_effect=AssertionError('Source must not open')):
            default=ReaderFactory(None,self.prepared,'SYNTHETIC')
            with self.assertRaises(PermissionError):default('Train',1,self.ids,Path('B5_train_reads_01'))
            new=ReaderFactory(None,self.prepared,'SYNTHETIC',allowed_models=('B5',))
            for kind,epoch,ids in [('B4',1,self.ids),('B6',1,self.ids),('B5',0,self.ids),('B5',1,('CHANGED',))]:
                with self.assertRaises(PermissionError):new('Train',epoch,ids,Path(f'{kind}_train_reads_01'))
if __name__=='__main__':unittest.main()
