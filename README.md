# Climate Extremes and Pedestrian Safety

Phase II research on Great Britain STATS19, quantitative weather exposures, local climate anomalies and urban–rural heterogeneity. Phase I repository: https://github.com/ys30/Climate-Pedestrian-Safety-STATS19 (2022 portfolio only; later manuscript and results remain to be recovered).

## Design
- Pilot: January 2022; core comparison: 2021–2025; extension: 2016–2025 after severity coding audit.
- Fixed climate baseline: 1991–2020. ERA5-Land hourly exposures; independent HadUK-Grid and station validation.
- Separate recorded pedestrian casualty occurrence and conditional KSI severity. Neither is per-trip risk without mobility exposure.
- Compare police weather categories, absolute weather and local anomalies; test urban–rural heterogeneity on common samples. Report standardized risk differences and clustered uncertainty.
- Future UKCP18/CMIP6 scenarios deferred until historical validation.

## Execution
`python src/audit.py --year 2022 --out results/2022.json` downloads official DfT annual files via the official catalog, checks identifiers and records provenance. The pilot audit is not a replication of the later Phase I manuscript.

Source: https://www.gov.uk/government/statistical-data-sets/road-safety-open-data

No unpublished manuscript, credentials, or individual event files are committed. Results are pending successful execution.
