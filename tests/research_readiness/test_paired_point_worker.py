"""Synthetic worker wiring checks without scientific inputs or torch imports."""

import copy
from contextlib import contextmanager, nullcontext
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from tools.research_readiness import paired_point_worker as worker


@contextmanager
def workspace_directory():
    base = (Path(__file__).resolve().parents[2] / "docs/research_readiness/.local/paired_point_worker_test_tmp").resolve()
    base.mkdir(parents=True, exist_ok=True)
    folder = (base / uuid.uuid4().hex).resolve()
    if folder.parent != base:
        raise ValueError("Synthetic fixture must remain inside its workspace root")
    folder.mkdir()
    try:
        yield str(folder)
    finally:
        if folder.resolve().parent != base or len(folder.name) != 32:
            raise ValueError("Refusing cleanup outside the synthetic fixture root")
        shutil.rmtree(folder)


class TensorStub:
    def detach(self):
        return self

    def cpu(self):
        return self

    def double(self):
        return self

    def numpy(self):
        return "SYNTHETIC_ARRAY_STUB"


def fixture(folder):
    ids = tuple(f"2024-synthetic-{i:04d}" for i in range(963))
    summary = dict(scenes=963, n_valid=3303090, n_rain=407820,
                   brier=.1, auroc=.8, average_precision=.6, conditional_pinball=.2,
                   covered=[380000], coverage=[.93])
    reference = dict(scope="2024_DEVELOPMENT_FIXED_F006_RETROSPECTIVE",
                     source_identity={"population": "synthetic", "population_sha256": "d" * 64},
                     population_ids_sha256="synthetic-ids", partition_sha256="synthetic-partition",
                     groups={"all": dict(ids_sha="synthetic-ids", complete=True, summary=summary)})
    prepared = dict(private_inputs=dict(stage3_run="metadata-stage3", request="metadata-request"),
                    roles={"Development": dict(file_count=7950, bytes_per_pass=26639253112)})
    static = folder / "synthetic_static.bin"
    static.write_bytes(b"s" * 312828)
    checkpoint = folder / "synthetic_checkpoint.bin"
    checkpoint.write_bytes(b"synthetic trusted archive")
    state = dict(seed_calls=[], forwards=[], evaluation=[], accumulator=[], load_calls=[],
                 strict_load=[], closed=[], to_device=[], metadata_reads=[], grad_modes=[], joint=[])
    report = copy.deepcopy(reference)
    totals = dict(opened_files=7950, delivered_bytes=26639253112,
                  reserved_bytes=26639253112, states={"READ_COMPLETE": 7950})
    model = SimpleNamespace()
    model.load_state_dict = lambda payload, strict: state["strict_load"].append((payload, strict))
    model.to = lambda device: state["to_device"].append(device) or model
    model.eval = lambda: model

    class Plan:
        def __init__(self, run, request, root):
            self.identity = reference["source_identity"]
            self.rows = {"Development": {sid: {"analysis_time": "2024-01-01T00:00:00Z"} for sid in ids}}
            self.strong_scene_ids = ()

        def ids(self, role):
            assert role == "Development"
            return ids

    class Reader:
        def __init__(self):
            self.reader = SimpleNamespace(meter=SimpleNamespace(totals=lambda: totals))

        def batch(self, role, members):
            assert role == "Development"
            batch = SimpleNamespace(ids=members, analyses=tuple("2024-01-01T00:00:00Z" for _ in members),
                                    rate=TensorStub(), valid=TensorStub(), region=TensorStub())
            batch.to = lambda device: batch
            return batch

        def close(self):
            state["closed"].append("reader")

    class ReaderFactory:
        def __init__(self, plan, prepared, decision, allowed_models, dynamic_transform):
            assert allowed_models == ("B7",)

        def __call__(self, role, epoch, members, path):
            assert (role, epoch, members, path.name) == (
                "Development", 9, ids, "B7_development_09_reads",
            )
            return Reader()

    class Evaluation:
        def __init__(self, members, analyses, identity, path, strong_scene_ids):
            assert members == ids and len(analyses) == 963

        def add(self, output, batch):
            state["evaluation"].append((output, batch.ids))

        def finish(self):
            return report

        def close(self):
            state["closed"].append("evaluator")

    class Accumulator:
        def __init__(self, members, *, expected_n_valid, expected_n_rain):
            assert members == ids
            assert expected_n_valid == 3303090 and expected_n_rain == 407820

        def add(self, members, *arrays):
            assert len(arrays) == 5
            state["accumulator"].append(members)

        def finish(self):
            assert tuple(sid for batch in state["accumulator"] for sid in batch) == ids
            return {"scope": "SYNTHETIC_POINT_METRICS"}

    class JointAccumulator:
        def __init__(self, members, analyses, **kwargs):
            assert members == ids and len(analyses) == 963
            assert kwargs["expected_strong"] == 717

        def add(self, members, analyses, *arrays):
            assert len(analyses) == len(members) and len(arrays) == 5
            state["joint"].append(members)

        def finish(self, **kwargs):
            assert tuple(sid for batch in state["joint"] for sid in batch) == ids
            return {"scope": "SYNTHETIC_JOINT_METRICS"}

    def forward(model, batch):
        state["forwards"].append(batch.ids)
        prediction = SimpleNamespace(rain_prob=TensorStub(), conditional_quantiles_log=TensorStub())
        return prediction, "SYNTHETIC_LOSS"

    def load(path, **kwargs):
        state["load_calls"].append((path, kwargs))
        return {"model": {"synthetic_state": 1}, "optimizer": "UNUSED_SYNTHETIC_STATE"}

    metadata = {"report": reference, "preparation": {"prepared": prepared},
                "static_receipt": {"scalers": {"B6": "synthetic"}}}

    def read_metadata(path):
        state["metadata_reads"].append(path)
        return metadata[path]

    class OptimizerStub:
        pass

    identity = dict(torch_version="synthetic-torch", cuda_build="synthetic-cuda",
                    numpy_version="synthetic-numpy", gpu_name="synthetic-gpu", gpu_total_bytes=12345)
    runtime = SimpleNamespace(
        torch=SimpleNamespace(set_num_threads=lambda n: None, load=load,
                              no_grad=nullcontext, autocast=lambda *a, **kw: nullcontext(), bfloat16="bf16",
                              set_grad_enabled=lambda enabled: state["grad_modes"].append(enabled),
                              optim=SimpleNamespace(Optimizer=OptimizerStub),
                              __version__=identity["torch_version"],
                              version=SimpleNamespace(cuda=identity["cuda_build"]),
                              cuda=SimpleNamespace(
                                  get_device_name=lambda index: identity["gpu_name"],
                                  get_device_properties=lambda index: SimpleNamespace(total_memory=12345))),
        np=SimpleNamespace(__version__=identity["numpy_version"]),
        seed_all=lambda seed: state["seed_calls"].append(seed), read=read_metadata,
        unpack=lambda raw, kind, receipt: "SYNTHETIC_PACK", PopulationPlan=Plan,
        digest=lambda members: "synthetic-ids", PhysicalDote=lambda *a: "SYNTHETIC_TRANSFORM",
        DoteDefinition=lambda **kw: kw,
        model_factory=lambda *a, **kw: lambda seed, root: {"B7": model},
        ReaderFactory=ReaderFactory, Evaluation=Evaluation,
        PointMetricAccumulator=Accumulator, StrongJointAccumulator=JointAccumulator, forward=forward,
    )
    private = dict(tasks={"CONTROL_E0": dict(checkpoint_path=str(checkpoint), dev_report_path="report")},
                   preparation_path="preparation", static_source=str(static), static_receipt="static_receipt")
    proposal = dict(models=[dict(task="CONTROL_E0", model="B7", seed=2029,
                                checkpoint_bytes=checkpoint.stat().st_size,
                                checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())],
                    expected_summaries={"CONTROL_E0": summary}, static_sha256=hashlib.sha256(static.read_bytes()).hexdigest(),
                    runtime=dict(identity, python_version="controller-bound", executable_sha256="controller-bound"),
                    data_identity=reference["source_identity"],
                    scientific_choices=dict(DOTE={"synthetic": True}, modulation_limit=.1))
    return runtime, proposal, private, state, report, totals


class WorkerTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        temporary_directory = patch.object(tempfile, "tempdir", tempfile.tempdir)
        temporary_directory.start()
        self.addCleanup(temporary_directory.stop)

    def test_runtime_initialization_rebinds_cached_temp_and_inductor_paths(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            tempfile.tempdir = "SYNTHETIC_OUTSIDE_OUTPUT"
            with patch.object(worker, "_runtime", return_value=runtime):
                actual, identity = worker._initialize_runtime(folder, proposal["runtime"])
            self.assertIs(actual, runtime)
            self.assertEqual(Path(tempfile.gettempdir()), folder / "runtime")
            for name in ("TMPDIR", "TEMP", "TMP"):
                self.assertEqual(Path(os.environ[name]), folder / "runtime")
            self.assertEqual(Path(os.environ["TORCHINDUCTOR_CACHE_DIR"]), folder / "runtime/torchinductor")
            self.assertEqual(state["seed_calls"], [2029])
            self.assertEqual(state["grad_modes"], [False])

    def test_one_forward_feeds_both_accumulators(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            with patch.object(worker, "_runtime", return_value=runtime):
                result = worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["forward_calls"], 121)
            self.assertEqual(len(state["forwards"]), len(state["evaluation"]))
            self.assertEqual(state["forwards"], state["accumulator"])
            self.assertEqual(state["forwards"], state["joint"])
            self.assertEqual(len(state["load_calls"]), 1)
            self.assertEqual(state["load_calls"][0][1], dict(map_location="cpu", weights_only=False))
            self.assertEqual(state["strict_load"], [({"synthetic_state": 1}, True)])
            self.assertEqual(state["closed"], ["evaluator", "reader"])
            self.assertTrue((folder / "output/task_result.json").is_file())
            self.assertEqual(result["optimizer_updates"], 0)
            self.assertEqual(state["grad_modes"], [False])
            with self.assertRaisesRegex(PermissionError, "optimizer construction"):
                runtime.torch.optim.Optimizer()

    def test_runtime_mismatch_precedes_all_input_reads(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            proposal["runtime"]["gpu_total_bytes"] += 1
            with patch.object(worker, "_runtime", return_value=runtime):
                with patch.object(Path, "read_bytes", side_effect=AssertionError("Payload read before runtime gate")):
                    with self.assertRaisesRegex(ValueError, "runtime identity"):
                        worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertEqual(state["metadata_reads"], [])
            self.assertEqual(state["load_calls"], [])
            self.assertEqual(state["forwards"], [])

    def test_runtime_library_and_gpu_fields_all_bound(self):
        with workspace_directory() as temporary:
            runtime, proposal, private, state, report, totals = fixture(Path(temporary))
            expected = proposal["runtime"]
            self.assertEqual(worker._validate_runtime(runtime, expected),
                             {key: expected[key] for key in ("torch_version", "cuda_build", "numpy_version",
                                                            "gpu_name", "gpu_total_bytes")})
            for field in ("torch_version", "cuda_build", "numpy_version", "gpu_name", "gpu_total_bytes"):
                with self.subTest(field=field):
                    changed = dict(expected)
                    changed[field] = "different"
                    with self.assertRaisesRegex(ValueError, "runtime identity"):
                        worker._validate_runtime(runtime, changed)

    def test_bad_checkpoint_stops_before_forward(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            proposal["models"][0]["checkpoint_sha256"] = "0" * 64
            with patch.object(worker, "_runtime", return_value=runtime):
                with self.assertRaisesRegex(ValueError, "checkpoint identity"):
                    worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertEqual(state["load_calls"], [])
            self.assertEqual(state["forwards"], [])

    def test_frozen_gate_failure_preserves_no_completion(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            report["groups"]["all"]["summary"]["brier"] += .01
            with patch.object(worker, "_runtime", return_value=runtime):
                with self.assertRaisesRegex(ValueError, "frozen metric"):
                    worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertFalse((folder / "output/task_result.json").exists())
            self.assertEqual(state["closed"], ["evaluator", "reader"])

    def test_read_meter_failure_stops_completion(self):
        with workspace_directory() as temporary:
            folder = Path(temporary)
            runtime, proposal, private, state, report, totals = fixture(folder)
            totals["delivered_bytes"] -= 1
            with patch.object(worker, "_runtime", return_value=runtime):
                with self.assertRaisesRegex(RuntimeError, "accounting"):
                    worker.run_task(folder, proposal, private, "CONTROL_E0", folder / "output", lambda: None)
            self.assertFalse((folder / "output/task_result.json").exists())

    def test_report_identity_rejects_partition_change(self):
        report = dict(scope="synthetic", source_identity={}, population_ids_sha256="p", partition_sha256="a", groups={})
        changed = dict(report, partition_sha256="b")
        with self.assertRaisesRegex(ValueError, "partition_sha256"):
            worker._gate_report(changed, report)


if __name__ == "__main__":
    unittest.main()
