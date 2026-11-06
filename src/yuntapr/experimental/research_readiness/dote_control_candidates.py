"""Isolated, array-only DOTE control candidates; not a training integration.

The caller supplies artificial or separately authorized arrays. This module
never opens data, changes PhysicalDote, dispatches a task, or grants approval.
Changing direction tests a representation, not physical uplift causality.
Removing numeric channels is FEATURE_AVAILABILITY conditional on the retained
real masks; it does not match effective capacity or remove all mask information.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib

import numpy as np


CHANNELS = ('O850', 'O700', 'W850', 'W700', 'L850', 'L700', 'M850', 'M700')
PRESSURES_PA = (85000, 70000)


@dataclass(frozen=True)
class WindControl:
    u_east: np.ndarray
    v_north: np.ndarray
    valid: np.ndarray
    metadata: dict


@dataclass(frozen=True)
class NumericControl:
    values: np.ndarray
    valid: np.ndarray
    metadata: dict


def _winds(u_east, v_north, valid, *, unit, pressure_levels_pa):
    if unit != 'm/s' or tuple(pressure_levels_pa) != PRESSURES_PA:
        raise ValueError('Explicit m/s and frozen 85000,70000 Pa order required')
    u, v, m = np.asarray(u_east), np.asarray(v_north), np.asarray(valid)
    if (u.ndim != 3 or u.shape[0] != 2 or not all(u.shape[1:])
            or v.shape != u.shape or m.shape != u.shape or m.dtype != np.bool_
            or not np.issubdtype(u.dtype, np.floating)
            or not np.issubdtype(v.dtype, np.floating)):
        raise ValueError('Two-level floating winds and aligned bool validity required')
    if not np.isfinite(u[m]).all() or not np.isfinite(v[m]).all():
        raise ValueError('Nonfinite valid wind')
    # Invalid source numbers are never promoted to valid observations.
    return (np.where(m, u, 0.).astype(np.float64),
            np.where(m, v, 0.).astype(np.float64), m.copy())


def _wind_result(u, v, m, *, kind, extra):
    if not np.isfinite(u[m]).all() or not np.isfinite(v[m]).all():
        raise FloatingPointError('Candidate wind overflow; no clipping permitted')
    return WindControl(np.where(m, u, np.nan), np.where(m, v, np.nan), m.copy(), {
        'status': 'CANDIDATE_NOT_EXECUTED', 'kind': kind,
        'scope': 'DOTE_INTERNAL_WIND_ONLY_NOT_MEE_OR_STATIC_INPUTS',
        'unit': 'm/s', 'pressure_levels_pa': PRESSURES_PA,
        'real_masks_retained': True,
        'effective_capacity_equivalence': 'NOT_ESTABLISHED',
        'physical_causality': 'NOT_IDENTIFIED',
        'distribution_and_geographical_confounds_remain': True, **extra,
    })


def fixed_wind_direction(u_east, v_north, valid, *, direction_degrees,
                         unit, pressure_levels_pa):
    """Keep speed at every valid cell; use one predeclared east/north angle.

    Angle zero means toward east, 90 toward north, not a meteorological
    wind-from bearing. An angle choice is a scientific proposal, not a sweep.
    """
    if (isinstance(direction_degrees, (bool, np.bool_))
            or not np.isscalar(direction_degrees)
            or not np.isfinite(direction_degrees)
            or not 0 <= direction_degrees < 360):
        raise ValueError('Explicit finite direction in [0,360) degrees required')
    u, v, m = _winds(u_east, v_north, valid, unit=unit,
                     pressure_levels_pa=pressure_levels_pa)
    with np.errstate(over='ignore', invalid='ignore'):
        speed = np.hypot(u, v)
        theta = np.deg2rad(float(direction_degrees))
        a, b = speed * np.cos(theta), speed * np.sin(theta)
    return _wind_result(a, b, m, kind='FIXED_WIND_DIRECTION', extra={
        'direction_degrees_toward_east_north': float(direction_degrees),
        'speed_preserved': True, 'direction_information_removed': True,
    })


def scene_rotation_degrees(*, scene_id, scene_time, control_seed):
    """Stable label-free scene angle, independent of model seed/order/RNG.

    Only explicit 2023/2024 UTC identities are supported. No model seed,
    outcome, rainfall label, fitted quantity or file path is accepted.
    """
    if not isinstance(scene_id, str) or not scene_id.strip():
        raise ValueError('Explicit nonempty scene identity required')
    if (not isinstance(scene_time, datetime) or scene_time.tzinfo is None
            or scene_time.utcoffset() is None):
        raise ValueError('Explicit timezone-aware scene time required')
    utc_time = scene_time.astimezone(timezone.utc)
    if utc_time.year not in (2023, 2024):
        raise PermissionError('Only 2023/2024 development scene identities supported')
    if (isinstance(control_seed, (bool, np.bool_))
            or not isinstance(control_seed, (int, np.integer))
            or not 0 <= int(control_seed) < 2**64):
        raise ValueError('Explicit independent uint64 control seed required')
    # Length-prefix the ID: separators inside IDs cannot cause key collisions.
    sid = scene_id.encode('utf-8')
    prefix = ('YunTAPR-DOTE-SCENE-ROTATION-V1\0'
              f'{int(control_seed)}\0{utc_time.isoformat(timespec="microseconds")}\0').encode('ascii')
    digest = hashlib.sha256(prefix + len(sid).to_bytes(8, 'big') + sid).digest()
    mantissa = int.from_bytes(digest[:8], 'big') >> 11
    return mantissa * (360. / (2**53))


def scene_random_rotation(u_east, v_north, valid, *, scene_id, scene_time,
                          control_seed, unit, pressure_levels_pa):
    """Rotate the whole scene and both pressure levels by the same angle.

    This retains each speed and relative directions within the scene/levels,
    but changes projections on the real terrain and their scalar distribution.
    It is not a conditional randomization test or an exchangeability claim.
    """
    angle = scene_rotation_degrees(scene_id=scene_id, scene_time=scene_time,
                                   control_seed=control_seed)
    u, v, m = _winds(u_east, v_north, valid, unit=unit,
                     pressure_levels_pa=pressure_levels_pa)
    theta = np.deg2rad(angle)
    with np.errstate(over='ignore', invalid='ignore'):
        a = u * np.cos(theta) - v * np.sin(theta)
        b = u * np.sin(theta) + v * np.cos(theta)
    return _wind_result(a, b, m, kind='SCENE_FIXED_RANDOM_ROTATION', extra={
        'angle_degrees': angle, 'control_seed': int(control_seed),
        'scene_id': scene_id,
        'scene_time_utc': scene_time.astimezone(timezone.utc).isoformat(),
        'hash_scheme': 'SHA256_V1_LENGTH_PREFIXED_ID_TOP53_BITS',
        'speed_preserved': True, 'same_angle_for_scene_and_levels': True,
        'conditional_randomization_test': False,
    })


def _numeric(values, valid, *, channel_order):
    x, m = np.asarray(values), np.asarray(valid)
    if (tuple(channel_order) != CHANNELS or x.ndim != 3 or x.shape[0] != 8
            or not all(x.shape[1:]) or m.shape != x.shape or m.dtype != np.bool_
            or not np.issubdtype(x.dtype, np.floating)):
        raise ValueError('Explicit frozen eight-channel floating values and bool masks required')
    if not np.isfinite(x[m]).all():
        raise ValueError('Nonfinite valid dynamic value')
    return x.copy(), m.copy()


def _remove(values, valid, indices, *, channel_order, kind):
    x, m = _numeric(values, valid, channel_order=channel_order)
    for i in indices:
        x[i] = np.where(m[i], 0., np.nan)
    return NumericControl(x, m, {
        'status': 'CANDIDATE_NOT_EXECUTED', 'kind': kind,
        'interpretation': 'FEATURE_AVAILABILITY_CONDITIONAL_ON_REAL_MASKS',
        'removed_numeric_channels': tuple(CHANNELS[i] for i in indices),
        'real_masks_retained': True,
        'removed_level_or_moisture_mask_information': False,
        'effective_capacity_equivalence': False,
        'structurally_zero_numeric_projection_columns': len(indices),
        'width16_structurally_zero_loss_gradient_weights': 16 * len(indices),
        'physical_causality': 'NOT_IDENTIFIED',
    })


def remove_moisture_numbers(values, valid, *, channel_order):
    """Set M850/M700 numbers to zero; retain actual moisture-validity bits."""
    return _remove(values, valid, (6, 7), channel_order=channel_order,
                   kind='REMOVE_M_NUMBERS_KEEP_REAL_MASKS')


def select_pressure_level_numbers(values, valid, *, level_pa, channel_order):
    """Keep one level's O/W/L/M numbers; retain BOTH levels' real masks.

    This is not a model using only that pressure level's information, because
    validity information from the opposite level is deliberately retained.
    """
    if isinstance(level_pa, (bool, np.bool_)) or level_pa not in PRESSURES_PA:
        raise ValueError('Select explicit 85000 or 70000 Pa; units are not inferred')
    removed = (1, 3, 5, 7) if level_pa == 85000 else (0, 2, 4, 6)
    return _remove(values, valid, removed, channel_order=channel_order,
                   kind=f'KEEP_{int(level_pa)}PA_NUMBERS_KEEP_BOTH_REAL_MASKS')


def reject_post_mask_unmasking():
    """No upstream discarded pressure support can be restored by this module."""
    raise PermissionError('Post-mask invalid values cannot be reconstructed or made valid; '
                          'an independent source-bound scientific proposal is required')


def reject_unbound_specific_humidity():
    """No implicit RH/T-to-q derivation or PWAT unit substitution is implemented."""
    raise NotImplementedError('q_k source, units, derivation and authorization are unbound; '
                              'this candidate does not derive specific humidity')
