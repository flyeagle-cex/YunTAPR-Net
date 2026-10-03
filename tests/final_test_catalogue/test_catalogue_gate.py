"""B0 v1.1 catalogue gates, using synthetic metadata only.

No test loads a checkpoint, runs a model, computes a performance metric, or
opens H:/F: sources. The 2025-looking paths below are identity strings only.
Positive authorization tests use isolated synthetic JSON/CSV files to test the
validator; they do not authorize or execute a real 2025 catalogue/Final Test.
"""
from contextlib import contextmanager
from datetime import timedelta
from functools import lru_cache
import csv
import json
from pathlib import Path, PureWindowsPath
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

import numpy as np
import torch

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.imerg_v07 import decode_imerg
from yuntapr.evaluation import catalogue_gate_b0 as gate
from yuntapr.evaluation import final_test_b0 as legacy
from yuntapr.training import phase_a_validation, scientific_review


@contextmanager
def workspace_fixture():
    """Use inherited Windows ACLs and verify the cleanup target's parent."""
    workspace = REPO_ROOT.parent.resolve()
    parent = (workspace / "tmp" / "final_test_catalogue_units").resolve()
    if not parent.is_relative_to(workspace):
        raise ValueError("Fixture parent escaped the workspace")
    parent.mkdir(parents=True, exist_ok=True)
    root = (parent / ("unit_" + uuid.uuid4().hex)).resolve()
    if root.parent != parent:
        raise ValueError("Unsafe fixture creation target")
    root.mkdir()
    try:
        yield root
    finally:
        if root.resolve().parent != parent:
            raise ValueError("Unsafe fixture cleanup target")
        shutil.rmtree(root)


def eligible_row(index=0, start=None):
    start = start or gate.START + timedelta(minutes=30 * index)
    item = gate.candidate_template(index, start)
    nominal = start + timedelta(minutes=20)
    item.update(
        b13_relative_path=nominal.strftime(
            "%Y%m\\%d\\NC_H09_%Y%m%d_%H%M_R21_FLDK.06001_06001.nc"),
        b13_bytes="123", b13_sha256="a" * 64,
        expected_latest_available="True", b13_readable="True",
        b13_metadata_valid="True", full_valid_native_pixels="251001",
        b13_finite="True", obs_start=nominal.isoformat(),
        obs_end=(start + timedelta(minutes=29)).isoformat(),
        selected_nominal=nominal.isoformat(), used_older_causal_frame="False",
        imerg_bytes="456", imerg_sha256="b" * 64,
        imerg_product="IMERG", imerg_version="V07", imerg_run_type="Final",
        imerg_time_grid_provenance_pass="True", imerg_valid_yunnan_count="1",
        eligible="True", rejection_reason="",
    )
    return item


def rejected_row(index=0):
    item = eligible_row(index)
    item["imerg_valid_yunnan_count"] = "0"
    item["eligible"] = "False"
    item["rejection_reason"] = ";".join(gate.eligibility(item))
    return item


@lru_cache(maxsize=1)
def _synthetic_rows():
    return tuple(eligible_row(index, start)
                 for index, start in enumerate(gate.scheduled_times()))


def candidate_rows():
    # The dictionaries are never mutated in place; replace a row for each test.
    return list(_synthetic_rows())


def population_rows(candidates):
    return [{key: row[key] for key in gate.POPULATION_COLUMNS}
            for row in candidates if row["eligible"] == "True"]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8")
    return sha256(path)


class FixtureBackend:
    fixture_only = True

    def __init__(self):
        self.telemetry = {}
        self.calls = []

    def probe(self, index, start):
        self.calls.append((index, start))
        return eligible_row(index, start)


class NoRawAccessTests(unittest.TestCase):
    def setUp(self):
        self.raw_guard = legacy.RawSourceGuard(preflight=True)
        self.raw_guard.__enter__()
        self.addCleanup(self.raw_guard.__exit__, None, None, None)
        self.addCleanup(lambda: self.assertEqual(self.raw_guard.raw_open_events, 0))


class ProtocolTests(NoRawAccessTests):
    def test_v1_1_inherits_all_frozen_science(self):
        protocol = gate.load_protocol()
        old = legacy.load_protocol()
        self.assertEqual(protocol["version"], "v1.1")
        self.assertEqual(protocol["inherits"]["sha256"], legacy.PROTOCOL_SHA)
        for key in gate.SCIENCE_KEYS:
            with self.subTest(key=key):
                self.assertEqual(protocol[key], old[key])
        self.assertEqual(tuple(protocol["catalogue_schema"]["columns"]), gate.COLUMNS)
        self.assertEqual(tuple(protocol["catalogue_schema"]["eligible_identity_columns"]),
                         gate.POPULATION_COLUMNS)

    def test_protocol_tamper_rejected_before_inherited_provenance(self):
        with workspace_fixture() as root:
            target = root / gate.PROTOCOL_PATH
            target.parent.mkdir(parents=True)
            target.write_bytes((REPO_ROOT / gate.PROTOCOL_PATH).read_bytes() + b"\n# mutation\n")
            with patch.object(legacy, "load_protocol") as inherited:
                with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                    gate.load_protocol(root)
                inherited.assert_not_called()

    def test_population_whitelist_is_exact_twelve_identity_fields(self):
        self.assertEqual(gate.POPULATION_COLUMNS, (
            "candidate_index", "sample_id", "window_start", "analysis_time",
            "expected_nominal", "b13_relative_path", "b13_bytes", "b13_sha256",
            "imerg_day_path", "imerg_bytes", "imerg_sha256", "imerg_index"))
        self.assertEqual(len(set(gate.COLUMNS)), len(gate.COLUMNS))
        self.assertNotIn("imerg_rain_yunnan_count", gate.COLUMNS)


