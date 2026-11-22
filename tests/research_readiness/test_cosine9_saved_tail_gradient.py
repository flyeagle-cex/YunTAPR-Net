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
        n = 717
        physical = np.broadcast_to(np.linspace(8, 19, 32), (n, 32)).copy()
        physical[:100, -1] = 26
        physical[100:160, -1] = 23
        qlog = np.log1p(physical)
        p = np.full(n, .25)
        fields = dict(
            p_occ=p, qlog=qlog, truth_mm_h=np.full(n, 25.),
            point_A_mm_h=p * np.expm1(qlog).mean(axis=1),
            scene_id=np.full(n, "synthetic"),
            analysis_time=np.full(n, "2024-SYNTHETIC"),
            pixel_index=np.arange(n),
        )
        for drift in (False, True):
            with self.subTest(baseline_changed=drift):
                stream = BytesIO()
                arrays = fields | {"point_A_mm_h": fields["point_A_mm_h"] + float(drift)}
                np.savez_compressed(stream, **arrays)
                raw = stream.getvalue()
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


if __name__ == "__main__":
    unittest.main()
