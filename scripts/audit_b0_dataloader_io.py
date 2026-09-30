"""Eight real final-eligible 2023 samples with isolated staging per Windows worker."""
import argparse
import csv
from dataclasses import replace
import json
from pathlib import Path
import statistics
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, get_worker_info

from yuntapr.contracts.loader import REPO_ROOT, load_contract, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.himawari_b13 import read_b13_local
from yuntapr.data.imerg_v07 import read_imerg_local
from yuntapr.data.masks import read_frozen_yunnan_mask
from yuntapr.data.normalization import PhaseANormalizer
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.data.staging import BoundedEnglishStaging
from yuntapr.spatial.sp04_mapping import load_sp04
from fit_phase_a_v1_1 import HROOT, MASK, PRIOR as DEVELOPMENT_PRIOR

PRIOR = REPO_ROOT / "docs/b0_pretraining_closure/runs/run_20260930T095416Z"


class MeasuredReader:
    def __init__(self, staging, mapping, kind):
        self.staging, self.mapping, self.kind = staging, mapping, kind
        self.last = None

    def __call__(self, source, index_or_nominal):
        began = time.perf_counter()
        profile = {}
        with self.staging.local(source) as english:
            if self.kind == "b13":
                data, valid, frame = read_b13_local(english, self.mapping, index_or_nominal, profile=profile)
            else:
                data, valid, frame = read_imerg_local(english, index_or_nominal, self.mapping, profile=profile)
        record = self.staging.records[-1]
        self.last = {"copy_seconds": record.copy_seconds,
                     "read_and_reader_qc_seconds": record.read_seconds,
                     "netcdf_open_seconds": profile["netcdf_open_seconds"],
                     "netcdf_read_seconds": profile["netcdf_read_seconds"],
                     "reader_qc_seconds": profile["reader_qc_seconds"],
                     "integrity_and_cleanup_seconds": max(0.,time.perf_counter()-began-record.copy_seconds-record.read_seconds),
                     "total_reader_seconds": time.perf_counter()-began,
                     "temporary_bytes": record.temporary_bytes,
                     "source_sha256": record.source_sha256,
                     "sha256_match": record.sha256_match,
                     "cleanup_success": record.cleanup_success,
                     "owned_copy_count_after": len(self.staging._owned)}
        return (data, valid, replace(frame, path=source)) if self.kind == "b13" else (data, valid, frame)


class MeasuredNormalizer:
    def __init__(self, normalizer):
        self.base = normalizer
        self.version, self.mu, self.sigma, self.artifact_sha256 = (
            normalizer.version, normalizer.mu, normalizer.sigma, normalizer.artifact_sha256)
        self.last_seconds = None

    def transform(self, raw, valid, start):
        began = time.perf_counter()
        result = self.base.transform(raw, valid, start)
        self.last_seconds = time.perf_counter()-began
        return result


