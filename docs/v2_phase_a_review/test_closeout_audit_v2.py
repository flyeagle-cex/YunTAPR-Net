"""Synthetic corruption checks for the terminal audit. CPU fixtures only."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import closeout_audit_v2 as audit

ROOT = Path(__file__).resolve().parent
EXECUTION = ROOT.parents[2] / 'YunTAPR-Net-v2-phase-a-execution'
sys.path.insert(0, str(EXECUTION / 'src'))
import torch
from yuntapr.training.upper_tail_v2 import UpperTailDiagnostics


class CloseoutAuditTests(unittest.TestCase):
    def diagnostic(self, high=False):
        mask = torch.zeros((100, 100), dtype=torch.bool)
        mask.reshape(-1)[:3430] = True
        observer = UpperTailDiagnostics(mask, 'TRAIN')
        qlog = (.2 + torch.arange(32, dtype=torch.float64) * .01)[None, :, None, None].expand(1, 32, 100, 100).clone()
        if high: qlog[:, 31] = 1000
        row = observer.observe(qlog, ['synthetic-2023-id'])
        row['event'] = 'UPPER_TAIL_FORWARD'
        return [row], observer.report()

    def test_finite_physical_overflow_risk_is_only_descriptive(self):
        rows, report = self.diagnostic(high=True)
        self.assertTrue(report['YUNNAN_INSIDE']['FP64_PHYSICAL_OVERFLOW_RISK'])
        audit.verify_diagnostics(rows, 'TRAIN', [['synthetic-2023-id']], report, UpperTailDiagnostics)

    def test_changed_percentile_rejected(self):
        rows, report = self.diagnostic()
        report['YUNNAN_INSIDE']['q32_per_forward_max_p99'] += .1
        with self.assertRaisesRegex(ValueError, 'aggregate'):
            audit.verify_diagnostics(rows, 'TRAIN', [['synthetic-2023-id']], report, UpperTailDiagnostics)

    def test_changed_scene_id_and_exposure_rejected(self):
        rows, report = self.diagnostic()
        for changed in ('sample_ids', 'exposure'):
            bad = copy.deepcopy(rows)
            if changed == 'sample_ids': bad[0]['sample_ids'] = ['another-scene']
            else: bad[0]['YUNNAN_INSIDE']['scene_pixel_tau_exposure'] -= 1
            with self.assertRaises(ValueError):
                audit.verify_diagnostics(bad, 'TRAIN', [['synthetic-2023-id']], report, UpperTailDiagnostics)

    def test_wrong_any_tau_counts_and_risk_rejected(self):
        rows, report = self.diagnostic(high=True)
        for field in ('count', 'risk'):
            bad = copy.deepcopy(rows)
            if field == 'count': bad[0]['YUNNAN_INSIDE']['threshold_exceedances']['10']['scene_pixel_any_tau_exposure'] = 0
            else: bad[0]['YUNNAN_INSIDE']['FP64_PHYSICAL_OVERFLOW_RISK'] = False
            with self.assertRaises(ValueError):
                audit.verify_diagnostics(bad, 'TRAIN', [['synthetic-2023-id']], report, UpperTailDiagnostics)

    def test_append_prefix_allowed_but_prefix_change_rejected(self):
        with tempfile.TemporaryDirectory(prefix='closeout_fixture_', dir=ROOT) as name:
            root = Path(name).resolve(); self.assertTrue(root.is_relative_to(ROOT.resolve()))
            path = root / 'journal.jsonl'; path.write_bytes(b'first\nsecond\n')
            ref = {'absolute_local_path': str(path), 'bytes': 6, 'sha256': hashlib.sha256(b'first\n').hexdigest()}
            self.assertEqual(audit.verify_ref(ref, root, prefix=True)['verification'], 'APPEND_ONLY_PREFIX_PRESERVED')
            with self.assertRaisesRegex(ValueError, 'size'):
                audit.verify_ref(ref, root)
            path.write_bytes(b'other\nsecond\n')
            with self.assertRaisesRegex(ValueError, 'SHA'):
                audit.verify_ref(ref, root, prefix=True)
            with self.assertRaises(PermissionError): audit.verify_ref(ref, root / 'different-root', prefix=True)

    def test_singleton_validation_tail_and_order(self):
        ids = ['synthetic-id-' + str(i) for i in range(10501)]
        rows = [{'event': 'VALIDATION_FORWARD_START', 'step': i + 1, 'sample_ids': ids[start:start + 8]}
                for i, start in enumerate(range(0, 10501, 8))]
        self.assertEqual(len(audit.verify_validation(rows, ids)[-1]), 5)
        rows[-1]['sample_ids'].append('duplicated-id')
        with self.assertRaisesRegex(ValueError, 'identity'):
            audit.verify_validation(rows, ids)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main(verbosity=2)
