"""B13 packed-data reader; caller supplies a local English-path staging copy."""
from pathlib import Path
import netCDF4
import numpy as np
from yuntapr.data.sample_schema import HimawariFrame, utc
from yuntapr.spatial.sp04_mapping import SP04Mapping


def decode_b13(raw: np.ndarray, attrs: dict) -> tuple[np.ndarray, np.ndarray]:
    required = ("scale_factor", "add_offset", "valid_min", "valid_max")
    if any(k not in attrs for k in required) or not any(k in attrs for k in ("_FillValue", "missing_value")):
        raise ValueError("B13 packed scale/valid/missing metadata incomplete")
    raw = np.asarray(raw)
    valid = np.isfinite(raw) & (raw >= attrs["valid_min"]) & (raw <= attrs["valid_max"])
    for key in ("_FillValue", "missing_value"):
        if key in attrs:
            for missing in np.asarray(attrs[key]).reshape(-1):
                valid &= raw != missing
    x = raw.astype(np.float32) * np.float32(attrs["scale_factor"]) + np.float32(attrs["add_offset"])
    valid &= np.isfinite(x)
    x[~valid] = np.nan
    return x, valid


def _cf_time(ds, name: str):
    variable = ds[name]
    if variable.size != 1:
        raise ValueError(f"{name} must contain one time")
    dt = netCDF4.num2date(variable[:].reshape(-1)[0], variable.units, calendar=getattr(variable, "calendar", "standard"), only_use_cftime_datetimes=False)
    return utc(dt.isoformat() + "Z")


def read_b13_local(local_english_path: Path, mapping: SP04Mapping, nominal_time) -> tuple[np.ndarray, np.ndarray, HimawariFrame]:
    with netCDF4.Dataset(str(local_english_path)) as ds:
        ds.set_auto_maskandscale(False)
        variable = ds["tbb_13"]
        if variable.dimensions != ("latitude", "longitude") or variable.shape != (501, 501) or variable.units != "K":
            raise ValueError("B13 dimension/shape/units mismatch")
        mapping.assert_axes(np.asarray(ds["latitude"][:]), np.asarray(ds["longitude"][:]), mapping.axes["target_lat"], mapping.axes["target_lon"])
        attrs = {key: variable.getncattr(key) for key in variable.ncattrs()}
        x, valid = decode_b13(np.asarray(variable[:]), attrs)
        frame = HimawariFrame(Path(local_english_path), utc(nominal_time), _cf_time(ds, "start_time"), _cf_time(ds, "end_time"), utc(str(ds.date_created)) if hasattr(ds, "date_created") else None)
        return x, valid, frame
