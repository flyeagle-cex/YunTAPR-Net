"""Explicit in-memory bridge to the two-argument dynamic-transform seam.

The unchanged run_task calls dynamic_transform_factory(pack, definition), but
does not pass its newly constructed PopulationPlan. PopulationPlan retains
accepted rows and identity claims, not complete original manifest bodies.
An authorized future dispatcher must explicitly build this closure from an
already validated in-memory plan AND complete in-memory original manifests.
This module never opens them, rebuilds a fake manifest from rows, registers a
default, dispatches a task, or establishes payload provenance/authorization.
"""
from collections.abc import Mapping, Sequence
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType

import numpy as np

from ..core_innovation.gfs import EnvironmentFrame
from ..core_innovation.grid import GridSpec
from ..core_innovation.stage3.planning import digest
from ..core_innovation.terrain import TerrainFeatures
from .dote_direction_transform import (
    DirectionControl, DirectionDoteTransform, SceneManifestLookup,
)


ROLES = ('Train', 'Development')
EXPERIMENT_READY = False
_REQUIRED_IDENTITY = frozenset({
    'population_sha256', 'populations_sha256', 'statistics_sha256',
    'target_QC_sha256', 'candidate_manifest_sha256',
    'lead', 'mode', 'train', 'dev',
})


def _ids(value, context):
    if (not isinstance(value, Sequence) or isinstance(value, (str, bytes))
            or not value or any(not isinstance(s, str) or not s
                                or s != s.strip() for s in value)
            or len(set(value)) != len(value)):
        raise ValueError(f'{context}: materialized nonempty unique ordered IDs required')
    return tuple(value)


def _plan_snapshot(plan):
    identity = getattr(plan, 'identity', None)
    rows = getattr(plan, 'rows', None)
    ids_method = getattr(plan, 'ids', None)
    if (not isinstance(identity, Mapping) or not _REQUIRED_IDENTITY <= set(identity)
            or not isinstance(rows, Mapping) or set(rows) != set(ROLES)
            or not callable(ids_method)):
        raise ValueError('Already materialized PopulationPlan identity/rows/ids required; no loader fallback')
    snapshot = copy.deepcopy(dict(identity))
    if (type(snapshot['lead']) is not int or snapshot['lead'] != 6
            or snapshot['mode'] != 'retrospective'
            or not isinstance(snapshot['candidate_manifest_sha256'], Mapping)
            or set(snapshot['candidate_manifest_sha256']) != set(ROLES)):
        raise ValueError('Existing retrospective f006 role identities required')
    role_ids, role_rows = {}, {}
    for role, count_key in (('Train', 'train'), ('Development', 'dev')):
        ids = _ids(ids_method(role), f'plan.ids({role})')
        if (type(snapshot[count_key]) is not int or snapshot[count_key] <= 0
                or len(ids) != snapshot[count_key]
                or not isinstance(rows[role], Mapping)
                or tuple(rows[role]) != ids):
            raise ValueError(f'{role}: identity count, ordered IDs or accepted rows differ')
        if any(not isinstance(rows[role][sid], Mapping) for sid in ids):
            raise ValueError(f'{role}: explicit accepted scene records required')
        role_ids[role] = ids
        role_rows[role] = {sid: copy.deepcopy(dict(rows[role][sid])) for sid in ids}
    if set(role_ids['Train']) & set(role_ids['Development']):
        raise ValueError('Train/Development scene membership conflicts')
    return snapshot, role_ids, role_rows


def _terrain_from_pack(pack):
    """Mirror only PhysicalDote.__init__'s B6-pack mapping, with owned arrays.

    No model is imported or instantiated. These are already physical B6 values,
    not learned/static normalized tensors; no scaler or source is inferred.
    """
    values = np.asarray(getattr(pack, 'values', None))
    valid = np.asarray(getattr(pack, 'valid', None))
    grid = getattr(pack, 'grid', None)
    channels = getattr(pack, 'channels', ())
    if (len(channels) != 6 or values.shape != (6, 100, 100)
            or valid.shape != values.shape or valid.dtype != np.bool_
            or not np.issubdtype(values.dtype, np.floating)
            or not isinstance(grid, GridSpec) or grid.shape != (100, 100)
            or not np.isfinite(values[valid]).all()):
        raise ValueError('Explicit in-memory physical B6 six-channel 100x100 pack required')
    v, m = values.copy(), valid.copy()
    return TerrainFeatures(grid, v[0], m[0], v[1], v[2], m[1] & m[2], v[3],
                           np.degrees(np.arctan2(v[4], v[5])) % 360., m[4] & m[5])


@dataclass(frozen=True)
class FactoryBinding:
    population_identity_sha256: str
    population_sha256: str
    manifest_sha256_by_role: tuple
    ordered_ids_sha256_by_role: tuple
    canonical_time_role: str
    scope: str = 'IN_MEMORY_IDENTITY_AND_ROW_AGREEMENT_NOT_PAYLOAD_OR_AUTHORIZATION_VERIFIED'
    source_payloads_verified: bool = False
    authorization_granted: bool = False
    default_reader_registered: bool = False
    experiment_ready: bool = False


