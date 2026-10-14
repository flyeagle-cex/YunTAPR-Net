"""One-time namespace adaptation of the tested operator; no old file writes."""
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
OLD=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v1'
NEW=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_operator_v2'


def main():
    NEW.mkdir(exist_ok=False)
    for path in OLD.glob('*.py'):
        text=path.read_text(encoding='utf-8')
        text=text.replace('phase_b_v2_seed2026_operator_v1','phase_b_v2_seed2026_operator_v2')
        text=text.replace('seed2026_epoch7_operator_v1','seed2026_epoch7_operator_v2')
        text=text.replace('seed2026_operator_v1','seed2026_operator_v2')
        text=text.replace('EPOCH7_OPERATOR_20261013_V1','EPOCH7_OPERATOR_20261014_V2')
        text=text.replace('291451','296679')
        if path.name=='protocol.py':
            text=text.replace('OLD_RESERVED = 186891','OLD_RESERVED = 192119').replace('ABANDONED = 9139','ABANDONED = 14367')
            text=text.replace("a.get('additional_replay_allowance')!=3911","a.get('additional_replay_allowance')!=5228")
        if path.name=='checkpoint.py':
            text=text.replace('SEED2026_OPERATOR_LAST_v1','SEED2026_OPERATOR_V2_LAST_v1')
            text=text.replace("q['old_campaign_reserved']!=186891 or q['abandoned_old_updates']!=9139","q['old_campaign_reserved']!=192119 or q['abandoned_old_updates']!=14367")
        if path.name=='engine.py':text=text.replace('abandoned_old_updates=9139','abandoned_old_updates=14367')
        if path.name=='worker.py':text=text.replace('all 186891 attempts','all 192119 attempts')
        if path.name=='recovery.py':
            text=text.replace("self.receipt['abandoned_updates'] != 9139","self.receipt['abandoned_updates'] != 14367")
            text=text.replace('abandoned_updates_total=9139','abandoned_updates_total=14367')
            text=text.replace("'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite'}", "'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v2.sqlite',\n                       '.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite',\n                       '.git/phase_b_v2_seed2026_epoch7_operator_v1.once'}")
            text=text.replace("'docs/phase_b_v2_formal_execution/seed2026_resume_v2/'))", "'docs/phase_b_v2_formal_execution/seed2026_resume_v2/',\n                            'docs/phase_b_v2_formal_execution/seed2026_operator_v1/'))")
            anchor='            # Hold parent directory objects against rename/reparse replacement.'
            block="""            with sqlite3.connect((ROOT/'.git/phase_b_v2_seed2026_epoch7_operator_v1.sqlite').as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_stopped_operator(con)
"""
            if text.count(anchor)!=1:raise ValueError('ANCESTOR_ADAPTATION_ANCHOR')
            text=text.replace(anchor,block+anchor)
            text += """

def verify_stopped_operator(con):
    \"\"\"Exact emergency ancestor; no epoch8 LAST and no ambiguous update.\"\"\"
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=5228
        or con.execute("SELECT count(*) FROM attempts WHERE status='RETURNED_VERIFIED'").fetchone()[0]!=5228
        or con.execute('SELECT status,reason FROM campaign').fetchone()!=('FAILED_NO_RETRY','RESEARCHER_EMERGENCY_STOP_NO_RETRY')
        or con.execute('SELECT epoch,updates,last_sha FROM runs WHERE id=?',(RECOVER_RUN,)).fetchone()!=(7,41824,LAST_SHA)
        or con.execute('SELECT epoch,phase FROM epochs WHERE run=?',(RECOVER_RUN,)).fetchall()!=[(8,'WAIT_VALIDATION')]):
        raise ValueError('EXACT_EMERGENCY_STOPPED_OPERATOR_ANCESTRY')
"""
        (NEW/path.name).write_text(text,encoding='utf-8',newline='\n')
    print('NEW_OPERATOR_V2_SOURCE_CREATED_NO_LAUNCH')

if __name__=='__main__':main()
