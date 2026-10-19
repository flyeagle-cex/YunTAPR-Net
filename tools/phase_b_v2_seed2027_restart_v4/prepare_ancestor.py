"""Seal the four stopped attempts without writing any old ledger."""
from pathlib import Path
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib,json,os,sqlite3,sys
ROOT=Path(__file__).absolute().parents[2];sys.path.insert(0,str(ROOT/'src'))
from yuntapr.training.phase_b_v2_seed2027_restart_v4.protocol import OUT
from yuntapr.training.phase_b_v2_seed2027_restart_v4.ancestor import (
    REGISTERED,PREFIX,OLD_DB,STOPPED_CAMPAIGN,S1,S2,read_registered,verify_old_rows,
    FirstFailureGuard,inspect,require_stopped,accounted_bytes,Guard)

def main():
    observed=inspect(STOPPED_CAMPAIGN);require_stopped(observed)
    with ExitStack() as stack:
        raws={r:read_registered(stack,r) for r in sorted(REGISTERED)}
        pins={r:hashlib.sha256(v).hexdigest() for r,v in raws.items()}
        release=json.loads(raws[PREFIX+'release.json'])
        first=stack.enter_context(FirstFailureGuard(release['failed_ancestor_sha256']))
        with sqlite3.connect((ROOT/OLD_DB).as_uri()+'?mode=ro',uri=True) as con:
            con.execute('PRAGMA query_only=ON');verify_old_rows(con)
            if con.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('ANCESTOR_SQLITE_INTEGRITY')
        stamp=datetime.now(timezone.utc).isoformat()
        hb1=json.loads(raws[S1+'heartbeat.json']);hb2=json.loads(raws[S2+'heartbeat.json'])
        launch1=json.loads(raws[S1+'launch.json'])
        events1=[json.loads(s) for s in raws[S1+'access_and_events.jsonl'].splitlines()]
        events2=[json.loads(s) for s in raws[S2+'access_and_events.jsonl'].splitlines()]
        carried=first.receipt['carried_resources']
        total1,ab1=accounted_bytes(events1,carried['content_bytes'],hb1['content_bytes'],allow_trailing_abandon=True)
        total2,ab2=accounted_bytes(events2,total1,hb2['content_bytes'],allow_trailing_abandon=True)
        elapsed=carried['elapsed_seconds']+(datetime.fromisoformat(stamp)-datetime.fromisoformat(launch1['utc'])).total_seconds()
        row=dict(schema='SEED2027_STOPPED_70099_FRESH_RESTART_ANCESTOR_v4',old_campaign=STOPPED_CAMPAIGN,
            prior_reserved=70099,prior_returned_verified=70098,prior_unverified=1,completed_epochs=13,adopted_last=None,
            original_termination_receipt=True,old_ledger_preserved='FAILED_NO_RETRY',sealed_utc=stamp,
            effective_state=observed['observation']['effective_state'],native_probes=observed['native_probes'],
            first_failure_receipt_sha256=release['failed_ancestor_sha256'],
            abandoned_read_reservations={'session_0001':(list(ab1) if ab1 is not None else None),
                                         'session_0002':(list(ab2) if ab2 is not None else None)},
            prior_fresh_b0_sha256=first.receipt['prior_fresh_b0_sha256'],pins=pins,
            carried_resources=dict(elapsed_seconds=elapsed,content_bytes=total2),
            time_method='Conservative first-launch-to-seal wall time plus prior campaign time, including downtime; not measured GPU time.',
            gpu_fault_root_cause='NOT_ESTABLISHED',historical_cleanup_execution='NOT_VERIFIED',
            restart_kind='FRESH_RESTART_EXISTING_LAST_NOT_ADOPTED',old_unknown_attempt_refunded=False)
        raw=(json.dumps(row,indent=2)+'\n').encode()
        with (OUT/'FAILED_ANCESTOR.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    sha=hashlib.sha256(raw).hexdigest()
    with Guard(sha):pass
    print(json.dumps(dict(status='FOUR_ANCESTORS_SEALED_NO_TRAINING',sha256=sha,
                         reserved=70099,verified=70098,carried_resources=row['carried_resources'])))

if __name__=='__main__':main()
