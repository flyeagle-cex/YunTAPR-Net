# Future main/thermo interface schema — definition only

This schema is eligible for researcher review because structure/time/variable coverage evidence exists. No merged file, Dataset, sample pairing database or training sample was constructed.
COMPATIBILITY/main_thermo_pairing.csv is the explicitly requested file-level audit table, with no rain targets, splits, model tensors or operational vintage selection.

| Field | Type / rule |

|---|---|

| forecast_id | Stable identity derived from UTC init + lead, with explicit rule version; not instantiated here |
| init_time, valid_time | UTC timestamp; valid=init+lead |
| lead_time | Numeric hours, not a forecast-selection rule |
| main_file, thermo_file | Separate immutable source paths; multiple candidates retained as ambiguity, never silently selected |
| PWAT_source, CAPE_source, U_source, V_source, PS_source | Main file + explicit raw variable/level name |
| T_source, RH_source | Thermo file + Temperature_isobaric / Relative_humidity_isobaric and pressure index |
| grid_match, time_match | Exact coordinates/hashes and init/lead/valid checks |
| variable_complete | All six thermo variable/level metadata entries present; not per-pixel validity |
| source_lineage_status | STRONGLY_SUPPORTED / SUPPORTED_WITH_CAVEATS / NOT_ESTABLISHED / CONFLICTING |
| pair_quality | MATCHED_COMPLETE / MATCHED_PARTIAL_VARIABLES / MAIN_ONLY / THERMO_ONLY / TIME_CONFLICT / GRID_CONFLICT / METADATA_CONFLICT |
| main_pressure_units, thermo_pressure_units | Retain native Pa; no pressure mask generated |
| T_units, RH_units | Retain K and %; no automatic unit conversion |
| release_time_if_known | Nullable, currently null; conservative timestamp stored separately as assumption |
| vintage_status | NOT_YET_FROZEN |
| researcher_integration_approval | Required, currently false |
| source_status, notes | Evidence run, hashes, unresolved lineage caveats |

PS comes from main; thermo PS absence is expected and not filled using MSLP. Specific humidity, dewpoint and potential temperature do not substitute for target T/RH. GFS precipitation never enters predictor sources.
