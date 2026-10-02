"""Audit/correct physical units on new aggregate metadata, preserving all values."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from netCDF4 import Dataset

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"scripts")]
from yuntapr.contracts.loader import sha256
from yuntapr.training.formal_phase_a import atomic_json
from review_b0_phase_a_scientific_v1 import PUBLIC,PRIVATE,BLOCKED_RUN,read


def values_digest(path):
    result={}
    with Dataset(str(path)) as nc:
        for name,var in nc.variables.items():
            array=np.asarray(var[:])
            result[name]={"shape":list(array.shape),"dtype":str(array.dtype),
                "values_sha256":hashlib.sha256(array.tobytes()).hexdigest()}
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--run-id",required=True)
    args=parser.parse_args()
    if Path(args.run_id).name!=args.run_id or args.run_id==BLOCKED_RUN:
        raise ValueError("New completed inference run required")
    out=PUBLIC/args.run_id
    if read(out/"reinference_summary.json")["status"]!="PASS":
        raise ValueError("Full inference must pass")
    identity=read(out/"spatial_artifact_identity.json")
    source=Path(identity["english_local_path"]).resolve()
    private=(PRIVATE/args.run_id).resolve()
    public=out/"spatial_cell_metrics.nc"
    if not source.is_relative_to(private) or sha256(source)!=identity["sha256"] or sha256(public)!=identity["sha256"]:
        raise ValueError("Owned aggregate identity mismatch")
    before=values_digest(source)
    destination=private/"spatial_cell_metrics_units_verified.nc"
    if destination.exists():
        raise FileExistsError("Metadata audit cannot overwrite prior verified file")
    shutil.copyfile(source,destination)
    corrected={"raw_proxy_signed_sum":"mm h-1","raw_proxy_abs_sum":"mm h-1","raw_proxy_squared_sum":"mm2 h-2"}
    with Dataset(str(destination),"r+") as nc:
        for name,units in corrected.items():
            nc[name].units=units
        nc.metadata_units_audit="Raw proxy sum units explicitly audited; all variable values and coordinates unchanged"
        nc.metadata_units_audit_script_sha256=sha256(Path(__file__))
    after=values_digest(destination)
    if before!=after:
        raise ValueError("STOP: metadata edit changed array/coordinate values")
    # Replace only the SHA-verified aggregate this run generated; source/old files untouched.
    temporary=public.with_name("spatial_cell_metrics.nc.metadata_audit.tmp")
    with destination.open("rb") as reader,temporary.open("xb") as writer:
        shutil.copyfileobj(reader,writer)
    if sha256(temporary)!=sha256(destination):
        raise ValueError("Metadata-audited copy SHA mismatch")
    temporary.replace(public)
    identity.update(english_local_path=str(destination),bytes=destination.stat().st_size,sha256=sha256(destination),
        original_aggregate_path=str(source),original_aggregate_sha256=sha256(source),metadata_units_audited=True)
    atomic_json(out/"spatial_artifact_identity.json",identity)
    atomic_json(out/"spatial_metadata_audit.json",{"status":"PASS","corrected_units":corrected,
        "all_array_values_and_coordinates_unchanged":True,"variable_value_identities":after,
        "original_sha256":sha256(source),"verified_sha256":sha256(destination),
        "metadata_script_sha256":sha256(Path(__file__)),"scope":"THIS_RUN_AGGREGATE_METADATA_ONLY"})
    print(json.dumps({"status":"PASS","variables_verified":len(after),"array_values_unchanged":True,"source_and_old_artifacts_unchanged":True}))


if __name__=="__main__":
    main()
