"""Isolated frame-callable DOTE control; no I/O or production registration.

The caller supplies a manifest already in memory and an explicit identity list.
Its digest is checked, but research authorization and source/payload provenance
are not established here. Real integration, data access and experiments remain
separately gated. No default reader, model, MEE tensor or static pack is changed.
"""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from types import MappingProxyType

import numpy as np

from ..core_innovation.dote import dote_proxy
from ..core_innovation.gfs import EnvironmentFrame, _above_ground
from ..core_innovation.stage2.dote_v13 import complete_dote
from ..core_innovation.stage3.planning import digest
from ..core_innovation.terrain import TerrainFeatures
from .dote_control_candidates import (
    CHANNELS, PRESSURES_PA, fixed_wind_direction, scene_random_rotation,
)


EXPERIMENT_READY = False
_TIME_ROLES = ('ANALYSIS_TIME_UTC', 'WINDOW_START_UTC')


def _time(value):
    if not isinstance(value, str) or value != value.strip():
        raise ValueError('Explicit timestamp string required')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError('Timezone-aware timestamp required')
    stamp = stamp.astimezone(timezone.utc)
    if stamp.year not in (2023, 2024) or not 3 <= stamp.month <= 10:
        raise PermissionError('Only March-October 2023/2024 scene metadata')
    return stamp


@dataclass(frozen=True)
class SceneBinding:
    sample_id: str
    window_start: datetime
    analysis: datetime
    canonical_scene_time: datetime


@dataclass(frozen=True, init=False)
class SceneManifestLookup:
    """Exact analysis -> scene lookup from the existing scene_records schema.

    Digest follows the unchanged stage3 planning.digest convention, excluding
    manifest_sha256 itself. IDs must come from a separately declared population;
    a shared omission in manifest and IDs is not detectable by this interface.
    """
    manifest_sha256: str
    canonical_time_role: str
    bindings: tuple[SceneBinding, ...]
    _by_analysis: Mapping

    def __init__(self, manifest, *, accepted_ids, expected_manifest_sha256,
                 canonical_time_role):
        if canonical_time_role not in _TIME_ROLES:
            raise ValueError('Declare canonical scene time role explicitly')
        if (not isinstance(expected_manifest_sha256, str)
                or re.fullmatch('[0-9a-f]{64}', expected_manifest_sha256) is None
                or not isinstance(manifest, Mapping)):
            raise ValueError('Manifest and canonical expected SHA256 required')
        body = dict(manifest)
        embedded = body.pop('manifest_sha256', None)
        if embedded != expected_manifest_sha256 or digest(body) != embedded:
            raise ValueError('Manifest content or expected fingerprint differs')
        if (not isinstance(accepted_ids, Sequence)
                or isinstance(accepted_ids, (str, bytes)) or not accepted_ids
                or any(not isinstance(s, str) or not s or s != s.strip()
                       for s in accepted_ids)
                or len(set(accepted_ids)) != len(accepted_ids)):
            raise ValueError('Nonempty ordered unique population IDs required')
        records = body.get('scene_records')
        if not isinstance(records, list) or not records:
            raise ValueError('Existing scene_records list required')
        by_id, analyses = {}, set()
        for row in records:
            if not isinstance(row, Mapping):
                raise ValueError('Explicit scene record required')
            sid = row.get('sample_id')
            start, analysis = _time(row.get('window_start')), _time(row.get('analysis_time'))
            if not isinstance(sid, str) or not sid or sid != sid.strip():
                raise ValueError('Explicit sample_id required')
            if _time(sid) != start or analysis - start != timedelta(minutes=30):
                raise ValueError('Inherited sample ID / half-hour window conflict')
            if sid in by_id or analysis in analyses:
                raise ValueError('Duplicate scene or ambiguous analysis time')
            analyses.add(analysis)
            canonical = analysis if canonical_time_role == 'ANALYSIS_TIME_UTC' else start
            by_id[sid] = SceneBinding(sid, start, analysis, canonical)
        if any(sid not in by_id for sid in accepted_ids):
            raise ValueError('Declared population scene missing from manifest')
        bindings = tuple(by_id[sid] for sid in accepted_ids)
        object.__setattr__(self, 'manifest_sha256', embedded)
        object.__setattr__(self, 'canonical_time_role', canonical_time_role)
        object.__setattr__(self, 'bindings', bindings)
        object.__setattr__(self, '_by_analysis', MappingProxyType({b.analysis: b for b in bindings}))

    def resolve(self, analysis):
        if (not isinstance(analysis, datetime) or analysis.tzinfo is None
                or analysis.utcoffset() is None):
            raise ValueError('Explicit aware frame analysis time required')
        key = analysis.astimezone(timezone.utc)
        if key not in self._by_analysis:
            raise ValueError('Frame analysis absent from declared manifest population')
        return self._by_analysis[key]


@dataclass(frozen=True)
class DirectionControl:
    kind: str
    control_seed: int | None = None
    direction_degrees: float | None = None

    def __post_init__(self):
        if self.kind == 'SCENE_RANDOM_ROTATION':
            if (isinstance(self.control_seed, (bool, np.bool_))
                    or not isinstance(self.control_seed, (int, np.integer))
                    or not 0 <= int(self.control_seed) < 2**64
                    or self.direction_degrees is not None):
                raise ValueError('Explicit independent uint64 seed, no fixed angle')
        elif self.kind == 'FIXED_DIRECTION':
            a = self.direction_degrees
            if (self.control_seed is not None or isinstance(a, (bool, np.bool_))
                    or not isinstance(a, (int, float, np.integer, np.floating))
                    or not np.isfinite(a) or not 0 <= a < 360):
                raise ValueError('Explicit toward-east/north angle, no random seed')
        else:
            raise ValueError('Only the two explicit direction candidates supported')


