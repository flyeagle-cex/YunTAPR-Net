"""Check the native-grid 700 hPa moisture-flux-divergence operator on synthetic fields."""

import json

import numpy as np


EARTH_RADIUS_M = 6_371_000.0
LEVEL_PA = 70_000.0


def convergence700(latitudes, longitudes, specific_humidity, u, v, surface_pressure, valid):
    """Return convergence, wind and moisture-gradient terms, and the common stencil mask.

    Axes are in degrees. Specific humidity is in kg/kg, winds in m/s and pressure in Pa.
    The fluxes and the decomposition share the same finite-volume face values.
    """
    axes = [np.asarray(axis, dtype=np.float64) for axis in (latitudes, longitudes)]
    if any(axis.ndim != 1 or len(axis) < 3 or not np.isfinite(axis).all() for axis in axes):
        raise ValueError("Expected finite one-dimensional geographic axes")
    steps = [np.diff(axis) for axis in axes]
    if any(not np.allclose(step, step[0], rtol=0, atol=1e-9) or not 0 < abs(step[0]) < 180
           for step in steps) or np.max(np.abs(axes[0])) >= 90 or np.ptp(axes[1]) >= 180:
        raise ValueError("Expected regular geographic axes without a pole or longitude seam")

    order = tuple(slice(None, None, 1 if step[0] > 0 else -1) for step in steps)
    shape = (len(axes[0]), len(axes[1]))
    values = [np.asarray(value, dtype=np.float64) for value in (specific_humidity, u, v, surface_pressure)]
    valid = np.asarray(valid)
    if any(value.shape != shape for value in values) or valid.shape != shape or valid.dtype != np.bool_:
        raise ValueError("Fields and boolean validity must align with the native grid")

    q, u, v, ps = (value[order] for value in values)
    usable = valid[order] & np.isfinite(q) & np.isfinite(u) & np.isfinite(v) & np.isfinite(ps)
    usable &= ps > LEVEL_PA
    if np.any(usable & ((q < 0) | (q >= 1))):
        raise ValueError("Expected nonnegative specific humidity in kg/kg")
    q, u, v = (np.where(usable, value, 0.0) for value in (q, u, v))
    interior = np.s_[1:-1, 1:-1]
    center_valid = (
        usable[interior] & usable[1:-1, :-2] & usable[1:-1, 2:]
        & usable[:-2, 1:-1] & usable[2:, 1:-1]
    )
    lat = np.deg2rad(axes[0][order[0]])
    dlon = np.deg2rad(abs(steps[1][0]))
    south = ((lat[:-2] + lat[1:-1]) / 2)[:, None]
    north = ((lat[1:-1] + lat[2:]) / 2)[:, None]
    area = EARTH_RADIUS_M ** 2 * dlon * (np.sin(north) - np.sin(south))
    zonal_face_length = EARTH_RADIUS_M * (north - south)
    south_length = EARTH_RADIUS_M * dlon * np.cos(south)
    north_length = EARTH_RADIUS_M * dlon * np.cos(north)

    q0, u0, v0 = q[interior], u[interior], v[interior]
    winds = (
        (u0 + u[1:-1, 2:]) / 2 * zonal_face_length,
        -(u0 + u[1:-1, :-2]) / 2 * zonal_face_length,
        (v0 + v[2:, 1:-1]) / 2 * north_length,
        -(v0 + v[:-2, 1:-1]) / 2 * south_length,
    )
    humidity = tuple((q0 + neighbor) / 2 for neighbor in
                     (q[1:-1, 2:], q[1:-1, :-2], q[2:, 1:-1], q[:-2, 1:-1]))
    total = -sum(wind * q_face for wind, q_face in zip(winds, humidity)) / area
    wind_convergence = -q0 * sum(winds) / area
    moisture_advection = -sum(wind * (q_face - q0) for wind, q_face in zip(winds, humidity)) / area

    usable_output = np.zeros(shape, dtype=bool)
    usable_output[interior] = center_valid
    result = []
    for term in (total, wind_convergence, moisture_advection):
        array = np.full(shape, np.nan, dtype=np.float64)
        array[interior] = np.where(center_valid, term, np.nan)
        result.append(array[order])
    return *result, usable_output[order]


