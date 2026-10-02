"""Render source-backed static figures using the existing CPU plotting environment."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from netCDF4 import Dataset

ROOT = Path(__file__).resolve().parents[1]
FORMAL = ROOT / "docs/formal_training/b0_phase_a/runs/run_20261001T035003_243409Z"
BLUE, ORANGE, GREEN = "#0072B2", "#D55E00", "#009E73"


def rows(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def col(data, key):
    return np.array([float(r[key]) if r[key] not in ("", "None") else np.nan for r in data])


def mark(ax):
    ax.axvline(11, color=GREEN, linestyle="--", linewidth=1, label="BEST epoch 11")
    ax.axvline(19, color="#555555", linestyle=":", linewidth=1, label="Early stop epoch 19")
    ax.set(xlim=(.5,19.5), xlabel="Completed epoch", xticks=[1,3,6,9,11,15,19])
    ax.grid(axis="y", alpha=.18)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--history-only", action="store_true", help="Render completed-epoch history when raw validation is unavailable")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise ValueError("Safe run identifier required")
    out = ROOT / "docs/scientific_review/b0_phase_a/runs" / args.run_id
    figs = out / "figures"
    figs.mkdir(exist_ok=False)
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":10, "axes.titlesize":11,
        "axes.labelsize":10, "legend.fontsize":8, "xtick.labelsize":9, "ytick.labelsize":9,
        "axes.spines.top":False, "axes.spines.right":False, "savefig.facecolor":"white"})
    evidence = []
    def save(fig, name, dpi=600, note=None):
        if note:
            fig.text(.5,.006,note,ha="center",fontsize=8)
        fig.tight_layout(rect=(0,.025 if note else 0,1,1))
        file = figs / name
        fig.savefig(file,dpi=dpi)
        width,height = (fig.get_size_inches()*dpi).round().astype(int)
        evidence.append({"path":str(file.relative_to(out)).replace("\\","/"), "bytes":file.stat().st_size,
            "sha256":hashlib.sha256(file.read_bytes()).hexdigest(), "dpi":dpi, "width_pixels":int(width), "height_pixels":int(height),
            "smoothing":False, "figure_source":"persisted formal histories or full 2024 review aggregates"})
        plt.close(fig)
        print("FIGURE " + name, flush=True)
    train,val = rows(FORMAL/"training_history.csv"),rows(FORMAL/"validation_history.csv")
    epochs = col(train,"epoch")
    fig,axes=plt.subplots(1,3,figsize=(12,3.5))
    for ax,title,tkey,vkey in zip(axes,["A. Global core loss","B. Occurrence loss","C. Quantile core loss"],
            ["global_train_core_loss","global_train_L_occ","global_train_L_qr"],
            ["global_val_core_loss","global_L_occ","global_core_L_qr"]):
        ax.plot(epochs,col(train,tkey),"o-",color=BLUE,ms=3,label="Train 2023")
        ax.plot(epochs,col(val,vkey),"s-",color=ORANGE,ms=3,label="Validation 2024")
        ax.set(title=title,ylabel="Global numerator / N valid (dimensionless)")
        mark(ax)
    axes[0].legend()
    save(fig,"loss_curves.png",note="All 19 completed epochs; original data points, no smoothing. Checkpoint selection remains epoch 11.")
    fig,axes=plt.subplots(1,3,figsize=(12,3.5))
    for ax,key,title in zip(axes,["Brier_Score","AUROC","Average_Precision"],["Brier score","AUROC","Average precision"]):
        ax.plot(epochs,col(val,key),"o-",color=BLUE,ms=3)
        mark(ax)
        ax.set(title="D. Validation " + title,ylabel=title+" (dimensionless)")
    axes[0].legend()
    save(fig,"occurrence_metrics.png")
    fig,ax=plt.subplots(figsize=(6.5,4))
    ax.plot(epochs,col(val,"conditional_mean_pinball"),"o-",color=BLUE,ms=4)
    mark(ax);ax.legend();ax.set(title="E. Validation conditional mean pinball",ylabel="Mean pinball in log1p(rate / mm h-1)")
    save(fig,"quantile_metrics.png")
    fig,ax=plt.subplots(figsize=(7,4))
    x=np.column_stack((col(train,"global_update_start"),col(train,"global_update_end"))).ravel()
    lr=np.column_stack((col(train,"LR_start"),col(train,"LR_end"))).ravel()
    ax.plot(x,lr,"o-",color=BLUE,ms=3,label="Recorded epoch start/end LR")
    ax.axvline(64460,color=GREEN,ls="--",label="BEST epoch 11 / update 64460")
    ax.axvline(111340,color="#555555",ls=":",label="Stop epoch 19 / update 111340")
    ax.set(title="F. Recorded learning-rate progression",xlabel="Global optimizer update (historical training)",ylabel="Learning rate",yscale="log")
    ax.legend();ax.grid(axis="y",alpha=.18)
    save(fig,"learning_rate.png",note="Recorded history boundary values only; warmup lower bound is 0 < LR, cosine lower bound is 1e-6.")
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    axes[0].plot(epochs,col(train,"pre_clip_grad_norm_mean"),"o-",color=BLUE,ms=3,label="Mean")
    axes[0].plot(epochs,col(train,"pre_clip_grad_norm_max"),"s-",color=ORANGE,ms=3,label="Maximum")
    axes[0].axhline(5,color="#777777",ls="-.",label="Frozen clip norm 5")
    axes[0].set(title="G. Train pre-clip gradient norm",ylabel="Global L2 norm")
    axes[1].plot(epochs,col(train,"clipping_fraction"),"o-",color=BLUE,ms=3)
    axes[1].set(title="G. Train clipping fraction",ylabel="Fraction of 5860 updates")
    for ax in axes:mark(ax)
    axes[0].legend();save(fig,"gradient_clipping.png")
    gap=rows(out/"generalization_gap.csv")
    fig,ax=plt.subplots(figsize=(7,4))
    ax.plot(col(gap,"epoch"),col(gap,"generalization_gap"),"o-",color=BLUE,ms=4)
    ax.axhline(0,color="#777777",lw=.8);mark(ax);ax.legend()
    ax.set(title="Generalization gap: Validation core - Train core",ylabel="Loss difference (dimensionless)")
    save(fig,"generalization_gap.png")
    if args.history_only:
        (out/"figure_manifest.json").write_text(json.dumps({"status":"RENDERED_AWAITING_VISUAL_REVIEW", "scope":"FORMAL_HISTORY_ONLY",
            "matplotlib_version":matplotlib.__version__, "python":sys.executable, "numpy_version":np.__version__,
            "figures":evidence, "figure_count":len(evidence), "no_smoothing":True, "all_19_epochs_plotted":True,
            "no_2025_data_access":True, "full_reinference_figures":"NOT_RUN_SOURCE_DRIVE_UNAVAILABLE"},indent=2)+"\n",encoding="utf-8",newline="\n")
        return
    month=rows(out/"monthly_metrics.csv")
    mx=np.arange(8)
    def monthly_plot(keys,labels,name,title):
        fig,ax=plt.subplots(figsize=(7,4))
        for key,label,color,marker in zip(keys,labels,[BLUE,ORANGE,GREEN],["o","s","^"]):
            ax.plot(mx,col(month,key),marker+"-",color=color,ms=4,label=label)
        ax.set(xticks=mx,xticklabels=[r["month"][5:] for r in month],xlabel="2024 month",ylabel=title+" (dimensionless)",title=title+" by month | BEST epoch 11")
        ax.legend();ax.grid(axis="y",alpha=.18);save(fig,name)
    monthly_plot(["global_val_core_loss","global_L_occ","global_core_L_qr"],["Core","Occurrence","Quantile core"],"monthly_core_loss.png","Global core loss")
    monthly_plot(["AUROC","Average_Precision"],["AUROC","AP"],"monthly_AUROC_AP.png","Occurrence rank metrics")
    monthly_plot(["Brier_Score"],["Brier score"],"monthly_brier.png","Brier score")
    monthly_plot(["conditional_mean_pinball"],["Conditional pinball"],"monthly_conditional_pinball.png","Conditional pinball (log1p domain)")
    rel=rows(out/"reliability_table.csv")
    fig,axes=plt.subplots(1,2,figsize=(9,4),gridspec_kw={"width_ratios":[1.3,1]})
    axes[0].plot([0,1],[0,1],"--",color="#777777",label="Ideal reliability")
    axes[0].plot(col(rel,"mean_predicted_probability"),col(rel,"observed_rain_frequency"),"o-",color=BLUE,label="Fixed-bin diagnostic")
    axes[0].set(xlim=(0,1),ylim=(0,1),xlabel="Mean predicted probability",ylabel="Observed rain frequency",title="Occurrence reliability | BEST epoch 11")
    axes[0].legend();axes[0].set_aspect("equal")
    axes[1].bar(np.arange(10),col(rel,"count"),color=BLUE,width=.8)
    axes[1].set(xlabel="Fixed probability bin index",ylabel="Valid pixel count",title="Bin support",xticks=[0,3,6,9])
    save(fig,"reliability_diagram.png",note="Bins [0,0.1), ..., [0.9,1]; last includes 1. No probability cutoff or calibration fitted.")
    prob=json.loads((out/"probability_distribution_stats.json").read_text(encoding="utf-8"))
    fig,ax=plt.subplots(figsize=(7,4))
    for group,color,label in (("rainy_truth",BLUE,"Rainy truth (R > 0.1)"),("dry_truth",ORANGE,"Dry truth")):
        counts=np.array(prob["histogram_counts"][group])
        ax.stairs(counts/counts.sum()/.01,prob["histogram_edges"],label=label,color=color,lw=1.2)
    ax.set(xlim=(0,1),xlabel="Predicted p_rain",ylabel="Probability density (bin width 0.01)",title="Predicted probability distributions | BEST epoch 11")
    ax.legend();save(fig,"probability_distributions.png",note="Density-style fixed-bin histogram; no smoothing, KDE or classification threshold.")
    quant=rows(out/"quantile_calibration.csv")
    tau=col(quant,"tau");coverage=col(quant,"conditional_coverage")
    for name,key,title,ylabel,reference in (("quantile_coverage.png","conditional_coverage","Conditional quantile coverage","Observed rainy coverage",True),
            ("quantile_coverage_error.png","coverage_minus_tau","Conditional coverage error","Coverage - tau",False),
            ("quantile_pinball.png","conditional_pinball_log1p_mm_h","Conditional pinball by quantile","Pinball (log1p domain)",False)):
        fig,ax=plt.subplots(figsize=(6.5,4.5))
        ax.plot(tau,col(quant,key),"o-",color=BLUE,ms=3,label="BEST epoch 11")
        if reference:
            ax.plot([0,1],[0,1],"--",color="#777777",label="Ideal: coverage = tau")
            ax.set_ylim(0,1)
        if key=="coverage_minus_tau":ax.axhline(0,color="#777777",ls="--")
        ax.set(xlim=(0,1),xlabel="Conditional quantile level tau",ylabel=ylabel,title=title+" | 32 unchanged quantiles")
        ax.legend();ax.grid(axis="y",alpha=.18);save(fig,name)
    with Dataset("scientific_review_spatial.nc", memory=(out/"spatial_cell_metrics.nc").read_bytes()) as nc:
        lat,lon=nc["lat"][:].data,nc["lon"][:].data
        mask=np.asarray(nc["yunnan_evaluation_mask"][:],dtype=bool)
        if lat.shape!=(100,) or lon.shape!=(100,) or not np.all(np.diff(lat)>0):
            raise ValueError("Actual target latitude must ascend")
        maps=[("rain_frequency","Rain occurrence frequency","Fraction",False),
            ("mean_probability","Mean predicted rain probability","Probability",False),
            ("brier","Cell Brier score","Brier score",False),
            ("conditional_pinball","Conditional pinball (rain count >= 30)","Pinball (log1p domain)",False),
            ("DIAGNOSTIC_PROXY_bias_mm_h","DIAGNOSTIC_PROXY signed bias","mm h-1",True),
            ("DIAGNOSTIC_PROXY_MAE_mm_h","DIAGNOSTIC_PROXY MAE","mm h-1",False),
            ("valid_count","Valid sample count","Count",False),("rainy_count","Rainy sample count","Count",False)]
        for key,title,units,diverging in maps:
            data=np.asarray(nc[key][:],dtype=float)
            values=np.ma.array(data,mask=~mask|~np.isfinite(data))
            fig,ax=plt.subplots(figsize=(6,5))
            options={"cmap":"cividis"}
            if diverging:
                limit=float(np.max(np.abs(values.compressed())))
                options={"cmap":"RdBu_r","norm":TwoSlopeNorm(vmin=-limit,vcenter=0,vmax=limit)}
            elif key in ("rain_frequency","mean_probability"):
                options.update(vmin=0,vmax=1)
            elif key=="valid_count" and np.ptp(values.compressed())==0:
                options.update(vmin=0,vmax=float(values.compressed()[0]))
            image=ax.pcolormesh(lon,lat,values,shading="nearest",rasterized=True,**options)
            ax.contour(lon,lat,mask.astype(float),levels=[.5],colors="#333333",linewidths=.5)
            ax.set(xlabel="Longitude (degrees E)",ylabel="Latitude (degrees N)",title=title+" | BEST epoch 11")
            ax.set_aspect(1/np.cos(np.deg2rad(float(np.mean(lat)))))
            label=(f"Count (all Yunnan cells = {int(values.compressed()[0])})"
                if key=="valid_count" and np.ptp(values.compressed())==0 else units)
            fig.colorbar(image,ax=ax,label=label,shrink=.85)
            save(fig,"spatial_"+key+".png",dpi=300,note="Frozen Yunnan mask only; actual ascending target coordinates, no transpose/flip. Diagnostic display only.")
    rate=rows(out/"rainrate_stratified_metrics.csv")
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    rx=np.arange(7)
    axes[0].bar(rx,col(rate,"pixel_count"),color=BLUE)
    axes[0].set(yscale="log",ylabel="Rainy pixel count (log scale)",title="Rain-rate stratum support | BEST epoch 11")
    axes[1].plot(rx,col(rate,"DIAGNOSTIC_PROXY_Bias_mm_h"),"o-",color=BLUE,label="Proxy bias")
    axes[1].plot(rx,col(rate,"DIAGNOSTIC_PROXY_MAE_mm_h"),"s-",color=ORANGE,label="Proxy MAE")
    axes[1].set(ylabel="mm h-1",title="Descriptive proxy errors by true rate");axes[1].legend()
    for ax in axes:
        ax.set_xticks(rx,[r["rate_bin_mm_h"] for r in rate],rotation=35,ha="right")
        ax.set_xlabel("True rain-rate bin (mm h-1)")
    save(fig,"rainrate_diagnostics.png",note="DESCRIPTIVE_RATE_BINS_ONLY; extreme definition NOT_FROZEN. No loss reweighting or exact expectation claim.")
    (out/"figure_manifest.json").write_text(json.dumps({"status":"RENDERED_AWAITING_VISUAL_REVIEW","matplotlib_version":matplotlib.__version__,
        "python":sys.executable,"numpy_version":np.__version__,"figures":evidence,"figure_count":len(evidence),
        "no_smoothing":True,"all_19_epochs_plotted":True,"no_2025_data_access":True},indent=2)+"\n",encoding="utf-8",newline="\n")


if __name__=="__main__":
    main()
