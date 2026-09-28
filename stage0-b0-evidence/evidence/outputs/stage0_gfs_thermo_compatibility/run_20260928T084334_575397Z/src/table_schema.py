"""Explicit nullable booleans preserve absent-side metadata, never fill unknown with False."""
import pandas as pd
PAIR_BOOL_COLUMNS=["main_auxiliary_metadata_conflict","thermo_auxiliary_metadata_conflict"]
def read_audit_csv(path):
    if path.name=="main_thermo_pairing.csv":
        return pd.read_csv(path,dtype={name:"boolean" for name in PAIR_BOOL_COLUMNS})
    return pd.read_csv(path)