class RoleBoundDirectionTransform:
    """One frame-callable using the separately bound original role manifests.

    It does not create a combined manifest or label its content with an old
    fingerprint. Each DirectionDoteTransform keeps its original role lookup.
    """
    def __init__(self, transforms, binding):
        self.transforms_by_role = MappingProxyType(dict(transforms))
        self.binding = binding
        by_analysis = {}
        for role in ROLES:
            for scene in self.transforms_by_role[role].lookup.bindings:
                if scene.analysis in by_analysis:
                    raise ValueError('Frame analysis has ambiguous Train/Development ownership')
                by_analysis[scene.analysis] = role
        self._by_analysis = MappingProxyType(by_analysis)

    def role_for(self, frame):
        if not isinstance(frame, EnvironmentFrame):
            raise ValueError('Explicit existing EnvironmentFrame required')
        stamp = frame.identity.valid
        if (not isinstance(stamp, datetime) or stamp.tzinfo is None
                or stamp.utcoffset() is None):
            raise ValueError('Aware frame analysis required')
        role = self._by_analysis.get(stamp.astimezone(timezone.utc))
        if role is None:
            raise ValueError('Frame analysis absent from both declared role populations')
        return role

    def physical(self, frame):
        return self.transforms_by_role[self.role_for(frame)].physical(frame)

    def __call__(self, frame):
        return self.transforms_by_role[self.role_for(frame)](frame)


class DirectionTransformFactory:
    """Closure with the actual dynamic_transform_factory(pack, definition) API.

    Compatibility does not install the closure in run_task. A future explicit
    dispatcher must bind it before calling that unchanged seam. The supplied
    plan's original validation is a caller prerequisite, not verified history.
    """
    def __init__(self, plan, snapshot, role_ids, role_rows, lookups, control,
                 canonical_time_role):
        self._plan = plan
        self._snapshot = copy.deepcopy(snapshot)
        self._role_ids = copy.deepcopy(role_ids)
        self._role_rows = copy.deepcopy(role_rows)
        self._lookups = MappingProxyType(dict(lookups))
        self._control = control
        self.binding = FactoryBinding(
            digest(snapshot), snapshot['population_sha256'],
            tuple((r, lookups[r].manifest_sha256) for r in ROLES),
            tuple((r, digest(role_ids[r])) for r in ROLES), canonical_time_role)

    @property
    def population_identity(self):
        return copy.deepcopy(self._snapshot)

    def __call__(self, pack, definition):
        current = _plan_snapshot(self._plan)
        if current != (self._snapshot, self._role_ids, self._role_rows):
            raise ValueError('Supplied in-memory plan changed after factory binding')
        names = ('pwat_reference_kg_m2', 'reference_provenance',
                 'moisture_basis', 'velocity_reference_m_s')
        if any(not hasattr(definition, name) for name in names):
            raise ValueError('Explicit existing DoteDefinition fields required; no defaults')
        terrain = _terrain_from_pack(pack)
        transforms = {role: DirectionDoteTransform(terrain, self._lookups[role], self._control,
                         **{name: getattr(definition, name) for name in names}) for role in ROLES}
        return RoleBoundDirectionTransform(transforms, self.binding)


def bind_direction_transform_factory(plan, *, ids_by_role, manifests_by_role,
                                     expected_plan_identity, canonical_time_role,
                                     control):
    """Bind already-loaded original role manifests; fail rather than discover I/O.

    Expected identity is the actual existing PopulationPlan.identity schema.
    Complete manifest bodies must already be in memory. Accepted rows alone,
    a file path, or a claimed fingerprint cannot substitute for that content.
    """
    snapshot, plan_ids, plan_rows = _plan_snapshot(plan)
    if not isinstance(expected_plan_identity, Mapping) or snapshot != dict(expected_plan_identity):
        raise ValueError('Expected and actual existing plan identities differ')
    if (not isinstance(ids_by_role, Mapping) or set(ids_by_role) != set(ROLES)
            or not isinstance(manifests_by_role, Mapping)
            or set(manifests_by_role) != set(ROLES)):
        raise ValueError('Both explicit role-ID lists and complete in-memory manifests required')
    if not isinstance(control, DirectionControl):
        raise ValueError('Explicit already specified direction control required')
    lookups = {}
    analyses = set()
    for role in ROLES:
        ids = _ids(ids_by_role[role], f'ids_by_role[{role}]')
        if ids != plan_ids[role]:
            raise ValueError(f'{role}: declared IDs differ from existing plan order/membership')
        manifest = manifests_by_role[role]
        if not isinstance(manifest, Mapping):
            raise ValueError(f'{role}: complete in-memory manifest required; no path or rows reconstruction')
        lookup = SceneManifestLookup(copy.deepcopy(dict(manifest)), accepted_ids=ids,
            expected_manifest_sha256=snapshot['candidate_manifest_sha256'][role],
            canonical_time_role=canonical_time_role)
        records = {row['sample_id']: row for row in manifest['scene_records']}
        if any(dict(records[sid]) != plan_rows[role][sid] for sid in ids):
            raise ValueError(f'{role}: original manifest and accepted plan rows differ')
        for scene in lookup.bindings:
            if scene.analysis in analyses:
                raise ValueError('Frame analysis has ambiguous Train/Development ownership')
            analyses.add(scene.analysis)
        lookups[role] = lookup
    return DirectionTransformFactory(plan, snapshot, plan_ids, plan_rows, lookups,
                                     control, canonical_time_role)
