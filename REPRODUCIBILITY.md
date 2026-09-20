# Reproducibility

## Environment

The analysis uses Python with pinned dependencies from `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the analysis

The frozen study inputs are included under `data/`. Run:

```bash
./scripts/run_reproduction.sh
```

The script rebuilds the derived analysis cohorts and runs the cross-stratum analysis, robustness checks, weight sensitivity, repeatability analysis, retrieval validation, exposure-definition sensitivity, permutation test, retrieval-failure analysis, and label-timing sensitivity. It then compares the generated results with the frozen expected values in `tests/expected_results.json`.

A successful run ends with:

```text
ALL EXPECTED RESULT CHECKS PASSED
```

## Fixed analysis settings

Randomized analyses use seed `20260918`. D-VPF scoring and acquisition settings are documented in `docs/dvpf_scoring.md`. The primary second-stratum posture analysis uses complete cases. The analysis pipeline regenerates `data/derived/` and `results/`; both are treated as generated outputs rather than source data.

## Interpretation boundaries

The corrected discovery association is exploratory because its uniform re-audit occurred after the initial outcome analysis. Cross-stratum attenuation is observational and does not identify rank as a causal moderator. D-VPF measures external configuration, not overall organizational security. The three sequential scans assess short-interval score repeatability only. Retrieval metrics are measured against study adjudication rather than an independent certification registry.

## Fresh measurements

The acquisition code can be used to collect new observations, but current Internet measurements should not be expected to match the frozen files. Public pages, DNS records, TLS configuration, HTTP headers, and certificates are time varying.
