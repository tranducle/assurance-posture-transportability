# Data

The code in this repository expects the frozen study data layers used for the verified analysis. The CSV files are not committed to this repository.

## Data source

The sampling frame is a frozen Tranco ranking snapshot dated 2026-09-17. The study then derives enterprise-service screening records, public-assurance adjudication records, and client-visible DNS/TLS/HTTP/PKI measurements.

The public-assurance labels are study reference labels based on first-party evidence. They are not independently authenticated certification ground truth.

## Expected data layout

The canonical analysis expects these main paths:

```text
5_Experiments_Simulations/
  data/
    tranco_seed_list.csv
    domain_classification_log.csv
    cohort_inclusion_adjudication.csv
    final_empirical_dataset.csv
  strengthening/
    discovery_corrected_empirical.csv
    discovery_negative_reaudit.csv
    repeatability/
      run1_merged.csv
      run2_merged.csv
      run3_merged.csv
    replication/
      tranco_ranks_1001_2000.csv
      domain_classification_log.csv
      cohort_adjudication_pre_outcome.csv
      attestation_adjudication_pre_outcome.csv
      attestation_adjudication_high_recall.csv
      final_empirical_replication.csv
      vendor_compliance_replication.csv
    canonical_v2/
      discovery_canonical_v2.csv
      replication_canonical_v2.csv
      replication_canonical_v2_complete.csv
      scope_reconciliation_ledger.csv
```

Several supporting screening/retrieval CSVs are also consumed by the acquisition and audit scripts.

## Analysis populations

- Discovery: N=53, including 43 observed-claim and 10 no-observed-claim services.
- Second stratum: exposure N=26; primary complete-case posture N=25, including 18 observed-claim and 7 no-observed-claim services.

One second-stratum service with failed TLS and HTTP acquisition is excluded from the primary complete-case posture analysis and retained in a sensitivity analysis.

## Availability boundary

The verified frozen data are distributed separately from this GitHub staging package. This repository intentionally contains code, specifications, pinned dependencies, and expected-result checks but not the CSV study records.

Do not substitute a fresh live Internet crawl for the frozen data when attempting to reproduce the reported statistics. Public pages, DNS, TLS, HTTP headers, and certificates can change over time.
