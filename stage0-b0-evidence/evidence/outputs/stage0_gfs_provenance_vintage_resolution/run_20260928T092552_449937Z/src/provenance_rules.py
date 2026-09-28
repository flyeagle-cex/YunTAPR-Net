"""Conservative, explicit evidence rules. Never derives a release time from other clocks."""
from pathlib import PureWindowsPath
from compat_rules import normalized_forecast_token
CONFIDENCES={'DIRECT','STRONG','PARTIAL','UNKNOWN'}

def classify_evidence(origin,available=True):
 if not available:return ('NOT_ESTABLISHED','UNKNOWN')
 return {'observed_attribute':('DIRECT_EVIDENCE','DIRECT'),'log':('DIRECT_EVIDENCE','DIRECT'),'official_document':('DIRECT_EVIDENCE','DIRECT'),'script_behavior':('INFERRED_FROM_SCRIPT','PARTIAL'),'filename':('INFERRED_FROM_FILENAME','PARTIAL')}.get(origin,('NOT_ESTABLISHED','UNKNOWN'))

def operational_release(value,semantic_class,official_semantics_verified=False,forecast_identity_verified=False):
 if value and semantic_class=='OBSERVED_OFFICIAL_PUBLICATION' and official_semantics_verified and forecast_identity_verified:return value
 return None

def token_agreement(main_source,thermo_source,cycle,lead):
 a=normalized_forecast_token(main_source);b=normalized_forecast_token(thermo_source);expected=(cycle,int(lead))
 if not a or not b:return 'UNKNOWN'
 return 'MATCH' if a==[expected] and b==[expected] else 'CONFLICT'

def acquisition_link(recorded_path,current_path,recorded_size,current_size,recorded_hash=None,current_hash=None):
 same_path=str(PureWindowsPath(recorded_path)).casefold()==str(PureWindowsPath(current_path)).casefold()
 if recorded_hash and current_hash and recorded_hash==current_hash:return 'CONTENT_HASH_MATCH'
 if recorded_size is not None and int(recorded_size)!=int(current_size):return 'SIZE_MISMATCH_VERSION_LINK_UNKNOWN'
 return 'SAME_PATH_SIZE_ONLY' if same_path and recorded_size is not None else 'LOGICAL_CASE_ONLY_PHYSICAL_LINK_UNKNOWN'

def vintage_candidates():return [{'id':x,'selected':False,'frozen':False,'delay_hours':None} for x in 'ABCD']
