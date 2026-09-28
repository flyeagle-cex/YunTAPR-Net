"""Measured Zarr-v2/NetCDF4-HDF5 candidates; all timing samples and roundtrips retained."""
from __future__ import annotations
import hashlib,json,logging,shutil,time
from pathlib import Path
import numpy as np
import pandas as pd
import netCDF4,numcodecs,zarr,torch
from config import CHANNELS,CONFIG,RAW
from common import MemoryMonitor,write_table,write_json,write_text,dumps
from read_himawari import read_himawari_7ch
from sample_audit import LABELS,frame_paths

def fingerprint(x,m):
    h=hashlib.sha256();h.update(np.ascontiguousarray(x).tobytes());h.update(np.ascontiguousarray(m).tobytes())
    return h.hexdigest()

def bytes_in(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob("*") if p.is_file())

def select_benchmark(sequences,selection,master,boundary):
    random=selection[selection.selection_reason.str.contains("random_seed_42")].copy()
    usable=sequences[sequences.sequence_complete & sequences.loadable].sort_values("target_time_utc")
    # Find a real continuous block of >=50 complete targets.
    times=pd.to_datetime(usable.target_time_utc)
    blocks=(times.diff()!=pd.Timedelta(minutes=10)).cumsum()
    continuous=None
    for _,block in usable.groupby(blocks):
        if len(block)>=50:continuous=block.head(50);break
    if continuous is None:raise RuntimeError("No continuous block of 50 complete target sequences")
    keys=set()
    for row in pd.concat([random,continuous]).to_dict("records"):
        keys.update(row["path_"+label] for label in LABELS)
    # Include readable all-fill/partial-valid/grid variants independently of complete histories.
    for flag in ("ALL_FILL","PARTIAL_VALID","GRID_VARIANT","COORD_ANOMALY"):
        keys.update(master.loc[master.read_success & master["flags"].str.contains(flag,regex=False),"relative_path"].head(2))
    entries=pd.concat([master,boundary],ignore_index=True)
    frames=entries[entries.relative_path.isin(keys)].sort_values(["grid_signature","timestamp_filename_utc","relative_path"]).copy()
    assert len(frames)==len(keys),"Benchmark source manifest mismatch"
    return random,continuous,frames