class AuditDataset(Dataset):
    def __init__(self, records, expected_hashes, mapping, yunnan, base_staging, max_bytes):
        self.records = records
        self.expected_hashes = expected_hashes
        self.mapping, self.yunnan = mapping, yunnan
        self.base_staging, self.max_bytes = base_staging, max_bytes
        self.normalizer = MeasuredNormalizer(PhaseANormalizer.from_pinned())
        self.set_staging("main")

    def set_staging(self, suffix):
        root = self.base_staging / suffix
        self.staging = BoundedEnglishStaging(root, self.max_bytes, True, True)
        self.b13 = MeasuredReader(self.staging, self.mapping, "b13")
        self.imerg = MeasuredReader(self.staging, self.mapping, "imerg")
        self.dataset = B0Dataset(self.records, self.mapping, self.yunnan, self.b13, self.imerg,
                                 frozen_mask_path=MASK, formal_supervised=True,
                                 normalizer=self.normalizer)

    def __len__(self):
        return len(self.records)

    def __getitem__(self, index):
        began = time.perf_counter()
        sample = self.dataset[index]
        dataset_seconds = time.perf_counter()-began
        b13, imerg = self.b13.last, self.imerg.last
        expected = self.expected_hashes[index]
        if (b13["source_sha256"] != expected["b13"] or imerg["source_sha256"] != expected["imerg"]
                or not b13["sha256_match"] or not imerg["sha256_match"]
                or not b13["cleanup_success"] or not imerg["cleanup_success"]
                or b13["owned_copy_count_after"] or imerg["owned_copy_count_after"]):
            raise ValueError("Read-only source hash, staging SHA, or cleanup changed")
        tensor_started = time.perf_counter()
        tensor_x = torch.from_numpy(np.array(sample.x_b13_normalized, copy=True))
        tensor_y = torch.from_numpy(np.array(sample.y_imerg, copy=True))
        tensor_seconds = time.perf_counter()-tensor_started
        if (tensor_x.shape != (501,501) or tensor_y.shape != (100,100)
                or not sample.formal_supervised_qc_pass or not sample.b13_full_valid
                or sample.used_older_causal_frame or not torch.isfinite(tensor_x).all()):
            raise ValueError("Formal real I/O sample contract failed")
        normal_seconds = self.normalizer.last_seconds
        assembly_seconds = max(0., dataset_seconds-b13["total_reader_seconds"]-imerg["total_reader_seconds"]-normal_seconds)
        return {"sample_id": sample.sample_id, "year": sample.imerg_window_start.year,
                "worker_id": get_worker_info().id if get_worker_info() else "main",
                "stage_root": str(self.staging.root), "status": "PASS",
                "b13_copy_seconds": b13["copy_seconds"], "b13_netcdf_open_seconds": b13["netcdf_open_seconds"],
                "b13_netcdf_read_seconds": b13["netcdf_read_seconds"],
                "b13_reader_qc_seconds": b13["reader_qc_seconds"],
                "b13_sha_cleanup_seconds": b13["integrity_and_cleanup_seconds"],
                "b13_temporary_bytes": b13["temporary_bytes"],
                "imerg_copy_seconds": imerg["copy_seconds"], "imerg_netcdf_open_seconds": imerg["netcdf_open_seconds"],
                "imerg_netcdf_read_seconds": imerg["netcdf_read_seconds"],
                "imerg_reader_qc_seconds": imerg["reader_qc_seconds"],
                "imerg_sha_cleanup_seconds": imerg["integrity_and_cleanup_seconds"],
                "imerg_temporary_bytes": imerg["temporary_bytes"],
                "normalization_seconds": normal_seconds, "formal_assembly_qc_seconds": assembly_seconds,
                "tensor_conversion_seconds": tensor_seconds,
                "sample_elapsed_seconds": time.perf_counter()-began,
                "b13_sha256_match": True, "imerg_sha256_match": True, "cleanup_success": True,
                "valid_yunnan_pixel_count": int((sample.imerg_valid_mask & sample.yunnan_eval_mask).sum())}


def isolate_worker(worker_id):
    dataset = get_worker_info().dataset
    torch.set_num_threads(1)
    dataset.set_staging(f"workers_{dataset.worker_count}_worker_{worker_id}")


def single_collate(items):
    return items[0]


