"""Bounded text-artifact discovery. Raw datasets and historical audit trees are never recursively scanned."""
import subprocess,re,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from collections import Counter
from config import *
from common import *
EXT={".py",".ps1",".bat",".cmd",".sh",".ipynb",".md",".txt",".json",".jsonl",".yaml",".yml",".toml",".log",".csv"}
TERMS=["GFS_thermo","thermo","GFS","NCAR","RDA","d084001","NOAA","AWS","nomads","download","wget","curl","requests","Herbie","cfgrib","wgrib2","convert","conversion","NetCDF","GRIB","archive","forecast","f000","f003","f006","init","lead"]
def discover():
    candidates=set();commands=[];errors=[]
    for root in [PROJECT,DATA]:
        args=["rg","--files","--hidden","--no-ignore",str(root)]
        for ext in sorted(EXT):args+=["-g","*"+ext]
        for exclude in [".venv","cache","outputs","raw","processed","tmp","stage0_himawari",".git","__pycache__","node_modules"]:
            args+=["-g",f"!**/{exclude}/**"]
        args+=["-g","!**/lesson_*/**","-g","!**/Imerge/**"]
        result=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace")
        commands.append({"argv":args,"returncode":result.returncode})
        if result.returncode not in (0,1):errors.append(result.stderr)
        candidates.update(Path(p) for p in result.stdout.splitlines() if p)
    # Known baseline evidence is included explicitly as secondary audit evidence, not independent acquisition proof.
    baseline=json.loads((OUT/"logs/reused_baseline_hashes_before.json").read_text(encoding="utf-8"))
    candidates.update(Path(r["path"]) for r in baseline)
    rows=[];snippets=[];limit=2*1024*1024
    for p in sorted(candidates):
        if not p.is_file():continue
        if p.name.lower().startswith(("era5","imerg","srtm","gpm_dpr")):continue
        stat=p.stat()
        try:
            with p.open("rb") as f:sample=f.read(limit)
            text=sample.decode("utf-8-sig",errors="replace")
        except Exception as e:
            errors.append({"path":str(p),"error":str(e)});continue
        matched=[k for k in TERMS if k.lower() in (p.name+"\n"+text).lower()]
        if not matched or not re.search(r"gfs|thermo|d084001",p.name+"\n"+text,re.I):continue
        secondary=p.is_relative_to(PROJECT/"outputs")
        script=p.suffix.lower() in {".py",".ps1",".bat",".cmd",".sh",".ipynb"}
        relevance="SECONDARY_AUDIT_EVIDENCE" if secondary else "ACQUISITION_OR_CONVERSION_SCRIPT_CANDIDATE" if script else "PRIMARY_LOCAL_LOG_OR_MANIFEST"
        rows.append({"path":str(p),"file_type":p.suffix,"matched_keyword":";".join(matched),
            "mtime":datetime.fromtimestamp(stat.st_mtime,timezone.utc).isoformat(),"mtime_ns":stat.st_mtime_ns,"size":stat.st_size,
            "evidence_relevance":relevance,"content_search_scope":"FULL" if stat.st_size<=limit else "FIRST_2_MIB_PLUS_FILENAME",
            "sha256_before":sha256(p)})
        if not secondary:
            for i,line in enumerate(text.splitlines(),1):
                if re.search(r"\.py\b|\.ps1\b|wgrib2|cfgrib|template|Last-Modified|response.?date|convert|script",line,re.I):
                    if re.search(r"password|authorization|bearer|access_token|refresh_token|secret",line,re.I):continue
                    snippets.append({"path":str(p),"line":i,"excerpt":line[:1600],"evidence_type":"DIRECT_EVIDENCE_OF_RECORDED_TEXT"})
    write_csv(OUT/"PROVENANCE/local_artifact_inventory.csv",rows)
    write_csv(OUT/"PROVENANCE/local_artifact_excerpts.csv",snippets,["path","line","excerpt","evidence_type"])
    write_json(OUT/"logs/search_scope.json",{"commands":commands,"allowed_roots":[str(PROJECT),str(DATA)],
        "excluded_trees":[".venv","cache","outputs except explicit baseline files","raw","processed","tmp","unrelated datasets","unrelated lessons"],
        "content_search_limit_bytes_per_file":limit,"jsonl_extension_added":"real manifests use JSON Lines",
        "candidate_files":len(candidates),"matched_files":len(rows),"errors":errors})
    print(dumps({"candidate_files":len(candidates),"matched_files":len(rows),"relevance_counts":dict(Counter(r["evidence_relevance"] for r in rows)),
        "script_candidates":[r["path"] for r in rows if "SCRIPT" in r["evidence_relevance"]],
        "excerpt_count":len(snippets),"errors":errors}),flush=True)
if __name__=="__main__":discover()
