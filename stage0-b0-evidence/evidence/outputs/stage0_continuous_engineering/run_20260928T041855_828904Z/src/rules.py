"""Conservative metadata mapping: no q->RH, MSLP->PS, or precipitation predictors."""
from datetime import datetime,timedelta,timezone
import re
from config import REQUIRED
def parse_filename(name):
    m=re.fullmatch(r"gfs(?:_thermo)?_0p25_(\d{10})_f(\d{3})\.(nc4?|grib2?|grb2?)",name,re.I)
    if not m:raise ValueError("UNKNOWN filename convention")
    init=datetime.strptime(m[1],"%Y%m%d%H").replace(tzinfo=timezone.utc)
    return {"init":init,"lead_hours":int(m[2]),"valid":init+timedelta(hours=int(m[2]))}
def unique_time(candidates):
    values=set(value for source,value in candidates if value is not None)
    if len(values)>1:return None,"CONFLICT"
    return (next(iter(values)),"KNOWN") if values else (None,"UNKNOWN")
def forbidden_precip(name,metadata):
    text=" ".join([name,str(metadata.get("standard_name","")),str(metadata.get("shortName","")),
                   str(metadata.get("long_name","")),str(metadata.get("Grib2_Parameter_Name",""))]).lower()
    # Precipitable water is atmospheric column water, not precipitation flux/accumulation.
    if "precipitable" in text or name.lower() in {"pwat","tcwv"}:return False
    return any(s in text for s in ("precipitation","apcp","prate","precipitation_flux","total_precipitation")) or name.lower()=="tp"
def canonical_variables(name,metadata,dims,pressure_levels_hpa):
    if forbidden_precip(name,metadata):return [],"FORBIDDEN_PRECIPITATION"
    low=name.lower();standard=str(metadata.get("standard_name","")).lower()
    short=str(metadata.get("shortName","")).lower()
    level=str(metadata.get("Grib2_Level_Type",metadata.get("GRIB_typeOfLevel",""))).lower()
    isobaric=any("pressure" in d.lower() or "isobaric" in d.lower() for d in dims)
    if low=="pressure_surface" or standard=="surface_air_pressure" or short=="sp":
        # Explicit sea-level context always wins over ambiguous short names.
        desc=" ".join([low,standard,str(metadata.get("long_name",""))]).lower()
        if "sea_level" in desc or "mean sea level" in desc or "msl" in desc:return [],"MSLP_NOT_SURFACE_PRESSURE"
        return ["PS"],"EXPLICIT_SURFACE_PRESSURE"
    if low in {"prmsl","msl","pressure_reduced_to_msl_msl"} or "mean_sea_level" in standard:return [],"MSLP_NOT_SURFACE_PRESSURE"
    if low=="precipitable_water_entire_atmosphere_single_layer" or short in {"pwat","tcwv"} or standard=="atmosphere_mass_content_of_water_vapor":
        return ["PWAT"],"COLUMN_WATER_NOT_PRECIPITATION"
    if low=="convective_available_potential_energy_surface" or short=="cape" or standard=="atmosphere_convective_available_potential_energy":
        if isobaric:return [],"CAPE_LEVEL_NEEDS_REVIEW"
        return ["CAPE"],"CAPE_METADATA"
    family=None
    if low=="relative_humidity_isobaric" or standard=="relative_humidity" or short=="r":family="RH"
    elif low=="temperature_isobaric" or standard=="air_temperature" or short=="t":family="T"
    elif low=="u-component_of_wind_isobaric" or standard=="eastward_wind" or short=="u":family="U"
    elif low=="v-component_of_wind_isobaric" or standard=="northward_wind" or short=="v":family="V"
    if family and isobaric:
        needed=(850,700,500) if family in {"T","RH"} else (850,700)
        return [f"{family}_{p}" for p in needed if p in pressure_levels_hpa],"EXPLICIT_PRESSURE_LEVEL"
    return [],"NOT_A_REQUIRED_CANONICAL_VARIABLE"
def pressure_to_hpa(values,units):
    units=str(units).strip().lower()
    if units in {"pa","pascal","pascals"}:return [float(x)/100 for x in values]
    if units in {"hpa","millibar","mbar","millibars"}:return [float(x) for x in values]
    raise ValueError("UNKNOWN pressure-coordinate units")
def choose_main(roots,preferred):
    if preferred in roots:return preferred
    exact=[p for p in roots if p.name.lower()=="gfs"]
    if len(exact)==1:return exact[0]
    if len(roots)==1:return roots[0]
    raise ValueError("BLOCKED: no unambiguous main GFS root")
def coverage_status(observed,expected,audited=True):
    if not audited:return "NOT_AUDITED"
    if observed==0:return "MISSING"
    return "READY" if observed==expected else "PARTIAL"
