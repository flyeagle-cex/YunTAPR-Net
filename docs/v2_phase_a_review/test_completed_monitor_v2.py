import copy
import unittest
from serve_completed_phase_a_v2 import completed_state


class CompletedMonitorTests(unittest.TestCase):
    def evidence(self):
        audit = {'status': 'V2_PAIRED_PHASE_A_COMPLETE_RESEARCHER_REVIEW_REQUIRED',
                 'requirement_checks': {'all': 'PASS'}, 'PDF_VISUALLY_VERIFIED': True,
                 'FINAL_GITHUB_ARTIFACT_PUBLICATION_VERIFIED': True,
                 '2025_RAW_ACCESS': 0, '2025_PIXELS_READ': 0, 'CLOSEOUT_OPTIMIZER_STEPS': 0,
                 'CLOSEOUT_BACKWARD_CALLS': 0, 'V2_PHASE_B_AUTHORIZED': False,
                 'AUTOMATIC_NEXT_STAGE': False, 'FORMAL_TRAINING_RUNNING': False,
                 'FORMAL_TRAINING_COMPLETED': True, 'FORMAL_OPTIMIZER_STEPS_RETAINED': {'B1_V2': 88876}}
        packet = {'models': {'B1_V2': {'early_stopping': {'completed_epoch': 17},
                 'BEST': {'epoch': 9}, 'LAST': {'epoch': 17}, 'metrics': {}}}}
        return audit, packet

    def test_display_requires_completed_evidence(self):
        audit, packet = self.evidence()
        state = completed_state(audit, packet, 'fixture-commit')
        self.assertEqual(state['models']['B1_V2']['retained_optimizer_steps'], 88876)
        audit['PDF_VISUALLY_VERIFIED'] = False
        with self.assertRaisesRegex(ValueError, 'Real completed audit'):
            completed_state(audit, packet, 'fixture-commit')

    def test_firewall_or_training_activity_cannot_display_completion(self):
        audit, packet = self.evidence()
        for key, value in [('2025_RAW_ACCESS', 1), ('FORMAL_TRAINING_RUNNING', True),
                           ('CLOSEOUT_OPTIMIZER_STEPS', 1), ('AUTOMATIC_NEXT_STAGE', True)]:
            bad = copy.deepcopy(audit); bad[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Scope violation'):
                completed_state(bad, packet, 'fixture-commit')


if __name__ == '__main__':
    unittest.main()