class SchemaTests(NoRawAccessTests):
    def test_imerg_rain_count_rejected_even_on_rejected_candidate(self):
        for factory in (eligible_row, rejected_row):
            item = factory()
            item["imerg_rain_yunnan_count"] = "0"
            with self.subTest(eligible=item["eligible"]):
                with self.assertRaisesRegex(ValueError, "allowed fields"):
                    gate.eligibility(item)

    def test_every_outcome_alias_and_unknown_field_is_rejected(self):
        names = ("rain_prevalence", "rain_rate_counts", "rain_rate_bins",
                 "count_gt_10", "count_gt_20", "count_gt_30", "count_gt_50",
                 "loss", "Brier", "AUROC", "AP", "pinball", "coverage",
                 "model_probability", "quantiles", "DIAGNOSTIC_PROXY",
                 "predictions", "N_rain", "innocent_looking_unknown_alias")
        for factory in (eligible_row, rejected_row):
            for name in names:
                item = factory()
                item[name] = "0"
                with self.subTest(eligible=item["eligible"], name=name):
                    with self.assertRaisesRegex(ValueError, "allowed fields"):
                        gate.eligibility(item)

    def test_nested_cells_cannot_hide_outcomes(self):
        hidden = ({"rain_count": 3}, [0, 20], (0, 20), {0, 20},
                  np.array([0, 20]), SimpleNamespace(rain_count=3))
        for factory in (eligible_row, rejected_row):
            for value in hidden:
                item = factory()
                item["rejection_reason"] = value
                with self.subTest(eligible=item["eligible"], kind=type(value).__name__):
                    with self.assertRaisesRegex(ValueError, "scalar|nested"):
                        gate.strict_schema(item)

    def test_missing_allowed_field_is_rejected(self):
        item = eligible_row()
        del item["imerg_valid_yunnan_count"]
        with self.assertRaisesRegex(ValueError, "allowed fields"):
            gate.eligibility(item)

    def test_csv_outcome_duplicate_or_reordered_header_is_rejected(self):
        variants = (list(gate.COLUMNS) + ["imerg_rain_yunnan_count"],
                    list(gate.COLUMNS) + [gate.COLUMNS[0]],
                    list(reversed(gate.COLUMNS)))
        with workspace_fixture() as root:
            for index, columns in enumerate(variants):
                path = root / (str(index) + ".csv")
                with path.open("w", encoding="utf-8", newline="") as stream:
                    csv.writer(stream).writerow(columns)
                with self.subTest(index=index):
                    with self.assertRaisesRegex(ValueError, "exact ordered whitelist"):
                        gate.read_csv(path)

    def test_candidate_metadata_qc_has_no_rain_occurrence_dependency(self):
        from yuntapr.evaluation.catalogue_backend_b0 import imerg_validity_only
        attrs = {"valid_min": 0, "valid_max": 100, "_FillValue": -9999}
        for rate in (0.0, 0.1, 1.0, 20.0):
            raw = np.full((2, 2), rate, dtype=np.float32)
            _, decoder_valid = decode_imerg(raw, attrs)
            qc_valid = imerg_validity_only(raw, attrs)
            np.testing.assert_array_equal(decoder_valid, np.ones((2, 2), dtype=bool))
            np.testing.assert_array_equal(qc_valid, decoder_valid)
            item = eligible_row()
            item["imerg_valid_yunnan_count"] = str(np.count_nonzero(qc_valid))
            with self.subTest(synthetic_rate=rate):
                self.assertEqual(gate.eligibility(item), [])

    def test_validity_only_matches_decoder_fill_scale_and_negative_qc(self):
        from yuntapr.evaluation.catalogue_backend_b0 import imerg_validity_only
        raw = np.array([0, 1, 200, -9999, -1, np.nan], dtype=np.float32)
        attrs = {"scale_factor": 0.1, "add_offset": 0.0,
                 "valid_min": 0, "valid_max": 1000, "_FillValue": -9999}
        _, expected = decode_imerg(raw, attrs)
        np.testing.assert_array_equal(imerg_validity_only(raw, attrs), expected)
        np.testing.assert_array_equal(expected, [True, True, True, False, False, False])

    def test_partial_imerg_validity_allowed_zero_valid_rejected(self):
        item = eligible_row()
        self.assertEqual(gate.eligibility(item), [])
        item["imerg_valid_yunnan_count"] = "0"
        self.assertEqual(gate.eligibility(item), ["NO_VALID_YUNNAN_SUPERVISION"])

    def test_full_b13_latest_causality_and_final_provenance_are_required(self):
        changes = (("full_valid_native_pixels", "251000", "B13_FULL_SCENE_REQUIRED"),
                   ("used_older_causal_frame", "True", "OLDER_FALLBACK_PROHIBITED"),
                   ("expected_latest_available", "False", "EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK"),
                   ("obs_end", (gate.START + timedelta(minutes=31)).isoformat(), "LATEST_CAUSAL_TIME_FAILED"),
                   ("imerg_run_type", "", "IMERG_V07_FINAL_REQUIRED"))
        for key, value, reason in changes:
            item = eligible_row()
            item[key] = value
            with self.subTest(key=key):
                self.assertEqual(gate.eligibility(item), [reason])

    def test_allowed_scalar_cells_cannot_embed_outcome_strings(self):
        changes = (("imerg_product", "IMERG;rain_count=3"),
                   ("imerg_run_type", "Early"),
                   ("obs_start", "2025-03-01T00:20:00+00:00;rain_count=3"),
                   ("b13_relative_path",
                    r"202503\01\NC_H09_20250301_0020_rain_count_3_R21_FLDK.06001_06001.nc"))
        for key, value in changes:
            item = eligible_row()
            item[key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    gate.eligibility(item)

    def test_eligible_source_hash_and_positive_size_required(self):
        for key, value in (("b13_sha256", ""), ("imerg_sha256", ""),
                           ("b13_bytes", "0"), ("imerg_bytes", "0")):
            item = eligible_row()
            item[key] = value
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "missing"):
                    gate.eligibility(item)


