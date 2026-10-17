"""Wire two new seed scopes to the verified operator, without launching it.

Training/validation arithmetic, same-byte checkpoint IO, external Job ownership,
dependency verification and resource code are reused. Only fresh scope,
run order, seed and non-recovery ledger initialization change. Authorization
remains an unconditional refusal until a NEW human execution instruction.
"""
from pathlib import Path
import ast,hashlib,json

ROOT=Path(__file__).absolute().parents[2]
BASE=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v3'
DEST=ROOT/'src/yuntapr/experimental/phase_b_v2_multiseed_candidate'
DOC=ROOT/'docs/phase_b_v2_multiseed_preparation/v1'
PINS=json.loads((ROOT/'docs/phase_b_v2_seed2026_scientific_analysis/v1/manifest.json').read_bytes())['public_sources_and_local_aggregate_receipt_sha256']
records={}
def source(name):
    path=BASE/(name+'.py');raw=path.read_bytes();key=path.relative_to(ROOT).as_posix()
    if hashlib.sha256(raw).hexdigest()!=PINS[key]:raise ValueError('VERIFIED_OPERATOR_SOURCE_CHANGED')
    records[key]=PINS[key];return raw.decode('utf-8')
def change(text,old,new,count=1):
    if text.count(old)!=count:raise ValueError('PRECISE_ADAPTATION_COUNT:'+old[:80])
    return text.replace(old,new)
def write(name,text):
    ast.parse(text);(DEST/(name+'.py')).write_bytes(text.encode('utf-8'))
