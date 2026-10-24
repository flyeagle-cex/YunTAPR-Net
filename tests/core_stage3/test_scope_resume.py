import unittest
import test_preparation as base
from yuntapr.experimental.core_innovation.stage3.statistics import SourceCache,digest
from yuntapr.experimental.core_innovation.stage3.planning import forecast_index


class ScopeResumeTests(unittest.TestCase):
    def test_inventory_identity_conflict_and_forbidden_year(self):
        row=dict(relative_path='2023/20230501/gfs_0p25_2023050100_f006.nc',size_bytes='100',valid_time='2023-05-01T03:00:00Z')
        with self.assertRaisesRegex(ValueError,'identity conflict'):forecast_index([row],kind='main')
        row['relative_path']='2025/20250501/gfs_0p25_2025050100_f006.nc'
        self.assertEqual(forecast_index([row],kind='main'),{})

    def test_pending_intent_reopen_never_calls_loader(self):
        helper=base.PreparationTests();m=helper.manifest();g=helper.grant(m);path=helper.path()
        cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        cache.db.execute('INSERT INTO jobs VALUES (?,?,?,?,NULL)',('a','PENDING',10,1));cache.db.commit();cache.close()
        cache=SourceCache(path,manifest=m,manifest_sha=digest(m),grant=g)
        with self.assertRaisesRegex(RuntimeError,'no automatic retry'):cache.read_once('a',lambda:self.fail('Unexpected decoder'))
        cache.close()
