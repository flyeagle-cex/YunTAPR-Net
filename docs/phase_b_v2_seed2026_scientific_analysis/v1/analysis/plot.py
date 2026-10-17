"""Ten reproducible manuscript figures: vector PDF/SVG and 600-dpi PNG."""
import os,re,sys
from common import OUT,read,save
sys.path.insert(0,str(OUT/'.local/deps'))
os.environ['MPLCONFIGDIR']=str(OUT/'.local/mpl-cache')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COL={'E0':'#0072B2','E1':'#D55E00','E2':'#009E73'}
STYLE={'B0':'--','B1':'-'};MARK={'B0':'o','B1':'s'}
plt.rcParams.update({'font.family':'sans-serif','font.sans-serif':['Arial','DejaVu Sans'],'font.size':9,
 'axes.labelsize':9,'axes.titlesize':10,'xtick.labelsize':8,'ytick.labelsize':8,'legend.fontsize':8,
 'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none'})
D=read(OUT/'ANALYSIS_DATA.json');FIG=OUT/'figures';FIG.mkdir(exist_ok=True);record=[]
def export(fig,name,title):
 fig.savefig(FIG/(name+'.pdf'),bbox_inches='tight',metadata={'Title':title,'CreationDate':None})
 fig.savefig(FIG/(name+'.svg'),bbox_inches='tight',metadata={'Title':title,'Date':None})
 svg=FIG/(name+'.svg');svg.write_bytes(re.sub(rb'[ \t]+\n',b'\n',svg.read_bytes().replace(b'\r\n',b'\n')))
 fig.savefig(FIG/(name+'.png'),bbox_inches='tight',dpi=600)
 record.append(dict(name=name,title=title,width_inches=fig.get_figwidth(),height_inches=fig.get_figheight(),scope='2024 development / seed2026 only'))
 plt.close(fig)
def lines(ax,key,models=('B0','B1'),arms=('E0','E1','E2')):
 for arm in arms:
  for model in models:
   r=[x for x in D['curves'] if x['model']==model and x['arm']==arm]
   ax.plot([x['epoch'] for x in r],[x[key] for x in r],color=COL[arm],ls=STYLE[model],marker=MARK[model],ms=3,label=f'{model}/{arm}')
 ax.set_xticks(range(1,10));ax.set_xlabel('Epoch');ax.grid(alpha=.18,axis='y')
def label(ax,text):ax.text(-.12,1.04,text,transform=ax.transAxes,fontweight='bold',va='bottom')
def summary(model,arm):return next(x for x in D['final'] if x['model']==model and x['arm']==arm)

