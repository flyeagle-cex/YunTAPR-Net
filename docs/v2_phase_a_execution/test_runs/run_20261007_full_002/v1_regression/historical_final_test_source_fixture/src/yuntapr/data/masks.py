"""Load frozen private evaluation mask by content hash; no payload in Git."""
from pathlib import Path
import netCDF4
import numpy as np
from yuntapr.contracts.loader import load_contract, sha256
from yuntapr.spatial.sp04_mapping import SP04Mapping


def read_frozen_yunnan_mask(path: Path, mapping: SP04Mapping) -> np.ndarray:
    science, _ = load_contract()
    expected = science["spatial"]["evaluation"]["frozen_mask_sha256"]
    if sha256(path) != expected:
        raise ValueError("Frozen Yunnan mask SHA256 mismatch")
    with netCDF4.Dataset(str(path)) as ds:
        full = np.asarray(ds["yunnan_mask"][:], dtype=bool)
        if full.shape != (130, 140) or int(full.sum()) != 3430:
            raise ValueError("Frozen mask shape/true count mismatch")
        lat = np.asarray(ds["lat"][:])
        lon = np.asarray(ds["lon"][:])
        mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"], lat[10:110], lon[20:120])
    target = full[10:110, 20:120]
    if int(target.sum()) != 3430:
        raise ValueError("Frozen Yunnan mask lost cells in target domain")
    return target
