"""Artificial metadata stubs and DOTE arrays; no model or source I/O."""
import copy
from datetime import datetime, timedelta, timezone
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from yuntapr.experimental.core_innovation.gfs import EnvironmentFrame, Field, ForecastIdentity
from yuntapr.experimental.core_innovation.grid import GridSpec
from yuntapr.experimental.core_innovation.stage3.planning import digest
from yuntapr.experimental.research_readiness.dote_direction_transform import (
    DirectionControl, DirectionDoteTransform,
)
from yuntapr.experimental.research_readiness.dote_transform_factory import (
    bind_direction_transform_factory, RoleBoundDirectionTransform,
)


class InMemoryPlanStub:
    def __init__(self, identity, rows):
        self.identity, self.rows = identity, rows

    def ids(self, role):
        return tuple(self.rows[role])


def record(year, hour):
    start = datetime(year, 6, 1, hour, 30, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    text = lambda t: t.strftime('%Y-%m-%dT%H:%M:%SZ')
    return dict(sample_id=text(start), window_start=text(start), analysis_time=text(end))


def inputs(dev_rows=None):
    rows = {'Train': [record(2023, 11), record(2023, 17)],
            'Development': [record(2024, 11)] if dev_rows is None else dev_rows}
    manifests = {}
    for role, values in rows.items():
        body = dict(scene_records=values, role=role, purpose='ARTIFICIAL_ONLY')
        manifests[role] = dict(body, manifest_sha256=digest(body))
    identity = dict(population_sha256='a'*64, populations_sha256='b'*64,
        statistics_sha256='c'*64, target_QC_sha256='d'*64, lead=6,
        mode='retrospective', train=len(rows['Train']), dev=len(rows['Development']),
        candidate_manifest_sha256={r: m['manifest_sha256'] for r, m in manifests.items()})
    plan = InMemoryPlanStub(identity, {
        role: {row['sample_id']: copy.deepcopy(row) for row in values}
        for role, values in rows.items()})
    ids = {role: plan.ids(role) for role in rows}
    return plan, ids, manifests


def bind(plan, ids, manifests, **changes):
    kwargs = dict(ids_by_role=ids, manifests_by_role=manifests,
        expected_plan_identity=copy.deepcopy(plan.identity),
        canonical_time_role='ANALYSIS_TIME_UTC',
        control=DirectionControl('FIXED_DIRECTION', direction_degrees=0.))
    kwargs.update(changes)
    return bind_direction_transform_factory(plan, **kwargs)


def pack_and_definition():
    grid = GridSpec(np.linspace(25., 24., 100), np.linspace(101., 102., 100))
    values = np.zeros((6, 100, 100), dtype=float)
    values[1] = 1.; values[5] = 1.
    pack = SimpleNamespace(channels=tuple(range(6)), values=values,
                           valid=np.ones_like(values, dtype=bool), grid=grid)
    definition = SimpleNamespace(pwat_reference_kg_m2=10.,
        reference_provenance='ARTIFICIAL_NOT_FITTED', moisture_basis='windward_W',
        velocity_reference_m_s=1.)
    return pack, definition


def frame_for(row, grid):
    stamp = datetime.fromisoformat(row['analysis_time'].replace('Z', '+00:00'))
    identity = ForecastIdentity(stamp-timedelta(hours=6), timedelta(hours=6), stamp)
    # Routing is stubbed below; no meteorological arrays or computation.
    return EnvironmentFrame(identity, grid, {}, 'retrospective', ())


class DoteTransformFactoryTests(unittest.TestCase):
    def test_real_wrapper_receives_routed_artificial_frames_and_preserves_inputs(self):
        plan, ids, manifests = inputs()
        pack, definition = pack_and_definition()
        factory = bind(plan, ids, manifests)
        with patch('builtins.open', side_effect=AssertionError('No bridge source I/O')):
            transform = factory(pack, definition)
            for role in ('Train', 'Development'):
                row = plan.rows[role][ids[role][0]]
                f = frame_for(row, pack.grid)
                shape = pack.grid.shape
                fields = {f'{axis}{level}': Field(
                    np.full(shape, 3. if axis == 'u' else 4.),
                    np.ones(shape, dtype=bool), axis, 'm/s', level*100.)
                    for axis in ('u', 'v') for level in (850, 700)}
                fields['ps'] = Field(np.full(shape, 100000.), np.ones(shape, dtype=bool),
                                     'surface_pressure', 'Pa', None)
                fields['pwat'] = Field(np.full(shape, 20.), np.ones(shape, dtype=bool),
                                       'precipitable_water', 'kg m-2', None)
                fields['ps'].values[0, 0] = 85000.
                fields['pwat'].valid[1, 1] = False
                f = EnvironmentFrame(f.identity, f.grid, fields, f.mode, f.provenance)
                before = copy.deepcopy(fields)
                values, valid = transform(f)
                self.assertEqual(values.shape, (8, 100, 100))
                self.assertEqual(values.dtype, np.float32)
                np.testing.assert_allclose(values[:4][valid[:4]], 5.)
                np.testing.assert_allclose(values[4:6][valid[4:6]], 0.)
                np.testing.assert_allclose(values[6:][valid[6:]], 10.)
                self.assertFalse(valid[0, 0, 0])
                self.assertTrue(valid[1, 0, 0])
                self.assertFalse(valid[6:, 1, 1].any())
                self.assertTrue((values[~valid] == 0.).all())
                for key in fields:
                    np.testing.assert_array_equal(fields[key].values, before[key].values)
                    np.testing.assert_array_equal(fields[key].valid, before[key].valid)

    def test_two_argument_seam_routes_original_role_manifests_without_combining(self):
        plan, ids, manifests = inputs()
        factory = bind(plan, ids, manifests)
        self.assertEqual(list(inspect.signature(factory).parameters), ['pack', 'definition'])
        pack, definition = pack_and_definition()
        transform = factory(pack, definition)
        self.assertIsInstance(transform, RoleBoundDirectionTransform)
        self.assertFalse(transform.binding.experiment_ready)
        self.assertFalse(transform.binding.default_reader_registered)
        self.assertFalse(transform.binding.source_payloads_verified)
        self.assertFalse(transform.binding.authorization_granted)
        for role in ('Train', 'Development'):
            inner = transform.transforms_by_role[role]
            self.assertEqual(inner.lookup.manifest_sha256, manifests[role]['manifest_sha256'])
            self.assertEqual(tuple(b.sample_id for b in inner.lookup.bindings), ids[role])
        with patch.object(DirectionDoteTransform, '__call__', autospec=True,
                          side_effect=lambda self, frame: self.lookup.resolve(frame.identity.valid).sample_id):
            for role in ('Train', 'Development'):
                row = plan.rows[role][ids[role][0]]
                self.assertEqual(transform(frame_for(row, pack.grid)), ids[role][0])
        with self.assertRaises(TypeError):
            transform.transforms_by_role['Train'] = object()

    def test_missing_complete_manifest_fails_without_open_or_rows_reconstruction(self):
        plan, ids, manifests = inputs()
        with patch('builtins.open', side_effect=AssertionError('No bridge I/O')):
            for bad in (None, {}, {'Train': manifests['Train']},
                        {'Train': 'manifest.json', 'Development': manifests['Development']},
                        {'Train': {'scene_records': list(plan.rows['Train'].values())},
                         'Development': manifests['Development']}):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    bind(plan, ids, bad)

    def test_expected_identity_role_membership_and_accepted_rows_must_match(self):
        plan, ids, manifests = inputs()
        wrong = copy.deepcopy(plan.identity); wrong['population_sha256'] = 'e'*64
        with self.assertRaises(ValueError):
            bind(plan, ids, manifests, expected_plan_identity=wrong)
        for bad in ({'Train': ids['Train']},
                    ids | {'Train': ids['Train'][::-1]},
                    ids | {'Train': ids['Train'][:1]},
                    ids | {'Train': ids['Train'] + ids['Train'][:1]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                bind(plan, bad, manifests)
        plan.rows['Train'][ids['Train'][0]]['extra_identity'] = 'differs'
        with self.assertRaisesRegex(ValueError, 'accepted plan rows differ'):
            bind(plan, ids, manifests)

    def test_role_collision_and_ambiguous_analysis_rejected(self):
        same = record(2023, 11)
        plan, ids, manifests = inputs([same])
        with self.assertRaisesRegex(ValueError, 'membership conflicts'):
            bind(plan, ids, manifests)
        # Distinct literal IDs with the same UTC instant still cannot own a frame twice.
        shifted = dict(same, sample_id='2023-06-01T19:30:00+08:00',
                       window_start='2023-06-01T19:30:00+08:00')
        plan, ids, manifests = inputs([shifted])
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            bind(plan, ids, manifests)

    def test_snapshots_do_not_follow_manifest_edits_and_plan_drift_stops_factory(self):
        plan, ids, manifests = inputs()
        factory = bind(plan, ids, manifests)
        pack, definition = pack_and_definition()
        manifests['Train']['scene_records'][0]['sample_id'] = 'changed after binding'
        transform = factory(pack, definition)
        self.assertEqual(transform.transforms_by_role['Train'].lookup.bindings[0].sample_id,
                         ids['Train'][0])
        public = factory.population_identity; public['candidate_manifest_sha256']['Train'] = 'e'*64
        self.assertNotEqual(factory.population_identity['candidate_manifest_sha256']['Train'], 'e'*64)
        plan.identity['statistics_sha256'] = 'e'*64
        with self.assertRaisesRegex(ValueError, 'changed after factory binding'):
            factory(pack, definition)

    def test_pack_definition_and_unknown_frame_are_rejected_without_fallback(self):
        plan, ids, manifests = inputs(); factory = bind(plan, ids, manifests)
        pack, definition = pack_and_definition()
        with self.assertRaises(ValueError):
            factory(pack, SimpleNamespace(pwat_reference_kg_m2=10.))
        bad = copy.deepcopy(pack); bad.valid = bad.valid.astype(np.uint8)
        with self.assertRaises(ValueError):
            factory(bad, definition)
        transform = factory(pack, definition)
        unknown = frame_for(record(2024, 17), pack.grid)
        with self.assertRaisesRegex(ValueError, 'absent'):
            transform(unknown)
        with self.assertRaises(ValueError):
            transform(object())
        # Terrain snapshot contains the same physical mapping, without a model.
        pack.values[1].fill(7.)
        self.assertTrue((transform.transforms_by_role['Train'].terrain.east_gradient == 1.).all())


if __name__ == '__main__':
    unittest.main()