def main():
 fig,axs=plt.subplots(2,3,figsize=(7.2,4.5),layout='constrained')
 for j,arm in enumerate(COL):
  lines(axs[0,j],'weighted_train_loss',arms=(arm,));lines(axs[1,j],'core_fp64',arms=(arm,))
  axs[0,j].set_title(arm);axs[0,j].set_ylabel('Weighted training objective')
  axs[1,j].set_ylabel('Common Core (FP64)');axs[0,j].legend(frameon=False)
  label(axs[0,j],chr(65+j));label(axs[1,j],chr(68+j))
 export(fig,'fig01_training_common_core','Nine-epoch arm-specific training objectives and unified development Core')
 fig,axs=plt.subplots(2,2,figsize=(7.2,4.8),layout='constrained')
 for ax,key,title in zip(axs.flat,['brier','auroc','average_precision','conditional_pinball'],['Brier score','AUROC','Average precision','Conditional Pinball [log1p(mm/h)]']):
  lines(ax,key);ax.set_ylabel(title)
 axs[0,0].legend(ncol=2,frameon=False);export(fig,'fig02_development_curves','Nine-epoch development metrics, six runs')
 fig,axs=plt.subplots(2,2,figsize=(7.2,5.2),layout='constrained')
 for j,model in enumerate(('B0','B1')):
  ax=axs[0,j];ax.plot([0,1],[0,1],':',color='.4',label='Perfect reliability')
  for arm in COL:
   r=[x for x in D['reliability'] if x['model']==model and x['arm']==arm and x['n']]
   p=[x['mean_probability'] for x in r];y=[x['frequency'] for x in r]
   ax.plot(p,y,color=COL[arm],marker='o',ms=3,label=arm)
   rare=[x for x in r if x['n']<100]
   ax.scatter([x['mean_probability'] for x in rare],[x['frequency'] for x in rare],s=45,facecolors='white',edgecolors=COL[arm],zorder=4)
   b=[x for x in D['reliability'] if x['model']==model and x['arm']==arm]
   axs[1,j].plot(np.arange(10)/10+.05,[x['n'] if x['n'] else np.nan for x in b],color=COL[arm],marker='o',ms=3,label=arm)
  ax.set(xlim=(0,1),ylim=(0,1),xlabel='Mean predicted rain probability',ylabel='Observed rain frequency',title=model);ax.legend(frameon=False,fontsize=7)
  axs[1,j].set(xlabel='Fixed probability bin center',ylabel='Valid scene-pixel exposures',yscale='log',xlim=(0,1));axs[1,j].grid(alpha=.15,axis='y')
 export(fig,'fig03_reliability','Fixed ten-bin reliability and exposure counts; hollow points have fewer than 100 exposures')
 fig,axs=plt.subplots(2,2,figsize=(7.2,4.8),layout='constrained')
 for j,model in enumerate(('B0','B1')):
  axs[0,j].plot([0,1],[0,1],':',color='.3')
  for arm in COL:
   r=[x for x in D['quantiles'] if x['model']==model and x['arm']==arm]
   axs[0,j].plot([x['tau'] for x in r],[x['coverage'] for x in r],color=COL[arm],label=arm)
   tail=[x for x in r if x['tau']>.85]
   axs[1,j].plot([x['tau'] for x in tail],[100*x['signed_bias'] for x in tail],marker='o',ms=3,color=COL[arm],label=arm)
  axs[0,j].set(title=model,xlabel='Target conditional quantile level',ylabel='Observed wet-pixel coverage',xlim=(0,1),ylim=(0,1));axs[0,j].legend(frameon=False)
  axs[1,j].axhline(0,color='.4',ls=':');axs[1,j].set(xlabel='Upper quantile level',ylabel='Coverage minus target (pp)')
 export(fig,'fig04_quantile_coverage','All 32 conditional quantile coverages; denominator 4,496,600 wet exposures')
 fig,axs=plt.subplots(1,2,figsize=(7.2,2.6),layout='constrained')
 for ax,contrast,mult,title in zip(axs,('E1-E0','E2-E0'),(1,100),('Brier difference: E1 - E0','Absolute q32 coverage error: E2 - E0 (pp)')):
  for j,model in enumerate(('B0','B1')):
   r=next(x for x in D['contrasts'] if x['model']==model and x['contrast']==contrast)
   ax.errorbar(mult*r['difference'],j,xerr=[[mult*(r['difference']-r['lower'])],[mult*(r['upper']-r['difference'])]],fmt='o',color=COL['E1' if contrast=='E1-E0' else 'E2'],capsize=4)
  ax.axvline(0,color='.3',ls=':');ax.set(yticks=[0,1],yticklabels=['B0','B1'],ylim=(-.6,1.6),xlabel=title)
 fig.suptitle('Paired 95% exploratory percentile intervals; lower is favorable',fontsize=10)
 export(fig,'fig05_registered_contrasts','Four predeclared contrasts; 35 seven-day UTC blocks, 2,000 paired bootstrap draws')
 labels=['(0.1,1]','(1,5]','(5,10]','(10,20]','(20,30]','(30,50]','>50']
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.0),layout='constrained')
 for ax,model in zip(axs,('B0','B1')):
  for arm in COL:
   r=[x for x in D['strata'] if x['model']==model and x['arm']==arm]
   ax.plot(range(7),[x['conditional_pinball'] for x in r],color=COL[arm],marker='o',ms=3,label=arm)
  ax.set(title=model,xticks=range(7),xticklabels=labels,ylabel='Conditional Pinball [log1p(mm/h)]',xlabel='IMERG reference rate stratum (mm/h)');ax.tick_params(axis='x',rotation=35);ax.legend(frameon=False)
 export(fig,'fig06_rain_intensity','Reference-intensity-stratified Conditional Pinball; n=69 in the >50 mm/h stratum')
 fig,axs=plt.subplots(2,3,figsize=(7.2,4.3),layout='constrained')
 for ax,key,name in zip(axs.flat,['brier','auroc','average_precision','conditional_pinball','core_fp64','q32_absolute_error'],['Brier','AUROC','AP','Conditional Pinball','Common Core','Abs. q32 error']):
  r=D['temporal'];ax.axhline(0,color='.4',ls=':');ax.plot(range(3),[x[key] for x in r],marker='o',color='#333333')
  ax.set(xticks=range(3),xticklabels=['E0','E1','E2'],ylabel='B1 - B0',title=name)
 export(fig,'fig07_temporal_contribution','Descriptive six-frame minus single-frame differences; no new confirmatory interaction test')
 fig,axs=plt.subplots(1,3,figsize=(7.2,3.2),layout='constrained');runlabels=[m+'/'+a for m,a in [('B0','E0'),('B1','E0'),('B0','E1'),('B1','E1'),('B0','E2'),('B1','E2')]]
 for ax,threshold in zip(axs[:2],(50,100)):
  r=[next(x for x in D['tails'] if x['model']==label.split('/')[0] and x['arm']==label.split('/')[1] and x['threshold_mm_h']==threshold) for label in runlabels]
  wet=[x['rain'] for x in r];dry=[x['dry'] for x in r]
  ax.bar(range(6),wet,color='#0072B2',label='Reference rain');ax.bar(range(6),dry,bottom=wet,color='#E69F00',label='Reference dry')
  ax.set(xticks=range(6),xticklabels=runlabels,ylabel='Scene-pixel exposures',title=f'Conditional q32 > {threshold} mm/h',yscale='symlog',ylim=(0,max(x['exposures'] for x in r)*1.6+2));ax.tick_params(axis='x',rotation=60)
  for i,x in enumerate(r):ax.text(i,x['exposures']*1.04+0.2,str(x['exposures']),ha='center',fontsize=7)
 axs[0].legend(frameon=False,fontsize=6)
 vals=[summary(*label.split('/'))['q32_max_mm_h'] for label in runlabels];axs[2].plot(range(6),vals,'o',color='#333333');axs[2].set(xticks=range(6),xticklabels=runlabels,ylabel='Maximum conditional q32 (mm/h)',ylim=(0,max(vals)*1.15));axs[2].tick_params(axis='x',rotation=60)
 export(fig,'fig08_upper_tail','Conditional upper-tail exposures and maxima; not independent extreme events or deterministic forecasts')
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.0),layout='constrained')
 for ax,arm in zip(axs,('E1','E2')):
  ax.axhline(0,color='.4',ls=':')
  for model in ('B0','B1'):
   a=[x['conditional_pinball'] for x in D['strata'] if x['model']==model and x['arm']==arm]
   b=[x['conditional_pinball'] for x in D['strata'] if x['model']==model and x['arm']=='E0']
   ax.plot(range(7),np.array(a)-b,color=COL[arm],ls=STYLE[model],marker=MARK[model],ms=3,label=model)
  ax.set(xticks=range(7),xticklabels=labels,title=arm+' - E0',ylabel='Conditional Pinball difference',xlabel='Reference rain rate (mm/h)');ax.tick_params(axis='x',rotation=35);ax.legend(frameon=False)
 export(fig,'fig09_intensity_side_effects','Descriptive stratified Pinball changes; positive values mean deterioration')
 fig,axs=plt.subplots(1,2,figsize=(7.2,3.1),layout='constrained')
 for ax,key,title in zip(axs,('train_seconds','validation_seconds'),('Observed full training epoch','Observed full validation pass')):
  for j,model in enumerate(('B0','B1')):
   r=[x[key]/60 for x in D['timing'] if x['model']==model];offset=np.linspace(-.13,.13,len(r))
   ax.scatter(j+offset,r,s=16,color='#0072B2' if model=='B0' else '#D55E00',alpha=.6)
   ax.plot([j-.22,j+.22],[np.median(r)]*2,color='black',lw=2)
  ax.set(xticks=[0,1],xticklabels=['B0 (27 epochs)','B1 (27 epochs)'],title=title,ylabel='Elapsed wall time (minutes)',yscale='log')
 export(fig,'fig10_observed_resources','Observed timings, including slow validation outlier; black lines are medians, not confidence intervals')
 save('FIGURE_INDEX.json',dict(figures=record,formats=['PDF','SVG','PNG'],png_dpi=600,uncertainty='Only fig05 shows predeclared paired exploratory intervals; other plots are single-seed point summaries'))
 print('TEN_FIGURES_EXPORTED')
if __name__=='__main__':main()