def load_candidates():
    development = json.loads((PRIOR/"manifest.json").read_text(encoding="utf-8"))
    files = ("normalization_phaseA_sample_manifest.csv", "formal_sample_eligibility_2023_2024.csv",
             "imerg_development_revalidation.json")
    for name in files:
        if sha256(PRIOR/name) != development["public_files_sha256"][name]:
            raise ValueError("Frozen Development evidence changed: "+name)
    local = development["prior_development_manifest_sha256"]
    prior_manifest_path = DEVELOPMENT_PRIOR/"manifest.json"
    if sha256(prior_manifest_path) != local:
        raise ValueError("Historical B13 QC evidence manifest changed")
    prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
    frame_info = prior_manifest["local_evidence"]["b13_per_frame.csv"]
    frame_path = Path(frame_info["local_path"])
    if sha256(frame_path) != frame_info["sha256"]:
        raise ValueError("Historical B13 per-frame evidence changed")
    with frame_path.open(encoding="utf-8", newline="") as stream:
        frame_by_rel = {r["relative_path"]: r for r in csv.DictReader(stream) if r["relative_path"]}
    with (PRIOR/files[0]).open(encoding="utf-8",newline="") as stream:
        eligible = list(csv.DictReader(stream))
    with (PRIOR/files[1]).open(encoding="utf-8",newline="") as stream:
        pairs = {r["window_start"]: r for r in csv.DictReader(stream)
                 if r["month"].startswith("2023") and r["formal_supervised_eligible"] == "True"}
    verified_days = json.loads((PRIOR/files[2]).read_text(encoding="utf-8"))["days"]
    day_hash = {r["day_path"]: r["sha256"] for r in verified_days}
    indices = np.linspace(0,len(eligible)-1,8,dtype=np.int64)
    records, hashes, selected = [],[],[]
    for index in indices:
        row = eligible[int(index)]
        pair = pairs[row["window_start"]]
        frame_row = frame_by_rel[row["b13_relative_path"]]
        frame = HimawariFrame(HROOT/row["b13_relative_path"], utc(frame_row["nominal"]),
                              utc(frame_row["obs_start"]), utc(frame_row["obs_end"]), utc(frame_row["date_created"]))
        target = Path(pair["imerg_day_path"])
        record = B0Record(row["sample_id"], utc(row["window_start"]), (frame,), target,
                          int(pair["imerg_index"]), "IMERG", "V07", "Final", True)
        records.append(record)
        hashes.append({"b13":row["source_sha256"],"imerg":day_hash[str(target)]})
        selected.append({"sample_id":row["sample_id"],"source_relative_path":row["b13_relative_path"],
                         "b13_sha256":row["source_sha256"],"imerg_day_path":str(target),
                         "imerg_sha256":day_hash[str(target)]})
    return records,hashes,selected


def write_csv(path, rows):
    if path.exists():
        raise FileExistsError("Versioned DataLoader evidence cannot be overwritten")
    fields = sorted({k for row in rows for k in row})
    with path.open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n")
        writer.writeheader();writer.writerows(rows)


