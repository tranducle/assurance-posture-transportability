# Data dictionary

## Common study identifiers

| Column | Meaning |
|---|---|
| `rank` | Tranco rank from the frozen 2026-09-17 sampling frame. |
| `domain` | Public service domain used as the measurement unit. |
| `title` | Page or service title captured during the study, when available. |
| `has_iso_27001` | Adjudicated or automated ISO/IEC 27001 claim indicator, depending on the file. |
| `has_soc_2` | Adjudicated or automated SOC 2 claim indicator, depending on the file. |
| `has_csa_star` | Adjudicated or automated CSA STAR claim indicator, depending on the file. |
| `total_claimed_attestations` | Sum of the three target claim indicators. |
| `attestation_audit_status` | Study status for the assurance evidence record. |
| `pages_inspected` | First-party URLs inspected during retrieval or adjudication. Query strings and fragments are removed in the public release. |
| `attestation_evidence` | First-party evidence URLs retained for provenance. Long scraped passages are not distributed. |

## D-VPF fields

| Column | Meaning |
|---|---|
| `score_tls_transport` | Transport-security pillar score. |
| `score_dns_email` | DNS/email pillar score. |
| `score_http_headers` | HTTP defensive-header pillar score. |
| `score_pki_cert` | PKI/certificate pillar score. |
| `d_vpf_technical_score` | Total D-VPF score on the 0 to 100 scale. |
| `dmarc_policy` | Observed DMARC policy state. |
| `hsts_present` | Whether HSTS was observed. |
| `csp_present` | Whether CSP was observed. |
| `tls_validation_status` | TLS validation state used by the measurement pipeline. |
| `cert_lifespan_days` | Observed certificate lifetime in days. |
| `cert_max_allowed_days` | Issuance-date-specific maximum lifetime used by the scoring rule. |
| `key_type` | Leaf certificate public-key type. |
| `key_bits` | Public-key size where applicable. |
| `http_probe_status` | HTTP acquisition status. |
| `dns_probe_status` | DNS acquisition status. |

## Adjudication fields

The adjudication CSV files record the study decision, brief rationale, and first-party evidence location used for label review. A positive label means that the public evidence was attributable to the sampled vendor or an explicitly represented service or platform family under the frozen scope rule. It does not independently verify formal certificate scope for every endpoint.

## Missing and failed acquisition

The primary second-stratum posture analysis uses complete technical cases. Failed acquisition is not automatically interpreted as a zero security score. The repository retains the incomplete case in the source input so the reported missingness sensitivity can be reproduced.
