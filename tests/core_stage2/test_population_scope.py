import unittest
from yuntapr.experimental.core_innovation.stage2.population import joint_population


class ScopeTests(unittest.TestCase):
    def test_forbidden_year_rejected_before_missing_evidence_join(self):
        row = dict(sample_id='2025-05-01T05:30:00+00:00', window_start='2025-05-01T05:30:00+00:00',
                   analysis_time='2025-05-01T06:00:00+00:00', role='Validation')
        for i, minute in enumerate((0, 10, 20, 30, 40, 50)):
            row[f'slot_{i}_nominal'] = f'2025-05-01T05:{minute:02d}:00+00:00'
        with self.assertRaises(PermissionError): joint_population([row], {}, native_grid_id='synthetic')


if __name__ == '__main__': unittest.main()
