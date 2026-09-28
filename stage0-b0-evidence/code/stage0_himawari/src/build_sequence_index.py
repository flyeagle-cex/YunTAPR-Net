"""Datetime history construction; ambiguous same-time candidates are never auto-selected."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from pathlib import Path
import json,re
import pandas as pd
from config import RAW
PATTERN=re.compile(r"NC_(H\d{2})_(\d{8})_(\d{4})_.*?\.(\d+_\d+)\.nc$",re.I)
class AmbiguousCandidateError(ValueError):pass

def parse_filename(filename:str)->dict:
    match=PATTERN.fullmatch(filename)
    if not match:raise ValueError(f"Unrecognized filename: {filename}")
    satellite,day,hm,grid=match.groups()
    return {"satellite":satellite,"grid_tag":grid,
            "time":datetime.strptime(day+hm,"%Y%m%d%H%M").replace(tzinfo=timezone.utc)}

def expected_times(target:datetime)->list[datetime]:
    return [target-timedelta(minutes=i*10) for i in range(6)]

def unique_candidate(candidates):
    if len(candidates)>1:raise AmbiguousCandidateError(f"{len(candidates)} same-time candidates: {candidates}")
    return candidates[0] if candidates else None

def boundary_paths(year:int,month:int)->list[Path]:
    """Only previous-day directory and only exact five required nominal times are eligible."""
    target=datetime(year,month,1,tzinfo=timezone.utc)
    needed=set(expected_times(target)[1:])
    previous=target-timedelta(days=1)
    folder=RAW/previous.strftime("%Y%m")/previous.strftime("%d")
    result=[]
    if folder.exists():
        for p in folder.rglob("*.nc"):
            try:
                if parse_filename(p.name)["time"] in needed:result.append(p)
            except ValueError:continue
    return sorted(result)

def build_sequences(master:pd.DataFrame,boundary:pd.DataFrame,year:int,month:int)->pd.DataFrame:
    entries=pd.concat([master,boundary],ignore_index=True)
    by_time={}
    for row in entries.to_dict("records"):
        if row.get("timestamp_filename_utc"):
            by_time.setdefault(row["timestamp_filename_utc"],[]).append(row)
    start=datetime(year,month,1,tzinfo=timezone.utc)
    end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)
    # Calendar grid also captures target times at which the current frame itself is absent.
    targets=set()
    t=start
    while t<end:targets.add(t);t+=timedelta(minutes=10)
    for key in by_time:
        t=datetime.fromisoformat(key)
        if start<=t<end:targets.add(t)
    result=[]
    for target in sorted(targets):
        row={"target_time_utc":target.isoformat()};frames=[];missing=0;ambiguity=0;notes=[]
        for i,t in enumerate(expected_times(target)):
            assert t<=target # Future nominal frames would leak information into the model.
            label="t" if i==0 else f"t_minus_{i*10}"
            row["frame_"+label]=t.isoformat()
            candidates=by_time.get(t.isoformat(),[])
            row["candidates_"+label]=json.dumps([r["relative_path"] for r in candidates])
            try:chosen=unique_candidate(candidates)
            except AmbiguousCandidateError as error:
                chosen=None;ambiguity+=1;notes.append(str(error))
            if not candidates:missing+=1
            row["path_"+label]=chosen["relative_path"] if chosen else None
            row["qc_"+label]=chosen["quality_class"] if chosen else None
            if chosen:frames.append(chosen)
        complete=missing==0 and ambiguity==0
        warning=any(r["quality_class"]!="OK" for r in frames)
        grids={r.get("grid_signature") for r in frames if r.get("grid_signature")}
        grid_variant=len(grids)>1 or any("GRID_VARIANT" in r.get("flags","") for r in frames)
        transition=len({r["satellite"] for r in frames})>1
        loadable=complete and len(grids)==1 and all(r["read_success"] and r["has_all_7_channels"] for r in frames)
        if ambiguity:quality="AMBIGUOUS"
        elif not complete:quality="INCOMPLETE"
        elif not loadable:quality="UNLOADABLE"
        elif warning or grid_variant:quality="QUALITY_WARNING"
        else:quality="OK"
        row.update(sequence_complete=complete,sequence_quality=quality,missing_frame_count=missing,
                   ambiguous_frame_count=ambiguity,contains_quality_warning=warning,
                   contains_grid_variant=grid_variant,contains_satellite_transition=transition,
                   loadable=loadable,notes="; ".join(notes))
        result.append(row)
    return pd.DataFrame(result)
