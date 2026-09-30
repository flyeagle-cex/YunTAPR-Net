"""Cross-check measured audit artifacts, not synthetic copies of their producer."""
import csv
import json
import math
import unittest
from pathlib import Path

from yuntapr.contracts.loader import REPO_ROOT, sha256


RUN = REPO_ROOT / "docs/training_environment_audit/runs/run_20260930T114738Z"


def artifact(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def table(name):
    with (RUN / name).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


class TrainingEnvironmentEvidenceTest(unittest.TestCase):
    def test_cpu_only_gpu_presence_and_no_false_gpu_pass(self):
        env, gpu = artifact("pytorch_cuda_environment.json"), artifact("gpu_inventory.json")
        self.assertEqual(env["TORCH_BUILD"], "CPU_ONLY")
        self.assertTrue(env["CURRENT_TORCH_CANNOT_USE_CUDA"])
        self.assertFalse(env["torch_cuda_is_available"])
        self.assertTrue(gpu["GPU_PRESENT"])
        self.assertFalse(gpu["CUDA_TORCH_AVAILABLE"])
        self.assertEqual(gpu["nvidia_smi_status"], "PASS")
        for name in ("gpu_batch_benchmark.csv", "gpu_amp_benchmark.csv", "gpu_validation_benchmark.csv"):
            rows = table(name)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "NOT_RUN_CUDA_UNAVAILABLE")

    def test_full_shape_real_backward_precision_and_peak_memory(self):
        cpu, model = artifact("cpu_benchmark.json"), artifact("model_memory_static.json")
        self.assertEqual(cpu["status"], "PASS")
        self.assertEqual(cpu["measurement_count"], 3)
        self.assertEqual(model["input_shape_batch_1"], [1, 1, 501, 501])
        self.assertEqual(model["trainable_parameter_count"], model["parameter_count"])
        self.assertEqual(model["float64_parameter_count"], 0)
        self.assertFalse(cpu["optimizer_step_performed"])
        self.assertGreater(cpu["memory_after"]["process_lifetime_peak_working_set_bytes"], 0)
        for measurement in cpu["measurements"]:
            self.assertEqual(measurement["rain_logit_shape"], [1, 1, 100, 100])
            self.assertEqual(measurement["quantile_shape"], [1, 32, 100, 100])
            self.assertEqual(measurement["qlog_dtype"], "torch.float64")
            self.assertEqual(measurement["qphysical_dtype"], "torch.float64")
            self.assertEqual(measurement["conditional_pinball_dtype"], "torch.float64")
            self.assertTrue(measurement["outputs_finite"])
            self.assertTrue(measurement["loss_finite"])
            self.assertTrue(measurement["gradients_finite"])

    def test_real_io_eight_samples_every_worker_configuration(self):
        io = artifact("io_breakdown.json")
        rows = table("dataloader_io_benchmark.csv")
        self.assertEqual(io["sample_count"], 8)
        self.assertFalse(io["source_2025_read"])
        self.assertEqual([r["num_workers"] for r in io["worker_summaries"]], [0, 2, 4])
        for summary in io["worker_summaries"]:
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["samples_completed"], 8)
            self.assertEqual(summary["owned_temporary_copies_remaining"], {})
            selected = [r for r in rows if int(r["num_workers"]) == summary["num_workers"]]
            self.assertEqual(len(selected), 8)
            self.assertTrue(all(r["status"] == "PASS" and r["cleanup_success"] == "True" for r in selected))
        self.assertEqual(io["measured_bottleneck"], "CPU_COMPUTE_BOUND")

    def test_estimates_are_explicitly_component_arithmetic(self):
        cpu, io = artifact("cpu_benchmark.json"), artifact("io_breakdown.json")
        rows = table("epoch_time_estimates.csv")
        self.assertEqual([int(r["epochs_illustrative_only"]) for r in rows], [1, 10, 30, 50])
        for row in rows:
            self.assertEqual(row["status"], "ENGINEERING_ESTIMATE_ONLY")
            self.assertEqual(int(row["steps_per_epoch"]), math.ceil(11720 / int(row["physical_batch"])))
            expected = 11720 * int(row["epochs_illustrative_only"]) * (
                cpu["mean_total_step_seconds"] + io["mean_end_to_end_sample_io_seconds"])
            self.assertAlmostEqual(float(row["serial_measured_components_seconds"]), expected, places=5)

    def test_recommendation_is_not_formal_training_authority(self):
        rec = artifact("engineering_recommendation.json")
        self.assertEqual(rec["status"], "ENGINEERING_RECOMMENDATION_ONLY")
        self.assertFalse(rec["TRAINING_ENVIRONMENT_READY"])
        self.assertTrue(rec["CUDA_ENVIRONMENT_ACTION_REQUIRED"])
        self.assertEqual(rec["MAX_TESTED_SAFE_BATCH"], "NOT_AVAILABLE")
        self.assertEqual(rec["AMP_FEASIBLE"], "NOT_TESTED")
        self.assertFalse(rec["B0_FORMAL_TRAINING_STARTED"])
        self.assertFalse(rec["FORMAL_TRAINING_AUTHORIZED"])
        for row in table("gradient_accumulation_candidates.csv"):
            self.assertEqual(row["gpu_feasibility"], "NOT_ASSESSED_CUDA_UNAVAILABLE")
            self.assertEqual(row["formal_effective_batch_frozen"], "False")

    def test_prior_evidence_and_contract_not_overwritten(self):
        prior = REPO_ROOT / "docs/b0_pretraining_closure/runs/run_20260930T095416Z"
        manifest = json.loads((prior / "manifest.json").read_text(encoding="utf-8"))
        for name in ("normalization_phaseA_sample_manifest.csv", "formal_sample_eligibility_2023_2024.csv"):
            self.assertEqual(sha256(prior / name), manifest["public_files_sha256"][name])
        self.assertEqual(sha256(REPO_ROOT / "config/science_contract_v1.1.yaml"),
                         "14209321d82107f58df96f234485cc56a806971cb62e8b9804ce4d25d05756c3")


if __name__ == "__main__":
    unittest.main()
