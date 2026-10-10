"""Synthetic geometry and missingness tests; never consume scientific files."""
import numpy as np
import pytest
from yuntapr.diagnostics.candidates import EventRule, event_components, terrain_fields, fixed_strata, wind_upslope_proxy


def rule(**changes):
    return EventRule(**({"threshold_mm_h": 10., "spatial_connectivity": 4,
                        "temporal_radius_cells": 0, "cadence_minutes": 30.} | changes))


def events(y, *, times=None, valid=None, **changes):
    return event_components(y, np.ones(y.shape, bool) if valid is None else valid,
                            np.arange(len(y)) * 30 if times is None else np.array(times), rule=rule(**changes))


def test_strict_reference_threshold():
    y = np.array([[[0., 10., 10.01]]])
    e = events(y)
    assert len(e) == 1 and e[0]["exposures"] == 1


def test_temporal_persistence_is_one_candidate_multiple_exposures():
    y = np.zeros((4, 5, 5)); y[1:3, 2, 2] = 20
    e = events(y)
    assert len(e) == 1 and e[0]["exposures"] == 2 and e[0]["unique_cells"] == 1
    assert not e[0]["censored"] and not e[0]["independence_established"]


def test_moving_cell_explicit_radius():
    y = np.zeros((2, 5, 5)); y[0, 2, 2] = 20; y[1, 2, 3] = 20
    assert len(events(y)) == 2
    assert len(events(y, temporal_radius_cells=1)) == 1


def test_connectivity_diagonal_policy():
    y = np.zeros((1, 4, 4)); y[0, 1, 1] = y[0, 2, 2] = 20
    assert len(events(y)) == 2
    assert len(events(y, spatial_connectivity=8)) == 1


def test_missing_time_never_bridged():
    y = np.ones((2, 3, 3)) * 20
    e = events(y, times=[0, 60], temporal_radius_cells=1)
    assert len(e) == 2 and all(x["censored"] for x in e)


def test_missing_pixels_not_dry():
    y = np.zeros((3, 5, 5)); y[1, 2, 2] = 20; y[1, 2, 3] = np.nan
    valid = np.ones(y.shape, bool); valid[1, 2, 3] = False
    assert events(y, valid=valid)[0]["censored"]
    with pytest.raises(ValueError): events(y)


def test_split_merge_deterministic_graph_component():
    y = np.zeros((3, 5, 5)); y[0, 2, 2] = y[2, 2, 2] = 20
    y[1, 2, 1:4] = 20
    e = events(y, temporal_radius_cells=1)
    assert len(e) == 1 and e[0]["exposures"] == 5
    assert e == events(y.copy(), temporal_radius_cells=1)


def test_empty_catalogue_is_empty():
    assert events(np.zeros((1, 2, 2))) == []


@pytest.mark.parametrize("change", [{"threshold_mm_h": 0}, {"threshold_mm_h": float("nan")},
                                   {"spatial_connectivity": True}, {"spatial_connectivity": 6},
                                   {"temporal_radius_cells": -1}, {"cadence_minutes": 0}])
def test_event_rule_rejects_invalid(change):
    with pytest.raises(ValueError): rule(**change)


@pytest.mark.parametrize("times", [[0, 0], [30, 0], [0, float("nan")]])
def test_event_invalid_times(times):
    with pytest.raises(ValueError): events(np.zeros((2, 3, 3)), times=times)


def test_terrain_plane_units_orientation_and_relief():
    row, col = np.mgrid[:5, :5]
    z = 100 + .1 * col * 100 - .2 * row * 200
    f = terrain_fields(z, np.ones(z.shape, bool), dx_m=100, dy_m=200, relief_radius_cells=1)
    assert f["east_gradient"][2, 2] == pytest.approx(.1)
    assert f["north_gradient"][2, 2] == pytest.approx(.2)
    assert f["slope_degrees"][2, 2] == pytest.approx(np.degrees(np.arctan(np.sqrt(.05))))
    assert f["aspect_degrees"][2, 2] == pytest.approx(206.565051177)
    assert f["relief_m"][2, 2] == pytest.approx(100, abs=1e-12)
    assert np.isnan(f["slope_degrees"][0]).all()


def test_flat_terrain_aspect_undefined():
    f = terrain_fields(np.ones((5, 5)), np.ones((5, 5), bool), dx_m=100, dy_m=100, relief_radius_cells=1)
    assert f["slope_degrees"][2, 2] == 0 and np.isnan(f["aspect_degrees"][2, 2])
    assert f["relief_m"][2, 2] == 0


def test_terrain_missing_stencil_never_filled():
    v = np.ones((5, 5), bool); v[2, 3] = False
    z = np.ones((5, 5)); z[2, 3] = np.nan
    f = terrain_fields(z, v, dx_m=1, dy_m=1, relief_radius_cells=1)
    assert np.isnan(f["slope_degrees"][2, 2]) and np.isnan(f["relief_m"][2, 2])


@pytest.mark.parametrize("spacing", [0, -1, float("nan"), True])
def test_terrain_requires_metric_spacing(spacing):
    with pytest.raises(ValueError):
        terrain_fields(np.zeros((3, 3)), np.ones((3, 3), bool), dx_m=spacing, dy_m=1, relief_radius_cells=1)


def test_strata_edges_and_invalid_conservation():
    a = np.array([-1, 0, 999, 1000, 2000, np.nan])
    b = fixed_strata(a, np.ones(6, bool), internal_edges=(1000, 2000))
    assert b.tolist() == [0, 0, 0, 1, 2, -1]


def test_strata_rejects_outcome_reordered_edges():
    with pytest.raises(ValueError): fixed_strata(np.ones(3), np.ones(3, bool), internal_edges=(2, 1))


def test_upslope_sign_depends_on_explicit_wind():
    f = {"east_gradient": np.array([[.1]]), "north_gradient": np.array([[.2]])}
    assert wind_upslope_proxy(f, u_east_m_s=np.array([[10]]), v_north_m_s=np.array([[0]])).item() == 1
    assert wind_upslope_proxy(f, u_east_m_s=np.array([[-10]]), v_north_m_s=np.array([[0]])).item() == -1
