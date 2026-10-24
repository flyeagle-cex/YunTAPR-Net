"""Directly approved 5,228-update replay; no refunds or uncertain-step promotion."""
PRIOR_RESERVED=265637
PRIOR_VERIFIED=265636
ADOPTED=172524
ABANDONED=93113
FRESH_CAP=109788
COMBINED_CAP=375425


def fields(new_reserved: int,new_verified: int) -> dict:
    if (type(new_reserved) is not int or type(new_verified) is not int or
        not 0<=new_verified<=new_reserved<=FRESH_CAP):
        raise ValueError('BOUNDED_NEW_ATTEMPT_COUNTS')
    return dict(limit=COMBINED_CAP,reserved=PRIOR_RESERVED+new_reserved,
        returned_verified=PRIOR_VERIFIED+new_verified,new_reserved=new_reserved,
        new_returned_verified=new_verified,old_campaign_reserved=PRIOR_RESERVED,
        old_campaign_returned_verified=PRIOR_VERIFIED,old_unverified_attempts=1,
        abandoned_old_updates=ABANDONED,adopted_prior_updates=ADOPTED,
        combined_authorized_attempt_cap=COMBINED_CAP)


def validate(q: dict,*,complete_transaction: bool) -> None:
    expected=fields(q.get('new_reserved'),q.get('new_returned_verified'))
    if any(q.get(k)!=v for k,v in expected.items()):
        raise ValueError('CUMULATIVE_NONREFUNDABLE_ANCESTRY_ACCOUNTING')
    if complete_transaction and q['new_reserved']!=q['new_returned_verified']:
        raise ValueError('CURRENT_CAMPAIGN_UNVERIFIED_UPDATE')
