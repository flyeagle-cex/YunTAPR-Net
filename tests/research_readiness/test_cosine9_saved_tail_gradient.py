"""Reproduce direction, archive, and approval checks using generated arrays only."""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools.research_readiness import cosine9_saved_tail_gradient as diagnostic


def synthetic_archive(*, point_drift=0.):
    n = 717
    physical = np.broadcast_to(np.linspace(8, 19, 32), (n, 32)).copy()
    physical[:100, -1] = 26
    physical[100:160, -1] = 23
    qlog = np.log1p(physical)
    p = np.full(n, .25)
    stream = BytesIO()
    np.savez_compressed(
        stream, p_occ=p, qlog=qlog, truth_mm_h=np.full(n, 25.),
        point_A_mm_h=p * np.expm1(qlog).mean(axis=1) + point_drift,
        scene_id=np.full(n, "synthetic"),
        analysis_time=np.full(n, "2024-SYNTHETIC"),
        pixel_index=np.arange(n),
    )
    return stream.getvalue()


class TailGradientDiagnosticTests(unittest.TestCase):
    def test_two_direction_definitions_and_boundary_cases(self):
        low = np.linspace(8, 20, 32)
        mixed = np.r_[np.linspace(8, 20, 16), np.linspace(30, 50, 16)]
        disagreement = np.r_[low[:-1], 1e6]
        near_knot = np.r_[low[:-1], 25.]
        report = diagnostic.summarize(
            np.array([.75, .75, .75, .75, 0.]),
            np.log1p(np.stack([low, mixed, disagreement, near_knot, low])),
            np.array([25., 25., 50., 25., 70.]),
        )
        all_strong = report["all_strong"]
        self.assertEqual(all_strong["strictly_mixed"], 2)
        self.assertEqual(all_strong["near_truth_knot"], 1)
        self.assertEqual(all_strong["zero_probability"], 1)
        self.assertEqual(all_strong["independent_nodes"],
                         dict(conflict=2, aligned=1, indeterminate=2, conflict_fraction=.4))
        self.assertEqual(all_strong["fixed_allocation_span"],
                         dict(conflict=1, aligned=2, indeterminate=2, conflict_fraction=.2))
        band = report["by_truth_mm_h"]["(30,50]"]
        self.assertEqual(band["independent_nodes"]["conflict"], 1)
        self.assertEqual(band["fixed_allocation_span"]["aligned"], 1)

    def test_identity_and_frozen_baseline_against_generated_archive(self):
        for drift in (False, True):
            with self.subTest(baseline_changed=drift):
                raw = synthetic_archive(point_drift=float(drift))
                with patch.multiple(diagnostic, ARCHIVE_BYTES=len(raw), ARCHIVE_SHA256=sha256(raw).hexdigest()):
                    if drift:
                        with self.assertRaisesRegex(ValueError, "frozen FP32 point A"):
                            diagnostic._verified_result(raw)
                    else:
                        result = diagnostic._verified_result(raw)["all_strong"]
                        self.assertEqual(result["all_nodes_below_truth"], 617)
                        self.assertEqual(result["strictly_mixed"], 100)
                    with self.assertRaisesRegex(ValueError, "digest differs"):
                        diagnostic._verified_result(raw[:-1] + bytes([raw[-1] ^ 1]))

    def test_wrong_grant_stops_before_archive_is_touched(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = diagnostic.build_proposal()
            proposal = root / "proposal.json"
            proposal.write_text(json.dumps(plan), encoding="utf-8")
            grant = root / "RESEARCHER_APPROVAL.json"
            grant.write_text(json.dumps(dict(
                approved_by_researcher=True, decision_id="synthetic-wrong-scope",
                run_folder=str(root.resolve()),
                authorization_scope="OLD_ALREADY_CONSUMED", budget=plan["budget"],
                proposal_sha256=plan["proposal_sha256"],
            )), encoding="utf-8")
            with patch.object(diagnostic, "PROPOSAL_PATH", proposal):
                with self.assertRaises(PermissionError):
                    diagnostic.execute_once(None, root)
            self.assertFalse((root / "output").exists())

    def test_grant_cannot_be_copied_or_reused_after_failed_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = diagnostic.build_proposal()
            proposal = root / "proposal.json"
            proposal.write_text(json.dumps(plan), encoding="utf-8")
            grant = dict(approved_by_researcher=True, decision_id="synthetic",
                         run_folder=str(root.resolve()), budget=plan["budget"],
                         authorization_scope=plan["authorization_scope"], proposal_sha256=plan["proposal_sha256"])
            approval_name = "RESEARCHER_APPROVAL.json"
            (root / approval_name).write_text(json.dumps(grant), encoding="utf-8")
            other = root / "other"
            other.mkdir()
            (other / approval_name).write_text(json.dumps(grant), encoding="utf-8")
            with patch.object(diagnostic, "PROPOSAL_PATH", proposal):
                with self.assertRaises(PermissionError):
                    diagnostic.execute_once(None, other)
                with self.assertRaisesRegex(ValueError, "archive name or size"):
                    diagnostic.execute_once(root / "unrecognized.npz", root)
                with self.assertRaises(FileExistsError):
                    diagnostic.execute_once(None, root)

    def test_approved_synthetic_run_emits_only_aggregate_and_cannot_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            archive = root / "strong_joint_pixels.npz"
            payload = synthetic_archive()
            archive.write_bytes(payload)
            budget = diagnostic.BUDGET | {"saved_record_bytes": len(payload)}
            proposal_path = root / "proposal.json"
            with patch.multiple(diagnostic, ARCHIVE_BYTES=len(payload), ARCHIVE_SHA256=sha256(payload).hexdigest(),
                                BUDGET=budget, PROPOSAL_PATH=proposal_path):
                plan = diagnostic.build_proposal()
                proposal_path.write_text(json.dumps(plan), encoding="utf-8")
                grant = {key: plan[key] for key in ("authorization_scope", "budget", "proposal_sha256")}
                grant.update(approved_by_researcher=True, decision_id="synthetic", run_folder=str(root))
                (root / "RESEARCHER_APPROVAL.json").write_text(json.dumps(grant), encoding="utf-8")
                result = diagnostic.execute_once(archive, root)
                archive.unlink()
                with self.assertRaises(FileExistsError):
                    diagnostic.execute_once(archive, root)

            outputs = list((root / "output").iterdir())
            self.assertEqual([file.name for file in outputs], ["completion.json"])
            self.assertEqual(json.loads(outputs[0].read_text(encoding="utf-8")), result)
            self.assertEqual(result["all_strong"]["n"], 717)
            self.assertEqual(result["all_strong"]["all_nodes_below_truth"], 617)
            self.assertEqual(result["status"], "COMPLETE_SAVED_STRONG_LOCAL_GRADIENT")
            self.assertEqual(result["scientific_status"], "NOT_VERIFIED")
            self.assertEqual(result["actual_usage"]["saved_record_opens"], 1)
            self.assertEqual(result["actual_usage"]["saved_record_bytes"], len(payload))
            self.assertEqual(result["actual_usage"]["forwards"], 0)
            self.assertFalse(result["actual_usage"]["final_2025_access"])


if __name__ == "__main__":
    unittest.main()
