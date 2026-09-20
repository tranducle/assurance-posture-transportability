# Data

The repository does not include the frozen study CSV files. To reproduce the reported statistics, place the study inputs under `data/` using the layout below.

## Source and measurement scope

The sampling frame uses a frozen Tranco ranking snapshot dated 2026-09-17. The study records enterprise-service screening decisions, first-party public-assurance evidence, adjudicated assurance labels, and client-visible DNS, TLS, HTTP, and PKI measurements.

The assurance labels are study reference labels. They should not be interpreted as independently authenticated certification ground truth.

## Expected layout

```text
data/
  discovery/
    tranco_seed.csv
    screening_log.csv
    enterprise_services.csv
    cohort_adjudication.csv
    automated_assurance_claims.csv
    technical_measurements.csv
    empirical_dataset.csv
    corrected_empirical_dataset.csv
    negative_reaudit.csv
  replication/
    tranco_ranks_1001_2000.csv
    screening_log.csv
    enterprise_services.csv
    cohort_adjudication_pre_outcome.csv
    assurance_adjudication_pre_outcome.csv
    assurance_adjudication_high_recall.csv
    automated_assurance_claims.csv
    empirical_dataset.csv
  repeatability/
    run1.csv
    run2.csv
    run3.csv
  derived/
    discovery.csv
    replication.csv
    replication_complete_case.csv
    scope_reconciliation.csv
```

## Analysis populations

The discovery cohort contains 53 services: 43 with an observed public-assurance claim and 10 without one. The second stratum contains 26 services for exposure analysis. Its primary posture analysis uses 25 complete cases: 18 observed-claim and 7 no-observed-claim services.

One second-stratum service had failed TLS and HTTP acquisition. It is excluded from the primary complete-case posture analysis and retained in a separate sensitivity analysis.

## Reproduction note

Use the frozen study inputs for exact reproduction. A new crawl is a new measurement because public pages, DNS records, TLS configuration, HTTP headers, and certificates can change over time.
