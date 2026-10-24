import unittest
import numpy as np
import torch
import test_stage2 as base
from yuntapr.experimental.core_innovation.dote import dote_proxy
from yuntapr.experimental.core_innovation.stage2.dote_v13 import complete_dote
from yuntapr.experimental.core_innovation.stage2.models import paired_spectral_candidates
from yuntapr.models.quantile_v2.parameterization import CandidateNumerics


class FinalConnectionTests(unittest.TestCase):
    def test_canonical_pwat_owlm_payload_and_missing_moisture_mask(self):
        t = base.DoteTests().terrain(); wind = np.ones((2, *t.grid.shape)); ps = np.full(t.grid.shape, 100000.)
        proxy = dote_proxy(t, wind, np.zeros_like(wind), np.ones_like(wind, bool), np.array([85000., 70000.]),
            ps, np.ones_like(ps, bool), wind_grid=t.grid, wind_unit='m/s', pressure_unit='Pa', surface_pressure_unit='Pa')
        mask = np.ones_like(ps, bool); mask[4, 4] = False
        result = complete_dote(proxy, np.full_like(ps, 20.), mask, pwat_grid=t.grid, pwat_unit='kg m-2',
            pwat_reference_kg_m2=20., reference_provenance='synthetic_scale_not_frozen', moisture_basis='windward_W')
        values, valid, keys = result.stack()
        self.assertEqual(keys, ('O850', 'O700', 'W850', 'W700', 'L850', 'L700', 'M850', 'M700'))
        self.assertEqual(values.shape, (8, *t.grid.shape)); self.assertTrue(valid[:6, 4, 4].all())
        self.assertFalse(valid[6:, 4, 4].any()); self.assertTrue(np.isnan(values[6:, 4, 4]).all())

    def test_paired_b3_b4_common_initialization_is_identical(self):
        b3, b4 = paired_spectral_candidates(numerics=CandidateNumerics(epsilon_w=1e-4, epsilon_span=1e-4), mee_width=16)
        for part in ('backbone', 'heads'):
            a = getattr(b3, part).state_dict(); b = getattr(b4, part).state_dict()
            self.assertTrue(all(torch.equal(a[k], b[k]) for k in a))
        self.assertTrue((b4.mee.output.weight == 0).all())


if __name__ == '__main__': unittest.main()