class PopulationTests(NoRawAccessTests):
    def test_exact_10272_scheduled_halfhour_windows(self):
        slots = gate.scheduled_times()
        self.assertEqual(len(slots), 10272)
        self.assertEqual(slots[0], gate.START)
        self.assertEqual(slots[-1], gate.END - timedelta(minutes=30))
        self.assertEqual(len(set(slots)), 10272)
        self.assertTrue(all(b - a == timedelta(minutes=30) for a, b in zip(slots, slots[1:])))
        self.assertEqual(len(gate.validate_catalogue(candidate_rows())), 10272)

    def test_october_windows_rejected_before_source_io(self):
        for time in (gate.END, gate.END + timedelta(days=30)):
            with patch.object(Path, "open") as opened, patch.object(Path, "stat") as stat:
                with self.subTest(time=time):
                    with self.assertRaisesRegex(ValueError, "October"):
                        gate.candidate_template(0, time)
                    opened.assert_not_called()
                    stat.assert_not_called()

    def test_october_source_identity_rejected_without_io(self):
        for key, value in (
            ("b13_relative_path", r"202510\01\NC_H09_20251001_0020_R21_FLDK.06001_06001.nc"),
            ("imerg_day_path", str(legacy.IROOT / "2025" / "imerg_20251001.nc")),
        ):
            item = eligible_row()
            item[key] = value
            with patch.object(Path, "open") as opened, patch.object(Path, "stat") as stat:
                with self.subTest(key=key):
                    with self.assertRaisesRegex(ValueError, "October"):
                        gate.eligibility(item)
                    opened.assert_not_called()
                    stat.assert_not_called()

    def test_missing_candidate_rejected(self):
        with self.assertRaisesRegex(ValueError, "10272"):
            gate.validate_catalogue(candidate_rows()[:-1])

    def test_duplicate_candidate_rejected(self):
        rows = candidate_rows()
        rows[1] = rows[0]
        with self.assertRaisesRegex(ValueError, "duplicate|reordered"):
            gate.validate_catalogue(rows)

    def test_reordered_candidate_rejected(self):
        rows = candidate_rows()
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaisesRegex(ValueError, "duplicate|reordered"):
            gate.validate_catalogue(rows)

    def test_candidate_identity_index_mismatch_rejected(self):
        item = eligible_row()
        item["candidate_index"] = "1"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            gate.eligibility(item)

    def test_frozen_eligibility_and_reason_cannot_be_rewritten(self):
        for key, value in (("eligible", "False"), ("rejection_reason", "invented")):
            rows = candidate_rows()
            rows[0] = {**rows[0], key: value}
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, "eligibility|rejection"):
                    gate.validate_catalogue(rows)

    def test_projection_excludes_rejected_candidates_and_all_qc_fields(self):
        rows = candidate_rows()
        rows[0] = rejected_row()
        population = population_rows(rows)
        self.assertEqual(len(population), 10271)
        self.assertEqual(population[0]["candidate_index"], "1")
        self.assertTrue(all(tuple(row) == gate.POPULATION_COLUMNS for row in population))
        self.assertEqual(len(gate.validate_manifests(rows, population)), 10271)

    def test_population_extra_qc_or_outcome_fields_rejected(self):
        rows = candidate_rows()
        for name in ("imerg_valid_yunnan_count", "eligible", "imerg_rain_yunnan_count"):
            population = population_rows(rows)
            population[0] = {**population[0], name: "1"}
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "allowed fields"):
                    gate.validate_manifests(rows, population)

    def test_population_missing_duplicate_reordered_and_identity_mutation_rejected(self):
        rows = candidate_rows()
        good = population_rows(rows)
        changed = [{**good[0], "b13_sha256": "c" * 64}, *good[1:]]
        for bad in (good[:-1], [good[0], good[0], *good[2:]],
                    [good[1], good[0], *good[2:]], changed):
            with self.subTest(length=len(bad), first=bad[0]["candidate_index"]):
                with self.assertRaisesRegex(ValueError, "identity projection"):
                    gate.validate_manifests(rows, bad)


