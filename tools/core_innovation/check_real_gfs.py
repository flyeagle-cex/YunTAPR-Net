"""Bounded engineering check from a private four-file schema probe, not an experiment."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse,json,os,re,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.dont_write_bytecode=True;sys.path.insert(0,str(ROOT/'src'))
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
from yuntapr.experimental.core_innovation.gfs import ForecastIdentity,VariableRequest,read_gfs_file,combine_environment
from yuntapr.experimental.core_innovation.grid import frozen_sp04_grid


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--dem-probe',type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'docs/core_innovation/.local'):raise PermissionError('Real-data engineering results and paths stay private in ignored .local')
    source=json.loads(args.probe.read_text(encoding='utf-8'));records=source['records']
    if len(records)!=4:raise ValueError('Exactly four previously selected files required')
    requests_main=tuple(VariableRequest(f'{q}{p}',q,name,p*100.) for q,name in (('u','u-component_of_wind_isobaric'),('v','v-component_of_wind_isobaric')) for p in (500,700,850)) + (
        VariableRequest('ps','surface_pressure','Pressure_surface'),VariableRequest('pwat','precipitable_water','Precipitable_water_entire_atmosphere_single_layer'),VariableRequest('cape','cape','Convective_available_potential_energy_surface'))
    requests_thermo=tuple(VariableRequest(f'{q}{p}',q,name,p*100.) for q,name in (('temperature','Temperature_isobaric'),('relative_humidity','Relative_humidity_isobaric')) for p in (500,700,850))
    grouped={};evidence=[]
    for r in records:
        path=Path(r['path']);match=re.fullmatch(r'gfs_(?:thermo_)?0p25_(\d{10})_f(\d{3})\.nc',path.name)
        if not match:raise ValueError('Explicit forecast filename required')
        init=datetime.strptime(match[1],'%Y%m%d%H').replace(tzinfo=timezone.utc);lead=timedelta(hours=int(match[2]));identity=ForecastIdentity(init,lead,init+lead)
        if r['kind'] not in ('main','thermo'):raise ValueError('Explicit source kind required')
        key=(init.year,identity.init.isoformat(),lead.total_seconds())
        if r['kind'] in grouped.setdefault(key,{}):raise ValueError('Duplicate paired source')
        grouped[key][r['kind']]=read_gfs_file(path,identity,requests_main if r['kind']=='main' else requests_thermo)
    target=frozen_sp04_grid();terrain=None
    if args.dem_probe is not None:
        from yuntapr.experimental.core_innovation.terrain import read_dem_window,terrain_features
        dem=json.loads(args.dem_probe.read_text(encoding='utf-8'))
        window=read_dem_window(dem['source_path'],**dem['window'],elevation_unit='m')
        terrain=terrain_features(window.elevation_m,window.valid,window.grid,elevation_unit='m')
    for key,pair in grouped.items():
        if set(pair)!={'main','thermo'}:raise ValueError('Incomplete explicit pair')
        a,b=pair['main'],pair['thermo']
        frame=combine_environment(a,b,target_valid_time=a.identity.valid,decision_time=a.identity.valid,mode='retrospective')
        mapped=frame.on_grid(target,operator='bilinear_point_candidate')
        values,mask=mapped.stack(tuple(mapped.fields))
        nan_invalid=bool(np.isnan(values[~mask]).all())
        finite_valid=bool(np.isfinite(values[mask]).all())
        if not nan_invalid or not finite_valid:raise AssertionError('Explicit mask/value consistency failed')
        rejected=False
        try:combine_environment(a,b,target_valid_time=a.identity.valid,decision_time=a.identity.valid,mode='operational')
        except PermissionError:rejected=True
        if not rejected:raise AssertionError('Unknown operational availability must reject')
        dote_check=None
        if terrain is not None:
            from yuntapr.experimental.core_innovation.dote import dote_proxy
            on_dem=frame.on_grid(terrain.grid,operator='bilinear_point_candidate')
            us,um=on_dem.stack(tuple('u'+str(p) for p in (500,700,850)))
            vs,vm=on_dem.stack(tuple('v'+str(p) for p in (500,700,850)))
            ps=on_dem.fields['ps']
            proxy=dote_proxy(terrain,us,vs,um&vm,np.array([50000.,70000.,85000.]),ps.values,ps.valid,
                wind_grid=terrain.grid,wind_unit='m/s',pressure_unit='Pa',surface_pressure_unit='Pa')
            if not proxy.valid.any() or not np.isfinite(proxy.orographic_proxy_m_s[proxy.valid]).all():raise AssertionError('Real bounded wind/DEM interface coupling failed')
            dote_check={'status':'PASS_ENGINEERING_INTERFACE_ONLY','shape':proxy.orographic_proxy_m_s.shape,
                'valid_values_finite':True,'mask_excludes_subsurface':bool(np.all(~proxy.valid|proxy.above_ground)),
                'scientific_status':proxy.scientific_status,'formal_DOTE_definition_approved':False}
        evidence.append({'year':key[0],'identity':{'init':a.identity.init.isoformat(),'valid':a.identity.valid.isoformat(),'lead_hours':a.identity.lead.total_seconds()/3600},
            'status':'PASS_BOUNDED_ENGINEERING_INTERFACE_ONLY','native_shape':a.grid.shape,'target_shape':values.shape,'channels':list(mapped.fields),
            'units':{k:f.unit for k,f in mapped.fields.items()},'mask_shape':mask.shape,'invalid_values_are_nan':nan_invalid,'valid_values_finite':finite_valid,
            'historical_operational_without_evidence_rejected':rejected,'source_provenance':frame.provenance,
            'formal_source_adoption_authorized_by_this_check':False,'spatial_operator_frozen':False,'bounded_real_DOTE_check':dote_check})
    report={'scope':'TWO_AUTHORIZED_2023_2024_F000_PAIRS_ENGINEERING_ONLY','test2025_access':False,
        'byte_read_budget_each_file':2*1024**2,'meteorological_fields_decoded':True,'GPU_used':False,'formal_training':False,
        'paired_checks':evidence,'scope_limit':'Two f000 samples do not establish archive-wide quality, operational vintage, or scientific performance.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as handle:json.dump(report,handle,ensure_ascii=False,indent=2);handle.write('\n')
    print(json.dumps({'status':'PASS','pairs':len(evidence),'years':[r['year'] for r in evidence],'real_DOTE_window_checks':sum(r['bounded_real_DOTE_check'] is not None for r in evidence),'result_visibility':'IGNORED_LOCAL_ONLY','operational_without_evidence':'REJECTED'},indent=2))


if __name__=='__main__':main()
