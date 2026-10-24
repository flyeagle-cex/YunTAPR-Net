import unittest
import numpy as np

from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.terrain import physical_spacing, terrain_features
from yuntapr.experimental.core_innovation.dote import above_ground_mask, dote_proxy


class DoteTests(unittest.TestCase):
    def setUp(self):
        self.grid=GridSpec(np.linspace(25.002,24.998,5),np.linspace(102.,102.004,5))
        _, north=physical_spacing(self.grid)
        z=np.concatenate((np.zeros((1,5)),np.cumsum(north,axis=0)),axis=0)*0.1
        self.terrain=terrain_features(z,np.ones((5,5),bool),self.grid,elevation_unit="m")
        self.u=np.zeros((2,3,5,5)); self.v=np.ones_like(self.u)*2.
        self.wind_valid=np.ones(self.u.shape,bool)
        self.ps=np.ones((2,5,5))*90000.; self.surface_valid=np.ones(self.ps.shape,bool)
        self.levels=np.array([850.,900.,950.])

    def run_proxy(self,**overrides):
        args=dict(terrain=self.terrain,u_east=self.u,v_north=self.v,wind_valid=self.wind_valid,
                  pressure_levels=self.levels,surface_pressure=self.ps,surface_valid=self.surface_valid,
                  wind_grid=self.grid,wind_unit="m/s",pressure_unit="hPa",surface_pressure_unit="Pa")
        args.update(overrides)
        return dote_proxy(**args)

    def test_physical_coupling_sign_pressure_and_borders(self):
        result=self.run_proxy()
        np.testing.assert_allclose(result.orographic_proxy_m_s[:,0,1:-1,1:-1],0.2,atol=1e-13)
        self.assertEqual(result.valid.sum(),18)
        self.assertFalse(result.valid[:,1:].any())
        self.assertTrue(np.isnan(result.orographic_proxy_m_s[:,1:]).all())
        np.testing.assert_array_equal(result.pressure_pa,[85000.,90000.,95000.])
        self.assertIn("NOT_VERTICAL_VELOCITY",result.scientific_status)

    def test_wind_reversal(self):
        positive=self.run_proxy()
        negative=self.run_proxy(v_north=-self.v)
        np.testing.assert_allclose(negative.orographic_proxy_m_s,-positive.orographic_proxy_m_s,equal_nan=True)
        np.testing.assert_array_equal(positive.valid,negative.valid)

    def test_pa_and_hpa_equivalence(self):
        pa=self.run_proxy(pressure_levels=self.levels*100,pressure_unit="Pa")
        hp=self.run_proxy(surface_pressure=self.ps/100,surface_pressure_unit="hPa")
        np.testing.assert_allclose(pa.orographic_proxy_m_s,hp.orographic_proxy_m_s,equal_nan=True)

    def test_missing_wind_surface_and_external_pressure_masks(self):
        winds=self.wind_valid.copy(); winds[0,0,2,2]=False
        ps=self.ps.copy();ps[1,2,2]=np.nan
        pv=np.ones(self.u.shape,bool);pv[0,0,1,1]=False
        result=self.run_proxy(wind_valid=winds,surface_pressure=ps,pressure_valid=pv)
        self.assertFalse(result.valid[0,0,2,2]);self.assertFalse(result.valid[1,0,2,2])
        self.assertFalse(result.valid[0,0,1,1])
        v=self.v.copy();v[0,0,2,3]=np.inf
        self.assertFalse(self.run_proxy(v_north=v).valid[0,0,2,3])

    def test_flat_slope_zero_proxy_with_undefined_aspect(self):
        flat=terrain_features(np.zeros((5,5)),np.ones((5,5),bool),self.grid,elevation_unit="m")
        result=self.run_proxy(terrain=flat)
        np.testing.assert_array_equal(result.orographic_proxy_m_s[result.valid],0.)
        self.assertFalse(flat.aspect_valid.any())

    def test_unbatched_shape(self):
        result=self.run_proxy(u_east=self.u[0],v_north=self.v[0],wind_valid=self.wind_valid[0],
                              surface_pressure=self.ps[0],surface_valid=self.surface_valid[0])
        self.assertEqual(result.valid.shape,(3,5,5))

    def test_explicit_pressure_levels_order_retained(self):
        above,levels=above_ground_mask(np.array([950.,850.]),self.ps,
            pressure_unit="hPa",surface_pressure_unit="Pa",surface_valid=self.surface_valid)
        self.assertFalse(above[:,0].any());self.assertTrue(above[:,1].all())
        np.testing.assert_array_equal(levels,[95000.,85000.])

    def test_reject_wrong_grid_units_level_count_and_silent_sample_broadcast(self):
        for overrides in (dict(wind_unit="knots"),dict(pressure_unit="auto"),
                          dict(pressure_levels=np.array([850.])),dict(surface_pressure=self.ps[0]),
                          dict(pressure_levels=np.array([850.,850.,950.])),
                          dict(pressure_levels=np.array([850.,np.nan,950.])),
                          dict(wind_grid=GridSpec(self.grid.lat[::-1],self.grid.lon))):
            with self.subTest(overrides=tuple(overrides)),self.assertRaises(ValueError):
                self.run_proxy(**overrides)


if __name__ == "__main__":
    unittest.main()