class CatalogueScopeTests(NoRawAccessTests):
    def test_catalogue_authority_never_grants_final_permission(self):
        with self.assertRaisesRegex(PermissionError, "cannot authorize FINAL"):
            gate.CatalogueAuthority.fixture_only().require_final()

    def test_fixture_scope_cannot_request_real_catalogue(self):
        backend = FixtureBackend()
        with workspace_fixture() as root:
            output = root / "blocked"
            with self.assertRaisesRegex(PermissionError, "Fixture authority"):
                gate.build_catalogue(gate.CatalogueAuthority.fixture_only(), backend, output)
            self.assertEqual(backend.calls, [])
            self.assertFalse(output.exists())

    def test_unsealed_authority_rejected_before_probe_or_output(self):
        authority = gate.CatalogueAuthority({"scope": gate.CATALOGUE_SCOPE}, "a" * 64, object())
        backend = FixtureBackend()
        with workspace_fixture() as root:
            output = root / "blocked"
            with self.assertRaisesRegex(PermissionError, "Verified catalogue authority"):
                gate.build_catalogue(authority, backend, output, fixture=True)
            self.assertEqual(backend.calls, [])
            self.assertFalse(output.exists())

    def test_fixture_authority_and_backend_must_agree(self):
        backend = FixtureBackend()
        backend.fixture_only = False
        with workspace_fixture() as root:
            output = root / "blocked"
            with self.assertRaisesRegex(PermissionError, "Fixture backend/authority"):
                gate.build_catalogue(gate.CatalogueAuthority.fixture_only(), backend, output, fixture=True)
            self.assertEqual(backend.calls, [])
            self.assertFalse(output.exists())

    def test_missing_catalogue_authority_precedes_protocol_hash_and_io(self):
        with patch.object(gate, "sha256") as hashed, patch.object(gate, "load_protocol") as protocol:
            with self.assertRaisesRegex(PermissionError, "Separate researcher"):
                gate.CatalogueAuthority.load(None, None)
            hashed.assert_not_called()
            protocol.assert_not_called()

    def test_real_backend_checks_authority_before_mask_staging_or_manifest(self):
        from yuntapr.evaluation import catalogue_backend_b0 as backend_module
        authority = gate.CatalogueAuthority.fixture_only()
        with patch.object(backend_module, "load_sp04") as mapping, \
                patch.object(backend_module, "load_completion_manifest") as manifest, \
                patch.object(backend_module, "BoundedEnglishStaging") as staging:
            with self.assertRaisesRegex(PermissionError, "Fixture authority"):
                backend_module.RealCatalogueBackend({}, authority, "unused")
            mapping.assert_not_called()
            manifest.assert_not_called()
            staging.assert_not_called()

    def test_guard_blocks_final_verification_and_model_loader(self):
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "FINAL_loading"):
                legacy.verify_final({})
            with self.assertRaisesRegex(PermissionError, "model_loading"):
                legacy.load_inference_model(None, "cpu")
        self.assertEqual(guard.attempts["FINAL_loading"], 1)
        self.assertEqual(guard.attempts["model_loading"], 1)

    def test_guard_blocks_torch_checkpoint_deserialization(self):
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "checkpoint_loading"):
                torch.load(None)
            with self.assertRaisesRegex(PermissionError, "checkpoint_loading"):
                torch.serialization.load(None)
        self.assertEqual(guard.attempts["checkpoint_loading"], 2)

    def test_guard_blocks_b0_constructor_before_its_body(self):
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "model_instantiation"):
                legacy.B0Model()
        self.assertEqual(guard.attempts["model_instantiation"], 1)

    def test_guard_blocks_b0_call_without_instantiating_model(self):
        # Allocate an empty Python object only; never invoke B0Model.__init__.
        empty = object.__new__(legacy.B0Model)
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "model_forward"):
                legacy.B0Model.__call__(empty, None, None)
        self.assertEqual(guard.attempts["model_forward"], 1)

    def test_guard_blocks_all_direct_b0_forward_entries(self):
        with gate.CatalogueOnlyGuard() as guard:
            for name, args in (("forward", (None, None, None)),
                               ("forward_formal", (None, None)),
                               ("_evaluate", (None, None, None, None))):
                with self.subTest(name=name):
                    with self.assertRaisesRegex(PermissionError, "model_forward"):
                        getattr(legacy.B0Model, name)(*args)
        self.assertEqual(guard.attempts["model_forward"], 3)

    def test_guard_blocks_metric_constructors(self):
        with gate.CatalogueOnlyGuard() as guard:
            for constructor in (legacy.GlobalValidationAccumulator,
                                legacy.FinalAccumulator, scientific_review.ReviewAccumulator):
                with self.subTest(constructor=constructor.__name__):
                    with self.assertRaisesRegex(PermissionError, "performance_metrics"):
                        constructor.__init__(None)
        self.assertEqual(guard.attempts["performance_metrics"], 3)

    def test_guard_blocks_existing_accumulator_metric_methods(self):
        methods = ((legacy.GlobalValidationAccumulator, "add", (None,) * 5),
                   (legacy.GlobalValidationAccumulator, "report", (None,)),
                   (legacy.FinalAccumulator, "add", (None,) * 5),
                   (legacy.FinalAccumulator, "primary_report", (None,)),
                   (legacy.FinalAccumulator, "diagnostics", (None, None)),
                   (scientific_review.ReviewAccumulator, "add", (None,) * 5),
                   (scientific_review.ReviewAccumulator, "spatial_metrics", (None, None)))
        with gate.CatalogueOnlyGuard() as guard:
            for owner, name, args in methods:
                with self.subTest(owner=owner.__name__, name=name):
                    with self.assertRaisesRegex(PermissionError, "performance_metrics"):
                        getattr(owner, name)(*args)
        self.assertEqual(guard.attempts["performance_metrics"], len(methods))

    def test_guard_blocks_standalone_metric_computation(self):
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "performance_metrics"):
                phase_a_validation.grouped_occurrence_metrics(None, None)
        self.assertEqual(guard.attempts["performance_metrics"], 1)

    def test_guard_blocks_loss_functions_and_imported_aliases(self):
        from yuntapr.losses import focal, pinball, total_loss
        from yuntapr.training import forward_step
        entries = ((total_loss, "b0_core_loss"), (focal, "focal_bce_sum"),
                   (pinball, "pinball_sum"), (total_loss, "focal_bce_sum"),
                   (total_loss, "pinball_sum"), (forward_step, "b0_core_loss"))
        with gate.CatalogueOnlyGuard() as guard:
            for owner, name in entries:
                with self.subTest(module=owner.__name__, name=name):
                    with self.assertRaisesRegex(PermissionError, "loss"):
                        getattr(owner, name)(None)
        self.assertEqual(guard.attempts["loss"], len(entries))

    def test_guard_blocks_metric_function_imported_alias(self):
        with gate.CatalogueOnlyGuard() as guard:
            with self.assertRaisesRegex(PermissionError, "performance_metrics"):
                legacy.probability_summary(None)
        self.assertEqual(guard.attempts["performance_metrics"], 1)

    def test_guard_restores_original_functions_after_exception(self):
        original = (torch.load, legacy.B0Model.forward, legacy.verify_final,
                    phase_a_validation.grouped_occurrence_metrics)
        with self.assertRaisesRegex(RuntimeError, "synthetic stop"):
            with gate.CatalogueOnlyGuard():
                raise RuntimeError("synthetic stop")
        self.assertEqual(original, (torch.load, legacy.B0Model.forward, legacy.verify_final,
                                    phase_a_validation.grouped_occurrence_metrics))

    def test_guard_restores_staticmethod_descriptor_and_inherited_methods(self):
        # The whole preflight may already have an outer catalogue guard.
        # Install an inert fixture descriptor, never a real metric function,
        # to verify raw staticmethod restoration under either nesting depth.
        def never_execute(*args, **kwargs):
            raise AssertionError("Fixture staticmethod body must not execute")
        with patch.object(legacy.FinalAccumulator, "report", staticmethod(never_execute)):
            descriptor = vars(legacy.FinalAccumulator)["report"]
            self.assertIsInstance(descriptor, staticmethod)
            inherited_present = "spatial_metrics" in vars(legacy.FinalAccumulator)
            for _ in range(2):
                with gate.CatalogueOnlyGuard():
                    with self.assertRaisesRegex(PermissionError, "performance_metrics"):
                        legacy.FinalAccumulator.report(None)
                self.assertIs(vars(legacy.FinalAccumulator)["report"], descriptor)
                self.assertEqual("spatial_metrics" in vars(legacy.FinalAccumulator), inherited_present)

    def test_same_guard_can_be_reused_without_stale_patches(self):
        original = torch.load
        guard = gate.CatalogueOnlyGuard()
        for _ in range(2):
            with guard:
                with self.assertRaisesRegex(PermissionError, "checkpoint_loading"):
                    torch.load(None)
            self.assertIs(torch.load, original)
            self.assertEqual(guard.saved, [])
            self.assertFalse(guard.enabled)
        self.assertEqual(guard.attempts["checkpoint_loading"], 2)

    def test_guard_installation_failure_rolls_back_already_installed_patches(self):
        original = (torch.load, legacy.B0Model.__init__, legacy.B0Model.forward)
        guard = gate.CatalogueOnlyGuard()
        # Force a failure midway through patch installation, before any model
        # construction, source access, metric operation, or optimizer call.
        with patch.object(legacy, "GlobalValidationAccumulator", object()):
            with self.assertRaises(TypeError):
                guard.__enter__()
        self.assertEqual(original, (torch.load, legacy.B0Model.__init__, legacy.B0Model.forward))
        self.assertEqual(guard.saved, [])
        self.assertFalse(guard.enabled)
        self.assertIsNone(guard.inference_guard)


