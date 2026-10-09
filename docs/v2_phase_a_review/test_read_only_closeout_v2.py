"""Synthetic safety fixtures; never run a model or real subprocess."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import run_read_only_closeout_v2 as c


class CloseoutSafetyTests(unittest.TestCase):
    def test_all_commands_exclude_formal_train_resume_and_2025(self):
        for phase in ('B1_TERMINAL_AUDIT', 'FULL_2024_BEST_REVIEW', 'PAIRED_DECISION_PACKET'):
            command = c.allowed_command(phase, Path('auth.json'), 'sha', Path('b0'),
                b1_audit=Path('b1'), review=Path('review'), packet=Path('packet'))
            self.assertEqual(command[0], str(c.PYTHON))
            self.assertNotIn('run_paired_phase_a_v2.py', ' '.join(command))
            self.assertNotIn('resume', command)
            self.assertNotIn('train', command)
            self.assertNotIn('2025', command)
        for forbidden in ('FORMAL_TRAIN', 'RESUME', 'PHASE_B', '2025_TEST'):
            with self.assertRaises(PermissionError):
                c.allowed_command(forbidden, Path('auth.json'), 'sha', Path('b0'))

    def test_gate_rejects_partial_pair_before_launch(self):
        with patch.object(c, 'sha', return_value='sha'), \
             patch.object(c, 'check_pair', return_value={'status': 'WAITING_FOR_BOTH_PHASE_A_COMPLETION'}), \
             patch.object(c, 'resolve_authority') as authority, \
             patch.object(c.subprocess, 'Popen') as popen:
            with self.assertRaises(PermissionError): c.enforce_gate(Path('auth.json'), 'sha')
            authority.assert_not_called(); popen.assert_not_called()

    def test_gate_rejects_wrong_auth_and_2025_scope(self):
        with patch.object(c, 'sha', return_value='wrong'), patch.object(c, 'check_pair') as gate:
            with self.assertRaises(PermissionError): c.enforce_gate(Path('auth.json'), 'sha')
            gate.assert_not_called()
        gate = {'status': 'METADATA_COMPLETION_GATE_PASS', 'origin_authorization_sha256': c.ORIGIN_SHA}
        with patch.object(c, 'sha', return_value='sha'), patch.object(c, 'check_pair', return_value=gate), \
             patch.object(c.Path, 'exists', return_value=False), \
             patch.object(c, 'resolve_authority', return_value=({'V2_PHASE_B_AUTHORIZED': False,
                 '2025_RAW_ACCESS': 1, '2025_PIXELS_READ': 0}, c.ORIGIN_SHA)):
            with self.assertRaises(PermissionError): c.enforce_gate(Path('auth.json'), 'sha')

    def test_child_failure_preserves_evidence_and_is_not_retried(self):
        process = MagicMock()
        process.stdout = io.StringIO('{"verified_epoch": 1, "total_epochs": 17}\n')
        process.wait.return_value = 1
        process.pid = 123
        fixture_root = c.REPO / 'tmp' / 'closeout_safety_fixtures'
        fixture_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=fixture_root) as tmp, patch.object(c.subprocess, 'Popen', return_value=process) as popen:
            out = Path(tmp)
            with self.assertRaisesRegex(RuntimeError, 'no automatic retry'):
                c.run_child('B1_TERMINAL_AUDIT', ['fixture_only_no_process'], out,
                    {'code_sha256': {}}, lambda **_: None)
            popen.assert_called_once()
            self.assertTrue((out / 'B1_TERMINAL_AUDIT_exit.json').is_file())
            self.assertTrue((out / 'B1_TERMINAL_AUDIT.stdout.log').is_file())
            self.assertEqual(popen.call_args.kwargs['env']['CUDA_VISIBLE_DEVICES'], '-1')


if __name__ == '__main__':
    unittest.main()
