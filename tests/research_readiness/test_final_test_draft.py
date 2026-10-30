"""Only new non-executing catalog and synthetic metadata guards."""
import copy
import hashlib
import unittest
from yuntapr.experimental.research_readiness.final_test_draft import validate_catalog,validate_synthetic_alignment,authorize_payload,MODELS,SEEDS


class FinalDraftTests(unittest.TestCase):
    def catalog(self):
        return [dict(model=m,seed=s,endpoint='FIXED_EPOCH_9_LAST',epochs=9,checkpoint_sha256=hashlib.sha256(f'{m}/{s}'.encode()).hexdigest()) for m in MODELS for s in SEEDS]
    def scene(self):
        return dict(synthetic_fixture=True,sample_id='SYNTHETIC_2001',analysis_time='2001-03-01T06:00:00+00:00',satellite_shape=[7,6],GFS_variables=13,lead_hours=6,DEM_channels=6,target_shape=[100,100],supervised_points=3430)
    def test_catalog_all_seeds_and_endpoint_guard(self):
        x=self.catalog();self.assertFalse(validate_catalog(x)['payload_access_authorized'])
        with self.assertRaises(ValueError):validate_catalog(x[:-1])
        x[0]['endpoint']='BEST'
        with self.assertRaises(ValueError):validate_catalog(x)
    def test_synthetic_only_duplicate_and_modality_guard(self):
        row=self.scene();self.assertEqual(validate_synthetic_alignment([row])['actual_inference_adapter'],'NOT_IMPLEMENTED')
        with self.assertRaises(PermissionError):validate_synthetic_alignment([dict(row,analysis_time='2025-03-01T06:00:00+00:00')])
        with self.assertRaises(ValueError):validate_synthetic_alignment([row,row])
        with self.assertRaises(ValueError):validate_synthetic_alignment([dict(row,lead_hours=0)])
    def test_no_draft_can_authorize_final_payloads(self):
        with self.assertRaises(PermissionError):authorize_payload(approved_by_researcher=True)


if __name__=='__main__':unittest.main()
