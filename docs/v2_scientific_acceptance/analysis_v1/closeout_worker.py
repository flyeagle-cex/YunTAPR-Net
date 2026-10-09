"""Finish registered statistics after read-only inference; pause before figure/publication closure."""
from pathlib import Path
import time,json,subprocess,sys,hashlib,traceback
def main():
    package=Path(__file__).resolve().parent;repo=package.parents[2]
    run=Path(json.loads((package/'current_run.json').read_text())['run'])
    def status(value):
        temporary=run/'analysis_closeout_status.tmp'
        temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');temporary.replace(run/'analysis_closeout_status.json')
    try:
        code={str(package/n):hashlib.sha256((package/n).read_bytes()).hexdigest() for n in ('analyze.py','build_reports.py','sufficient_stats.py','analysis_preregistration.json')}
        with (run/'statistical_closeout_code_binding.json').open('x',encoding='utf-8') as f:json.dump(code,f,indent=2)
        while not (run/'paired_best_metrics.json').exists():
            if (run/'failure.json').exists(): raise RuntimeError('Read-only inference failed; STOP, no retry/resume')
            time.sleep(10)
        result=json.loads((run/'paired_best_metrics.json').read_text())
        assert result['status']=='PAIRED_SCIENTIFIC_ACCEPTANCE_READ_ONLY_2024_PASS'
        for k,v in result['models'].items():
            assert v['BEST']['epoch']==9 and v['REVIEW_FORWARD_CALLS']==1313
            assert v['io']['2025_RAW_ACCESS']==v['io']['2025_PIXELS_READ']==0
            assert v['model_state_sha256_before']==v['model_state_sha256_after']
            assert len(set(v['supplemental_statistics']['scene_ids']))==10501
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in code.items())
        for script in ('analyze.py','build_reports.py'):
            status({'status':'RUNNING_REGISTERED_STATISTICS','stage':script,'MODEL_PARAMETERS_UPDATED':False,'OPTIMIZER_STEPS':0,'2025_RAW_ACCESS':0})
            with (run/(script+'.stdout.log')).open('xb') as out,(run/(script+'.stderr.log')).open('xb') as err:
                completed=subprocess.run([sys.executable,'-B',str(package/script),'--run',str(run)],cwd=repo,stdout=out,stderr=err)
            if completed.returncode: raise RuntimeError(script+' failed; no silent retry')
        assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha for path,sha in code.items())
        names=('PHASE_A_SCIENTIFIC_ACCEPTANCE_PACKET.md','PAIRED_STRATIFIED_ANALYSIS.csv','PROBABILITY_CALIBRATION_REPORT.md','UPPER_TAIL_PHYSICAL_REVIEW.md','RECOVERY_GOVERNANCE_DEVIATION.md','RESEARCHER_SCIENTIFIC_DECISION_FORM.md')
        assert all((run/n).is_file() for n in names)
        status({'status':'READ_ONLY_STATISTICS_COMPLETE_FIGURES_PDF_PUBLICATION_PENDING','requested_text_and_table_deliverables':{n:hashlib.sha256((run/n).read_bytes()).hexdigest() for n in names},
            'READ_ONLY_INFERENCE_FORWARDS_ADDED':2626,'READ_ONLY_RAW_SOURCE_OPENS':sum(v['io']['RAW_SOURCE_OPENS'] for v in result['models'].values()),
            'FORMAL_OPTIMIZER_STEPS_ADDED':0,'MODEL_PARAMETERS_UPDATED':False,'BACKWARD_CALLS':0,'2025_RAW_ACCESS':0,'2025_PIXELS_READ':0,
            'V2_PHASE_B_AUTHORIZED':False,'RESEARCHER_SCIENTIFIC_APPROVAL_REQUIRED':True,'FIGURE_STATUS':'PENDING_WEB_GPT_ACCESS_OR_RESEARCHER_LOCAL_PLOT_EXCEPTION',
            'PDF_STATUS':'NOT_YET_GENERATED','GITHUB_PUBLICATION_STATUS':'NOT_YET_PUBLISHED','AUTOMATIC_TRAIN_OR_RESUME':False})
    except BaseException as exc:
        value={'status':'ANALYSIS_CLOSEOUT_FAILED_STOP','error':repr(exc),'traceback':traceback.format_exc(),'FORMAL_OPTIMIZER_STEPS_ADDED':0,'2025_RAW_ACCESS':0,'V2_PHASE_B_AUTHORIZED':False}
        with (run/'closeout_failure.json').open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
        status(value);raise
if __name__=='__main__':main()
