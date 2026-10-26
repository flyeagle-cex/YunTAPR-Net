import unittest
import numpy as np
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.research_readiness.terrain_production import edges,dilate,latitude_area,interval_integrals,finish_features

class ProductionTests(unittest.TestCase):
    def test_area_integral_constant_and_fractional_cell_is_not_point_sample(self):
        s=np.array([0.,1.,2.,3.]);t=np.array([.5,1.5,2.5]);v=np.array([[0.,10.,20.]])
        np.testing.assert_allclose(interval_integrals(v,s,t),[[5.,15.]])
        np.testing.assert_allclose(interval_integrals(v*0+4,s,t),[[4.,4.]])
    def test_area_support_and_orientation_fail_closed(self):
        for target in ([-.1,1.],[0.,4.],[1.,0.]):
            with self.assertRaises(ValueError):interval_integrals(np.ones(3),np.arange(4.),target)
    def test_actual_target_edges_are_explicit_float32_rounds(self):
        a=np.array([97.04999542236328,97.1500015258789,97.25]);e=edges(a)
        self.assertEqual(e[0],float(np.float32(a[0]-(a[1]-a[0])/2)))
        self.assertNotEqual(e[0],97.)
    def test_ellipsoid_area_additive_and_latitude_dependent(self):
        q=latitude_area(np.array([20.,21.,22.]));self.assertGreater(q[1]-q[0],q[2]-q[1])
        self.assertAlmostEqual((q[1]-q[0])+(q[2]-q[1]),q[2]-q[0],delta=.001)
    def test_two_cell_context_does_not_shrink_supervision(self):
        m=np.zeros((9,9),bool);m[4,4]=True;d=dilate(m,2)
        self.assertEqual(d.sum(),25);self.assertTrue(d[m].all());self.assertEqual(m.sum(),1)
    def test_mean_gradient_vector_precedes_slope_and_flat_aspect_mask(self):
        g=GridSpec([20.,21.],[100.,101.]);z=np.ones((2,2));v=np.ones((2,2),bool)
        f=finish_features(g,z,z*0,z*0,v,v)
        self.assertFalse(f.aspect_valid.any());self.assertTrue(np.isnan(f.aspect_degrees).all());self.assertTrue((f.slope_degrees==0).all())
        f=finish_features(g,z,z*.1,z*0,v,v)
        np.testing.assert_allclose(f.aspect_degrees,270.);np.testing.assert_allclose(f.slope_degrees,np.degrees(np.arctan(.1)))

if __name__=='__main__':unittest.main()