def main():
    DEST.mkdir(exist_ok=False)
    write('__init__','"""Prepared seeds2027/2028; no real execution authorization is installed."""\n')
    # No changes to the numerical methods in these modules.
    for name in ('resources','supervisor','control','evaluation','analysis','checkpoint','engine','worker','quota'):
        text=source(name)
        if name in ('control','supervisor'):
            text=text.replace('yuntapr.training.phase_b_v2_seed2026_operator_v3.','yuntapr.experimental.phase_b_v2_multiseed_candidate.')
        if name=='control':
            text=change(text,'    release=verify_release()','    release=verify_release()\n    from .protocol import require_predecessor\n    require_predecessor()')
        if name=='supervisor':
            text=change(text,"from .protocol import ROOT,OUT,LOCAL,CAMPAIGN,LIMITS,atomic_json,verify_release,session_root,owned_json", "from .protocol import ROOT,OUT,LOCAL,DB,CAMPAIGN,LIMITS,atomic_json,verify_release,session_root,owned_json")
            text=change(text,"db=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v3.sqlite'",'db=DB')
        if name=='evaluation':
            text=change(text,'from .protocol import DEV_N,LIMITS,digest','from .protocol import DEV_N,LIMITS,digest,SEED')
            text=change(text,"report['scope']='FORMAL_PHASE_B_V2_SEED2026'","report['scope']=f'FORMAL_PHASE_B_V2_SEED{SEED}'")
        if name=='analysis':
            text=change(text,'from .protocol import OUT,run_id,atomic_json,digest','from .protocol import OUT,run_id,atomic_json,digest,SEED')
            # Bootstrap PCG64 seed2026 is a fixed statistical convention, NOT model seed.
            text=change(text,'dict(model=model,seed=2026,contrast=', 'dict(model=model,seed=SEED,contrast=')
        if name=='checkpoint':
            text=change(text,'from .protocol import ROOT,LIMITS,LOCAL,CAMPAIGN,STEPS,TRAIN_N,DEV_N,digest,epoch_order,atomic_json',
                        'from .protocol import ROOT,LIMITS,LOCAL,CAMPAIGN,STEPS,TRAIN_N,DEV_N,TOTAL,SEED,digest,epoch_order,atomic_json')
            text=change(text,"SCHEMA='FORMAL_PHASE_B_V2_SEED2026_OPERATOR_V3_LAST_v1'","SCHEMA=f'FORMAL_PHASE_B_V2_SEED{SEED}_FRESH_LAST_v1'")
            text=change(text,"q['limit']!=298474","q['limit']!=TOTAL")
            text=change(text,"q['old_campaign_reserved']!=193914 or q['abandoned_old_updates']!=16162", "q['old_campaign_reserved']!=0 or q['abandoned_old_updates']!=0")
            text=change(text,"        recovery=self.identity.get('recovery')\n        if recovery and epoch==8 and p['parent_last_sha']!=recovery['last_sha256']:\n            raise ValueError('EXACT_APPROVED_RECOVERY_PARENT')\n",'')
        if name=='engine':
            text=change(text,'No BEST selection or automatic retry. Only the approved epoch7 recovery exists.',
                        'No BEST selection, historical recovery or automatic retry. Prepared fresh seeds only.')
            text=change(text,'DEV_N,digest,atomic_json','DEV_N,SEED,digest,atomic_json')
            begin=text.index('        from .recovery import completed_results');end=text.index('    def run_one(',begin)
            text=text[:begin]+'''        self.completed=[]
        self.initial_by_model={}
        for model,arm in ORDER:
            ident=run_id(model,arm);state=ledger.run_row(ident)
            if state['status']=='COMPLETE':
                result=json.loads((OUT/(ident+'.json')).read_bytes())
                if result['run_id']!=ident or result['epochs'][-1]['checkpoint']['payload_sha256']!=state['last_sha']:
                    raise ValueError('SAME_CAMPAIGN_COMPLETED_RESULT_IDENTITY')
                initial=result['initial_sha256']
                if model in self.initial_by_model and self.initial_by_model[model]!=initial:
                    raise ValueError('CROSS_ARM_FRESH_INITIAL_IDENTITY')
                self.initial_by_model[model]=initial
'''+text[end:]
            text=change(text,'with seeded_environment(2026):','with seeded_environment(SEED):')
            text=change(text,'fresh_paired_models(2026)','fresh_paired_models(SEED)')
            text=change(text,'arm=arm,seed=2026','arm=arm,seed=SEED')
            begin=text.index("            resumed=model_kind=='B1_V2' and arm=='E1'");end=text.index('            if existing:',begin)
            text=text[:begin]+text[end:]
            text=change(text,"row['epoch'] if row['epoch']>7 or not resumed else 0","row['epoch']")
            text=change(text,"existing and row['epoch']>0 and (row['epoch']>7 or not resumed)","existing and row['epoch']>0")
            begin=text.index('                elif resumed:');end=text.index('                for epoch in range',begin)
            text=text[:begin]+text[end:]
            text=change(text,'for model,arm in ORDER[3:]:','for model,arm in ORDER:')
            text=text[:text.index('def boundary_flags():')]+'''def boundary_flags():
    return dict(selected_seed=SEED,execution_scope='PREPARATION_ONLY_PENDING_NEW_HUMAN_INSTRUCTION',
        FORMAL_SCIENTIFIC_EXECUTION_AUTHORIZED=False,FINALFIT_AUTHORIZED=False,
        HISTORICAL_RECOVERY_RATIFICATION='NOT_GRANTED',TEST_2025_AUTHORIZED=False,
        PIXELS_2025_READ=0,HISTORICAL_2025_PATH_ATTRIBUTE_ACCESS='NOT_INSTRUMENTED',
        statistics='M-C_EXPLORATORY',no_automatic_retry_or_recovery=True)
'''
        if name=='worker':
            text=change(text,'    from .recovery import Guard\n','')
            text=change(text,'budget=ledger=adapter=ancestor_guard=None','budget=ledger=adapter=None')
            begin=text.index('        # Retain no-write/no-delete native handles');end=text.index('        ledger=Ledger()',begin)
            text=text[:begin]+text[end:]
            text=change(text,'        if ancestor_guard is not None:ancestor_guard.close()\n','')
        if name=='quota':
            text=change(text,'    def __init__(self):','    def __init__(self):\n        from .protocol import verify_release\n        release=verify_release()')
            text=change(text,'    def initialize(cls,release):','    def initialize(cls,release):\n        from .protocol import verify_release\n        if verify_release()!=release:raise PermissionError(\'EXACT_NEW_SEED_EXECUTION_RELEASE_REQUIRED\')')
            text=change(text,'from yuntapr.training.phase_b_v2_seed2026_resume_v2.quota import Ledger as BaseLedger','from yuntapr.training.phase_b_v2_seed2026.quota import Ledger as BaseLedger')
            text=change(text,"    return json.loads((OUT/'ancestor.json').read_bytes())","    return dict(elapsed_seconds=0.,content_bytes=0)")
            text=change(text,"self.ancestor_sha=json.loads((OUT/'release.json').read_bytes())['ancestor_receipt_sha256']","self.ancestor_sha=release['source_sha256']")
            text=change(text,"witness=ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v3.once'","witness=DB.with_suffix('.once')")
            begin=text.index('                if i<3:');end=text.index("                con.execute('INSERT INTO runs",begin)
            text=text[:begin]+"                values=(ident,i,'PENDING',0,0,None)\n"+text[end:]
            line=next(x for x in text.splitlines(True) if "elif ident==run_id('B1_V2','E1')" in x)
            text=change(text,line,'')
            text=change(text,"'298474_COMBINED_HARD_CAP'","'282312_INDEPENDENT_SEED_HARD_CAP'")
        write(name,text)
    recovery=source('recovery');tree=ast.parse(recovery)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='apply_validated_state')
    write('recovery','"""Only verified clean same-campaign LAST continuation; no historical adoption."""\n'+ast.get_source_segment(recovery,fn)+'\n')
    (DOC/'SOURCE_REUSE_INPUTS.json').write_bytes((json.dumps(records,indent=2)+'\n').encode())
    print('ISOLATED_SCOPE_ADAPTERS_GENERATED_NO_EXECUTION')
if __name__=='__main__':main()
