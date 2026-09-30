"""IMERG converted V07 Final reader with valid-zero preservation."""
from datetime import timedelta
from pathlib import Path
import netCDF4
import numpy as np
from yuntapr.data.sample_schema import utc
from yuntapr.spatial.sp04_mapping import SP04Mapping


def decode_imerg(raw: np.ndarray, attrs: dict) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(raw)
    valid = np.isfinite(raw)
    for key in ("_FillValue", "missing_value"):
        if key in attrs:
            for missing in np.asarray(attrs[key]).reshape(-1):
                valid &= raw != missing
    if "valid_min" in attrs:
        valid &= raw >= attrs["valid_min"]
    if "valid_max" in attrs:
        valid &= raw <= attrs["valid_max"]
    if "scale_factor" in attrs or "add_offset" in attrs:
        if "scale_factor" not in attrs or "add_offset" not in attrs:
            raise ValueError("IMERG scale/offset metadata incomplete")
        decoded = raw.astype(np.float32) * np.float32(attrs["scale_factor"]) + np.float32(attrs["add_offset"])
    else:
        decoded = raw.astype(np.float32)
    valid &= np.isfinite(decoded) & (decoded >= 0)
    decoded[~valid] = np.nan
    return decoded, valid


def read_imerg_local(local_path: Path, index: int, mapping: SP04Mapping) -> tuple[np.ndarray, np.ndarray, object]:
    with netCDF4.Dataset(str(local_path)) as ds:
        ds.set_auto_maskandscale(False)
        variable = ds["precipitation"]
        if variable.dimensions != ("time", "lat", "lon") or variable.units != "mm hr-1" or variable.shape[1:] != (130, 140):
            raise ValueError("IMERG converted dimension/shape/units mismatch")
        lat = np.asarray(ds["lat"][:])
        lon = np.asarray(ds["lon"][:])
        mapping.assert_axes(mapping.axes["native_lat"], mapping.axes["native_lon"], lat[10:110], lon[20:120])
        attrs = {key: variable.getncattr(key) for key in variable.ncattrs()}
        y, valid = decode_imerg(np.asarray(variable[index, 10:110, 20:120]), attrs)
        t = ds["time"]
        converted = netCDF4.num2date(t[index], t.units, calendar=getattr(t, "calendar", "standard"), only_use_cftime_datetimes=False)
        return y, valid, utc(converted.isoformat() + "Z")
