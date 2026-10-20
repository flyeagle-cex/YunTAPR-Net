"""Pure accounting: no refund and no promotion of the uncertain old attempt."""
PRIOR_RESERVED=86415
PRIOR_VERIFIED=86414
FRESH_CAP=271856
COMBINED_CAP=358271

def prior_content_bytes(events,heartbeat_lower_bound: int) -> int:
    """The original Budget charges both public manifests and raw payloads."""
    total=0
    for event in events:
        if event['event'] in ('READ_FINISHED','PUBLIC_METADATA_READ'):
            size=event['bytes']
            if type(size) is not int or size<0:raise ValueError('PRIOR_BYTE_AUDIT_FORMAT')
            total+=size
    if type(heartbeat_lower_bound) is not int or total<heartbeat_lower_bound:
        raise ValueError('INCOMPLETE_PRIOR_BYTE_ACCOUNTING')
    return total

def fields(new_reserved: int,new_verified: int) -> dict:
    if (type(new_reserved) is not int or type(new_verified) is not int or
        not 0<=new_verified<=new_reserved<=FRESH_CAP):
        raise ValueError('BOUNDED_NEW_ATTEMPT_COUNTS')
    return dict(limit=COMBINED_CAP,reserved=PRIOR_RESERVED+new_reserved,
        returned_verified=PRIOR_VERIFIED+new_verified,new_reserved=new_reserved,
        new_returned_verified=new_verified,old_campaign_reserved=PRIOR_RESERVED,
        old_campaign_returned_verified=PRIOR_VERIFIED,old_unverified_attempts=1,
        abandoned_old_updates=75959,adopted_prior_updates=10456,combined_authorized_attempt_cap=COMBINED_CAP)

def validate(q: dict,*,complete_transaction: bool) -> None:
    expected=fields(q.get('new_reserved'),q.get('new_returned_verified'))
    if any(q.get(k)!=v for k,v in expected.items()):
        raise ValueError('CUMULATIVE_NONREFUNDABLE_ANCESTRY_ACCOUNTING')
    if complete_transaction and q['new_reserved']!=q['new_returned_verified']:
        raise ValueError('CURRENT_CAMPAIGN_UNVERIFIED_UPDATE')
