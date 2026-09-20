# Code and data availability

This repository contains the frozen study inputs, measurement and analysis code, D-VPF scoring specification, pinned dependencies, adjudication records, and expected-result checks used for the study.

The public CSV files under `data/` are curated versions of the frozen research inputs. They preserve the values required for exact statistical reproduction while omitting long scraped webpage passages, URL query strings, and local or credential-bearing material that is not needed for the analysis.

Run `./scripts/run_reproduction.sh` from the repository root to rebuild the derived cohorts and analyses. The verifier compares the outputs with the frozen expected values and reports `ALL EXPECTED RESULT CHECKS PASSED` when the reproduction succeeds.

A fresh Internet crawl is a new measurement because public assurance pages and Internet-facing DNS, TLS, HTTP, and PKI configurations can change over time.
