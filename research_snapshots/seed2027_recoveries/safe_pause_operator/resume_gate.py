"""Operator-only P1 fix; the scheduled scientific worker remains byte-identical."""
import json
import secrets
from bootstrap import quota
from bootstrap import protocol

CAMPAIGN = protocol.CAMPAIGN
session_root = protocol.session_root
owned_json = protocol.owned_json


class ResumeLedger(quota.Ledger):
    def claim_session(self):
        def work():
            state=self.con.execute('SELECT status FROM campaign').fetchone()[0]
            if state=='ACTIVE':raise PermissionError('ALREADY_RUNNING_NO_DUPLICATE_SESSION')
            if state not in ('READY','PAUSED') or (state=='READY' and self.con.execute('SELECT count(*) FROM sessions').fetchone()[0]):raise PermissionError('ONE_HUMAN_APPROVED_LAUNCH_ONLY')
            if state=='PAUSED':
                n,receipt=self.con.execute("SELECT n,receipt FROM sessions WHERE status='PAUSED' ORDER BY n DESC LIMIT 1").fetchone()
                row=json.loads(receipt);path=session_root(n)
                actual=owned_json(path/'paused.json');term=owned_json(path/'termination.json')
                if actual!=row or not term['job_empty_and_handles_signaled'] or term['status']!='PAUSED':
                    raise PermissionError('PAUSE_CLOSING_OR_RECEIPT_NOT_VERIFIED')
                gui=owned_json(path/'gui_termination.json')
                if (gui['nonce']!=row['nonce'] or gui['session']!=n or gui['campaign']!=CAMPAIGN
                    or gui['supervisor_exit_code']!=0 or not gui['job_empty_and_handles_signaled']):
                    raise PermissionError('GUI_PAUSE_OWNER_NOT_CLOSED')
                if self.snapshot()['reserved']!=row['quota']['reserved']:
                    raise PermissionError('PAUSED_QUOTA_ROLLBACK_OR_AMBIGUITY')
            n=self.con.execute('SELECT coalesce(max(n),0)+1 FROM sessions').fetchone()[0]
            if n>999:raise PermissionError('SESSION_ID_BOUND')
            nonce=secrets.token_hex(16)
            self.con.execute('INSERT INTO sessions VALUES(?,?,?,NULL)',(n,'CLAIMED',nonce))
            self.con.execute("UPDATE campaign SET status='ACTIVE',reason=NULL")
            self.con.execute('UPDATE control SET pause_requested=0')
            return n,nonce
        return self._atomic(work)
