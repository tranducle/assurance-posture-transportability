# Assurance and External Posture Transportability

This repository contains the code and frozen study data used to examine whether public cybersecurity assurance claims are associated with externally observable technical controls across two Tranco rank strata.

Public assurance is treated as an adjudicated first-party claim. It is not an independent verification of certificate or audit scope. D-VPF is a 0 to 100 external-configuration index covering transport, DNS and email, HTTP headers, and PKI.

## Repository structure

- `data/`: frozen analysis inputs and adjudication records used for the reported results.
- `src/acquisition/`: service screening, public-assurance retrieval, and D-VPF measurement code.
- `src/analysis/`: cohort construction, statistical analysis, robustness checks, and sensitivity analyses.
- `scripts/run_reproduction.sh`: runs the full analysis sequence.
- `tests/`: expected values and the result verifier.
- `docs/dvpf_scoring.md`: D-VPF scoring and acquisition settings.
- `DATA.md`: data provenance, curation, and file descriptions.
- `REPRODUCIBILITY.md`: environment setup and reproduction steps.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./scripts/run_reproduction.sh
```

The repository already contains the frozen inputs needed for the analysis. A successful run ends with:

```text
ALL EXPECTED RESULT CHECKS PASSED
```

Randomized analyses use the fixed seed `20260918`. The corrected discovery analysis is exploratory because the uniform re-audit occurred after the initial outcome analysis. The second stratum is used to assess transportability, not to support a causal interpretation.

## Data release

The public data are curated frozen research inputs derived from publicly observable organizational assurance evidence and non-intrusive Internet-facing measurements. Long scraped webpage passages and URL query strings are not included because they are not needed to reproduce the statistical results. See `DATA.md` and `data/DATA_DICTIONARY.md` for details.

## Citation

A formal article citation will be added after publication.
