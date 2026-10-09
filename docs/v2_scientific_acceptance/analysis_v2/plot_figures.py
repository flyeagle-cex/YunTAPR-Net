"""Read-only, user-authorized figures from completed aggregate observations."""
import csv,json,hashlib,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

RUN=Path(__file__).resolve().parents[1]/'runs/run_20261009T112710_013267Z'
OUT=RUN/'delivery_v2'; FIG=OUT/'figures'
MODELS=('B0_MATCHED_V2','B1_V2'); LABELS=('B0-Matched-v2','B1-v2'); COLORS=('#1766a5','#c86713')
def rows(name):
    with (OUT/name).open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
def val(items,key):return np.array([float(x[key]) for x in items])
def ident(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(fig,name):
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight',facecolor='white')
    fig.savefig(FIG/(name+'.png'),dpi=300,bbox_inches='tight',facecolor='white')
    plt.close(fig)
def main():
    assert (OUT/'LOCAL_SCIENTIFIC_PLOTTING_AUTHORIZATION.json').is_file()
    FIG.mkdir()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','axes.titlesize':11,'axes.labelsize':10})
    rel=rows('reliability_fixed_bins.csv')
    fig,ax=plt.subplots(1,2,figsize=(10.8,4.5),layout='constrained',gridspec_kw={'width_ratios':[1.4,1]})
    for model,label,color in zip(MODELS,LABELS,COLORS):
        data=[x for x in rel if x['model']==model and int(x['count'])>0]
        x=val(data,'mean_probability');y=val(data,'observed_frequency')
        ax[0].plot(x,y,'o-',color=color,label=label,markersize=4)
        ax[0].vlines(x,val(data,'observed_ci_lower'),val(data,'observed_ci_upper'),color=color,alpha=.65,lw=1.2)
        ax[0].hlines(y,val(data,'predicted_ci_lower'),val(data,'predicted_ci_upper'),color=color,alpha=.45,lw=1)
        ax[1].plot(val(data,'bin_index'),val(data,'count'),'o-',color=color,label=label,markersize=4)
    ax[0].plot([0,1],[0,1],'--',color='#777777',lw=1,label='Calibration reference')
    ax[0].set(xlabel='Mean predicted occurrence probability',ylabel='Observed rainy frequency',xlim=(0,1),ylim=(0,1),title='Fixed 10 bins; pointwise paired week-block intervals')
    ax[0].legend(loc='upper left',fontsize=8)
    ax[1].set(xlabel='Fixed probability bin index (0 to 9)',ylabel='Scene-pixel exposures',yscale='log',xticks=range(10),title='Bin counts (empty bins omitted)')
    for a in ax:a.grid(alpha=.18)
    fig.suptitle('2024 development: occurrence reliability | 36,018,430 valid Yunnan exposures',fontsize=12)
    save(fig,'occurrence_reliability')
    cov=rows('conditional_quantile_calibration.csv')
    fig,ax=plt.subplots(1,2,figsize=(10.8,4.5),layout='constrained')
    for model,label,color in zip(MODELS,LABELS,COLORS):
        data=[x for x in cov if x['model']==model];t=val(data,'tau');v=val(data,'coverage');low=val(data,'coverage_ci_lower');high=val(data,'coverage_ci_upper')
        ax[0].plot(t,v,color=color,label=label,lw=1.7)
        ax[0].fill_between(t,low,high,color=color,alpha=.18)
        ax[1].plot(t,v-t,color=color,label=label,lw=1.7)
        ax[1].fill_between(t,low-t,high-t,color=color,alpha=.18)
    ax[0].plot([0,1],[0,1],'--',color='#777777',lw=1)
    ax[1].axhline(0,color='#777777',ls='--',lw=1)
    ax[0].set(xlabel='Frozen conditional tau',ylabel='Empirical conditional coverage',xlim=(0,1),ylim=(0,1),title='All 32 quantiles; true rainy valid Yunnan cells')
    ax[1].set(xlabel='Frozen conditional tau',ylabel='Coverage minus tau',title='Pointwise 95% intervals (not simultaneous bands)')
    for a in ax:a.legend(fontsize=9);a.grid(alpha=.18)
    fig.suptitle('2024 development: conditional quantile calibration | 4,496,600 rainy exposures',fontsize=12)
    save(fig,'conditional_quantile_calibration')
    groups=['(0.1,1]','(1,5]','(5,10]','(10,20]','(20,30]','(30,50]','(50,inf)']
    data=rows('PAIRED_STRATIFIED_ANALYSIS.csv')
    fig,ax=plt.subplots(figsize=(10.8,4.8),layout='constrained')
    counts=[]
    for j,(model,label,color) in enumerate(zip(MODELS,LABELS,COLORS)):
        selected=[next(x for x in data if x['model']==model and x['group']==g) for g in groups]
        x=np.arange(len(groups))+(-.12 if j==0 else .12)
        ax.vlines(x,val(selected,'conditional_pinball_ci_lower'),val(selected,'conditional_pinball_ci_upper'),color=color,alpha=.8)
        ax.plot(x,val(selected,'conditional_pinball'),'o-',color=color,label=label,lw=1.4,markersize=5)
        if j==0:counts=[int(x['N_rain']) for x in selected]
    labels=[g.replace('inf','infinity')+'\nN='+format(n,',') for g,n in zip(groups,counts)]
    ax.set(xticks=range(len(groups)),xticklabels=labels,xlabel='Predeclared IMERG truth strata (mm/h); N = scene-pixel exposures',ylabel='Conditional mean pinball [log1p(mm/h)]',title='2024 development: fixed truth rain strata | pointwise week-block intervals')
    ax.legend();ax.grid(axis='y',alpha=.2)
    save(fig,'rain_stratified_pinball')
    cases=[]
    for model in MODELS:
        with (RUN/model/'threshold_locations.jsonl').open(encoding='utf-8') as stream:
            cases.extend({'model':model,**json.loads(line)} for line in stream if 'YUNNAN_INSIDE' in line)
    assert all(c['region']=='YUNNAN_INSIDE' and c['q32_log']>np.log1p(50) for c in cases)
    with (FIG/'inside_q32_gt50_observations.csv').open('x',encoding='utf-8',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(cases[0]));w.writeheader();w.writerows(cases)
    fig,ax=plt.subplots(1,2,figsize=(10.8,4.8),layout='constrained',sharex=True,sharey=True)
    for model,label,a in zip(MODELS,LABELS,ax):
        selected=[c for c in cases if c['model']==model and c['target_valid']]
        y=np.expm1(np.array([c['q32_log'] for c in selected]));x=np.array([c['truth_mm_h'] for c in selected]);p=np.array([c['p_rain'] for c in selected])
        assert np.isfinite(x).all() and np.isfinite(y).all()
        sc=a.scatter(x,y,c=p,cmap='viridis',norm=Normalize(0,1),s=13,alpha=.65,edgecolors='none')
        a.axhline(100,color='#777777',lw=.8,ls='--')
        a.set(xscale='symlog',yscale='log',xlabel='IMERG truth (mm/h; symlog keeps zero)',title=label+' | N='+str(len(selected))+' selected exposures')
        a.grid(alpha=.15)
    ax[0].set_ylabel('Conditional q32 = expm1(qlog) (mm/h)')
    fig.colorbar(sc,ax=ax,label='Occurrence probability',shrink=.85)
    fig.suptitle('2024 development: Yunnan q32 > 50 diagnostic subset | tau = 0.984375',fontsize=12)
    save(fig,'inside_q32_vs_truth')
    inputs=[OUT/n for n in ('reliability_fixed_bins.csv','conditional_quantile_calibration.csv','PAIRED_STRATIFIED_ANALYSIS.csv','LOCAL_SCIENTIFIC_PLOTTING_AUTHORIZATION.json')]+[RUN/m/'threshold_locations.jsonl' for m in MODELS]
    with (OUT/'figure_provenance.json').open('x',encoding='utf-8') as stream:json.dump({'status':'FOUR_SOURCE_BACKED_FIGURES_GENERATED_VISUAL_AUDIT_PENDING','generator':ident(Path(__file__).resolve()),'python':sys.executable,'matplotlib':matplotlib.__version__,'numpy':np.__version__,'sources':[ident(p) for p in inputs],'outputs':[ident(p) for p in FIG.iterdir()],'scope':'Exploratory 2024 development only; local plotting exception explicitly approved; no inference or training'},stream,ensure_ascii=False,indent=2)
    print('4 figures / SVG + 300dpi PNG; no model/raw source opened')
if __name__=='__main__':main()