def run_benchmark(sequences,selection,master,boundary,staging,out):
    random,continuous,frames=select_benchmark(sequences,selection,master,boundary)
    write_table(frames,out/"benchmark/benchmark_frame_manifest_202407.csv",parquet=True)
    targets=pd.concat([random.assign(benchmark_group="random_50"),continuous.assign(benchmark_group="continuous_50")])
    write_table(targets,out/"benchmark/benchmark_sequence_manifest_202407.csv")
    base=out/"benchmark/candidates";base.mkdir(exist_ok=False)
    shape_groups=list(frames.groupby("grid_signature",sort=True))
    locators={};reference_hash={};rows=[];creation={}
    for format_name in ("zarr","netcdf4"):
        folder=base/format_name;folder.mkdir()
        total_started=time.perf_counter();write_seconds=0.0;source_seconds=0.0
        with MemoryMonitor() as memory:
            for group_no,(sig,group) in enumerate(shape_groups):
                records=group.to_dict("records")
                first=records[0];n=len(records);h=int(first["shape_lat"]);w=int(first["shape_lon"])
                if shutil.disk_usage(folder).free < n*7*h*w*5+CONFIG["min_disk_free_bytes"]:
                    raise RuntimeError("Insufficient disk for conservatively sized benchmark candidate")
                chunks=(1,7,min(128,h),min(128,w))
                if format_name=="zarr":
                    path=folder/f"grid_{group_no}.zarr"
                    tick=time.perf_counter()
                    store=zarr.open_group(str(path),mode="w-",zarr_format=2)
                    codec=numcodecs.Blosc(cname="zstd",clevel=3,shuffle=numcodecs.Blosc.BITSHUFFLE)
                    xa=store.create_array("x",shape=(n,7,h,w),chunks=chunks,dtype="f4",compressor=codec,fill_value=np.nan)
                    ma=store.create_array("valid_mask",shape=(n,7,h,w),chunks=chunks,dtype="bool",compressor=codec,fill_value=False)
                    store.attrs.update({"axes":["time","channel","latitude","longitude"],"channels":list(CHANNELS),
                                        "units":"K","missing_policy":"NaN plus explicit bool mask",
                                        "metadata_sidecar":f"grid_{group_no}_metadata.jsonl",
                                        "scope":"QC_STAT_ONLY; benchmark candidate; not frozen"})
                else:
                    path=folder/f"grid_{group_no}.nc"
                    tick=time.perf_counter();store=netCDF4.Dataset(str(path),"w",format="NETCDF4")
                    for dim,size in [("time",n),("channel",7),("latitude",h),("longitude",w)]:store.createDimension(dim,size)
                    xa=store.createVariable("x","f4",("time","channel","latitude","longitude"),
                                            chunksizes=chunks,compression="zlib",complevel=3,shuffle=True,fill_value=np.nan)
                    ma=store.createVariable("valid_mask","u1",("time","channel","latitude","longitude"),
                                            chunksizes=chunks,compression="zlib",complevel=3,shuffle=True)
                    xa.units="K";ma.encoding_description="0 invalid, 1 valid; decode as bool"
                    store.setncatts({"channels":json.dumps(list(CHANNELS)),"axes":"time,channel,latitude,longitude",
                                     "metadata_sidecar":f"grid_{group_no}_metadata.jsonl",
                                     "scope":"QC_STAT_ONLY; benchmark candidate; not frozen"})
                write_seconds+=time.perf_counter()-tick
                try:
                    with (folder/f"grid_{group_no}_metadata.jsonl").open("x",encoding="utf-8") as metadata_file:
                        for j,r in enumerate(records):
                            tick=time.perf_counter()
                            x,m,lat,lon,meta=read_himawari_7ch(RAW/r["relative_path"],staging)
                            source_seconds+=time.perf_counter()-tick
                            digest=fingerprint(x,m)
                            if format_name=="zarr":reference_hash[r["relative_path"]]=digest
                            else:assert reference_hash[r["relative_path"]]==digest,"Source decoding changed between candidates"
                            tick=time.perf_counter()
                            if j==0:
                                if format_name=="zarr":
                                    store.create_array("latitude",data=lat)
                                    store.create_array("longitude",data=lon)
                                    store.create_array("timestamp_ns",data=pd.to_datetime(group.timestamp_filename_utc,utc=True).dt.as_unit("ns").astype("int64").to_numpy())
                                else:
                                    store.createVariable("latitude","f4",("latitude",))[:]=lat
                                    store.createVariable("longitude","f4",("longitude",))[:]=lon
                                    tv=store.createVariable("timestamp_ns","i8",("time",));tv[:]=pd.to_datetime(group.timestamp_filename_utc,utc=True).dt.as_unit("ns").astype("int64").to_numpy()
                                    tv.units="nanoseconds since 1970-01-01 00:00:00 UTC"
                            xa[j]=x;ma[j]=m if format_name=="zarr" else m.astype(np.uint8)
                            metadata_file.write(dumps({"source":r["relative_path"],"nominal_utc":r["timestamp_filename_utc"],"metadata":meta})+"\n")
                            write_seconds+=time.perf_counter()-tick
                            locators[(format_name,r["relative_path"])]=(str(path),j)
                            del x,m
                            if (j+1)%50==0:logging.info("Benchmark create %s grid=%d frames=%d/%d",format_name,group_no,j+1,n)
                finally:
                    if format_name=="netcdf4":
                        tick=time.perf_counter();store.close();write_seconds+=time.perf_counter()-tick
            total_seconds=time.perf_counter()-total_started
        creation[format_name]=dict(format=format_name,operation="create",repeat=0,operations=len(frames),
              seconds=total_seconds,write_seconds=write_seconds,source_decode_seconds=source_seconds,
              total_bytes=bytes_in(folder),chunk_shape=str(CONFIG["chunk_shape"]),
              compressor="Blosc zstd level=3 bitshuffle" if format_name=="zarr" else "zlib level=3 shuffle=True",
              mask_dtype="bool" if format_name=="zarr" else "uint8 with explicit boolean semantics",
              storage_dtype="float32",metadata_preserved=True,**memory.report())
        rows.append(creation[format_name])
    opened={}
    def read_frame(format_name,key):
        path,i=locators[(format_name,key)]
        if path not in opened:
            if format_name=="zarr":opened[path]=zarr.open_group(path,mode="r")
            else:
                opened[path]=netCDF4.Dataset(path,"r");opened[path].set_auto_maskandscale(False)
        ds=opened[path]
        x=np.asarray(ds["x"][i]);m=np.asarray(ds["valid_mask"][i],dtype=bool)
        return x,m
    try:
        # Every stored frame is compared byte-for-byte against decoded source fingerprints.
        validation=[]
        for format_name in ("zarr","netcdf4"):
            for r in frames.to_dict("records"):
                x,m=read_frame(format_name,r["relative_path"])
                assert fingerprint(x,m)==reference_hash[r["relative_path"]],f"Roundtrip mismatch: {r['relative_path']}"
            validation.append({"format":format_name,"roundtrip_frames":len(frames),"status":"PASS"})
        write_table(pd.DataFrame(validation),out/"benchmark/storage_roundtrip_validation_202407.csv")
        rng=np.random.default_rng(CONFIG["seed"])
        singles=list(rng.choice(frames.relative_path,size=min(50,len(frames)),replace=False))
        groups={
            "single_frame_random":[[p] for p in singles],
            "sequential_6frame":[[r["path_"+label] for label in LABELS] for r in continuous.to_dict("records")],
            "random_6frame":[[r["path_"+label] for label in LABELS] for r in random.to_dict("records")]}
        # Repeated warm-cache timing, alternate order to reduce systematic order bias.
        for repeat in range(CONFIG["benchmark_repeats"]):
            order=("zarr","netcdf4") if repeat%2==0 else ("netcdf4","zarr")
            for format_name in order:
                for operation,batches in groups.items():
                    t=time.perf_counter()
                    with MemoryMonitor() as memory:
                        for keys in batches:
                            pairs=[read_frame(format_name,key) for key in keys]
                            x=np.stack([a for a,b in pairs]);mask=np.stack([b for a,b in pairs])
                            assert np.isnan(x[~mask]).all()
                            del pairs,x,mask
                    elapsed=time.perf_counter()-t
                    rows.append(dict(format=format_name,operation=operation,repeat=repeat,operations=len(batches),
                                      seconds=elapsed,seconds_per_operation=elapsed/len(batches),
                                      cache_state="warm_OS_and_backend_cache; not cold-disk measurement",**memory.report()))
                t=time.perf_counter()
                with MemoryMonitor() as memory:
                    for keys in groups["random_6frame"]:
                        x=np.stack([read_frame(format_name,key)[0] for key in keys])
                        tensor=torch.from_numpy(x)
                        assert tensor.dtype==torch.float32 and tensor.shape[:2]==(6,7)
                        del x,tensor
                elapsed=time.perf_counter()-t
                rows.append(dict(format=format_name,operation="pytorch_6frame",repeat=repeat,operations=len(random),
                                  seconds=elapsed,seconds_per_operation=elapsed/len(random),**memory.report()))
    finally:
        for path,ds in opened.items():
            if path.endswith(".nc"):ds.close()
    table=pd.DataFrame(rows)
    write_table(table,out/"benchmark/storage_benchmark_202407.csv")
    write_json(out/"benchmark/storage_locators.json",
               [{"format":fmt,"relative_path":key,"store":p,"index":i} for (fmt,key),(p,i) in locators.items()])
    return table,frames
