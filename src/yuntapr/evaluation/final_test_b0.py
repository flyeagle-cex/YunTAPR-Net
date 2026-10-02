"""Frozen B0 Final Test semantics; this release grants preflight permission only.

Existing 2024 diagnostics and full-population numerical arithmetic are inherited
without editing their implementation. New time and authority guards run before I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import sys
from types import SimpleNamespace

import numpy as np
import torch
import yaml

from yuntapr.contracts.loader import REPO_ROOT, sha256
from yuntapr.data.dataset_b0 import B0Dataset, B0Record
from yuntapr.data.formal_policy import require_full_valid
from yuntapr.data.sample_schema import utc
from yuntapr.data.staging import BoundedEnglishStaging, StagedB13Reader, StagedIMERGReader
from yuntapr.models.b0 import B0Model
from yuntapr.training import formal_phase_b as inherited_finalfit
from yuntapr.training.phase_a_protocol import state_digest
from yuntapr.training.phase_a_validation import GlobalValidationAccumulator
from yuntapr.training.phase_b_preparation import PhaseBNormalizer
from yuntapr.training.scientific_review import (
    InferenceOnlyGuard, ReviewAccumulator, TAU, diagnostic_rules, probability_summary,
)

BASELINE = "ddbb69ccca6c806973a89a91127ea02c9af42afd"
PROTOCOL_PATH = Path("config/evaluation/b0_2025_final_test_protocol_v1.yaml")
PROTOCOL_SHA = "6d08def2602dda3d931937c68cadeae86b5c16b60f9f7132c9e134b962cdbe3b"
FINAL_PATH = Path(r"F:\pytorch\Research\outputs\formal_training\b0_phase_b_finalfit\run_20261002T035929_487644Z\epoch_011.pt")
FINAL_SHA = "05359d2fee2ae61daf654ae5a59b7977cb65247fd46d97a69a690a0133da7f65"
NORMALIZATION_SHA = "c7042beac2412594ca9fc264d7df10981755b393158c539cb48c9b56cd314327"
MU, SIGMA = 270.5900486586461, 20.368583874067266
HROOT = PureWindowsPath(r"H:\葵花202303_202510")
IROOT = PureWindowsPath(r"F:\云南极端降水数据\raw\IMERG")
START = datetime(2025, 3, 1, tzinfo=timezone.utc)
END = datetime(2025, 10, 1, tzinfo=timezone.utc)
SCOPE = "B0_2025_MAR_SEP_FINAL_TEST_ONLY"
PREFLIGHT_SCOPE = "SYNTHETIC_OR_HISTORICAL_FIXTURE_PREFLIGHT_ONLY"
PRIMARY = ["global_core_loss", "occurrence_loss", "quantile_loss", "Brier", "AUROC", "Average_Precision",
    "conditional_mean_pinball", "per_tau_pinball", "32_tau_conditional_coverage", "coverage_error",
    "crossing_count", "nonfinite_count", "support_violation_count"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_protocol(root=REPO_ROOT):
    root = Path(root)
    path = root / PROTOCOL_PATH
    if sha256(path) != PROTOCOL_SHA:
        raise ValueError("Frozen Final Test protocol SHA mismatch")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (value["FINAL_TEST_2025_AUTHORIZED"] is not False or value["FINAL_TEST_2025_EXECUTED"] is not False
            or value["baseline_commit"] != BASELINE or value["primary_metrics"] != PRIMARY
            or value["population"]["months"] != list(range(3, 10))
            or value["inherited_diagnostics"] != diagnostic_rules()
            or value["FINAL"]["sha256"] != FINAL_SHA
            or value["FINAL"]["absolute_local_path"] != str(FINAL_PATH)
            or (value["normalization"]["mean_K"], value["normalization"]["std_K"], value["normalization"]["sha256"])
                != (MU, SIGMA, NORMALIZATION_SHA)):
        raise ValueError("Frozen Final Test semantics changed")
    for identity in value["identity"].values():
        if sha256(root / identity["path"]) != identity["sha256"]:
            raise ValueError("Protocol-bound historical provenance changed: " + identity["path"])
    if sha256(root / value["normalization"]["path"]) != NORMALIZATION_SHA:
        raise ValueError("Phase-B normalization file identity changed")
    return value


def guard_time(value):
    t = utc(value)
    if not START <= t < END:
        raise ValueError("2025 March-September only; October rejected before source I/O")
    if t.minute not in (0, 30) or t.second or t.microsecond:
        raise ValueError("Final Test requires exact half-hour window starts")
    return t


def guard_source_paths(row):
    """Pure Windows path checks: no exists/stat/open calls, including rejected paths."""
    t = guard_time(row["window_start"])
    relative = PureWindowsPath(row["b13_relative_path"])
    imerg = PureWindowsPath(row["imerg_day_path"])
    if relative.is_absolute() or relative.drive or ".." in relative.parts or ".." in imerg.parts:
        raise ValueError("Source path traversal or alternate source is prohibited")
    nominal = t + timedelta(minutes=20)
    if (len(relative.parts) != 3 or relative.parts[:2] != (nominal.strftime("%Y%m"), nominal.strftime("%d"))
            or "_"+nominal.strftime("%Y%m%d_%H%M")+"_" not in relative.name
            or relative.suffix.lower() != ".nc"
            or imerg.parent != IROOT / "2025" or imerg.name != "imerg_"+t.strftime("%Y%m%d")+".nc"):
        raise ValueError("Source time/root identity changed; October and alternate sources prohibited")
    return Path(str(HROOT / relative)), Path(str(imerg))


def flag(value):
    if value is True or value == "True": return True
    if value is False or value == "False": return False
    raise ValueError("Explicit True/False metadata required")


def eligibility(row):
    """Predeclared metadata criteria; never uses predicted values or rain prevalence."""
    t = guard_time(row["window_start"])
    guard_source_paths(row)
    if row["sample_id"] != t.isoformat() or utc(row["analysis_time"]) != t+timedelta(minutes=30):
        raise ValueError("Sample/time identity mismatch")
    if utc(row["expected_nominal"]) != t+timedelta(minutes=20):
        raise ValueError("Expected latest slot was changed")
    reasons = []
    if not flag(row["expected_latest_available"]): reasons.append("EXPECTED_LATEST_B13_MISSING_NO_FORMAL_FALLBACK")
    if not flag(row["b13_readable"]): reasons.append("B13_NOT_READABLE")
    if int(row["full_valid_native_pixels"]) != 251001 or not flag(row["b13_finite"]):
        reasons.append("B13_FULL_SCENE_REQUIRED")
    if not flag(row["b13_metadata_valid"]): reasons.append("B13_METADATA_INVALID")
    else:
        if (utc(row["selected_nominal"]) != t+timedelta(minutes=20)
                or utc(row["obs_start"]) > utc(row["obs_end"])
                or utc(row["obs_end"]) > utc(row["analysis_time"])):
            reasons.append("LATEST_CAUSAL_TIME_FAILED")
    if flag(row["used_older_causal_frame"]): reasons.append("OLDER_FALLBACK_PROHIBITED")
    if (row["imerg_product"], row["imerg_version"], row["imerg_run_type"]) != ("IMERG", "V07", "Final"):
        reasons.append("IMERG_V07_FINAL_REQUIRED")
    if not flag(row["imerg_time_grid_provenance_pass"]): reasons.append("IMERG_TIME_GRID_PROVENANCE_FAILED")
    count = int(row["imerg_valid_yunnan_count"])
    if not 0 <= count <= 3430: raise ValueError("Invalid frozen-Yunnan valid count")
    if count == 0: reasons.append("NO_VALID_YUNNAN_SUPERVISION")
    return reasons


def validate_population(rows):
    """Account for all scheduled windows before accepting a frozen eligible subset."""
    if len(rows) != 10272: raise ValueError("All 10272 scheduled candidate slots must be accounted for")
    eligible = []
    for index, row in enumerate(rows):
        if guard_time(row["window_start"]) != START+timedelta(minutes=30*index):
            raise ValueError("Missing, duplicate, reordered or out-of-period candidate slot")
        reasons = eligibility(row)
        if flag(row["eligible"]) != (not reasons) or row["rejection_reason"] != ";".join(reasons):
            raise ValueError("Candidate eligibility/rejection reason differs from frozen rules")
        if not reasons:
            if (not all(re.fullmatch("[0-9a-f]{64}", row[k]) for k in ("b13_sha256", "imerg_sha256"))
                    or int(row["b13_bytes"]) <= 0 or int(row["imerg_bytes"]) <= 0
                    or int(row["imerg_index"]) != index % 48
                    or not 0 <= int(row["imerg_rain_yunnan_count"]) <= int(row["imerg_valid_yunnan_count"])):
                raise ValueError("Eligible source identity/index/count schema failed")
            eligible.append(row)
    if not eligible: raise ValueError("No eligible Final Test population; no empty PASS")
    return eligible


def implementation_hashes(root=REPO_ROOT):
    """Verify the trained dependency snapshot, then separately pin new evaluation code.

    Adding this module does not redefine the historical training dependency list.
    """
    root = Path(root)
    p = yaml.safe_load((root/PROTOCOL_PATH).read_text(encoding="utf-8"))
    expected = read(root/p["identity"]["finalfit_run_manifest"]["path"])["checkpoint_expected"]["implementation_sha256"]
    result = {}
    for name, digest in expected.items():
        if sha256(root/name) != digest: raise ValueError("Trained implementation changed: "+name)
        result[name] = digest
    for name in ("src/yuntapr/evaluation/__init__.py", "src/yuntapr/evaluation/final_test_b0.py",
                 "scripts/test_b0_2025_final_v1.py"):
        result[name] = sha256(root/name)
    return result


@dataclass(frozen=True)
class FinalAuthorization:
    sha256: str
    value: dict

    @classmethod
    def load(cls, path, expected_sha, population_path):
        if path is None or not expected_sha:
            raise PermissionError("FINAL_TEST_2025_AUTHORIZED=false; separate researcher authorization required")
        path = Path(path)
        if sha256(path) != expected_sha: raise ValueError("Final Test authorization SHA mismatch")
        value = read(path)
        wanted = {"version":"v1", "AUTHORIZED_BY":"RESEARCHER", "scope":SCOPE,
            "FINAL_TEST_2025_AUTHORIZED":True, "protocol_sha256":PROTOCOL_SHA,
            "FINAL_sha256":FINAL_SHA, "normalization_sha256":NORMALIZATION_SHA,
            "implementation_sha256":implementation_hashes(), "population_manifest_sha256":sha256(Path(population_path))}
        if any(value.get(k) != v for k,v in wanted.items()):
            raise PermissionError("Final Test authorization scope/provenance mismatch")
        return cls(expected_sha, value)

    def require(self):
        if self.value.get("scope") != SCOPE or self.value.get("FINAL_TEST_2025_AUTHORIZED") is not True:
            raise PermissionError("Verified researcher Final Test authority required before source access")


class FinalInferenceGuard(InferenceOnlyGuard):
    def __enter__(self):
        super().__enter__()
        # Reject at the subclass constructor boundary too, before AdamW/SGD can
        # parse inputs or call their base initializer.
        for constructor in vars(torch.optim).values():
            if (isinstance(constructor,type) and issubclass(constructor,torch.optim.Optimizer)
                    and constructor is not torch.optim.Optimizer and "__init__" in constructor.__dict__):
                original_init=constructor.__init__
                def reject_constructor(*args,**kwargs):
                    self.attempts["optimizer_creation"]+=1
                    raise RuntimeError("Final Test prohibits optimizer_creation")
                self.saved.append((constructor,"__init__",original_init))
                constructor.__init__=reject_constructor
        self.attempts["training_mode"] = 0
        original = torch.nn.Module.train
        def guarded_train(module, mode=True):
            if mode:
                self.attempts["training_mode"] += 1
                raise RuntimeError("Final Test prohibits training mode")
            return original(module, mode)
        self.saved.append((torch.nn.Module,"train",original))
        torch.nn.Module.train = guarded_train
        return self


class RawSourceGuard:
    """Prevent Python opens and direct netCDF backend opens of prohibited sources."""
    def __init__(self, *, preflight=True):
        self.preflight = preflight
        self.enabled = False
        self.prohibited_attempts = []
        self.raw_open_events = 0

    def check(self, value, mode="r", flags=0):
        if not isinstance(value, (str,bytes,os.PathLike)): return
        path = PureWindowsPath(os.fsdecode(value))
        writing = any(c in str(mode or "") for c in "wax+") or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
        if path.is_relative_to(PureWindowsPath(r"F:\pytorch\Research\outputs\formal_training")):
            if writing or path!=PureWindowsPath(str(FINAL_PATH)):
                self.prohibited_attempts.append(str(path)); raise PermissionError("Only read-only frozen FINAL checkpoint access is permitted")
        for root in (HROOT,IROOT):
            if path.is_relative_to(root):
                parts = path.relative_to(root).parts
                allowed = bool(parts) and ((root == HROOT and len(parts)==3
                    and parts[0] in {f"2025{m:02d}" for m in range(3,10)}
                    and re.search(r"_"+re.escape(parts[0]+parts[1])+r"_\d{4}_",path.name) is not None)
                    or (root == IROOT and parts[0] == "2025" and re.fullmatch(r"imerg_20250[3-9]\d{2}\.nc",path.name)))
                if self.preflight or writing or not allowed:
                    self.prohibited_attempts.append(str(path)); raise PermissionError("Raw source access prohibited before I/O")
                self.raw_open_events += 1

    def __enter__(self):
        import netCDF4
        self.enabled = True
        def audit(event,args):
            if self.enabled and event == "open": self.check(args[0],args[1],args[2] if len(args)>2 else 0)
        sys.addaudithook(audit)
        self.nc_original = netCDF4.Dataset
        def checked_dataset(path,*args,**kwargs):
            self.check(path, args[0] if args else kwargs.get("mode","r"))
            return self.nc_original(path,*args,**kwargs)
        netCDF4.Dataset = checked_dataset
        return self

    def __exit__(self,*exc):
        import netCDF4
        self.enabled = False
        netCDF4.Dataset = self.nc_original


@dataclass(frozen=True)
class FinalTestNormalizer:
    version: str
    mu: float
    sigma: float
    artifact_sha256: str
    fixture: bool = False

    @classmethod
    def load(cls, protocol, *, fixture=False):
        original = PhaseBNormalizer.from_artifact(REPO_ROOT/protocol["normalization"]["path"], NORMALIZATION_SHA)
        if (original.mu,original.sigma) != (MU,SIGMA): raise ValueError("Frozen normalization constants changed")
        return cls(original.version,original.mu,original.sigma,original.artifact_sha256,fixture)

    def transform(self, raw, valid, start):
        if self.fixture:
            t=utc(start)
            if t.year not in (2023,2024): raise ValueError("Historical fixture scope only")
        else: guard_time(start)
        require_full_valid(raw,valid)
        normalized=((raw.astype(np.float64)-self.mu)/self.sigma).astype(np.float32)
        if not np.isfinite(normalized).all(): raise FloatingPointError("Nonfinite normalized input")
        return normalized


def verify_final(protocol):
    """Read-only file/schema/model-state verification; no optimizer is instantiated."""
    root=REPO_ROOT
    identity=read(root/protocol["identity"]["final_checkpoint_identity"]["path"])
    manifest=read(root/protocol["identity"]["finalfit_run_manifest"]["path"])
    if (identity["sha256"]!=FINAL_SHA or identity["absolute_local_path"]!=str(FINAL_PATH)
            or identity["epoch"]!=11 or identity["global_update"]!=128964):
        raise ValueError("FINAL identity is not the frozen epoch11")
    implementation_hashes(root)
    payload=inherited_finalfit.load_verified_checkpoint(identity,manifest["checkpoint_expected"])
    return payload, {"absolute_local_path":str(FINAL_PATH),"sha256":FINAL_SHA,"bytes":identity["bytes"],
        "epoch":11,"global_update":128964,"model_state_sha256":payload["model_state_dict_sha256"],
        "provenance_before_state_application":True,"optimizer_state_applied":False,"RNG_state_applied":False}


def load_inference_model(payload, device):
    model=B0Model().to(device)
    candidate=payload["model_state_dict"]
    current=model.state_dict()
    if candidate.keys()!=current.keys() or any(candidate[k].shape!=v.shape or candidate[k].dtype!=v.dtype for k,v in current.items()):
        raise ValueError("FINAL model shape/dtype schema mismatch before state application")
    model.load_state_dict(candidate,strict=True)
    model.requires_grad_(False); model.eval()
    if state_digest(model.state_dict())!=payload["model_state_dict_sha256"]:
        raise ValueError("Loaded FINAL state digest mismatch")
    return model


class FinalDataset:
    def __init__(self, rows, mapping, yunnan, mask_path, stage_root, protocol, authorization):
        authorization.require()
        for row in rows: guard_source_paths(row)
        self.rows,self.mapping,self.yunnan,self.mask_path=rows,mapping,yunnan,mask_path
        self.normalizer=FinalTestNormalizer.load(protocol)
        self.staging=BoundedEnglishStaging(Path(stage_root),734003200,True,True)
        self.reader=StagedB13Reader(self.staging,mapping)
        self.ireader=StagedIMERGReader(self.staging,mapping)

    def __len__(self): return len(self.rows)

    def __getitem__(self,index):
        row=self.rows[index]; h,i=guard_source_paths(row)
        before=len(self.staging.records)
        x,valid,observed=self.reader(h,utc(row["expected_nominal"]))
        if (observed.nominal_time!=utc(row["selected_nominal"]) or observed.obs_start!=utc(row["obs_start"])
                or observed.obs_end!=utc(row["obs_end"]) or observed.obs_end>utc(row["analysis_time"])
                or (observed.date_created.isoformat() if observed.date_created else "")!=row["date_created"]):
            raise ValueError("Frozen source timestamp identity changed")
        record=B0Record(row["sample_id"],utc(row["window_start"]),(observed,),i,int(row["imerg_index"]),"IMERG","V07","Final",True)
        def cached(path,nominal):
            if path!=h or nominal!=observed.nominal_time: raise ValueError("Unexpected cached source request")
            return x,valid,observed
        sample=B0Dataset([record],self.mapping,self.yunnan,cached,self.ireader,
            frozen_mask_path=self.mask_path,formal_supervised=True,normalizer=self.normalizer)[0]
        ops=self.staging.records[before:]
        if (len(ops)!=2 or [r.source_sha256 for r in ops]!=[row["b13_sha256"],row["imerg_sha256"]]
                or [r.temporary_bytes for r in ops]!=[int(row["b13_bytes"]),int(row["imerg_bytes"])]
                or any(not r.cleanup_success or not r.size_match or not r.sha256_match for r in ops) or self.staging._owned
                or int((sample.imerg_valid_mask&self.yunnan).sum())!=int(row["imerg_valid_yunnan_count"])
                or int(((sample.y_imerg>.1)&sample.imerg_valid_mask&self.yunnan).sum())!=int(row["imerg_rain_yunnan_count"])):
            raise ValueError("STOP: fixed source SHA/size/QC/count/cleanup mismatch")
        del self.staging.records[before:]
        return sample,{"index":index,"sample_id":sample.sample_id,"obs_start":observed.obs_start.isoformat(),
            "obs_end":observed.obs_end.isoformat(),"date_created":row["date_created"],"cleanup_success":True,
            "copy_seconds":sum(r.copy_seconds for r in ops),"read_seconds":sum(r.read_seconds for r in ops),
            "temporary_bytes_peak":max(r.temporary_bytes for r in ops),"source_operations":[r.__dict__ for r in ops]}


class FinalAccumulator(ReviewAccumulator):
    def __init__(self, axes, sample_ids, rules=None):
        rules=diagnostic_rules() if rules is None else rules
        if rules!=diagnostic_rules(): raise ValueError("Inherited diagnostic definitions changed")
        if not sample_ids or len(set(sample_ids))!=len(sample_ids): raise ValueError("Unique nonempty frozen population required")
        for sample_id in sample_ids: guard_time(sample_id)
        if [utc(s) for s in sample_ids]!=sorted(utc(s) for s in sample_ids): raise ValueError("Fixed chronological order required")
        super().__init__(axes,rules)
        self.sample_ids=tuple(sample_ids)
        self.months={m:GlobalValidationAccumulator() for m in range(3,10)}
        self.scenes={m:0 for m in range(3,10)}
        self.extra_numerics={"nonfinite_occurrence":0,"probability_range_violation":0,"physical_support_violation":0}

    @torch.no_grad()
    def add(self,output,batch,samples,details):
        expected=list(self.sample_ids[self.seen:self.seen+len(samples)])
        if len(expected)!=len(samples) or [s.sample_id for s in samples]!=expected:
            raise ValueError("Missing/duplicate/reordered/out-of-population sample before accumulation")
        for s in samples:
            if guard_time(s.imerg_window_start)!=utc(s.sample_id): raise ValueError("Sample window identity mismatch")
        checked={"nonfinite_occurrence":sum(int((~torch.isfinite(t)).sum()) for t in (output.rain_logit,output.rain_prob)),
            "probability_range_violation":int(((output.rain_prob<0)|(output.rain_prob>1)).sum()),
            "physical_support_violation":int((output.conditional_quantiles_physical[:,0]<=.1).sum())}
        for key,n in checked.items(): self.extra_numerics[key]+=n
        if any(checked.values()): raise FloatingPointError("STOP: occurrence/support numerical violation")
        super().add(output,batch,samples,details)

    def reconcile(self):
        g=self.global_acc
        checks={"full_population_exactly_once":self.seen==len(self.sample_ids),
            "monthly_scenes":sum(self.scenes.values())==self.seen,
            "monthly_valid":sum(a.n_valid for a in self.months.values())==g.n_valid,
            "monthly_rain":sum(a.n_rain for a in self.months.values())==g.n_rain,
            "spatial_valid":int(self.spatial["valid_count"].sum())==g.n_valid,
            "spatial_rain":int(self.spatial["rainy_count"].sum())==g.n_rain,
            "rate_strata":int(self.rate[:,0].sum())==g.n_rain,
            "reliability_valid":int(self.bins[:,0].sum())==g.n_valid,
            "reliability_rain":int(self.bins[:,2].sum())==g.n_rain,
            "probability_frequencies":sum(sum(v.values()) for v in self.frequencies.values())==g.n_valid,
            "probability_histogram":sum(int(v.sum()) for v in self.hist.values())==g.n_valid,
            "numerics":not any(self.numerics.values()) and not any(self.extra_numerics.values())}
        if not all(checks.values()): raise ValueError("STOP: full-population reconciliation failed: "+str(checks))
        return checks

    @staticmethod
    def report(accumulator):
        old=accumulator.report()
        coverage=old["per_tau_conditional_coverage"]
        error=[c-float(t) if c is not None else None for c,t in zip(coverage,TAU)]
        return {"global_core_loss":old["global_val_core_loss"],"occurrence_loss":old["global_L_occ"],
            "quantile_loss":old["global_core_L_qr"],"Brier":old["Brier_Score"],
            **{k:old[k] for k in ("S_occ","S_qr","N_valid","N_rain","prevalence","AUROC","Average_Precision",
                "AP_convention","AUROC_convention","conditional_mean_pinball","per_tau_pinball","DIAGNOSTIC_PROXY_METRIC")},
            "32_tau_conditional_coverage":coverage,"coverage_error":error,
            "absolute_coverage_error":[abs(v) if v is not None else None for v in error],
            "mean_absolute_coverage_error":float(np.mean(np.abs(error))) if old["N_rain"] else None,
            "crossing_count":old["strict_crossing_count"],"nonfinite_count":old["nonfinite_count"],
            "POD":"THRESHOLD_NOT_FROZEN","FAR":"THRESHOLD_NOT_FROZEN","CSI":"THRESHOLD_NOT_FROZEN",
            "undefined_reasons":{"AUROC":"SINGLE_CLASS" if old["AUROC"] is None else None,
                "Average_Precision":"NO_POSITIVE_CLASS" if old["N_rain"]==0 else None,
                "conditional_metrics":"NO_VALID_RAINY_PIXELS" if old["N_rain"]==0 else None}}

    def primary_report(self):
        self.reconcile()
        result=self.report(self.global_acc)
        result["support_violation_count"]=self.numerics["q1_support_violation"]+self.extra_numerics["physical_support_violation"]
        result["numerical_checks"]={**self.numerics,**self.extra_numerics}
        return result

    def diagnostics(self,yunnan):
        primary=self.primary_report()
        monthly=[{"month":f"2025-{m:02d}","scene_count":self.scenes[m],
            "metrics":self.report(a) if a.n_valid else None,
            "undefined_reason":None if a.n_valid else "NO_ELIGIBLE_SCENES"} for m,a in self.months.items()]
        reliability=[{"bin":j,"lower":j/10,"upper":(j+1)/10,"upper_inclusive":j==9,"count":int(n),
            "rainy_count":int(r),"mean_predicted_probability":p/n if n else None,
            "observed_rain_frequency":r/n if n else None,"scope":"BINNED_DIAGNOSTIC"}
            for j,(n,p,r) in enumerate(self.bins)]
        rate=[{"rate_bin_mm_h":label,"pixel_count":int(n),
            "fraction_of_rainy_population":n/primary["N_rain"] if primary["N_rain"] else None,
            "conditional_pinball_log1p_mm_h":pin/n if n else None,
            "DIAGNOSTIC_PROXY_Bias_mm_h":signed/n if n else None,"DIAGNOSTIC_PROXY_MAE_mm_h":absolute/n if n else None,
            "scope":"DESCRIPTIVE_RATE_BINS_ONLY","extreme_definition":"NOT_FROZEN"}
            for label,(n,pin,signed,absolute) in zip(self.rules["rainrate_bins"],self.rate)]
        exceed=[{"threshold_mm_h":t,"count":int(n),"conditional_pinball_log1p_mm_h":pin/n if n else None,
            "DIAGNOSTIC_PROXY_Bias_mm_h":signed/n if n else None,"DIAGNOSTIC_PROXY_MAE_mm_h":absolute/n if n else None,
            "coverage":(self.exceed_coverage[j]/n).tolist() if n else [None]*32,
            "pinball":(self.exceed_tau_sum[j]/n).tolist() if n else [None]*32,
            "scope":"DESCRIPTIVE_ONLY","extreme_definition":"NOT_FROZEN"}
            for j,(t,(n,pin,signed,absolute)) in enumerate(zip(self.rules["exceedances_mm_h"],self.exceed))]
        groups={name:{"number_of_tau":int(use.sum()),"mean_absolute_coverage_error":
            float(np.mean(np.abs(np.array(primary["coverage_error"])[use]))) if primary["N_rain"] else None}
            for name,use in (("low",TAU<.2),("middle",(TAU>=.2)&(TAU<=.8)),("high",TAU>.8))}
        cases=[{"rank":rank,**entry[-1]} for heap in self.heaps.values()
            for rank,entry in enumerate(sorted(heap,key=lambda e:e[:3],reverse=True),1)]
        return {"monthly":monthly,"reliability":reliability,"rainrate":rate,"exceedances":exceed,
            "quantile_groups":groups,"cases":cases,"spatial":self.spatial_metrics(yunnan),
            "probability_distributions":{k:probability_summary(v) if v else None for k,v in self.frequencies.items()},
            "probability_histogram_edges":self.rules["probability_histogram_edges"],
            "probability_histogram_counts":{k:v.tolist() for k,v in self.hist.items()}}