class ProtectedPathTests(NoRawAccessTests):
    @staticmethod
    def paths():
        return (str(legacy.HROOT / "202503" / "01" / "synthetic.nc"),
                str(legacy.IROOT / "2025" / "imerg_20250301.nc"),
                str(legacy.FINAL_PATH))

    def test_protected_artifacts_rejected_before_resolve_or_open(self):
        with patch.object(Path, "resolve") as resolve, patch.object(Path, "open") as opened:
            for path in self.paths():
                with self.subTest(path=path):
                    with self.assertRaisesRegex(PermissionError, "raw sources or checkpoints"):
                        gate.safe_artifact_path(path)
            resolve.assert_not_called()
            opened.assert_not_called()

    def test_metadata_helpers_reject_raw_or_checkpoint_artifact_targets(self):
        with patch.object(Path, "resolve") as resolve, \
                patch.object(Path, "open") as opened, patch.object(Path, "read_bytes") as read:
            for path in self.paths():
                operations = (lambda: gate.read_csv(path),
                              lambda: gate.write_csv(path, [eligible_row()]),
                              lambda: gate.save(path, {}),
                              lambda: gate.CatalogueAuthority.load(path, "a" * 64),
                              lambda: gate.FinalAuthority.load(path, "a" * 64, None, None, None))
                for index, operation in enumerate(operations):
                    with self.subTest(path=path, operation=index):
                        with self.assertRaises(PermissionError):
                            operation()
            resolve.assert_not_called()
            opened.assert_not_called()
            read.assert_not_called()

    def test_builder_rejects_protected_output_before_probe_or_mkdir(self):
        backend = FixtureBackend()
        with patch.object(Path, "resolve") as resolve, patch.object(Path, "mkdir") as mkdir:
            for path in self.paths():
                with self.subTest(path=path):
                    with self.assertRaises(PermissionError):
                        gate.build_catalogue(gate.CatalogueAuthority.fixture_only(), backend,
                                             path, fixture=True)
            self.assertEqual(backend.calls, [])
            resolve.assert_not_called()
            mkdir.assert_not_called()

    def test_real_backend_rejects_protected_staging_before_mask_manifest_or_staging_io(self):
        from yuntapr.evaluation import catalogue_backend_b0 as backend_module
        authority = SimpleNamespace(require_catalogue=lambda: None)
        with patch.object(Path, "resolve") as resolve, \
                patch.object(backend_module, "load_sp04") as mapping, \
                patch.object(backend_module, "load_completion_manifest") as manifest, \
                patch.object(backend_module, "CatalogueEnglishStaging") as staging:
            for path in self.paths():
                with self.subTest(path=path):
                    with self.assertRaises(PermissionError):
                        backend_module.RealCatalogueBackend({}, authority, path)
            resolve.assert_not_called()
            mapping.assert_not_called()
            manifest.assert_not_called()
            staging.assert_not_called()

    def test_preflight_check_blocks_original_roots_after_synthetic_root_retargeting(self):
        guard = gate.PreflightSourceGuard()
        paths = self.paths()
        with patch.object(legacy, "HROOT", PureWindowsPath(r"C:\synthetic_himawari")), \
                patch.object(legacy, "IROOT", PureWindowsPath(r"C:\synthetic_imerg")):
            for path in paths:
                with self.subTest(path=path):
                    with self.assertRaisesRegex(PermissionError, "any real raw source or checkpoint"):
                        guard.check(path)
        self.assertEqual(guard.raw_open_events, 0)

    def test_telemetry_types_cannot_hide_outcomes_or_nonfinite_values(self):
        values = ({"read_seconds": {"rain_count": 3}}, {"2025_PIXELS_READ": [3]},
                  {"cleanup_success": "True"}, {"read_seconds": float("nan")},
                  {"read_seconds": float("inf")}, {"source_hash_bytes_read": -1})
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    gate.sanitized_telemetry(value)


