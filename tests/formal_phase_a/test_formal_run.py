"""Formal authorization, epoch state and atomic BEST/LAST guards; no formal fitting."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from torch import nn
from yuntapr.training import formal_phase_a as formal
from yuntapr.training.phase_a_protocol import ValidationSelection, capture_rng, state_digest
import train_b0_phase_a_formal_v1 as runner


class FormalRunTests(unittest.TestCase):
    def fixture(self, epoch=1):
        model = nn.Conv2d(1, 1, 1)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
        rng = capture_rng()
        expected = {"scope": formal.SCOPE, "FORMAL_TRAINING_AUTHORIZED": True,
            "EPOCH_BOUNDARY_RESUME_ONLY": True, "authorization_manifest_sha256": "a" * 64,
            "protocol_sha256": "b" * 64, "source_identity_preflight_sha256": "c" * 64}
        payload = {**expected, "completed_epoch": epoch, "global_update": epoch * 5860,
            "validation_completed": True, "training_samples": 11720, "validation_samples": 11727,
            "selected_checkpoint_epoch": epoch, "best_checkpoint_value": .2, "early_stop_best": .2,
            "global_val_core_loss": .2, "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(), "model_state_dict_sha256": state_digest(model.state_dict()),
            "optimizer_state_dict_sha256": state_digest(optimizer.state_dict()),
            "python_rng_state": rng["python"], "numpy_rng_state": rng["numpy"],
            "torch_cpu_rng_state": rng["torch_cpu"], "torch_cuda_rng_state": rng["torch_cuda"],
            "rng_states_sha256": state_digest(rng)}
        return model, optimizer, expected, payload

    def test_immutable_protocol_and_exact_scheduler(self):
        protocol = runner.load_protocol(expected_sha256=runner.PROTOCOL_SHA)
        self.assertEqual(runner.assert_protocol(protocol)["status"], "PASS")
        self.assertFalse(protocol["authorization"]["FORMAL_TRAINING_AUTHORIZED"])
        self.assertEqual(runner.sha256(runner.ROOT / runner.PROTOCOL_DOC), runner.PROTOCOL_DOC_SHA)
        self.assertEqual(runner.sha256(runner.ROOT / runner.SCHEDULER_PATH), runner.SCHEDULER_SHA)

    def test_explicit_formal_authorization_required(self):
        with self.assertRaisesRegex(ValueError, "authorization"):
            formal.formal_batch([], [], None)
        with self.assertRaisesRegex(ValueError, "authorization"):
            formal.formal_forward(None, None, None)

    def test_protocol_parameter_change_is_rejected(self):
        protocol = deepcopy(runner.load_protocol(expected_sha256=runner.PROTOCOL_SHA))
        protocol["loss"]["occurrence"]["alpha"] = .25
        with self.assertRaisesRegex(ValueError, "alpha"):
            runner.assert_protocol(protocol)

    def test_partial_epoch_and_missing_validation_rejected(self):
        _, _, expected, payload = self.fixture()
        formal.validate_payload(payload, expected)
        for key, value in (("global_update", 5859), ("completed_epoch", 0), ("validation_completed", False), ("validation_samples", 11726)):
            bad = deepcopy(payload)
            bad[key] = value
            with self.assertRaises(ValueError):
                formal.validate_payload(bad, expected)

    def test_all_provenance_rejected_before_apply(self):
        model, optimizer, expected, payload = self.fixture()
        before = state_digest(model.state_dict())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "epoch_001.pt"
            for key in expected:
                bad = deepcopy(payload)
                bad[key] = "TAMPERED"
                torch.save(bad, path)
                identity = {"absolute_local_path": str(path), "bytes": path.stat().st_size, "sha256": runner.sha256(path)}
                with patch.object(formal, "CHECKPOINT_ROOT", root), self.assertRaises(ValueError):
                    formal.apply_verified_checkpoint(identity, expected, model, optimizer)
                self.assertEqual(state_digest(model.state_dict()), before)

    def test_corrupt_state_rejected(self):
        _, _, expected, payload = self.fixture()
        payload["model_state_dict"]["weight"] = torch.full_like(payload["model_state_dict"]["weight"], float("nan"))
        with self.assertRaisesRegex(ValueError, "checksum"):
            formal.validate_payload(payload, expected)

    def test_atomic_best_last_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local, public = root / "run_fixture", root / "public"
            local.mkdir()
            public.mkdir()
            registry = {"BEST": None, "LAST": None}
            with patch.object(formal, "CHECKPOINT_ROOT", root):
                for epoch, selected in ((1, True), (2, False), (3, True)):
                    _, _, expected, payload = self.fixture(epoch)
                    payload["selected_checkpoint_epoch"] = epoch if selected else 1
                    registry, action = formal.save_checkpoint(local, public, payload, expected, registry, selected)
                    self.assertEqual(registry["LAST"]["epoch"], epoch)
                    self.assertEqual(registry["BEST"]["epoch"], epoch if selected else 1)
                    self.assertEqual(len(list(local.glob("*.pt"))), 1 if selected else 2)
                    self.assertFalse(list(local.glob("*.tmp_*")))
                    formal.load_verified_checkpoint(registry["BEST"], expected)
                self.assertEqual(len(action["deleted_old_owned_payloads"]), 2)

    def test_2025_blocked_before_source_access(self):
        from datetime import datetime, timezone
        from yuntapr.data.dataset_b0 import B0Record
        record = B0Record("forbidden", datetime(2025, 3, 1, tzinfo=timezone.utc), (), None, None, None, None, None)
        with self.assertRaisesRegex(ValueError, "2025"):
            formal.guard_record(record)

    def test_checkpoint_selection_and_early_stop_are_independent(self):
        selection = ValidationSelection()
        selection.update(1, .2)
        second = selection.update(2, .19999)
        self.assertTrue(second["checkpoint_selected"])
        self.assertFalse(second["early_stop_improvement"])
        self.assertEqual(selection.non_improvement_count, 1)
        tie = selection.update(3, .19999)
        self.assertFalse(tie["checkpoint_selected"])
        self.assertEqual(selection.selected_checkpoint_epoch, 2)
