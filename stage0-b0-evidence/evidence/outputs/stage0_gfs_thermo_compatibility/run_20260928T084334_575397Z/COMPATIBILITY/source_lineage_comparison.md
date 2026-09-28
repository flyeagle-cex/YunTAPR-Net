# Source / conversion lineage comparison

Conclusion: **SUPPORTED_WITH_CAVEATS** for all 12,960 paired thermo forecasts. This is declared-metadata evidence, not independent verification of converted field values.

Thermo declares NCAR RDA d084001 official GFS archive via THREDDS NCSS and per-forecast source URLs containing cycle and lead.
Primary matched files declare either NCAR GDEX/RDA d084001/NCEP GFS or NOAA GFS AWS Open Data, with NCEP center/process metadata, forecast identifiers, History and/or original_grib_url.
Main-source declaration counts among matched pairs: {'NOAA AWS declared primary': 10028, 'NCAR archive declaration': 2932}.

The engineering evidence exceeds matching folder names, times or bbox: every pair has explicit GFS product/archive text and a current source-file identity token matching its cycle/lead. Source URL tokens and retained History tokens are stored separately in source_lineage_fields.csv.
NCAR-style token gfs.0p25.YYYYMMDDHH.fNNN and AWS-style gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.0p25.fNNN normalize only forecast identifiers; no weather arrays are modified.
For primary NCAR records without a direct per-file URL, the matching Original Dataset token in History is used with caveats. For AWS records, the current original_grib_url is checked independently of stale inherited History.
A direct current URL token conflict would yield CONFLICTING; missing product/forecast-token evidence would yield NOT_ESTABLISHED. Observed counts: {'SUPPORTED_WITH_CAVEATS': 12960}.

Main subset contains conversion_time, fallback_validation claims and historical template metadata. These are retained claims; this audit did not independently replay download/conversion pipelines, fetch source GRIBs or prove checksummed upstream payload identity.
Thermo has no institution/center/model/process attrs in some structures beyond source/archive/title evidence; absent fields remain absent, not copied from main.
This warrants source-lineage PARTIAL in the overall assessment; no automatic adoption or integration is authorized.
