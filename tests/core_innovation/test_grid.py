import unittest
import numpy as np
from yuntapr.experimental.core_innovation.grid import GridSpec,BilinearMap,frozen_sp04_grid


class GridTests(unittest.TestCase):
    def test_direction_and_affine_reconstruction(self):
        target=GridSpec([.25,.75],[.25,.75])
        for lat in ([0,1],[1,0]):
            for lon in ([0,1],[1,0]):
                source=GridSpec(lat,lon);y,x=np.meshgrid(source.lat,source.lon,indexing='ij')
                out,valid=BilinearMap.build(source,target).apply(2*y+3*x,np.ones((2,2),bool))
                yy,xx=np.meshgrid(target.lat,target.lon,indexing='ij')
                np.testing.assert_allclose(out,2*yy+3*xx);self.assertTrue(valid.all())

    def test_mask_no_fill_or_extrapolation(self):
        s=GridSpec([0,1],[0,1]);t=GridSpec([0,.5,2],[0,.5])
        x=np.ones((2,2));x[1,1]=np.nan;m=np.isfinite(x)
        out,v=BilinearMap.build(s,t).apply(x,m)
        self.assertTrue(v[0,0]);self.assertFalse(v[1,1]);self.assertFalse(v[-1].any());self.assertTrue(np.isnan(out[-1]).all())

    def test_grid_immutable_and_invalid_axes(self):
        a=np.array([1.,2.]);g=GridSpec(a,[3,4]);a[0]=0
        self.assertEqual(g.lat[0],1)
        with self.assertRaises(ValueError):g.lat[0]=0
        for lat in ([1,1],[2,1,3],[np.nan,2]):
            with self.assertRaises(ValueError):GridSpec(lat,[1,2])

    def test_actual_frozen_axes(self):
        g=frozen_sp04_grid();self.assertEqual(g.shape,(100,100));self.assertTrue(np.all(np.diff(g.lat)>0))


if __name__=='__main__':unittest.main()
