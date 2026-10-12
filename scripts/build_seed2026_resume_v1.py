"""One-time source adaptation; scientific arithmetic is copied unchanged.

This builds NEW files only. It never edits a prior release, ledger or payload.
"""
from pathlib import Path

ROOT = Path(__file__).absolute().parents[1]
OLD = ROOT / 'src/yuntapr/training/phase_b_v2_seed2026_v2'
NEW = ROOT / 'src/yuntapr/training/phase_b_v2_seed2026_resume_v1'


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Adaptation anchor is not unique: ' + before[:80])
    return text.replace(before, after)


def build():
    NEW.mkdir(exist_ok=False)
    def write(name, text):
        (NEW / name).write_text(text, encoding='utf-8', newline='\n')
    write('__init__.py', '"""Explicitly approved epoch3 LAST recovery; no automatic retry."""\n')
    text = (OLD / 'protocol.py').read_text(encoding='utf-8')
    text = text.replace('seed2026_v2', 'seed2026_resume_v1')
    text = text.replace("RESEARCHER_PHASE_B_V2_SEED2026_ZERO_UPDATE_REPUBLISH_a1863dc_V2", "RESEARCHER_PHASE_B_V2_SEED2026_EPOCH3_RECOVERY_20261013_V1")
    text = replace_once(text, "TOTAL = 282312", "TOTAL = 287540\nOLD_RESERVED = 162068\nMAX_NEW = 125472\nABANDONED = 5228\nLAST_SHA = '64bb7c2158cabfb90bc3aa4f0bb454b80129dfa4ee6c4c8e4e8b5582a457ffdf'\nOLD_OUT = ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2'")
    start = text.index('    if release.get(\'publication_kind\')')
    end = text.index('    return release', start)
    text = text[:start] + "    if release.get('publication_kind')!='EXPLICIT_LAST_BOUND_RECOVERY_WITH_NONREFUNDABLE_REPLAY':\n        raise ValueError('EXPLICIT_RECOVERY_RELEASE_REQUIRED')\n    from .recovery import Guard\n    guard=Guard(release['ancestor_receipt_sha256']);guard.close()\n" + text[end:]
    text = text.replace('This module does not approve other seeds, interruption recovery or FinalFit.', 'Only the explicitly bound epoch3 recovery is approved; no other retry or seed.')
    write('protocol.py', text)

    text = (OLD / 'resources.py').read_text(encoding='utf-8')
    text = replace_once(text, 'self.start=time.monotonic(); self.bytes=0; self.stopped=False', "ancestor=json.loads((LOCAL.parent/'ancestor.json').read_bytes())\n        self.start=time.monotonic()-ancestor['elapsed_seconds']; self.bytes=ancestor['content_bytes']; self.stopped=False")
    write('resources.py', text)

    text = (OLD / 'checkpoint.py').read_text(encoding='utf-8')
    text = text.replace("FORMAL_PHASE_B_V2_SEED2026_REPUBLISH_LAST_v2", "FORMAL_PHASE_B_V2_SEED2026_EXPLICIT_RECOVERY_LAST_v1")
    text = text.replace("q['limit']!=282312", "q['limit']!=287540")
    text = replace_once(text, "        m=p['model']", "        if q['old_campaign_reserved']!=162068 or q['abandoned_old_updates']!=5228:\n            raise ValueError('NONREFUNDABLE_RECOVERY_ANCESTRY')\n        recovery=self.identity.get('recovery')\n        if recovery and epoch==4 and p['parent_last_sha']!=recovery['last_sha256']:\n            raise ValueError('EXACT_APPROVED_RECOVERY_PARENT')\n        m=p['model']")
    write('checkpoint.py', text)
    text = (OLD / 'quota.py').read_text(encoding='utf-8')
    text = text.replace('run_id\n', 'run_id, OLD_RESERVED, MAX_NEW, ABANDONED, LAST_SHA\n')
    text = text.replace('phase_b_v2_seed2026_a1863dc_republish_v2', 'phase_b_v2_seed2026_epoch3_recovery_20261013_v1')
    text = text.replace("self.ancestor_sha=release['old_ancestor_receipt_sha256']", "self.ancestor_sha=release['ancestor_receipt_sha256']")
    text = replace_once(text, "            self.con.execute('INSERT INTO runs VALUES(?,?,?,?,?,NULL)',(run_id(model,arm),i,'PENDING',0,0))", "            ident=run_id(model,arm)\n            if i<3:\n                old=json.loads((ROOT/'docs/phase_b_v2_formal_execution/seed2026_v2'/f'{ident}.json').read_bytes())\n                row=(ident,i,'COMPLETE',9,47052,old['epochs'][-1]['checkpoint']['payload_sha256'])\n            elif i==3: row=(ident,i,'PENDING',3,15684,LAST_SHA)\n            else: row=(ident,i,'PENDING',0,0,None)\n            self.con.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',row)")
    text = text.replace('if count>=TOTAL:', 'if count>=MAX_NEW:').replace('282312_ATTEMPT_HARD_CAP', '287540_COMBINED_NONREFUNDABLE_HARD_CAP')
    text = replace_once(text, "reserved=self.con.execute('SELECT count(*) FROM attempts').fetchone()[0],", "reserved=OLD_RESERVED+self.con.execute('SELECT count(*) FROM attempts').fetchone()[0],\n            new_reserved=self.con.execute('SELECT count(*) FROM attempts').fetchone()[0],")
    text = text.replace('old_campaign_reserved=0,combined_authorized_attempt_cap=TOTAL', 'old_campaign_reserved=OLD_RESERVED,abandoned_old_updates=ABANDONED,combined_authorized_attempt_cap=TOTAL')
    text = text.replace('returned_verified=self.con.execute(', 'returned_verified=OLD_RESERVED+self.con.execute(')
    write('quota.py', text)

    text = (OLD / 'engine.py').read_text(encoding='utf-8')
    text = text.replace('No BEST selection, warm start, retry, or automatic recovery branch exists.', 'No BEST selection or automatic retry. Only the approved epoch3 recovery exists.')
    text = replace_once(text, '        self.initial_by_model={};self.completed=[]', "        from .recovery import completed_results\n        self.completed=completed_results()\n        self.initial_by_model={r['run_id'].split('__')[0]:r['initial_sha256'] for r in self.completed}")
    text = replace_once(text, "                initial_sha256=initial,warm_start=False)", "                initial_sha256=initial,warm_start=False)\n            resumed=model_kind=='B1_V2' and arm=='E1'\n            if resumed:\n                from .protocol import LAST_SHA\n                identity['recovery']=dict(last_sha256=LAST_SHA,source_epoch=3,source_update=15684,\n                    replay_epoch=4,abandoned_old_updates=5228,independent_researcher_decision=self.release['authorization'])")
    text = replace_once(text, "            epochs=[]\n            try:\n                for epoch in range(1,10):", "            epochs=[];first_epoch=1\n            try:\n                if resumed:\n                    from .recovery import restore_authorized, history\n                    proof=restore_authorized(model,optimizer,schedule,initial,self.plan)\n                    self.budget.emit('EXPLICIT_LAST_RECOVERY_VERIFIED',run_id=ident,**proof)\n                    atomic_json(folder/'recovery_receipt.json',proof)\n                    epochs=history();first_epoch=4\n                for epoch in range(first_epoch,10):")
    text = replace_once(text, '        for model,arm in ORDER:self.run_one(model,arm)', '        for model,arm in ORDER[3:]:self.run_one(model,arm)')
    text = text.replace("AUTHORIZED_EXECUTION_SCOPE='SEED2026_SIX_RUNS_ONLY'", "AUTHORIZED_EXECUTION_SCOPE='SEED2026_EXPLICIT_EPOCH3_RECOVERY_AND_TWO_E2_RUNS'")
    write('engine.py', text)
    for name in ('evaluation.py','analysis.py'):
        write(name, (OLD/name).read_text(encoding='utf-8'))

    text = (OLD / 'worker.py').read_text(encoding='utf-8')
    text = text.replace('    from .data import Plan,Adapter', '    from yuntapr.training.phase_b_v2_seed2026_v2.data import Plan,Adapter')
    text = text.replace('    from .ancestor import Guard', '    from .recovery import Guard')
    text = text.replace('    from .dependencies import verify as verify_dependencies', '    from yuntapr.training.phase_b_v2_seed2026_v2.dependencies import verify as verify_dependencies')
    text = text.replace("release['old_ancestor_receipt_sha256']", "release['ancestor_receipt_sha256']")
    text = text.replace("current_run='B0_MATCHED_V2__E0__s2026'", "current_run='B1_V2__E1__s2026'")
    write('worker.py', text)

    text = (OLD / 'supervisor.py').read_text(encoding='utf-8')
    text = text.replace('yuntapr.training.phase_b_v2_seed2026_v2.worker', 'yuntapr.training.phase_b_v2_seed2026_resume_v1.worker')
    text = text.replace('phase_b_v2_seed2026_a1863dc_republish_v2', 'phase_b_v2_seed2026_epoch3_recovery_20261013_v1')
    text = replace_once(text, '    start=time.monotonic();worker=None;', "    ancestor=json.loads((OUT/'ancestor.json').read_bytes())\n    launched=time.monotonic();start=launched-ancestor['elapsed_seconds'];worker=None;")
    text = text.replace('worker is None and elapsed>30', 'worker is None and time.monotonic()-launched>30')
    write('supervisor.py', text)


if __name__ == '__main__':
    build()
