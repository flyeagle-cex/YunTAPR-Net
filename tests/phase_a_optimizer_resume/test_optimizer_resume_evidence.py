"""Cross-check the real CUDA evidence without executing additional optimizer steps."""
import csv
import json
import os
from pathlib import Path
import unittest

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.training.phase_a_protocol import phase_a_lr_for_update


class OptimizerResumeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE"):
            raise RuntimeError("Supply the actually executed CUDA run; no synthetic replacement")
        cls.evidence_dir = Path(os.environ["YUNTAPR_PROTOCOL_DRYRUN_EVIDENCE"])
        cls.identity = cls.read("protocol_identity.json")

    @classmethod
    def read(cls,name):
        return json.loads((cls.evidence_dir/name).read_text(encoding="utf-8"))

    @classmethod
    def rows(cls,name):
        with (cls.evidence_dir/name).open(encoding="utf-8",newline="") as stream:
            return list(csv.DictReader(stream))

    def test_protocol_and_previous_failure_immutable(self):
        for kind in ("protocol","document"):
            self.assertEqual(sha256(REPO_ROOT/self.identity[kind+"_path"]),self.identity[kind+"_sha256"])
        prior=REPO_ROOT/self.identity["previous_run_path"]
        manifest=json.loads((prior/"manifest.json").read_text(encoding="utf-8"))
        for name,info in manifest["public_files"].items():
            self.assertEqual(sha256(prior/name),info["sha256"])
        self.assertFalse(self.identity["scientific_parameters_changed"])
        self.assertFalse(self.identity["protocol_version_changed"])

    def test_actual_nine_steps_from_six_2023_samples(self):
        steps=self.rows("optimizer_steps.csv")
        self.assertEqual(len(steps),9)
        selected=self.read("selected_dryrun_samples.json")
        self.assertEqual(selected["indices"],[0,2343,4687,7031,9375,11719])
        self.assertEqual(len(selected["samples"]),6)
        self.assertEqual({s["year"] for s in selected["samples"]},{2023})
        for run in ("A","B","C"):
            rows=[r for r in steps if r["run"]==run]
            self.assertEqual([int(r["global_update"]) for r in rows],[1,2,3])
            for row in rows:
                u=int(row["global_update"])
                self.assertEqual(float(row["LR"]),phase_a_lr_for_update(u))
                self.assertEqual(row["scope"],"ENGINEERING_ONLY")
                self.assertEqual(row["optimizer_step_performed"],"True")
                self.assertEqual(int(row["valid_Yunnan_supervised_pixels"]),6860)

    def test_actual_dedicated_memory_and_initialized_moments(self):
        rows=self.rows("optimizer_memory.csv")
        self.assertEqual(len(rows),9)
        for row in rows:
            total=float(row["dedicated_total_MiB"])
            self.assertLessEqual(float(row["peak_reserved_MiB"]),.8*total)
            self.assertGreaterEqual(float(row["estimated_min_device_free_MiB"]),.2*total)
            self.assertEqual(row["safe_20pct"],"True")
            self.assertEqual(int(row["optimizer_state_parameter_tensors"]),74)
            self.assertEqual(float(row["optimizer_cuda_state_MiB"]),4329361*8/1024**2)
            self.assertEqual(row["optimizer_state_first_initialized"],str(row["global_update"]=="1"))
            estimate=min(float(row["device_free_MiB"]),float(row["pre_device_free_MiB"])
                -max(0,float(row["peak_reserved_MiB"])-float(row["pre_reserved_MiB"])))
            self.assertEqual(float(row["estimated_min_device_free_MiB"]),estimate)

    def test_actual_precision_autocast_and_gradient_clip(self):
        evidence=self.read("precision_checks.json")
        self.assertEqual(evidence["status"],"PASS")
        self.assertEqual(len(evidence["checks"]),9)
        for row in evidence["checks"]:
            self.assertEqual(row["parameters"],["torch.float32"])
            self.assertEqual(row["raw_quantile"],"torch.float32")
            self.assertTrue(row["autocast_enabled"])
            self.assertEqual(row["autocast_dtype"],"torch.bfloat16")
            for key in ("qlog","qphysical","pinball"):
                self.assertEqual(row[key],"torch.float64")
            self.assertIn(row["backbone_autocast_output"],("torch.float32","torch.bfloat16"))
            for key in ("finite_outputs","finite_loss","gradients_finite","parameters_after_step_finite","optimizer_state_finite","pass_"):
                self.assertTrue(row[key])
            self.assertEqual(row["strict_crossing_count"],0)
        for row in self.rows("optimizer_steps.csv"):
            self.assertEqual(float(row["clip_threshold"]),5.)
            self.assertGreater(float(row["pre_clip_norm"]),5.)
            self.assertEqual(row["clipping_triggered"],"True")
            self.assertLessEqual(float(row["post_clip_norm"]),5.)

    def test_real_bit_exact_replay_including_resume(self):
        runs=[self.read("determinism_run_"+letter+".json") for letter in ("a","b","c")]
        for other in runs[1:]:
            for key in ("initial_model_state_sha256","model_state_sha256","optimizer_state_sha256","RNG_states_sha256","global_update"):
                self.assertEqual(runs[0][key],other[key])
            for left,right in zip(runs[0]["steps"],other["steps"]):
                for key in ("LR","loss","pre_clip_norm","clipping_triggered"):
                    self.assertEqual(left[key],right[key])
        resume=self.read("resume_checkpoint_test.json")
        self.assertTrue(resume["exact_pass"])
        self.assertTrue(resume["original_model_optimizer_destroyed"])
        self.assertTrue(resume["temporary_checkpoint_deleted"])
        self.assertTrue(resume["temporary_root_deleted"])
        self.assertTrue(resume["schema_complete"])

    def test_real_corrupt_loader_rejection_precedes_all_state_application(self):
        cases=self.read("checkpoint_provenance_guard.json")["cases"]
        self.assertEqual({r["mutated_metadata_key"] for r in cases},
            {"protocol_sha256","normalization_artifact_sha256","scientific_contract_sha256"})
        for row in cases:
            self.assertTrue(row["rejected_before_state_application"])
            self.assertIn(row["mutated_metadata_key"],row["error"])
            for key in ("model_load_calls","optimizer_load_calls","rng_restore_calls"):
                self.assertEqual(row[key],0)

    def test_real_reader_staging_QC_provenance(self):
        audit=self.read("real_sample_read_audit.json")
        self.assertEqual(len(audit["samples"]),6)
        self.assertEqual(audit["num_workers"],2)
        self.assertEqual({r["worker_id"] for r in audit["samples"]},{0,1})
        roots={r["staging_root"] for r in audit["samples"]}
        self.assertEqual(len(roots),2)
        self.assertTrue(all(root.isascii() for root in roots))
        for row in audit["samples"]:
            self.assertEqual(row["year"],2023)
            self.assertTrue(row["formal_QC_pass"])
            self.assertTrue(row["causality_pass"])
            self.assertEqual(row["valid_Yunnan_cells"],3430)
            for reader in row["readers"].values():
                self.assertTrue(reader["sha256_match"])
                self.assertTrue(reader["cleanup_success"])
                self.assertEqual(reader["owned_copy_count_after"],0)
                self.assertLessEqual(reader["temporary_bytes"],734003200)
        self.assertEqual(audit["owned_staging_copies_remaining"],0)

    def test_engineering_scope_without_binaries_or_authorization(self):
        status=self.read("gpu_dryrun_status.json")
        self.assertEqual(status["actual_optimizer_steps"],9)
        self.assertFalse(status["B0_FORMAL_TRAINING_STARTED"])
        self.assertFalse(status["FORMAL_TRAINING_AUTHORIZED"])
        banned={".pt",".pth",".bin",".nc",".h5",".hdf5",".whl",".npy",".npz"}
        self.assertFalse([p for p in self.evidence_dir.rglob("*") if p.is_file() and p.suffix in banned])


if __name__=="__main__":
    unittest.main()