class FixtureBuildTests(NoRawAccessTests):
    @classmethod
    def setUpClass(cls):
        cls._workspace = workspace_fixture()
        cls.root = cls._workspace.__enter__()
        cls.addClassCleanup(cls._workspace.__exit__, None, None, None)
        cls.backend = FixtureBackend()
        cls.output = cls.root / "synthetic_catalogue_only"
        with legacy.RawSourceGuard(preflight=True) as raw_guard:
            cls.result = gate.build_catalogue(gate.CatalogueAuthority.fixture_only(),
                                             cls.backend, cls.output, fixture=True)
        if raw_guard.raw_open_events:
            raise AssertionError("Synthetic catalogue accessed raw sources")

    def test_fixture_probes_exact_schedule_and_freezes_all_candidates(self):
        self.assertEqual(self.backend.calls, list(enumerate(gate.scheduled_times())))
        self.assertEqual(self.result["candidate_count"], 10272)
        self.assertEqual(self.result["eligible_count"], 10272)
        self.assertEqual(self.result["rejected_count"], 0)
        self.assertEqual(self.result["rejection_reason_counts"], {})

    def test_fixture_population_csv_is_twelve_field_identity_projection(self):
        candidates = gate.read_csv(self.output / "b0_2025_final_test_candidate_catalogue_v1.csv")
        population = gate.read_csv(self.output / "b0_2025_final_test_population_manifest_v1.csv",
                                   gate.POPULATION_COLUMNS)
        self.assertEqual(population, population_rows(candidates))
        self.assertTrue(all(tuple(row) == gate.POPULATION_COLUMNS for row in population))

    def test_fixture_freeze_hashes_pin_exact_written_csv_bytes(self):
        self.assertEqual(self.result["candidate_catalogue_sha256"],
                         sha256(self.output / "b0_2025_final_test_candidate_catalogue_v1.csv"))
        self.assertEqual(self.result["eligible_population_manifest_sha256"],
                         sha256(self.output / "b0_2025_final_test_population_manifest_v1.csv"))
        frozen = json.loads((self.output / "catalogue_freeze_record.json").read_text(encoding="utf-8"))
        self.assertEqual(frozen, self.result)

    def test_fixture_never_claims_real_raw_access_inference_metrics_or_outcomes(self):
        self.assertTrue(self.result["fixture_only"])
        self.assertEqual(self.result["status"], "FIXTURE_CATALOGUE_FROZEN")
        self.assertEqual(self.result["scope"], gate.FIXTURE_SCOPE)
        self.assertFalse(self.result["2025_CATALOGUE_QC_ACCESS"])
        self.assertFalse(self.result["2025_FINAL_TEST_EXECUTED"])
        self.assertEqual(self.result["2025_MODEL_INFERENCE_SCENES"], 0)
        self.assertFalse(self.result["2025_FINAL_TEST_METRICS_COMPUTED"])
        self.assertFalse(self.result["2025_TARGET_OUTCOME_SUMMARIES_EXPOSED"])
        self.assertEqual(self.result["raw_access_telemetry"], {})

    def test_fixture_outcome_row_rejected_before_freeze(self):
        backend = FixtureBackend()
        backend.probe = Mock(return_value={**eligible_row(), "imerg_rain_yunnan_count": "0"})
        with self.assertRaisesRegex(ValueError, "allowed fields"):
            gate.build_catalogue(gate.CatalogueAuthority.fixture_only(), backend,
                                 self.root / "poisoned_fixture", fixture=True)
        backend.probe.assert_called_once_with(0, gate.START)
        self.assertFalse((self.root / "poisoned_fixture" / "catalogue_freeze_record.json").exists())

    def test_fixture_unknown_and_nested_outcome_telemetry_rejected_before_freeze(self):
        for index, telemetry in enumerate((
            {"rain_prevalence": 0.5},
            {"read_seconds": {"imerg_rain_yunnan_count": 3}},
        )):
            backend = FixtureBackend()
            backend.telemetry = telemetry
            output = self.root / ("telemetry_rejection_" + str(index))
            with self.subTest(index=index):
                with self.assertRaisesRegex(ValueError, "telemetry|scalar|Outcome|duration"):
                    gate.build_catalogue(gate.CatalogueAuthority.fixture_only(),
                                         backend, output, fixture=True)
                self.assertFalse((output / "catalogue_freeze_record.json").exists())


