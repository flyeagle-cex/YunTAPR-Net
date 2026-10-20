"""Activated scope check: no torch, host admission, Job, data or ledger writes."""
import json,sys
from .protocol import OUT,DB,CAMPAIGN,verify_published_release,verify_release
def main():
    release=verify_release()
    gate='AUTHORIZED_EPOCH2_RECOVERY_PRIOR_86415_CHARGED_REPLAY_632'
    if 'torch' in sys.modules:raise RuntimeError('PUBLICATION_CHECK_IMPORTED_TORCH')
    print(json.dumps(dict(publication='PASS',campaign=CAMPAIGN,source_commit=release['source_commit'],
        source_sha256=release['source_sha256'],launch_gate=gate,ledger_exists=DB.exists(),
        once_exists=DB.with_suffix('.once').exists(),sessions_exist=(OUT/'.local/sessions').exists(),
        status='NOT_STARTED' if not DB.exists() else 'LEDGER_PRESENT_USE_STATUS',
        optimizer_updates='NOT_EXECUTED_BY_THIS_CHECK',raw_observation_reads=0)))
if __name__=='__main__':main()
