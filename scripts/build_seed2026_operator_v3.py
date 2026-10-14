"""One-time namespace adaptation for the v2 GPU-crash recovery; no old file writes."""
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v2'
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v3'


def once(text,before,after):
    if text.count(before)!=1:raise ValueError('ADAPTATION_ANCHOR '+before[:80])
    return text.replace(before,after)


def main():
    NEW.mkdir(exist_ok=False)
    for path in OLD.glob('*.py'):
        text=path.read_text(encoding='utf-8')
        text=text.replace('phase_b_v2_seed2026_operator_v2','phase_b_v2_seed2026_operator_v3')
        text=text.replace('seed2026_epoch7_operator_v2','seed2026_epoch7_operator_v3')
        text=text.replace('seed2026_operator_v2','seed2026_operator_v3')
        text=text.replace('EPOCH7_OPERATOR_20261014_V2','EPOCH7_OPERATOR_20261014_V3')
        text=text.replace('296679','298474')
        if path.name=='protocol.py':
            text=text.replace('OLD_RESERVED = 192119','OLD_RESERVED = 193914').replace('ABANDONED = 14367','ABANDONED = 16162')
        if path.name=='checkpoint.py':
            text=text.replace('SEED2026_OPERATOR_V2_LAST_v1','SEED2026_OPERATOR_V3_LAST_v1')
            text=text.replace("q['old_campaign_reserved']!=192119 or q['abandoned_old_updates']!=14367",
                              "q['old_campaign_reserved']!=193914 or q['abandoned_old_updates']!=16162")
        if path.name=='engine.py':text=text.replace('abandoned_old_updates=14367','abandoned_old_updates=16162')
        if path.name=='worker.py':text=text.replace('all 192119 attempts','all 193914 attempts')
        if path.name=='recovery.py':
            text=text.replace("self.receipt['abandoned_updates'] != 14367","self.receipt['abandoned_updates'] != 16162")
            text=text.replace('abandoned_updates_total=14367','abandoned_updates_total=16162')
            text=once(text,"'.git/phase_b_v2_seed2026_epoch7_operator_v1.once'}",
                      "'.git/phase_b_v2_seed2026_epoch7_operator_v1.once',\n                       '.git/phase_b_v2_seed2026_epoch7_operator_v2.sqlite',\n                       '.git/phase_b_v2_seed2026_epoch7_operator_v2.once'}")
            text=once(text,"'docs/phase_b_v2_formal_execution/seed2026_operator_v1/'))",
                      "'docs/phase_b_v2_formal_execution/seed2026_operator_v1/',\n                            'docs/phase_b_v2_formal_execution/seed2026_operator_v2/'))")
            text=once(text,"with sqlite3.connect((ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite').as_uri()+'?mode=ro',uri=True) as con:\n                con.execute('PRAGMA query_only=ON');verify_stopped_operator(con)",
                      "with sqlite3.connect((ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v2.sqlite').as_uri()+'?mode=ro',uri=True) as con:\n                con.execute('PRAGMA query_only=ON');verify_crashed_operator(con)")
            old_fn='''def verify_stopped_operator(con):
    """Exact emergency ancestor; no epoch8 LAST and no ambiguous update."""
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=5228
        or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=5228
        or con.execute('SELECT status,reason FROM campaign').fetchone()!=('FAILED_NO_RETRY','RESEARCHER_EMERGENCY_STOP_NO_RETRY')
        or con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',(RECOVER_RUN,)).fetchone()!=(7,41824,LAST_SHA)
        or con.execute('SELECT epoch,phase FROM epochs WHERE run=?',(RECOVER_RUN,)).fetchall()!=[(8,'WAIT_VALIDATION')]):
        raise ValueError('EXACT_EMERGENCY_STOPPED_OPERATOR_ANCESTRY')'''
            new_fn='''def verify_crashed_operator(con):
    """Exact crashed v2 ancestor: GPU driver kill mid epoch-8 replay; no receipts."""
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=1795
        or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=1795
        or con.execute('SELECT status,reason FROM campaign').fetchone()!=('ACTIVE',None)
        or con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',(RECOVER_RUN,)).fetchone()!=(7,38391,LAST_SHA)
        or con.execute('SELECT epoch,phase FROM epochs WHERE run=?',(RECOVER_RUN,)).fetchall()!=[(8,'TRAINING')]):
        raise ValueError('EXACT_CRASHED_OPERATOR_ANCESTRY')'''
            text=once(text,old_fn,new_fn)
        (NEW/path.name).write_text(text,encoding='utf-8',newline='\n')
    print('NEW_OPERATOR_V3_SOURCE_CREATED_NO_LAUNCH')

if __name__=='__main__':main()