class AuthorizationTests(NoRawAccessTests):
    @classmethod
    def setUpClass(cls):
        cls._workspace = workspace_fixture()
        cls.root = cls._workspace.__enter__()
        cls.addClassCleanup(cls._workspace.__exit__, None, None, None)
        cls.implementation = gate.implementation_hashes()
        cls.candidate = cls.root / "synthetic_candidates.csv"
        cls.population = cls.root / "synthetic_eligible_identities.csv"
        rows = candidate_rows()
        gate.write_csv(cls.candidate, rows)
        gate.write_csv(cls.population, population_rows(rows), gate.POPULATION_COLUMNS)
        cls.candidate_sha = sha256(cls.candidate)
        cls.population_sha = sha256(cls.population)

    def setUp(self):
        super().setUp()
        self.freeze = self.root / (uuid.uuid4().hex + "_synthetic_freeze.json")
        self.auth = self.root / (uuid.uuid4().hex + "_synthetic_authorization.json")
        # This is a validator fixture only, never actual raw QC evidence.
        self.freeze_value = {
            "version": "v1.1", "status": "CATALOGUE_FROZEN", "fixture_only": False,
            "scope": gate.CATALOGUE_SCOPE, "protocol_sha256": gate.PROTOCOL_SHA,
            "implementation_sha256": self.implementation,
            "catalogue_authorization_sha256": "a" * 64,
            "candidate_catalogue_sha256": self.candidate_sha,
            "eligible_population_manifest_sha256": self.population_sha,
            "candidate_count": 10272, "eligible_count": 10272, "rejected_count": 0,
            "rejection_reason_counts": {}, "2025_CATALOGUE_QC_ACCESS": True,
            "2025_FINAL_TEST_EXECUTED": False, "2025_MODEL_INFERENCE_SCENES": 0,
            "2025_FINAL_TEST_METRICS_COMPUTED": False,
            "2025_TARGET_OUTCOME_SUMMARIES_EXPOSED": False,
            "raw_access_telemetry": {},
            "freeze_completed_utc": "2026-10-03T00:00:00+00:00",
        }
        freeze_sha = write_json(self.freeze, self.freeze_value)
        self.value = {
            "version": "v1.1", "AUTHORIZED_BY": "RESEARCHER", "scope": gate.FINAL_SCOPE,
            "FINAL_TEST_2025_AUTHORIZED": True, "protocol_sha256": gate.PROTOCOL_SHA,
            "implementation_sha256": self.implementation,
            "FINAL_sha256": legacy.FINAL_SHA, "normalization_sha256": legacy.NORMALIZATION_SHA,
            "candidate_catalogue_sha256": self.candidate_sha,
            "eligible_population_manifest_sha256": self.population_sha,
            "catalogue_freeze_record_sha256": freeze_sha,
            "created_utc": "2026-10-03T00:00:01+00:00",
        }

    def load(self, value=None):
        digest = write_json(self.auth, self.value if value is None else value)
        return gate.FinalAuthority.load(self.auth, digest, self.candidate, self.population, self.freeze)

    def rebind_freeze(self):
        self.value["catalogue_freeze_record_sha256"] = write_json(self.freeze, self.freeze_value)

    def test_missing_final_authority_precedes_hash_protocol_catalogue_and_source_io(self):
        with patch.object(gate, "sha256") as hashed, \
                patch.object(gate, "implementation_hashes") as implementation, \
                patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(PermissionError, "Second-stage"):
                gate.FinalAuthority.load(None, None, None, None, None)
            hashed.assert_not_called()
            implementation.assert_not_called()
            reader.assert_not_called()

    def test_final_authority_requires_candidate_population_and_freeze_sha_bindings(self):
        for key in ("candidate_catalogue_sha256", "eligible_population_manifest_sha256",
                    "catalogue_freeze_record_sha256"):
            value = dict(self.value)
            del value[key]
            with patch.object(gate, "implementation_hashes") as implementation, \
                    patch.object(gate, "read_csv") as reader:
                with self.subTest(missing=key):
                    with self.assertRaisesRegex(PermissionError, "SHA bindings"):
                        self.load(value)
                    implementation.assert_not_called()
                    reader.assert_not_called()

    def test_legacy_population_only_final_grant_rejected_before_manifest_io(self):
        value = dict(self.value)
        value["version"] = "v1"
        for key in ("candidate_catalogue_sha256", "eligible_population_manifest_sha256",
                    "catalogue_freeze_record_sha256"):
            del value[key]
        value["population_manifest_sha256"] = self.population_sha
        with patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(PermissionError, "SHA bindings"):
                self.load(value)
            reader.assert_not_called()

    def test_catalogue_scope_cannot_be_used_as_final_authorization(self):
        self.value["scope"] = gate.CATALOGUE_SCOPE
        with patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(PermissionError, "scope/provenance"):
                self.load()
            reader.assert_not_called()

    def test_final_authority_hash_mutation_rejected(self):
        digest = write_json(self.auth, self.value)
        self.auth.write_bytes(self.auth.read_bytes() + b"\n")
        with patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                gate.FinalAuthority.load(self.auth, digest, self.candidate, self.population, self.freeze)
            reader.assert_not_called()

    def test_each_frozen_artifact_binding_must_match(self):
        for key in ("candidate_catalogue_sha256", "eligible_population_manifest_sha256",
                    "catalogue_freeze_record_sha256"):
            value = {**self.value, key: "0" * 64}
            with self.subTest(key=key), patch.object(gate, "read_csv") as reader:
                with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                    self.load(value)
                reader.assert_not_called()

    def test_actual_population_bytes_mutation_rejected(self):
        mutated = self.root / (uuid.uuid4().hex + "_mutated_population.csv")
        mutated.write_bytes(self.population.read_bytes() + b"\n")
        digest = write_json(self.auth, self.value)
        with patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                gate.FinalAuthority.load(self.auth, digest, self.candidate, mutated, self.freeze)
            reader.assert_not_called()

    def test_authorization_created_before_catalogue_freeze_is_rejected(self):
        self.value["created_utc"] = "2026-10-02T23:59:59+00:00"
        with patch.object(gate, "read_csv") as reader:
            with self.assertRaisesRegex(PermissionError, "freeze before separate"):
                self.load()
            reader.assert_not_called()

    def test_fixture_freeze_cannot_authorize_formal_final_test(self):
        for key, value in (("status", "FIXTURE_CATALOGUE_FROZEN"),
                           ("fixture_only", True), ("scope", gate.FIXTURE_SCOPE)):
            frozen = dict(self.freeze_value)
            frozen[key] = value
            self.value["catalogue_freeze_record_sha256"] = write_json(self.freeze, frozen)
            with self.subTest(key=key), patch.object(gate, "read_csv") as reader:
                with self.assertRaisesRegex(PermissionError, "Real catalogue"):
                    self.load()
                reader.assert_not_called()

    def test_freeze_record_population_binding_mismatch_rejected(self):
        self.freeze_value["eligible_population_manifest_sha256"] = "0" * 64
        self.rebind_freeze()
        with self.assertRaisesRegex(ValueError, "Freeze record binding"):
            self.load()

    def test_outcome_exposure_flag_cannot_pass_final_gate(self):
        self.freeze_value["2025_TARGET_OUTCOME_SUMMARIES_EXPOSED"] = True
        self.rebind_freeze()
        with self.assertRaisesRegex(PermissionError, "Real catalogue"):
            self.load()

    def test_freeze_outcome_fields_and_nested_telemetry_cannot_pass_gate(self):
        for field, value in (("rain_prevalence", 0.5),
                             ("imerg_rain_yunnan_count", 3),
                             ("raw_access_telemetry", {"read_seconds": {"rain_count": 3}})):
            frozen = {**self.freeze_value, field: value}
            self.value["catalogue_freeze_record_sha256"] = write_json(self.freeze, frozen)
            with self.subTest(field=field), patch.object(gate, "read_csv") as reader:
                with self.assertRaisesRegex((PermissionError, ValueError),
                                           "freeze|Freeze|telemetry|outcome|Outcome|scalar|duration"):
                    self.load()
                reader.assert_not_called()

    def test_freeze_execution_and_qc_flags_are_reconciled(self):
        changes = (("2025_CATALOGUE_QC_ACCESS", False),
                   ("2025_FINAL_TEST_EXECUTED", True),
                   ("2025_MODEL_INFERENCE_SCENES", 1),
                   ("2025_FINAL_TEST_METRICS_COMPUTED", True))
        for field, value in changes:
            frozen = {**self.freeze_value, field: value}
            self.value["catalogue_freeze_record_sha256"] = write_json(self.freeze, frozen)
            with self.subTest(field=field):
                with self.assertRaisesRegex((PermissionError, ValueError),
                                           "freeze|Freeze|catalogue|Catalogue|flag"):
                    self.load()

    def test_frozen_rejection_counts_must_match_catalogue(self):
        self.freeze_value["rejection_reason_counts"] = {"NO_VALID_YUNNAN_SUPERVISION": 1}
        self.rebind_freeze()
        with self.assertRaisesRegex(ValueError, "reconciliation|rejection"):
            self.load()

    def test_missing_frozen_paths_rejected(self):
        digest = write_json(self.auth, self.value)
        for candidate, population, freeze in ((None, self.population, self.freeze),
                                              (self.candidate, None, self.freeze),
                                              (self.candidate, self.population, None)):
            with self.subTest(missing=(candidate, population, freeze)):
                with self.assertRaisesRegex(PermissionError, "paths required"):
                    gate.FinalAuthority.load(self.auth, digest, candidate, population, freeze)

    def test_valid_synthetic_second_stage_gate_never_loads_model_or_source(self):
        with patch.object(legacy, "verify_final") as verify, \
                patch.object(legacy, "load_inference_model") as model, \
                patch.object(torch, "load") as deserialize:
            authority = self.load()
            authority.require_final()
            verify.assert_not_called()
            model.assert_not_called()
            deserialize.assert_not_called()
        with self.assertRaisesRegex(PermissionError, "does not authorize rebuilding"):
            authority.require_catalogue()

    def test_forged_final_authority_cannot_pass_runtime_gate(self):
        authority = gate.FinalAuthority(dict(self.value), "a" * 64, object())
        with self.assertRaisesRegex(PermissionError, "Verified second-stage"):
            authority.require_final()

    def test_loaded_final_authority_and_population_snapshots_are_immutable(self):
        authority = self.load()
        self.assertEqual(len(authority.candidates), 10272)
        self.assertEqual(len(authority.population), 10272)
        self.assertEqual(dict(authority.candidates[0]), eligible_row())
        with self.assertRaises(TypeError):
            authority.value["scope"] = gate.CATALOGUE_SCOPE
        with self.assertRaises(TypeError):
            authority.value["implementation_sha256"]["new_alias"] = "0" * 64
        with self.assertRaises(TypeError):
            authority.candidates[0]["sample_id"] = "changed"
        with self.assertRaises(TypeError):
            authority.population[0]["sample_id"] = "changed"

    def test_catalogue_authority_json_pins_scope_roots_and_completion_manifest(self):
        value = {
            "version": "v1.1", "AUTHORIZED_BY": "RESEARCHER", "scope": gate.CATALOGUE_SCOPE,
            "FINAL_TEST_CATALOGUE_AUTHORIZED": True, "FINAL_TEST_2025_AUTHORIZED": False,
            "protocol_sha256": gate.PROTOCOL_SHA, "implementation_sha256": self.implementation,
            "source_roots": {"Himawari": str(legacy.HROOT), "IMERG": str(legacy.IROOT)},
            "created_utc": "2026-10-03T00:00:00+00:00",
            "imerg_completion_manifest_path": str(legacy.IROOT / "conversion_completion.jsonl"),
            "imerg_completion_manifest_sha256": "c" * 64,
        }
        digest = write_json(self.auth, value)
        with patch.object(legacy, "verify_final") as verify, patch.object(torch, "load") as model:
            authority = gate.CatalogueAuthority.load(self.auth, digest)
            authority.require_catalogue()
            with self.assertRaisesRegex(PermissionError, "cannot authorize FINAL"):
                authority.require_final()
            verify.assert_not_called()
            model.assert_not_called()
        for field, bad in (("scope", gate.FINAL_SCOPE),
                           ("FINAL_TEST_2025_AUTHORIZED", True),
                           ("protocol_sha256", "0" * 64),
                           ("imerg_completion_manifest_path", r"G:\alternate\manifest.jsonl"),
                           ("imerg_completion_manifest_path", str(legacy.IROOT / "2025" / "imerg_20250301.nc")),
                           ("imerg_completion_manifest_path", str(legacy.IROOT / "202510" / "completion.jsonl")),
                           ("imerg_completion_manifest_path", str(legacy.IROOT / "manifests" / "nested" / "completion.jsonl"))):
            broken = {**value, field: bad}
            with self.subTest(field=field):
                digest = write_json(self.auth, broken)
                with self.assertRaises(PermissionError):
                    gate.CatalogueAuthority.load(self.auth, digest)