def experiment():
    lat = np.arange(23.0, 25.01, 0.25)
    lon = np.arange(100.0, 102.01, 0.25)
    dlat = np.deg2rad(0.25)
    phi = np.deg2rad(lat)[:, None]
    x = EARTH_RADIUS_M * np.cos(phi) * np.deg2rad(lon - lon.mean())
    ps = np.full_like(x, 90_000.0)
    mask = np.ones_like(x, dtype=bool)
    q = np.full_like(x, 0.012)
    no_wind = np.zeros_like(x)
    east_wind = np.full_like(x, 8.0)
    analytic_wind_divergence = 2e-5
    # The sinc factor gives the exact cell-integrated zonal derivative.
    distance = x * (np.sin(dlat / 2) / (dlat / 2))
    inward_wind = -analytic_wind_divergence * distance

    def solve(q, u, v, ps=ps, mask=mask):
        return convergence700(lat, lon, q, u, v, ps, mask)

    flat, flat_wind, flat_advection, interior = solve(q, inward_wind, no_wind)
    uniform, *_ = solve(q, east_wind, no_wind)
    # A positive terrain gradient would give positive upslope forcing in this wind.
    upslope_m_s = float(east_wind[0, 0] * 0.04)
    assert upslope_m_s > 0
    west_moister = q - 2e-8 * distance
    gradient, grad_wind, grad_advection, _ = solve(west_moister, east_wind, no_wind)
    curved, *_ = solve(q, no_wind, east_wind)
    curve_expected = np.broadcast_to(0.012 * 8.0 * np.tan(phi) / EARTH_RADIUS_M, x.shape)
    for observed, expected in ((flat[interior], 0.012 * analytic_wind_divergence),
                               (flat_wind[interior], flat[interior]), (uniform[interior], 0.0),
                               (flat_advection[interior], 0.0), (gradient[interior], 8.0 * 2e-8),
                               (grad_wind[interior], 0.0), (grad_advection[interior], gradient[interior]),
                               (curved[interior], curve_expected[interior])):
        np.testing.assert_allclose(observed, expected, rtol=1e-11, atol=1e-17)

    mixed, wind, advection, _ = solve(west_moister, inward_wind, east_wind)
    np.testing.assert_allclose(mixed[interior], (wind + advection)[interior], rtol=1e-11, atol=1e-17)
    flipped = convergence700(lat[::-1], lon, west_moister[::-1], inward_wind[::-1], east_wind[::-1],
                             ps[::-1], mask[::-1])
    np.testing.assert_array_equal(flipped[0][::-1], mixed)
    area_by_lat = EARTH_RADIUS_M ** 2 * dlat * 2 * np.cos(phi) * np.sin(dlat / 2)
    integral = np.nansum(flat * area_by_lat)
    boundary = 0.012 * EARTH_RADIUS_M * dlat * np.sum(
        (inward_wind[1:-1, 0] + inward_wind[1:-1, 1]
         - inward_wind[1:-1, -1] - inward_wind[1:-1, -2]) / 2
    )
    np.testing.assert_allclose(integral, boundary, rtol=1e-11, atol=1e-12)

    ps[3, 3] = LEVEL_PA
    mask[5, 5] = False
    invalid, _, _, supported = solve(q, inward_wind, no_wind)
    expected_support = interior.copy()
    for row, col in ((3, 3), (5, 5)):
        expected_support[row - 1:row + 2, col] = False
        expected_support[row, col - 1:col + 2] = False
    np.testing.assert_array_equal(supported, expected_support)
    np.testing.assert_array_equal(np.isfinite(invalid), expected_support)
    return {
        "decision": "PASS_SYNTHETIC_OPERATOR_ONLY",
        "stage_3": "NOT_VERIFIED",
        "flat_wind_convergence_s_inv": float(np.nanmean(flat)),
        "pure_moisture_advection_s_inv": float(np.nanmean(gradient)),
        "uniform_humidity_upslope_test_m_s": upslope_m_s,
        "uniform_humidity_upslope_mfc_s_inv": float(np.nanmax(np.abs(uniform))),
        "area_integral_residual_m2_s_inv": float(abs(integral - boundary)),
        "decomposition_max_residual_s_inv": float(np.nanmax(np.abs(mixed - wind - advection))),
        "usable_cells_after_two_invalid_input_points": int(np.sum(supported)),
        "real_source_reads": 0,
        "checkpoint_loads": 0,
        "optimizer_updates": 0,
    }


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2, allow_nan=False))
