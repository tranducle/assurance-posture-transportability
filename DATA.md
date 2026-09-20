# Data

This repository includes the frozen study inputs used for the reported statistical analyses.

## What the data represent

The study combines two forms of evidence:

1. first-party public claims related to ISO/IEC 27001, SOC 2, and CSA STAR; and
2. non-intrusive measurements of publicly reachable DNS, TLS, HTTP, and PKI configuration.

The assurance labels are study reference labels based on the adjudication protocol. They are not independently authenticated certification ground truth, and they do not establish that every measured endpoint falls within the formal scope of a certificate or audit.

## Public release contents

```text
data/
  discovery/
    empirical_dataset.csv
    corrected_empirical_dataset.csv
    negative_reaudit.csv
  replication/
    automated_assurance_claims.csv
    empirical_dataset.csv
    assurance_adjudication_pre_outcome.csv
    assurance_adjudication_high_recall.csv
  repeatability/
    run1.csv
    run2.csv
    run3.csv
  adjudication/
    discovery_positive_adjudication.csv
    discovery_cohort_adjudication.csv
    replication_cohort_adjudication.csv
  DATA_DICTIONARY.md
  SHA256SUMS.txt
```

The files under `discovery/`, `replication/`, and `repeatability/` are the frozen inputs consumed by the analysis pipeline. Files under `adjudication/` provide additional provenance for cohort and assurance decisions.

## Analysis populations

The corrected discovery cohort contains 53 services: 43 with an observed public assurance claim and 10 without one.

The second stratum contains 26 services for exposure analysis. The primary posture comparison uses 25 complete technical cases: 18 observed-claim services and 7 services with no observed target claim. One service had failed TLS and HTTP acquisition and is retained only in the relevant sensitivity analysis.

## Curation for public release

The public files preserve the variables required to reproduce the reported analyses. The release removes material that is unnecessary for that purpose:

- URL query strings and fragments are stripped from stored evidence locations;
- long scraped webpage passages are replaced by the corresponding first-party evidence URLs where possible;
- local paths, credentials, cookies, private keys, and personal email addresses are not included.

This curation does not change the cohort labels, ranks, technical scores, probe status fields, statistical inputs, seeds, or expected results.

## Temporal scope

The sampling frame uses the Tranco snapshot dated 2026-09-17. Internet-facing configuration and public assurance pages can change, so the files in this repository should be used for exact reproduction of the article. A fresh crawl is a new measurement rather than a reproduction of the frozen study state.

Column definitions are in `data/DATA_DICTIONARY.md`. SHA-256 checksums are in `data/SHA256SUMS.txt`.
