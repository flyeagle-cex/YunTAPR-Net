"""Pure metadata contracts and an always-denying real-data boundary."""
from __future__ import annotations
from datetime import datetime,timezone,timedelta
import hashlib
from .protocol import sha_string

class IndependentAuthorityUnavailable(PermissionError): pass

class RejectingAuthority:
    def verify_execution(self,*args,**kwargs):
        raise IndependentAuthorityUnavailable("Independent approval infrastructure absent; no execution")
    def verify_resume(self,*args,**kwargs):
        raise IndependentAuthorityUnavailable("New independent LAST-bound approval cannot be authenticated")

class RealDataAdapter:
    """No reader/resolver/provider injection exists in this version."""
    def open_scene(self, scene_id, path=None, approval=None):
        # Do not inspect path, repr it, call __fspath__, resolve, stat or open.
        raise IndependentAuthorityUnavailable("Real connector disabled before all path access")
    def open_manifest(self,*args,**kwargs):
        raise IndependentAuthorityUnavailable("Real manifest loading disabled before path access")
    def open_artifact(self,*args,**kwargs):
        raise IndependentAuthorityUnavailable("Real scaler/mask/SP04 access disabled")

def start_formal(*args,**kwargs):
    raise IndependentAuthorityUnavailable("Scientific, code, data, resource and execution approvals absent")

def utc(value: str) -> datetime:
    t=datetime.fromisoformat(value)
    if t.tzinfo is None or t.utcoffset()!=timedelta(0):
        raise ValueError("Explicit UTC timestamp required")
    return t.astimezone(timezone.utc)

def audit_scene_metadata(scene: dict) -> dict:
    """In-memory metadata only; never establishes authentic source/permission."""
    if set(scene)!={"id","year","role","qualification","analysis","window_start","window_end",
                    "slots","product","units","artifacts"}:
        raise ValueError("Scene metadata fields")
    year=scene["year"]
    if type(year) is not int or year not in (2023,2024):
        raise PermissionError("Only 2023/2024 roles; reject sealed/unknown year")
    role={2023:"TRAIN",2024:"DEVELOPMENT"}[year]
    a,t,end=map(utc,(scene["analysis"],scene["window_start"],scene["window_end"]))
    if scene["role"]!=role or a!=t+timedelta(minutes=30) or end!=a or t.year!=year or t.month not in range(3,11):
        raise ValueError("Frozen temporal/data role")
    if scene["qualification"]!="M1_Q1" or scene["product"]!="IMERG_V07_Final" or scene["units"]!="mm hr-1":
        raise ValueError("Qualification/product/units changed")
    if type(scene["id"]) is not str or not scene["id"]: raise ValueError("Missing scene ID")
    if len(scene["slots"])!=6: raise ValueError("Exactly six B13 causal slots")
    late=0
    for row,offset in zip(scene["slots"],(60,50,40,30,20,10),strict=True):
        if set(row)!={"nominal","obs_start","obs_end","created","sha256","channel"}:raise ValueError("Slot fields")
        nominal,start,stop,created=map(utc,(row["nominal"],row["obs_start"],row["obs_end"],row["created"]))
        if row["channel"]!="B13" or nominal!=a-timedelta(minutes=offset) or not start<=stop<=a:
            raise ValueError("Causal B13 slot mismatch")
        sha_string(row["sha256"]); late+=int(created>a)
    if set(scene["artifacts"])!={"scaler","mask","sp04","qualification","imerg"}: raise ValueError("Artifact bindings")
    for v in scene["artifacts"].values():sha_string(v)
    return {"metadata_consistent":True,"file_created_after_analysis":late,
            "real_source_authenticated":False,"operational_availability":"NOT_VERIFIED",
            "real_access_allowed":False}

def audit_manifest_metadata(train: list[dict], development: list[dict], expected_ids: dict) -> dict:
    if len(train)!=10455 or len(development)!=10501: raise ValueError("Frozen scene counts")
    all_ids=[]
    for role,rows in (("TRAIN",train),("DEVELOPMENT",development)):
        ids=[r["id"] for r in rows]
        if ids!=expected_ids[role] or len(set(ids))!=len(ids):raise ValueError("Identity/order/uniqueness")
        dates=[]
        for row in rows:
            audit_scene_metadata(row)
            if row["role"]!=role:raise ValueError("Role mismatch")
            dates.append(utc(row["window_start"]))
        if dates!=sorted(set(dates)):raise ValueError("Strict original chronological order")
        all_ids.extend(ids)
    if len(set(all_ids))!=20956:raise ValueError("Role overlap")
    return {"count":20956,"real_access_allowed":False,"metadata_only":True}

def verify_synthetic_bytes(payload: bytes, expected_sha: str) -> dict:
    """Pure byte arithmetic for fixtures, no path/file API or authorization."""
    if type(payload) is not bytes:raise ValueError("In-memory synthetic bytes required")
    sha_string(expected_sha)
    if hashlib.sha256(payload).hexdigest()!=expected_sha:raise ValueError("SHA mismatch; stop")
    return {"bytes":len(payload),"sha256":expected_sha,"confers_access":False}
