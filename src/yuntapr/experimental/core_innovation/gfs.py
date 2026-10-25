"""Bounded 2023/2024 GFS environment reader; retrospective != operational availability.

Only explicitly named environmental fields are accepted. No precipitation,
implicit vintage lag, time interpolation, humidity derivation, or normalization.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib
import re
import numpy as np
from .grid import GridSpec,BilinearMap

UTC=timezone.utc
VARIABLES={
 'temperature':('Temperature_isobaric',),
 'relative_humidity':('Relative_humidity_isobaric',),
 'u':('u-component_of_wind_isobaric',),
 'v':('v-component_of_wind_isobaric',),
 'surface_pressure':('Pressure_surface',),
 'precipitable_water':('Precipitable_water_entire_atmosphere_single_layer',),
 'cape':('Convective_available_potential_energy_surface',),
}
PRESSURE_QUANTITIES={'temperature','relative_humidity','u','v'}


def utc(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Explicit timezone-aware datetime required')
    return value.astimezone(UTC)


def parse_utc(value):
    text=str(value).strip().replace(' UTC','+00:00').replace('Z','+00:00')
    return utc(datetime.fromisoformat(text))


def pressure_pa(values,unit):
    if unit not in ('Pa','hPa'):raise ValueError('Pressure unit must be explicitly Pa or hPa')
    return np.asarray(values,dtype=np.float64)*(100. if unit=='hPa' else 1.)


@dataclass(frozen=True)
class ForecastIdentity:
    init: datetime
    lead: timedelta
    valid: datetime

    def __post_init__(self):
        init,valid=utc(self.init),utc(self.valid)
        if init.year not in (2023,2024) or valid.year not in (2023,2024):raise PermissionError('Only authorized 2023/2024 input times')
        if not isinstance(self.lead,timedelta) or self.lead<timedelta(0) or init+self.lead!=valid:raise ValueError('GFS init + lead must equal valid')
        object.__setattr__(self,'init',init);object.__setattr__(self,'valid',valid)


@dataclass(frozen=True)
class Availability:
    observed_utc: datetime
    evidence_id: str
    evidence_kind: str
    forecast: ForecastIdentity
    source_sha256: tuple[str,...]

    def __post_init__(self):
        object.__setattr__(self,'observed_utc',utc(self.observed_utc))
        if self.evidence_kind!='observed_historical_first_availability' or not self.evidence_id.strip():
            raise ValueError('mtime/download/conversion or init+fixed-lag is not release evidence')
        hashes=tuple(self.source_sha256)
        if not isinstance(self.forecast,ForecastIdentity) or len(hashes)!=2 or len(set(hashes))!=2 or any(not re.fullmatch('[0-9a-f]{64}',h) for h in hashes):
            raise ValueError('Availability must bind the forecast and both exact source payload hashes')
        object.__setattr__(self,'source_sha256',hashes)


@dataclass(frozen=True)
class VariableRequest:
    key: str
    quantity: str
    variable: str
    level_pa: float|None=None

    def __post_init__(self):
        if not self.key or self.quantity not in VARIABLES or self.variable not in VARIABLES[self.quantity]:raise ValueError('Explicit audited environmental variable binding required')
        if self.quantity in PRESSURE_QUANTITIES:
            if self.level_pa is None or not np.isfinite(self.level_pa) or self.level_pa<=0:raise ValueError('Explicit pressure level in Pa required')
        elif self.level_pa is not None:raise ValueError('Surface/column fields do not have isobaric levels')


@dataclass(frozen=True)
class Field:
    values: np.ndarray
    valid: np.ndarray
    quantity: str
    unit: str
    level_pa: float|None


@dataclass(frozen=True)
class GFSFile:
    identity: ForecastIdentity
    grid: GridSpec
    fields: dict[str,Field]
    provenance: dict


@dataclass(frozen=True)
class EnvironmentFrame:
    identity: ForecastIdentity
    grid: GridSpec
    fields: dict[str,Field]
    mode: str
    provenance: tuple[dict,...]

    def stack(self,keys):
        """Explicit MEE channel order; retain NaNs + independent validity mask."""
        if not keys or len(set(keys))!=len(keys):raise ValueError('Nonempty unique explicit channel order required')
        return np.stack([self.fields[k].values for k in keys]),np.stack([self.fields[k].valid for k in keys])

    def on_grid(self,target,*,operator):
        if operator!='bilinear_point_candidate':raise ValueError('Explicit candidate spatial operator required')
        mapping=BilinearMap.build(self.grid,target);fields={}
        for name,f in self.fields.items():
            values,valid=mapping.apply(f.values,f.valid)
            fields[name]=Field(values,valid,f.quantity,f.unit,f.level_pa)
        fields=_above_ground(fields)
        return EnvironmentFrame(self.identity,target,fields,self.mode,self.provenance+({'spatial_operator':operator,'source_grid':self.grid.identity,'target_grid':target.identity,'SP04_25_center_reduction':False},))


def _convert(values,unit,quantity):
    aliases={'temperature':{'K':'K'},'relative_humidity':{'%':'%'},
      'u':{'m/s':'m/s','m s-1':'m/s','m.s-1':'m/s'},'v':{'m/s':'m/s','m s-1':'m/s','m.s-1':'m/s'},
      'surface_pressure':{'Pa':'Pa','hPa':'Pa'},
      'precipitable_water':{'kg m-2':'kg m-2','kg.m-2':'kg m-2','kg/m^2':'kg m-2'},
      'cape':{'J/kg':'J/kg','J kg-1':'J/kg','J.kg-1':'J/kg'}}
    if unit not in aliases[quantity]:raise ValueError('Unrecognized explicit units for '+quantity)
    value=pressure_pa(values,unit) if quantity=='surface_pressure' else np.asarray(values,dtype=np.float64)
    return value,aliases[quantity][unit]


def decode_packed(raw,attrs):
    """Apply fill/valid range in packed domain, then scale/offset once."""
    data=np.asarray(raw)
    if str(attrs.get('_Unsigned','false')).lower()=='true':
        raise ValueError('Unsigned packed representation requires a separately tested decoder')
    good=np.isfinite(data)
    for key in ('_FillValue','missing_value'):
        for fill in np.asarray(attrs.get(key,[])).ravel():good &= data!=fill
    if 'valid_range' in attrs:
        limits=np.asarray(attrs['valid_range']).ravel()
        if len(limits)!=2 or not np.isfinite(limits).all() or limits[0]>limits[1]:raise ValueError('Invalid packed valid_range')
        good &= (data>=limits[0])&(data<=limits[1])
    for key,op in (('valid_min',np.greater_equal),('valid_max',np.less_equal)):
        if key in attrs:
            if np.asarray(attrs[key]).ndim!=0 or not np.isfinite(attrs[key]):raise ValueError('Invalid packed range bound')
            good &= op(data,attrs[key])
    scale=float(attrs.get('scale_factor',1.));offset=float(attrs.get('add_offset',0.))
    if not np.isfinite([scale,offset]).all() or scale==0:raise ValueError('Invalid packing scale/offset')
    values=np.asarray(data,dtype=np.float64)*scale+offset;good &= np.isfinite(values)
    return np.where(good,values,np.nan),good


def _one(ds,names):
    found=[name for name in names if name in ds.variables]
    if len(found)!=1:raise ValueError('A unique explicit coordinate is required: '+','.join(names))
    return ds.variables[found[0]]


def _cf_time(var):
    from netCDF4 import num2date
    if var.size!=1:raise ValueError('One forecast time per file required')
    if getattr(var,'calendar','standard') not in ('standard','gregorian','proleptic_gregorian'):raise ValueError('Unsupported CF calendar')
    value=np.asarray(var[...]).ravel()[0]
    if not np.isfinite(value):raise ValueError('Nonfinite CF time')
    d=num2date(value,var.units,calendar=getattr(var,'calendar','standard'),only_use_cftime_datetimes=False)
    return datetime(d.year,d.month,d.day,d.hour,d.minute,d.second,d.microsecond,tzinfo=UTC)


def _above_ground(fields):
    surface=[f for f in fields.values() if f.quantity=='surface_pressure']
    if len(surface)!=1:raise ValueError('Exactly one explicitly requested PS required for pressure masking')
    ps=surface[0];out={}
    for key,f in fields.items():
        valid=f.valid.copy()
        if f.quantity=='surface_pressure':valid &= np.isfinite(f.values)&(f.values>0)
        if f.level_pa is not None:valid &= ps.valid & np.isfinite(ps.values) & (ps.values>0) & (f.level_pa<ps.values)
        out[key]=Field(np.where(valid,f.values,np.nan),valid,f.quantity,f.unit,f.level_pa)
    return out


def read_gfs_file(path,identity,requests,*,max_file_bytes=2*1024**2,max_cells=65536):
    """Read-only bounded NetCDF memory view also works with Unicode source paths.

    File byte reading is counted by provenance. This is NOT a zero-byte metadata
    check. The budget prevents materializing a large library/forecast archive.
    """
    from netCDF4 import Dataset
    if not isinstance(identity,ForecastIdentity):raise TypeError('Validated ForecastIdentity required before source access')
    if type(max_file_bytes) is not int or not 0<max_file_bytes<=8*1024**2 or type(max_cells) is not int or not 0<max_cells<=65536:raise ValueError('Small bounded interface read only')
    if not requests or len({r.key for r in requests})!=len(requests):raise ValueError('Unique explicit variable requests required')
    path=Path(path)
    def name_identity(p):
        m=re.fullmatch(r'gfs_(?:thermo_)?0p25_(\d{10})_f(\d{3})\.nc',p.name)
        if not m or any(part=='2025' for part in p.parts):raise PermissionError('Only explicit authorized forecast filenames')
        init=datetime.strptime(m[1],'%Y%m%d%H').replace(tzinfo=UTC)
        # Validate the forecast year before resolve/stat/open.
        if init.year not in (2023,2024):raise PermissionError('2025 and other source years are not authorized')
        if init!=identity.init or timedelta(hours=int(m[2]))!=identity.lead:raise ValueError('Filename and requested forecast identity differ')
    name_identity(path);resolved=path.resolve(strict=True);name_identity(resolved)
    before=resolved.stat()
    if not 0<before.st_size<=max_file_bytes:raise ValueError('Forecast exceeds bounded interface byte budget')
    with resolved.open('rb') as handle:raw=handle.read(max_file_bytes+1)
    if len(raw)!=before.st_size or len(raw)>max_file_bytes:raise ValueError('Bounded input changed or exceeded size')
    after=resolved.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('Source changed during bounded read')
    fields={};caveats={}
    with Dataset('bounded_forecast.nc',mode='r',memory=raw) as ds:
        ds.set_auto_maskandscale(False)
        lat=_one(ds,('latitude','lat'));lon=_one(ds,('longitude','lon'))
        if lat.ndim!=1 or lon.ndim!=1 or lat.size*lon.size>max_cells:raise ValueError('Bounded rectilinear grid required')
        if lat.units not in ('degrees_north','degree_north') or lon.units not in ('degrees_east','degree_east'):raise ValueError('Geographic coordinate units required')
        grid=GridSpec(lat[:],lon[:])
        if _cf_time(_one(ds,('forecast_reference_time','reftime','reference_time')))!=identity.init or _cf_time(_one(ds,('valid_time','time')))!=identity.valid:raise ValueError('Primary CF forecast identity mismatch')
        for name,expected in (('initialization_time_utc',identity.init),('valid_time_utc',identity.valid)):
            if name in ds.ncattrs() and parse_utc(ds.getncattr(name))!=expected:raise ValueError('Global/CF forecast time conflict')
        for name in ('forecast_hour','lead_time_hours'):
            if name in ds.ncattrs() and float(ds.getncattr(name))*3600!=identity.lead.total_seconds():raise ValueError('Global/CF lead conflict')
        pressure=_one(ds,('pressure_level','isobaric')) if any(r.level_pa is not None for r in requests) else None
        levels=pressure_pa(pressure[:],pressure.units) if pressure is not None else None
        if levels is not None and (levels.ndim!=1 or not np.isfinite(levels).all() or (levels<=0).any() or len(np.unique(levels))!=len(levels)):raise ValueError('Unique positive finite pressure coordinate required')
        for request in requests:
            if request.variable not in ds.variables:raise ValueError('Requested field missing: '+request.key)
            var=ds.variables[request.variable];index=[];remaining=[]
            for dim in var.dimensions:
                if dim==lat.dimensions[0] or dim==lon.dimensions[0]:index.append(slice(None));remaining.append(dim)
                elif pressure is not None and dim==pressure.dimensions[0] and request.level_pa is not None:
                    found=np.flatnonzero(levels==request.level_pa)
                    if len(found)!=1:raise ValueError('Exact requested pressure level unavailable')
                    index.append(int(found[0]))
                elif dim in ('valid_time','time') and len(ds.dimensions[dim])==1:index.append(0)
                else:raise ValueError('Unapproved variable dimensions or vertical level type')
            if remaining!=[lat.dimensions[0],lon.dimensions[0]]:raise ValueError('Explicit row=latitude col=longitude layout required')
            attrs={name:var.getncattr(name) for name in var.ncattrs()}
            values,valid=decode_packed(var[tuple(index)],attrs)
            if values.shape!=grid.shape:raise ValueError('Variable grid differs from coordinates')
            values,unit=_convert(values,str(attrs.get('units','')),request.quantity)
            fields[request.key]=Field(values,valid,request.quantity,unit,request.level_pa)
        # Preserve stale auxiliary/history evidence; these never establish release.
        for name in ('conservative_available_time_utc','availability_note','history','legacy_history_before_20260925'):
            if name in ds.ncattrs():caveats[name]=str(ds.getncattr(name))
        valid_var=_one(ds,('valid_time','time'))
        if 'udunits' in valid_var.ncattrs():caveats['auxiliary_udunits']=str(valid_var.udunits)
    return GFSFile(identity,grid,fields,{'input_sha256':hashlib.sha256(raw).hexdigest(),'file_bytes_read':len(raw),'historical_availability':'NOT_ESTABLISHED','source_lineage':'SUPPORTED_WITH_CAVEATS','legacy_metadata':caveats})


def combine_environment(main,thermo,*,target_valid_time,decision_time,mode,availability=None):
    """Identity-paired environment candidate, no temporal interpolation or frozen adoption."""
    if not isinstance(main,GFSFile) or not isinstance(thermo,GFSFile):raise TypeError('Two explicitly decoded GFS files required')
    if main.identity!=thermo.identity:raise ValueError('Mixed forecast vintage forbidden')
    main.grid.assert_same(thermo.grid)
    if utc(target_valid_time)!=main.identity.valid or main.identity.init>utc(decision_time):raise ValueError('Target valid time or future initialization mismatch')
    if mode not in ('retrospective','operational'):raise ValueError('Explicit retrospective/operational mode required')
    if mode=='operational':
        if not isinstance(availability,Availability):raise PermissionError('Historical availability evidence missing; no assumed init+lag')
        if availability.forecast!=main.identity or set(availability.source_sha256)!={main.provenance['input_sha256'],thermo.provenance['input_sha256']}:
            raise PermissionError('Availability evidence is not bound to these exact forecast files')
        if not main.identity.init<=availability.observed_utc<=utc(decision_time):raise PermissionError('Forecast not demonstrably available by decision time')
    if set(main.fields)&set(thermo.fields):raise ValueError('Ambiguous duplicate channels across main and thermo')
    fields=_above_ground({**main.fields,**thermo.fields})
    evidence={'mode':mode,'historical_available_time':None if availability is None else availability.observed_utc.isoformat(),'availability_evidence':None if availability is None else availability.evidence_id,'actual_publication_evidence_verified_by_adapter':False}
    return EnvironmentFrame(main.identity,main.grid,fields,mode,(main.provenance,thermo.provenance,evidence))