class DirectionDoteTransform:
    """Candidate dynamic_transform(frame), reusing unchanged physical formulas.

    Terrain/definition are supplied explicitly, e.g. from a separately approved
    PhysicalDote instance. No reader or source is constructed. Only local winds
    after native masks and target mapping are replaced. Original support must
    remain identical; changed validity stops instead of filtering samples.
    """
    def __init__(self, terrain, lookup, control, *, pwat_reference_kg_m2,
                 reference_provenance, moisture_basis, velocity_reference_m_s):
        if (not isinstance(terrain, TerrainFeatures)
                or not isinstance(lookup, SceneManifestLookup)
                or not isinstance(control, DirectionControl)):
            raise ValueError('Explicit terrain, scene lookup and direction control required')
        if (not np.isfinite(pwat_reference_kg_m2) or pwat_reference_kg_m2 <= 0
                or not isinstance(reference_provenance, str) or not reference_provenance.strip()
                or moisture_basis not in ('windward_W', 'signed_O')
                or velocity_reference_m_s != 1.0):
            raise ValueError('Explicit inherited PWAT definition and 1 m/s scale required')
        self.terrain, self.lookup, self.control = terrain, lookup, control
        self.pwat_reference = float(pwat_reference_kg_m2)
        self.reference_provenance = reference_provenance
        self.moisture_basis = moisture_basis

    def physical(self, frame):
        if (not isinstance(frame, EnvironmentFrame) or frame.mode != 'retrospective'
                or frame.identity.lead != timedelta(hours=6)):
            raise ValueError('Inherited retrospective f006 frame required')
        scene = self.lookup.resolve(frame.identity.valid)
        native = EnvironmentFrame(frame.identity, frame.grid, _above_ground(frame.fields),
                                  frame.mode, frame.provenance)
        mapped = native if frame.grid.identity == self.terrain.grid.identity else native.on_grid(
            self.terrain.grid, operator='bilinear_point_candidate')
        fields = mapped.fields
        for p in (850, 700):
            for axis in ('u', 'v'):
                f = fields[f'{axis}{p}']
                if f.quantity != axis or f.unit != 'm/s' or f.level_pa != p * 100.:
                    raise ValueError('Physical vector wind identity differs')
        ps, pw = fields['ps'], fields['pwat']
        if (ps.quantity != 'surface_pressure' or ps.unit != 'Pa'
                or pw.quantity != 'precipitable_water' or pw.unit != 'kg m-2'):
            raise ValueError('Canonical PS/PWAT quantities and units required')
        u = np.stack([fields[f'u{p}'].values for p in (850, 700)])
        v = np.stack([fields[f'v{p}'].values for p in (850, 700)])
        mask = np.stack([fields[f'u{p}'].valid & fields[f'v{p}'].valid for p in (850, 700)])
        kwargs = dict(unit='m/s', pressure_levels_pa=PRESSURES_PA)
        if self.control.kind == 'SCENE_RANDOM_ROTATION':
            wind = scene_random_rotation(u, v, mask, scene_id=scene.sample_id,
                scene_time=scene.canonical_scene_time, control_seed=self.control.control_seed, **kwargs)
        else:
            wind = fixed_wind_direction(u, v, mask,
                direction_degrees=self.control.direction_degrees, **kwargs)
        def proxy(a, b, valid):
            return dote_proxy(self.terrain, a, b, valid, np.array([850., 700.]),
                ps.values, ps.valid, wind_grid=mapped.grid, wind_unit='m/s',
                pressure_unit='hPa', surface_pressure_unit='Pa')
        baseline = proxy(u, v, mask)
        controlled = proxy(wind.u_east, wind.v_north, wind.valid)
        if not np.array_equal(wind.valid, mask) or not np.array_equal(controlled.valid, baseline.valid):
            raise FloatingPointError('DOTE support changed; no filtering, clipping or unmasking')
        result = complete_dote(controlled, pw.values, pw.valid, pwat_grid=mapped.grid,
            pwat_unit='kg m-2', pwat_reference_kg_m2=self.pwat_reference,
            reference_provenance=self.reference_provenance, moisture_basis=self.moisture_basis)
        result.definition['direction_control'] = dict(wind.metadata,
            manifest_sha256=self.lookup.manifest_sha256,
            canonical_time_role=self.lookup.canonical_time_role,
            scene_id=scene.sample_id, scene_time_utc=scene.canonical_scene_time.isoformat(),
            identity_scope='IN_MEMORY_MANIFEST_DIGEST_NOT_PAYLOAD_OR_AUTHORIZATION_VERIFIED',
            default_reader_registered=False, experiment_ready=False)
        return result

    def __call__(self, frame):
        result = self.physical(frame)
        values, valid, keys = result.stack()
        if keys != CHANNELS:
            raise ValueError('Inherited eight-channel order differs')
        with np.errstate(over='ignore', invalid='ignore'):
            values = np.where(valid, values, 0.).astype(np.float32)
        if not np.isfinite(values).all():
            raise FloatingPointError('DOTE float32 conversion overflow; no clipping')
        return values, valid.copy()
