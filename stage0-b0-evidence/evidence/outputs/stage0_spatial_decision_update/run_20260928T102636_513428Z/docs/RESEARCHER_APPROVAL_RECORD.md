# Researcher Stage-0 spatial decision

Authority: the researcher's explicit decision in this chat, received before this decision-update run. This is a faithful scope record, not an additional approval request.

1. Main evaluation remains the whole Yunnan provincial administrative mask.
2. Adopt GADM4.1 China Level1 Yunnan feature; all NAME_1/GID_1/HASC_1/ISO_1/ENGTYPE_1 identities must match, preserve source/version/CRS/geometry/archive hashes; no silent boundary replacement.
3. Adopt the verified 130x140/3430-cell center-in-polygon candidate using actual IMERG coordinates, not synthesized coordinates.
4. Preserve intersection candidate for boundary sensitivity/engineering comparison, not primary evaluation.
5. Freeze raw/SRTM as current primary DEM source; retain AWS_Skadi separately without merging or deletion.
6. Model-input bbox and weather-system context margin are not frozen.
7. 97–107E,20–30N is CANDIDATE COMMON NUMERICAL OVERLAP only.
8. DEM aggregation, slope/aspect/relief/curvature parameters, and formal dh/dx,dh/dy production remain unfrozen.
9. Freeze the principle that DOTE gradients require real physical distances; degree-index gradients are not physical gradients.
10. New run only, old audits read-only. Stop on completion. No B0, DEM resampling or formal DOTE features.
