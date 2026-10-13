"""Publish a new launch namespace after the explicitly approved zero-step failure.

Only launch identity and immutable failed-ancestor checks differ from v1.
No historical release, ledger, model mathematics or data reader is modified.
"""
from pathlib import Path

ROOT=Path(__file__).absolute().parents[1]
SOURCE=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_resume_v1'
TARGET=ROOT/'src/yuntapr/training/phase_b_v2_seed2026_resume_v2'


def main():
    TARGET.mkdir(exist_ok=False)
    for path in SOURCE.glob('*.py'):
        text=path.read_text(encoding='utf-8')
        if path.name in ('protocol.py','supervisor.py','quota.py'):
            text=text.replace('seed2026_resume_v1','seed2026_resume_v2')
            text=text.replace('EPOCH3_RECOVERY_20261013_V1','EPOCH3_RECOVERY_20261013_V2')
            text=text.replace('epoch3_recovery_20261013_v1','epoch3_recovery_20261013_v2')
        if path.name=='recovery.py':
            text=text.replace("'.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite'}",
                "'.git/phase_b_v2_seed2026_a1863dc_republish_v2.sqlite',\n"
                "                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.once',\n"
                "                       '.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'}")
            text=text.replace("text.startswith('docs/phase_b_v2_formal_execution/seed2026_v2/') or text in allowed",
                "text.startswith(('docs/phase_b_v2_formal_execution/seed2026_v2/',\n"
                "                            'docs/phase_b_v2_formal_execution/seed2026_resume_v1/')) or text in allowed")
            anchor='            # Hold parent directory objects against rename/reparse replacement.'
            insertion="""            zero=self.receipt['zero_update_predecessor']
            if zero['reserved']!=0 or zero['returned']!=0 or zero['job_empty'] is not True:
                raise ValueError('FAILED_RECOVERY_NOT_ZERO_AND_STOPPED')
            db=ROOT/'.git/phase_b_v2_seed2026_epoch3_recovery_20261013_v1.sqlite'
            with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as con:
                con.execute('PRAGMA query_only=ON');verify_zero_predecessor(con)
"""
            if text.count(anchor)!=1:raise ValueError('ZERO_ANCESTOR_ADAPTATION_ANCHOR')
            text=text.replace(anchor,insertion+anchor)
            text += """

def verify_zero_predecessor(con):
    \"\"\"Readonly SQL proof: no attempted update or adopted epoch in failed v1.\"\"\"
    if (con.execute('SELECT count(*) FROM attempts').fetchone()[0]!=0
            or con.execute('SELECT count(*) FROM epochs').fetchone()[0]!=0
            or con.execute('SELECT status FROM campaign').fetchone()!=('FAILED_NO_RETRY',)
            or con.execute('SELECT status,epoch,updates,last_sha FROM runs WHERE id=?',
                           (RECOVER_RUN,)).fetchone()!=('PENDING',3,15684,LAST_SHA)):
        raise ValueError('ZERO_UPDATE_FAILED_RECOVERY_ANCESTOR_CHANGED')
"""
        if path.name=='worker.py':
            text=text.replace('Old attempts stay zero; the new independent cap is not an extra grant.',
                'The failed recovery has zero new attempts; old 162068 remain spent.')
        (TARGET/path.name).write_bytes(text.encode('utf-8'))


if __name__=='__main__':main()
