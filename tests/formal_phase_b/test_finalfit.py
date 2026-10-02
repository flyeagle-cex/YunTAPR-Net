from argparse import Namespace
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.training import formal_phase_b as b
from yuntapr.training.phase_a_protocol import capture_rng, state_digest
import train_b0_phase_b_finalfit_v1 as runner


class FinalFitRunnerTests(unittest.TestCase):
    """All simulated boundary states/binaries belong to isolated TEST_FIXTURE_ONLY roots."""

    def fixture(self, epoch=1):
        torch.manual_seed(2026)
        model = nn.Conv2d(1, 1, 1)
        optimizer = torch.optim.AdamW(model.parameters(), lr=b.finalfit_lr(epoch*b.STEPS), foreach=False)
        # Only one real temporary step; the completed-epoch counter below is synthetic
        # checkpoint-schema evidence, not a claim that formal updates occurred.
        model(torch.ones(1, 1, 1, 1)).sum().backward()
        optimizer.step()
        for state in optimizer.state.values(): state["step"].fill_(epoch*b.STEPS)
        expected = {"scope": b.SCOPE, "checkpoint_kind": "FINALFIT_COMPLETED_EPOCH",
            "PHASE_B_AUTHORIZED": True, "EPOCH_BOUNDARY_RESUME_ONLY": True, **b.LOCKS,
            "run_id": "run_fixture", "authorization_sha256": "a"*64,
            "runner_config_sha256": "b"*64, "source_identity_preflight_sha256": "c"*64,
            "implementation_sha256": {"fixture": "d"*64}}
        coverage = b.EpochCoverage(epoch)
        for i in range(0, b.SCENES, 2):
            indices = coverage.order[i:i+2]
            coverage.add(indices, len(indices)*3430)
        payload = b.make_payload(model, optimizer, expected, epoch, coverage, {"training_core_loss": .25})
        return model, optimizer, expected, payload

    def identity(self, path, payload):
        return {"absolute_local_path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path),
            "epoch": payload["completed_epoch"], "global_update": payload["global_update"]}

    def test_locked_contract_and_normalization(self):
        contract = b.RunnerContract.load()
        self.assertEqual(len(contract.rows), 23447)
        self.assertEqual(contract.normalizer.artifact_sha256, b.NORMALIZATION_SHA)
        self.assertEqual(contract.normalizer.mu, 270.5900486586461)
        self.assertEqual(contract.normalizer.sigma, 20.368583874067266)
        self.assertFalse(contract.config["PHASE_B_AUTHORIZED"])
        self.assertEqual(b.EPOCHS*b.STEPS, b.UPDATES)

    def test_configuration_mutations_rejected(self):
        original = yaml.safe_load((REPO_ROOT/b.CONFIG).read_text(encoding="utf-8"))
        for key in b.LOCKS:
            value = deepcopy(original)
            value[key] = "MUTATED"
            with patch.object(b.yaml, "safe_load", return_value=value), self.assertRaisesRegex(ValueError, key):
                b.RunnerContract.load()

    def test_authorization_missing_rejected_before_reads_or_model(self):
        args = Namespace(authorization=None, authorization_sha256=None, run_id=None)
        with patch.object(runner, "source_identity_preflight") as source, patch.object(runner, "fresh_model") as model:
            for resume in (False, True):
                with self.assertRaises(PermissionError): runner.formal_run(args, resume=resume)
            source.assert_not_called(); model.assert_not_called()

    def test_formal_update_and_batch_require_phase_b_authorization(self):
        with self.assertRaises(PermissionError): b.prepare_batch([], [])
        with self.assertRaises(PermissionError): runner.execute_update(None, None, None, 1)

    def test_phase_a_authorization_cannot_authorize_finalfit(self):
        contract = b.RunnerContract.load()
        path = REPO_ROOT/"config/training/b0_phase_a_formal_authorization_v1.yaml"
        with self.assertRaises(PermissionError): b.PhaseBAuthorization.load(path, sha256(path), contract)

    def test_approved_authorization_is_bound_to_all_implementation_hashes(self):
        contract = b.RunnerContract.load()
        value = {"version": "v1", "AUTHORIZED_BY": "RESEARCHER", "AUTHORIZED_SCOPE": "B0_PHASE_B_FINALFIT_ONLY",
            "PHASE_B_AUTHORIZED": True, "PHASE_B_MODEL_INITIALIZATION": b.INITIALIZATION,
            "FINALFIT_EPOCHS": 11, "2025_access": False, "runner_config_sha256": contract.config_sha256,
            "NORMALIZATION_SHA256": b.NORMALIZATION_SHA, "manifest_sha256": b.MANIFEST_SHA,
            "checkpoint_root": str(b.CHECKPOINT_ROOT), "implementation_sha256": b.implementation_hashes()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"authorization_fixture.yaml"
            path.write_text(yaml.safe_dump(value), encoding="utf-8")
            auth = b.PhaseBAuthorization.load(path, sha256(path), contract)
            auth.require()
            value["implementation_sha256"]["src/yuntapr/models/b0.py"] = "wrong"
            path.write_text(yaml.safe_dump(value), encoding="utf-8")
            with self.assertRaises(PermissionError): b.PhaseBAuthorization.load(path, sha256(path), contract)

    def test_fresh_initialization_replay_never_loads_checkpoint(self):
        with patch("torch.load", side_effect=AssertionError("no checkpoint initialization")) as load:
            a = b.fresh_model(); digest = state_digest(a.state_dict()); del a
            torch.rand(100)
            c = b.fresh_model(); self.assertEqual(state_digest(c.state_dict()), digest); del c
            load.assert_not_called()

    def test_all_eleven_epochs_identity_exactly_once_and_actual_tail(self):
        for epoch in range(1, 12):
            coverage = b.EpochCoverage(epoch)
            self.assertEqual(sorted(coverage.order), list(range(23447)))
            for i in range(0, 23447, 2):
                indices = coverage.order[i:i+2]
                coverage.add(indices, len(indices)*3430)
            receipt = coverage.complete()
            self.assertEqual(receipt["updates"], 11724)
            self.assertEqual(receipt["tail_denominator"], 3430)
            self.assertEqual(receipt["denominator"], 80423210)

    def test_missing_duplicate_reordered_or_padded_identities_rejected(self):
        for mode in ("duplicate", "reversed", "padded"):
            coverage = b.EpochCoverage(1)
            pair = coverage.order[:2]
            indices = [pair[0]]*2 if mode == "duplicate" else pair[::-1] if mode == "reversed" else pair+[pair[0]]
            with self.assertRaises(ValueError): coverage.add(indices, len(indices)*3430)
        with self.assertRaises(ValueError): b.EpochCoverage(1).complete()

    def test_denominator_full_batch_and_singleton_not_divided_by_two(self):
        coverage = b.EpochCoverage(1)
        with self.assertRaises(ValueError): coverage.add(coverage.order[:2], 3430)
        for i in range(0, 23446, 2): coverage.add(coverage.order[i:i+2], 6860)
        with self.assertRaises(ValueError): coverage.add(coverage.order[-1:], 6860)
        coverage.add(coverage.order[-1:], 3430)
        coverage.complete()

    def test_stateless_tail_lr_exact_without_preceding_updates(self):
        self.assertEqual(b.finalfit_lr(11724), 1e-4)
        self.assertEqual(b.finalfit_lr(1), 1e-4*(1/11724))
        self.assertGreater(b.finalfit_lr(128964), 1e-6)
        self.assertEqual(b.finalfit_lr(586200), 1e-6)
        self.assertLess(b.finalfit_lr(1), 1e-6)

    def test_no_epoch_or_hyperparameter_override_flags(self):
        for flag in ("--epochs", "--lr", "--batch-size", "--init-checkpoint", "--best", "--early-stopping"):
            with patch("sys.stderr"), self.assertRaises(SystemExit): runner.parser().parse_args(["train", flag, "1"])

    def test_2025_and_alternate_source_root_rejected_without_raw_read(self):
        row = deepcopy(b.RunnerContract.load().rows[0])
        for key, value in (("window_start", "2025-03-01T00:00:00+00:00"), ("imerg_day_path", r"G:\fallback\imerg.nc")):
            bad = deepcopy(row); bad[key] = value
            with self.assertRaises(ValueError): b.source_paths(bad)

    def test_partial_epoch_or_wrong_counter_rejected(self):
        _, _, expected, payload = self.fixture()
        for key, value in (("epoch_completed", False), ("completed_epoch", 0), ("completed_epoch", 12), ("global_update", 11723)):
            bad = deepcopy(payload); bad[key] = value
            with self.assertRaises(ValueError): b.validate_payload(bad, expected)

    def test_phase_a_best_validation_or_scheduler_fields_rejected(self):
        _, _, expected, payload = self.fixture()
        for key in ("BEST", "selected_checkpoint_epoch", "early_stop_best", "validation_completed", "scheduler_state_dict"):
            bad = deepcopy(payload); bad[key] = 1
            with self.assertRaises(ValueError): b.validate_payload(bad, expected)

    def test_state_corruption_or_nonfinite_rejected(self):
        _, _, expected, payload = self.fixture()
        bad = deepcopy(payload); bad["model_state_dict"]["weight"].fill_(float("nan"))
        with self.assertRaisesRegex(ValueError, "checksum"): b.validate_payload(bad, expected)
        bad["model_state_dict_sha256"] = state_digest(bad["model_state_dict"])
        with self.assertRaisesRegex(ValueError, "Nonfinite"): b.validate_payload(bad, expected)

    def test_all_provenance_mismatches_rejected_before_state_application(self):
        model, optimizer, expected, payload = self.fixture()
        before = state_digest((model.state_dict(), optimizer.state_dict(), capture_rng()))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); local = root/"run_fixture"; local.mkdir()
            path = local/"epoch_001.pt"
            with patch.object(b, "CHECKPOINT_ROOT", root):
                for key in expected:
                    bad = deepcopy(payload); bad[key] = "TAMPERED"
                    torch.save(bad, path)
                    with self.assertRaises(ValueError): b.apply_verified_checkpoint(self.identity(path, payload), expected, model, optimizer)
                    self.assertEqual(before, state_digest((model.state_dict(), optimizer.state_dict(), capture_rng())))

    def test_optimizer_incompatibility_rejected_before_model_application(self):
        model, optimizer, expected, payload = self.fixture()
        for mutation in ("betas", "moment", "counter", "groups"):
            bad = deepcopy(payload)
            if mutation == "betas": bad["optimizer_state_dict"]["param_groups"][0]["betas"] = (.5, .9)
            if mutation == "moment": bad["optimizer_state_dict"]["state"][0]["exp_avg"] = torch.zeros(2)
            if mutation == "counter": bad["optimizer_state_dict"]["state"][0]["step"].fill_(11723)
            if mutation == "groups": bad["optimizer_state_dict"]["param_groups"] = []
            bad["optimizer_state_dict_sha256"] = state_digest(bad["optimizer_state_dict"])
            before = state_digest((model.state_dict(), optimizer.state_dict()))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); local = root/"run_fixture"; local.mkdir(); path = local/"epoch_001.pt"
                torch.save(bad, path)
                with patch.object(b, "CHECKPOINT_ROOT", root), self.assertRaises(ValueError):
                    b.apply_verified_checkpoint(self.identity(path, bad), expected, model, optimizer)
            self.assertEqual(before, state_digest((model.state_dict(), optimizer.state_dict())))

    def test_epoch_boundary_resume_replays_next_update_and_rng_exactly(self):
        model, optimizer, expected, payload = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); local = root/"run_fixture"; local.mkdir(); path = local/"epoch_001.pt"
            torch.save(payload, path); identity = self.identity(path, payload)
            with patch.object(b, "CHECKPOINT_ROOT", root):
                def next_update(model, optimizer):
                    optimizer.zero_grad(set_to_none=True)
                    for group in optimizer.param_groups: group["lr"] = b.finalfit_lr(11725)
                    model(torch.rand(2, 1, 1, 1)).sum().backward(); optimizer.step()
                    return state_digest((model.state_dict(), optimizer.state_dict(), capture_rng()))
                b.restore_rng(payload["rng_states"])
                reference = next_update(model, optimizer)
                other = nn.Conv2d(1, 1, 1)
                opt = torch.optim.AdamW(other.parameters(), lr=1e-4, foreach=False)
                restored = b.apply_verified_checkpoint(identity, expected, other, opt)
                self.assertEqual(restored["global_update"], 11724)
                self.assertEqual(next_update(other, opt), reference)

    def test_checkpoint_file_hash_mismatch_before_deserialization(self):
        _, _, expected, payload = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); local = root/"run_fixture"; local.mkdir(); path = local/"epoch_001.pt"
            torch.save(payload, path); identity = self.identity(path, payload); identity["sha256"] = "wrong"
            with patch.object(b, "CHECKPOINT_ROOT", root), patch("torch.load") as load, self.assertRaises(ValueError):
                b.load_verified_checkpoint(identity, expected)
            load.assert_not_called()

    def test_phase_a_checkpoint_root_rejected_before_load(self):
        expected = {"run_id": "run_fixture"}
        identity = {"absolute_local_path": r"F:\pytorch\Research\outputs\formal_training\b0_phase_a\run_fixture\epoch_011.pt", "epoch": 11}
        with patch("torch.load") as load, self.assertRaises(ValueError): b.load_verified_checkpoint(identity, expected)
        load.assert_not_called()

    def test_completed_epochs_last_final_only_no_best_no_reselection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); local = root/"run_fixture"; public = root/"public"; local.mkdir(); public.mkdir()
            registry = {"LAST": None, "FINAL": None}
            with patch.object(b, "CHECKPOINT_ROOT", root):
                for epoch in range(1, 12):
                    _, _, expected, payload = self.fixture(epoch)
                    registry = b.save_checkpoint(local, public, payload, expected, registry)
                    self.assertNotIn("BEST", registry)
                    self.assertEqual(registry["LAST"]["epoch"], epoch)
                    self.assertEqual(registry["FINAL"] is not None, epoch == 11)
                self.assertEqual(registry["LAST"], registry["FINAL"])
                self.assertFalse((public/"best_checkpoint_identity.json").exists())
                self.assertEqual(len(list(local.glob("*.pt"))), 11)
                self.assertFalse(list(local.glob("*.tmp_*")))
                with self.assertRaises(ValueError): b.save_checkpoint(local, public, payload, expected, registry)

    def test_boundary_coverage_and_rng_tamper_rejected(self):
        _, _, expected, payload = self.fixture()
        for field in ("coverage", "rng_states"):
            bad = deepcopy(payload); bad[field] = {}
            with self.assertRaises((ValueError, KeyError)): b.validate_payload(bad, expected)

    def test_final_metadata_recovery_never_executes_another_training_epoch(self):
        _, _, expected, payload = self.fixture(11)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); checkpoints = root/"checkpoints"; public_root = root/"public"
            local = checkpoints/"run_fixture"; public = public_root/"run_fixture"
            local.mkdir(parents=True); public.mkdir(parents=True)
            with patch.object(b, "CHECKPOINT_ROOT", checkpoints):
                registry = b.save_checkpoint(local, public, payload, expected, {"LAST": {"epoch": 10}, "FINAL": None})
                runner.exclusive_json(public/"run_manifest.json", {"checkpoint_expected": expected, "source_identity": {"fixture": True}})
                model = nn.Conv2d(1, 1, 1)
                optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, foreach=False)
                auth = b.PhaseBAuthorization("a"*64, {"AUTHORIZED_SCOPE": "B0_PHASE_B_FINALFIT_ONLY", "PHASE_B_AUTHORIZED": True})
                args = Namespace(authorization=Path("fixture-only.yaml"), authorization_sha256="a"*64, run_id="run_fixture")
                with patch.object(runner, "CHECKPOINT_ROOT", checkpoints), patch.object(runner, "PUBLIC", public_root), \
                        patch.object(runner.RunnerContract, "load", return_value=object()), \
                        patch.object(runner.PhaseBAuthorization, "load", return_value=auth), \
                        patch.object(runner, "source_identity_preflight", return_value={"fixture": True}), \
                        patch.object(runner, "fresh_model", return_value=model), \
                        patch.object(runner, "adamw", return_value=(optimizer, {})), \
                        patch.object(runner, "environment", return_value={"fixture": True}), \
                        patch.object(runner, "checkpoint_expected", return_value=expected), \
                        patch.object(runner, "train_epoch") as train, patch.object(runner, "make_dataset") as dataset:
                    runner.formal_run(args, resume=True)
                    train.assert_not_called(); dataset.assert_not_called()
                status = runner.read(public/"final_status.json")
                self.assertTrue(status["metadata_recovery_only"])
                self.assertEqual(status["additional_optimizer_steps"], 0)
                self.assertEqual(status["FINAL"], registry["FINAL"])


class FinalFitArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = Path(os.environ["YUNTAPR_PHASE_B_RUNNER_EVIDENCE"])
        cls.evidence = json.loads((cls.out/"engineering_preflight.json").read_text(encoding="utf-8"))

    def test_real_smoke_two_independent_updates(self):
        self.assertEqual(self.evidence["ENGINEERING_OPTIMIZER_STEPS"], 2)
        for batch in self.evidence["batches"]:
            self.assertEqual(batch["scope"], "ENGINEERING_ONLY")
            self.assertEqual(batch["actual_optimizer_steps_in_this_fixture"], 1)
            self.assertEqual(batch["preceding_updates_executed"], 0)
            self.assertTrue(batch["temporary_model_optimizer_released"])

    def test_actual_tail_lr_exact_and_denominator(self):
        a, tail = self.evidence["batches"]
        self.assertEqual((a["scheduler_u"], a["batch_size"], a["valid_denominator"]), (1, 2, 6860))
        self.assertEqual((tail["scheduler_u"], tail["batch_size"], tail["valid_denominator"]), (11724, 1, 3430))
        self.assertEqual(tail["LR"], 1e-4)
        self.assertEqual(tail["LR_hex"], (1e-4).hex())
        self.assertTrue(self.evidence["SINGLETON_ACTUAL_TAIL_LR_SMOKE_PASS"])

    def test_source_hash_copy_size_and_cleanup(self):
        for batch in self.evidence["batches"]:
            for detail in batch["source_read_audit"]:
                for op in detail["operations"]:
                    self.assertTrue(op["size_match"] and op["sha256_match"] and op["cleanup_success"])
                    self.assertIsNone(op["error"])
                    path = Path(op["source_path"])
                    year = path.relative_to(b.HROOT).parts[0][:4] if path.is_relative_to(b.HROOT) else path.relative_to(b.IROOT).parts[0]
                    self.assertIn(year, ("2023", "2024"))

    def test_precision_references_and_all_step_components(self):
        for batch in self.evidence["batches"]:
            for name in ("forward_pass", "loss_pass", "backward_pass", "clip_pass", "optimizer_step_pass"):
                self.assertTrue(batch[name])
            self.assertEqual(batch["raw_quantile_dtype"], "torch.float32")
            self.assertEqual(batch["qlog_dtype"], "torch.float64")
            self.assertEqual(batch["pinball_dtype"], "torch.float64")
            self.assertLessEqual(batch["occurrence_reference_abs_error"], 1e-7)
            self.assertLessEqual(batch["quantile_reference_abs_error"], 1e-12)

    def test_no_formal_optimizer_or_authorization_or_future_pixels(self):
        self.assertEqual(self.evidence["FORMAL_OPTIMIZER_STEPS"], 0)
        self.assertEqual(self.evidence["2025_PIXELS_READ"], 0)
        self.assertFalse(self.evidence["PHASE_B_AUTHORIZED"])
        self.assertFalse(self.evidence["PHASE_B_FORMAL_TRAINING_STARTED"])

    def test_no_checkpoint_binary_or_checkpoint_initialization(self):
        self.assertEqual(self.evidence["checkpoint_load_calls"], 0)
        self.assertEqual(self.evidence["temporary_checkpoint_binaries_created"], 0)
        self.assertEqual(self.evidence["owned_staging_files_remaining"], 0)

    def test_runtime_code_hashes_still_exact(self):
        self.assertEqual(self.evidence["implementation_sha256"], b.implementation_hashes())
        self.assertEqual(self.evidence["runner_config_sha256"], sha256(REPO_ROOT/b.CONFIG))

    def test_same_fresh_initialization_for_each_smoke(self):
        a, tail = self.evidence["batches"]
        self.assertEqual(a["initial_model_state_sha256"], tail["initial_model_state_sha256"])
        self.assertNotEqual(a["initial_model_state_sha256"], a["updated_model_state_sha256"])
        self.assertNotEqual(tail["initial_model_state_sha256"], tail["updated_model_state_sha256"])