class RunnerGateTests(NoRawAccessTests):
    @staticmethod
    def args():
        return SimpleNamespace(authorization=None, authorization_sha256=None,
                               candidate_catalogue=None, eligible_population=None,
                               catalogue_freeze_record=None)

    def test_new_formal_runner_rejects_no_authority_before_csv_model_and_output(self):
        from yuntapr.evaluation import final_test_b0_v1_1 as final_runner
        with patch.object(gate, "read_csv") as read_csv, \
                patch.object(final_runner, "verify_final") as verify, \
                patch.object(legacy, "load_inference_model") as model, \
                patch.object(Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(PermissionError, "Second-stage"):
                final_runner.formal(self.args())
            read_csv.assert_not_called()
            verify.assert_not_called()
            model.assert_not_called()
            mkdir.assert_not_called()

    def test_v1_1_script_uses_same_early_formal_gate(self):
        import test_b0_2025_final_v1_1 as script
        with patch.object(gate, "read_csv") as read_csv, \
                patch.object(legacy, "verify_final") as verify:
            with self.assertRaisesRegex(PermissionError, "Second-stage"):
                script.formal(self.args())
            read_csv.assert_not_called()
            verify.assert_not_called()

    def test_catalogue_scope_cannot_verify_final_or_construct_inference_dataset(self):
        from yuntapr.evaluation import final_test_b0_v1_1 as final_runner
        authority = gate.CatalogueAuthority.fixture_only()
        with patch.object(legacy, "verify_final") as verify, \
                patch.object(final_runner, "BoundedEnglishStaging") as staging:
            with self.assertRaisesRegex(PermissionError, "cannot authorize FINAL"):
                final_runner.verify_final({}, authority)
            with self.assertRaisesRegex(PermissionError, "cannot authorize FINAL"):
                final_runner.AuthorizedFinalDataset([], None, None, None, None, {}, authority)
            verify.assert_not_called()
            staging.assert_not_called()

    def test_legacy_v1_authorization_and_formal_entry_are_superseded(self):
        import test_b0_2025_final_v1 as old_script
        with patch.object(legacy, "sha256") as hashed, \
                patch.object(legacy, "read") as read, \
                patch.object(legacy, "verify_final") as verify:
            with self.assertRaisesRegex(PermissionError, "superseded"):
                legacy.FinalAuthorization.load(None, None, None)
            with self.assertRaisesRegex(PermissionError, "superseded"):
                old_script.formal(self.args())
            hashed.assert_not_called()
            read.assert_not_called()
            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
