import contextlib
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

import numpy as np

from yuntapr.experimental.core_innovation.grid import BilinearMap, GridSpec
from yuntapr.experimental.core_innovation.terrain import (
    TerrainFeatures, WGS84_A_M, WGS84_E2, physical_spacing,
    project_terrain, read_dem_window, terrain_features,
)


@contextlib.contextmanager
def fixture_directory():
    # Inherit workspace ACLs instead of tempfile's restrictive 0700 directory.
    root = Path(tempfile.gettempdir()).resolve()
    target = root / ("yuntapr_terrain_" + uuid.uuid4().hex)
    target.mkdir()
    try:
        yield target
    finally:
        if target.resolve().parent != root:
            raise RuntimeError("Fixture cleanup path escaped its owner")
        for child in target.iterdir():
            child.unlink()
        target.rmdir()


class TerrainTests(unittest.TestCase):
    def setUp(self):
        self.grid = GridSpec(np.linspace(25.002, 24.998, 5), np.linspace(102, 102.004, 5))
        self.valid = np.ones((5, 5), dtype=bool)

    def east_ramp(self, grid):
        east, _ = physical_spacing(grid)
        return np.concatenate((np.zeros((len(grid.lat), 1)), np.cumsum(east, axis=1)), axis=1) * 0.1

    def test_physical_spacing_wgs84_equator(self):
        grid = GridSpec(np.array([-0.001, 0, 0.001]), np.array([0, 0.001, 0.002]))
        east, north = physical_spacing(grid)
        self.assertAlmostEqual(east[1, 0], WGS84_A_M * np.radians(0.001), places=8)
        self.assertAlmostEqual(north[0, 0], WGS84_A_M * (1-WGS84_E2) * np.radians(0.001), places=7)
        self.assertGreater(east[1, 0], north[0, 0])

    def test_east_direction_units_and_borders(self):
        fields = terrain_features(self.east_ramp(self.grid), self.valid, self.grid, elevation_unit="m")
        np.testing.assert_allclose(fields.east_gradient[1:-1, 1:-1], 0.1, rtol=0, atol=1e-13)
        self.assertEqual(fields.gradient_valid.sum(), 9)
        self.assertTrue(np.isnan(fields.east_gradient[[0, -1]]).all())
        # East-up slope descends west; latitude-varying parallel distances can
        # create a small physical north component in this synthetic construction.
        np.testing.assert_allclose(fields.aspect_degrees[2, 1:-1], 270, atol=0.01)

    def test_north_direction_with_descending_rows(self):
        _, north = physical_spacing(self.grid)
        z = np.concatenate((np.zeros((1, 5)), np.cumsum(north, axis=0)), axis=0) * 0.2
        f = terrain_features(z, self.valid, self.grid, elevation_unit="m")
        np.testing.assert_allclose(f.north_gradient[1:-1, 1:-1], 0.2, atol=1e-13)
        np.testing.assert_allclose(f.aspect_degrees[1:-1, 1:-1], 180.0, atol=1e-10)
        np.testing.assert_allclose(f.slope_degrees[1:-1, 1:-1], np.degrees(np.arctan(0.2)), atol=1e-10)

    def test_axis_reversal_preserves_physical_derivatives(self):
        z = self.east_ramp(self.grid)
        base = terrain_features(z, self.valid, self.grid, elevation_unit="m")
        flipped = GridSpec(self.grid.lat[::-1], self.grid.lon[::-1])
        reverse = terrain_features(z[::-1, ::-1], self.valid, flipped, elevation_unit="m")
        np.testing.assert_allclose(base.east_gradient, reverse.east_gradient[::-1, ::-1], equal_nan=True)
        np.testing.assert_allclose(base.north_gradient, reverse.north_gradient[::-1, ::-1], equal_nan=True)

    def test_irregular_spacing_linear_north_ramp(self):
        grid = GridSpec(np.array([25.004,25.002,25.001,24.997,24.996]), self.grid.lon)
        _, spacing = physical_spacing(grid)
        z = np.concatenate((np.zeros((1, 5)), np.cumsum(spacing, axis=0)), axis=0) * 0.4
        f = terrain_features(z, self.valid, grid, elevation_unit="m")
        np.testing.assert_allclose(f.north_gradient[1:-1, 1:-1], 0.4, atol=1e-13)

    def test_invalid_stencil_and_flat_undefined_aspect(self):
        z = np.ones((5, 5))
        valid = self.valid.copy(); valid[2, 2] = False; z[2, 2] = -32768
        f = terrain_features(z, valid, self.grid, elevation_unit="m")
        self.assertFalse(f.gradient_valid[2, 2])
        self.assertFalse(f.gradient_valid[1, 2])
        self.assertFalse(f.gradient_valid[2, 1])
        self.assertEqual(f.gradient_valid.sum(), 4)
        self.assertFalse(f.aspect_valid.any())
        self.assertTrue(np.isnan(f.aspect_degrees).all())
        self.assertTrue(np.isnan(f.elevation_m[2, 2]))

    def test_explicit_units_nonfinite_and_geographic_guard(self):
        with self.assertRaises(ValueError):
            terrain_features(np.ones((5, 5)), self.valid, self.grid, elevation_unit="ft")
        z=np.ones((5,5)); z[2,2]=np.nan
        with self.assertRaises(ValueError):
            terrain_features(z, self.valid, self.grid, elevation_unit="m")
        with self.assertRaises(ValueError):
            physical_spacing(GridSpec(np.array([89.,90.]),np.array([0.,1.])))
        with self.assertRaises(ValueError):
            physical_spacing(GridSpec(np.array([24.,25.]),np.array([-179.,179.])))

    def test_project_components_do_not_average_azimuth_scalars(self):
        grid=GridSpec(np.array([24.,25.]),np.array([102.,103.]))
        angle=np.radians(np.array([[359.,1.],[359.,1.]]))
        east,north=-np.sin(angle),-np.cos(angle)
        valid=np.ones((2,2),bool)
        fields=TerrainFeatures(grid,np.zeros((2,2)),valid,east,north,valid,
                               np.full((2,2),45.),np.degrees(angle),valid)
        target=GridSpec(np.array([24.25,24.75]),np.array([102.25,102.75]))
        projected=project_terrain(fields,BilinearMap.build(grid,target))
        self.assertTrue(projected.gradient_valid.all())
        self.assertTrue(np.all((projected.aspect_degrees<1.) | (projected.aspect_degrees>359.)))
        wrong=GridSpec(np.array([24.,25.]),np.array([102.,104.]))
        with self.assertRaises(ValueError):
            project_terrain(fields,BilinearMap.build(wrong,target))

    def test_project_after_native_derivative_preserves_mask(self):
        fields=terrain_features(self.east_ramp(self.grid),self.valid,self.grid,elevation_unit="m")
        target=GridSpec(self.grid.lat[1:-1],self.grid.lon[1:-1])
        out=project_terrain(fields,BilinearMap.build(self.grid,target))
        self.assertTrue(out.gradient_valid.all())
        np.testing.assert_allclose(out.east_gradient,0.1,atol=1e-13)

    def test_native_hgt_and_zip_window_same_nodata_and_georeference(self):
        with fixture_directory() as root:
            hgt=root/"N25E102.SRTMGL1.hgt"
            tile=np.zeros((1201,1201),dtype=">i2"); tile[600:604,601:605]=np.arange(16).reshape(4,4)
            tile[601,602]=-32768
            hgt.write_bytes(tile.tobytes())
            archive=root/"N25E102.SRTMGL1.hgt.zip"
            with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as stream:
                stream.write(hgt,arcname=hgt.name)
            kwargs=dict(row_start=600,col_start=601,height=4,width=4,elevation_unit="m",max_cells=16)
            raw, compressed=read_dem_window(hgt,**kwargs),read_dem_window(archive,**kwargs)
            np.testing.assert_allclose(raw.elevation_m,compressed.elevation_m,equal_nan=True)
            np.testing.assert_array_equal(raw.valid,compressed.valid)
            self.assertFalse(raw.valid[1,1]); self.assertEqual(raw.valid.sum(),15)
            self.assertAlmostEqual(raw.grid.lat[0],25.5)
            self.assertAlmostEqual(raw.grid.lon[0],102+601/1200)
            self.assertLess(raw.grid.lat[1],raw.grid.lat[0])
            self.assertGreater(raw.grid.lon[1],raw.grid.lon[0])

    def test_hgt_read_limits_reject_before_read(self):
        with fixture_directory() as root:
            hgt=root/"N25E102.hgt"; hgt.write_bytes(b"no")
            for changes in ({"max_cells":8},{"row_start":-1},{"elevation_unit":"ft"}):
                args=dict(row_start=0,col_start=0,height=3,width=3,elevation_unit="m",max_cells=9); args.update(changes)
                with self.assertRaises(ValueError):read_dem_window(hgt,**args)
            with self.assertRaises(ValueError):
                read_dem_window(hgt,row_start=0,col_start=0,height=3,width=3,elevation_unit="m")


if __name__ == "__main__":
    unittest.main()
