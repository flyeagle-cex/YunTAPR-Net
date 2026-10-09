"""Metadata-only corruption tests; never constructs a model or opens raw data."""
import copy
from pathlib import Path
import tempfile
import unittest

from finalize_paired_closeout_v2 import identity, verify_pdf, verify_ref, verify_replay


class FinalCompletionTests(unittest.TestCase):
    def test_registered_evidence_byte_change_rejected(self):
        parent = Path(__file__).resolve().parents[2] / 'tmp'
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='final_completion_fixture_', dir=parent) as name:
            root = Path(name); path = root / 'evidence.json'
            path.write_text('{"status":"PASS"}', encoding='utf-8')
            ref = identity(path)
            self.assertEqual(verify_ref(ref, [root]), path)
            path.write_text('{"status":"FAIL"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Artifact bytes changed'):
                verify_ref(ref, [root])

    def test_unregistered_raw_root_rejected_before_open(self):
        with self.assertRaisesRegex(ValueError, 'Unregistered artifact root'):
            verify_ref({'absolute_local_path': 'H:/forbidden-raw/2025.nc', 'bytes': 1, 'sha256': 'x'},
                       [Path(__file__).resolve().parent])

    def pdf_fixture(self):
        return {'status': 'REAL_PAIRED_REPORT_COMPILE_AND_VISUAL_PASS', 'TEST_FIXTURE_ONLY': False,
                'overfull_box_count': 0, 'compile_passes': [{'exit_code': 0}, {'exit_code': 0}],
                'page_count': 2, 'pages': [{'page': 1, 'visually_checked': True},
                                          {'page': 2, 'visually_checked': True}]}

    def test_fixture_pdf_cannot_complete_goal(self):
        value = self.pdf_fixture(); value['TEST_FIXTURE_ONLY'] = True
        with self.assertRaisesRegex(ValueError, 'Fixture PDF'):
            verify_pdf(value, [])

    def test_one_uninspected_pdf_page_rejected(self):
        value = self.pdf_fixture(); value['pages'][1]['visually_checked'] = False
        with self.assertRaisesRegex(ValueError, 'Every real PDF page'):
            verify_pdf(value, [])

    def test_layout_warning_cannot_be_pass(self):
        value = self.pdf_fixture(); value['overfull_box_count'] = 1
        with self.assertRaisesRegex(ValueError, 'PDF compilation/layout failed'):
            verify_pdf(value, [])

    def test_replay_prefix_mismatch_cannot_complete_goal(self):
        value = {'status': 'B1_RETAINED_EPOCH_15_REPLAY_PREFIX_PASS',
                 'retained_trajectory_updates': 88876, 'all_attempt_updates': 92353,
                 'discarded_uncheckpointed_updates': 3477, 'verified_resume_LAST': {'epoch': 14},
                 'resume_retained_updates': 73192, 'retained_epoch_15_complete_updates': 5228,
                 'comparisons': [{'completed_updates_compared': 3095, 'tolerance': 0, 'mismatches': []},
                                 {'completed_updates_compared': 382, 'tolerance': 0, 'mismatches': ['LR']}],
                 'half_epoch_state_reused': False, 'historical_sources_unchanged': True}
        with self.assertRaisesRegex(ValueError, 'zero-tolerance proof missing'):
            verify_replay(value)


if __name__ == '__main__':
    unittest.main()
