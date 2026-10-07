"""Synthetic governance tests; zero raw/checkpoint access or formal updates."""
import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import paired_phase_a_resume_governance_v1 as r


class ResumeGovernanceTests(unittest.TestCase):
    def plan(self, td):
        return {'resume_completed_epoch':8, 'discarded_uncheckpointed_updates':5228,
                'resume_directory':str(td), 'public_directory':str(td)}

    def test_retained_and_all_attempts_counters(self):
        p = self.plan('fixture')
        for canonical, physical in [(0,47052),(41824,47052),(47052,52280),(109788,115016)]:
            v = r.accounting(canonical,p)
            self.assertEqual(v['ALL_ATTEMPTS_ACTUAL_FORMAL_OPTIMIZER_STEPS'], physical)
            self.assertEqual(v['MODEL_TRAJECTORY_OPTIMIZER_STEPS'], canonical)

    def test_origin_metadata_kept_byte_identical(self):
        with tempfile.TemporaryDirectory() as td, patch.object(r,'PLAN',self.plan(td)):
            path=Path(td)/'run_manifest.json';content='{"origin": true}\n';path.write_text(content)
            r.protected_atomic(path, {'origin':True})
            self.assertEqual(path.read_text(),content)

    def test_changed_origin_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as td, patch.object(r,'PLAN',self.plan(td)):
            path=Path(td)/'first_update_identity_gate.json';path.write_text('{"origin":true}')
            with self.assertRaises(PermissionError):r.protected_atomic(path, {'origin':False})

    def test_final_status_has_separate_actual_counts(self):
        with tempfile.TemporaryDirectory() as td, patch.object(r,'PLAN',self.plan(td)), patch.object(r,'ORIGINAL_ATOMIC') as write:
            r.protected_atomic(Path(td)/'final_status.json', {'FORMAL_OPTIMIZER_STEPS':47052})
            self.assertEqual(write.call_args.args[1]['ALL_ATTEMPTS_ACTUAL_FORMAL_OPTIMIZER_STEPS'],52280)

    def test_backward_event_before_optimizer_uses_actual_backward_count(self):
        v=r.accounting(41824,self.plan('fixture'),backward=41825)
        self.assertEqual(v['ALL_ATTEMPTS_ACTUAL_BACKWARD_CALLS'],47053)
        self.assertEqual(v['ALL_ATTEMPTS_ACTUAL_FORMAL_OPTIMIZER_STEPS'],47052)

    def test_event_marks_resumed_not_fresh(self):
        with tempfile.TemporaryDirectory() as td, patch.object(r,'PLAN',self.plan(td)):
            audit=r.ResumeRunAudit(td,'B1');audit.counters.FORMAL_OPTIMIZER_STEPS=41824
            audit.event('FORMAL_FRESH_RUN_READY')
            row=json.loads((Path(td)/'partial_training_log.jsonl').read_text())
            self.assertEqual(row['event'],'FORMAL_RESUMED_RUN_READY')
            self.assertEqual(row['ALL_ATTEMPTS_ACTUAL_FORMAL_OPTIMIZER_STEPS'],47052)

    def test_addition_hash_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            r.verify_additions({'resume_governance_code_hashes':{'scripts/paired_phase_a_resume_governance_v1.py':'bad'}})


if __name__ == '__main__':unittest.main()
