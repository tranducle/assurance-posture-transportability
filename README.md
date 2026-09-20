# Assurance and External Posture Transportability

This repository contains the code used to measure public security-assurance claims, compute D-VPF external posture scores, and evaluate whether the observed association transfers across two adjacent Tranco rank strata.

Public assurance is treated as an adjudicated first-party claim, not as independently authenticated certification ground truth. D-VPF is a 0 to 100 external-configuration index covering transport, DNS and email, HTTP headers, and PKI.

## Repository structure

- `src/acquisition/`: service screening, public-assurance retrieval, and D-VPF measurement.
- `src/analysis/`: cohort construction, statistical analysis, robustness checks, and sensitivity analyses.
- `scripts/run_reproduction.sh`: runs the full analysis sequence.
- `tests/`: frozen expected values and the result verifier.
- `docs/dvpf_scoring.md`: D-VPF scoring and acquisition settings.
- `DATA.md`: expected input layout and data notes.
- `REPRODUCIBILITY.md`: environment setup and reproduction steps.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Place the frozen study inputs under `data/` as described in `DATA.md`, then run:

```bash
./scripts/run_reproduction.sh
```

A successful run finishes with:

```text
ALL EXPECTED RESULT CHECKS PASSED
```

## Reproducibility notes

Randomized analyses use the fixed seed `20260918`. The repository preserves the scoring rules, cohort definitions, thresholds, and expected result values used for the reported analyses.

The corrected discovery analysis is exploratory because the uniform re-audit was performed after initial outcome analysis. The second stratum is used to assess transportability, not to support a causal interpretation.

## Citation

A formal citation will be added after publication.
