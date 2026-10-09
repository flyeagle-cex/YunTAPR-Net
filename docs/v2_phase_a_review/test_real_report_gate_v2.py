import copy
import unittest
from compile_real_report_delivery_v2 import FROZEN, validate_packet


class RealReportGateTests(unittest.TestCase):
    def fixture(self):
        return {'status': 'PAIRED_DECISION_PACKET_PDF_AND_PUBLICATION_PENDING',
                'PAIR_PHASE_A_TRAINING_COMPLETE': True, 'FULL_2024_BEST_REVIEW_EXECUTED': True,
                'frozen_identities': dict(FROZEN), '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0,
                'V2_PHASE_B_AUTHORIZED': False, 'PACKET_GENERATION_FORWARD_CALLS': 0,
                'PACKET_GENERATION_BACKWARD_CALLS': 0, 'PACKET_GENERATION_OPTIMIZER_STEPS': 0,
                'PACKET_GENERATION_RAW_SOURCE_OPENS': 0,
                'models': {k: {'metrics': {'scenes': 10501, 'forwards': 1313, 'N_valid': 36018430},
                               'early_stopping': {'termination_reason': 'EARLY_STOP_PATIENCE_8'}}
                           for k in ('B0_MATCHED_V2', 'B1_V2')}}

    def test_both_completed_real_review_records_required(self):
        value = self.fixture(); validate_packet(value)
        value['FULL_2024_BEST_REVIEW_EXECUTED'] = False
        with self.assertRaisesRegex(ValueError, 'real completed paired review'):
            validate_packet(value)

    def test_partial_9000_scene_review_is_rejected(self):
        value = self.fixture(); value['models']['B1_V2']['metrics']['scenes'] = 9000
        with self.assertRaisesRegex(ValueError, 'Partial validation'):
            validate_packet(value)

    def test_changed_science_sha_is_rejected(self):
        value = self.fixture(); value['frozen_identities']['normalization_sha256'] = 'refit'
        with self.assertRaisesRegex(ValueError, 'frozen identity mismatch'):
            validate_packet(value)

    def test_scope_change_is_rejected_before_compilation(self):
        value = self.fixture()
        for key, invalid in [('2025_RAW_ACCESS', 1), ('V2_PHASE_B_AUTHORIZED', True),
                             ('PACKET_GENERATION_OPTIMIZER_STEPS', 1)]:
            bad = copy.deepcopy(value); bad[key] = invalid
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'operation scope'):
                validate_packet(bad)


if __name__ == '__main__':
    unittest.main()