def run(out):
    _, cfg=load_contract()
    records, hashes, selected=load_candidates()
    mapping=load_sp04()
    yunnan=read_frozen_yunnan_mask(MASK,mapping)
    base=Path(r"F:\pytorch\Research\stage0_himawari\cache\staging")/f"audit_{out.name}"
    all_rows, summaries=[],[]
    for workers in (0,2,4):
        dataset=AuditDataset(records,hashes,mapping,yunnan,base,cfg["staging"]["max_temporary_bytes"])
        dataset.worker_count=workers
        start=time.perf_counter()
        rows=[]
        error=None
        try:
            loader=DataLoader(dataset,batch_size=1,shuffle=False,num_workers=workers,
                              collate_fn=single_collate,worker_init_fn=isolate_worker if workers else None,
                              pin_memory=False,persistent_workers=False)
            for result in loader:
                rows.append({"num_workers":workers,**result})
        except Exception as exc:
            error=repr(exc)[:2500]
        elapsed=time.perf_counter()-start
        roots = [base/"main"]+[base/f"workers_{workers}_worker_{i}" for i in range(workers)]
        leftovers = {str(root): [p.name for p in root.glob("yuntapr_b0_*.nc")] for root in roots if root.exists()}
        leaks = {k:v for k,v in leftovers.items() if v}
        if leaks:
            error = (error or "")+" OWNED_STAGING_COPY_REMAINED="+repr(leaks)
        status="PASS" if not error and len(rows)==len(records) and all(r["cleanup_success"] for r in rows) else "ERROR"
        summaries.append({"num_workers":workers,"status":status,"samples_completed":len(rows),
                          "samples_expected":len(records),"total_wall_seconds_including_spawn":elapsed,
                          "samples_per_second_including_spawn":len(rows)/elapsed if elapsed else None,
                          "per_worker_independent_staging":workers>0,
                          "one_owned_copy_at_a_time_per_staging_root":status=="PASS",
                          "owned_temporary_copies_remaining":leaks,"error":error})
        if error:
            all_rows.append({"num_workers":workers,"status":"ERROR","error":error})
        all_rows.extend(rows)
        print(json.dumps(summaries[-1]),flush=True)
    write_csv(out/"dataloader_io_benchmark.csv",all_rows)
    zero=[r for r in all_rows if r.get("num_workers")==0 and r.get("status")=="PASS"]
    if len(zero)!=8:
        raise ValueError("Eight real single-worker samples required for I/O breakdown")
    def avg(name):
        return statistics.mean(float(r[name]) for r in zero)
    cpu=json.loads((out/"cpu_benchmark.json").read_text(encoding="utf-8"))
    io_wall=avg("sample_elapsed_seconds")
    cpu_time=cpu["mean_total_step_seconds"]
    bottleneck="CPU_COMPUTE_BOUND" if cpu_time>=2*io_wall else "IO_BOUND" if io_wall>=2*cpu_time else "MIXED"
    breakdown={"sample_count":8,"population":"Eight hash-verified 2023 final-eligible Train samples",
               "source_2025_read":False,"worker_summaries":summaries,
               "mean_b13_copy_seconds":avg("b13_copy_seconds"),
               "mean_b13_netcdf_open_seconds":avg("b13_netcdf_open_seconds"),
               "mean_b13_netcdf_read_seconds":avg("b13_netcdf_read_seconds"),
               "mean_b13_reader_qc_seconds":avg("b13_reader_qc_seconds"),
               "mean_b13_sha_cleanup_seconds":avg("b13_sha_cleanup_seconds"),
               "mean_imerg_copy_seconds":avg("imerg_copy_seconds"),
               "mean_imerg_netcdf_open_seconds":avg("imerg_netcdf_open_seconds"),
               "mean_imerg_netcdf_read_seconds":avg("imerg_netcdf_read_seconds"),
               "mean_imerg_reader_qc_seconds":avg("imerg_reader_qc_seconds"),
               "mean_imerg_sha_cleanup_seconds":avg("imerg_sha_cleanup_seconds"),
               "mean_formal_assembly_qc_seconds":avg("formal_assembly_qc_seconds"),
               "mean_normalization_seconds":avg("normalization_seconds"),
               "mean_tensor_conversion_seconds":avg("tensor_conversion_seconds"),
               "mean_end_to_end_sample_io_seconds":io_wall,
               "mean_cpu_forward_seconds":cpu["mean_forward_seconds"],
               "mean_cpu_backward_seconds":cpu["mean_backward_seconds"],
               "mean_cpu_forward_loss_backward_seconds":cpu_time,
               "compute_to_io_ratio":cpu_time/io_wall,"measured_bottleneck":bottleneck,
               "source_read_strategy":"Production netCDF readers with optional timing hooks; SHA-verified per-file English staging; real formal QC/normalization",
               "timing_note":"Reader netCDF open/read excludes separately timed decode/axis QC; SHA/check/cleanup separately estimated from staging wall time. Formal assembly includes support mapping and metadata checks.",
               "selected_samples":selected,
               "DATALOADER_IO_READY":summaries[0]["status"]=="PASS",
               "per_worker_staging_is_experimental_only":True,
               "formal_dataloader_refactored":False}
    path=out/"io_breakdown.json"
    if path.exists():
        raise FileExistsError("Versioned I/O breakdown cannot be overwritten")
    path.write_text(json.dumps(breakdown,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-dir",type=Path,required=True)
    run(parser.parse_args().run_dir)
