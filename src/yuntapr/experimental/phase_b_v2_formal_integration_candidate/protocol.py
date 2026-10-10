"""Closed candidate identities; no approval or data I/O."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import json
import re
from pathlib import Path
from yuntapr.experimental.phase_b_v2_ablations.config import RunSpec, get_config

BASELINE = "c92eb1910c4bb94a27b250917f86ba82f6e16406"
ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/phase_b_v2_formal_integration_engineering/v1"
SCOPE = "SYNTHETIC_ENGINEERING_ONLY"
FLAGS = {"V2_PHASE_B_AUTHORIZED": False, "FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED": False,
         "RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED": True,
         "HISTORICAL_RECOVERY_RATIFICATION": "NOT_GRANTED", "FORMAL_OPTIMIZER_STEPS": 0,
         "2025_PIXELS_READ": 0, "historical_2025_path_attributes": "NOT_INSTRUMENTED"}

def digest(value) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()

def sha_string(value: str) -> None:
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}",value) is None:
        raise ValueError("Canonical SHA256 required")

def code_sha() -> str:
    return digest({p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in sorted(Path(__file__).parent.glob("*.py"))})

@dataclass(frozen=True)
class Profile:
    name: str
    train_scenes: int
    validation_scenes: int
    epochs: int = 9
    train_batch: int = 2
    validation_batch: int = 8

    def __post_init__(self):
        expected = {"LOGICAL_B9": (10455,10501), "SYNTHETIC_SMALL": (2,2)}
        if (self.name not in expected or (self.train_scenes,self.validation_scenes)!=expected[self.name]
            or self.epochs!=9 or self.train_batch!=2 or self.validation_batch!=8
            or any(type(v) is not int for v in (self.train_scenes,self.validation_scenes,self.epochs,self.train_batch,self.validation_batch))):
            raise ValueError("Closed B9 logical/small synthetic profiles only")

    @property
    def steps(self): return (self.train_scenes+1)//2

    @property
    def validation_batches(self): return (self.validation_scenes+7)//8

    def ids(self, role: str) -> tuple[str,...]:
        if role not in ("train","development"): raise ValueError("Role")
        n = self.train_scenes if role=="train" else self.validation_scenes
        offset = 0 if role=="train" else 20000
        return tuple(f"{SCOPE}/order_{i+offset:05d}" for i in range(n))

def identity(spec: RunSpec, profile: Profile, artifacts: dict) -> dict:
    spec.__post_init__(); profile.__post_init__()
    required={"data","qualification","scaler","mask","sp04","protocol","resource"}
    if set(artifacts)!=required: raise ValueError("Complete source artifact bindings required")
    for value in artifacts.values(): sha_string(value)
    return {"scope":SCOPE,"run":asdict(spec),"run_id":spec.run_id,
            "arm":asdict(get_config(spec.experiment_id)),"profile":asdict(profile),
            "source_commit":BASELINE,"code_sha":code_sha(),"artifacts":dict(artifacts),
            "execution_authorization_ancestor":"SYNTHETIC_EVENT_NO_AUTHORITY",
            "planned_formal_updates_per_epoch":5228,"planned_formal_updates_per_run":47052,
            "fixed_endpoint":9,"selection":"V0_NO_BEST","statistics":"M-C_RECOMMENDED_NOT_APPROVED",
            "scientific_success":"NOT_AUTHORIZED_OR_ESTABLISHED","flags":dict(FLAGS)}
