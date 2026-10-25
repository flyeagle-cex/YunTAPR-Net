import unittest
from datetime import timedelta
import test_stage2 as base
from yuntapr.experimental.core_innovation.stage2.coupling import TargetBinding


class TemporalInheritanceTests(unittest.TestCase):
    def test_no_new_observation_start_relative_to_nominal_qc_threshold(self):
        b = base.binding()
        # Inherited rule is actual start <= actual end <= analysis. A nominal
        # timestamp is not an extra physical start-time threshold.
        result = TargetBinding(b.window_start, b.analysis, b.nominal,
            tuple(n-timedelta(seconds=1) for n in b.nominal), b.observation_end)
        self.assertEqual(result.observation_end, b.observation_end)


if __name__ == '__main__': unittest.main()
