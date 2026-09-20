# Reproducibility

## Environment

The analysis uses Python with pinned dependencies from `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run the analysis

Place the frozen study inputs under `data/` as described in `DATA.md`, then run:

```bash
./scripts/run_reproduction.sh
```

The script rebuilds the analysis cohorts and runs the cross-stratum analysis, robustness checks, weight sensitivity, repeatability analysis, retrieval validation, exposure-definition sensitivity, permutation test, retrieval-failure analysis, and label-timing sensitivity. It then checks the generated results against the frozen expected values in `tests/expected_results.json`.

A successful run ends with:

```text
ALL EXPECTED RESULT CHECKS PASSED
```

## Fixed analysis settings

Randomized analyses use seed `20260918`. D-VPF scoring and acquisition settings are documented in `docs/dvpf_scoring.md`. The primary second-stratum posture analysis uses complete cases. Expected headline values are stored in `tests/expected_results.json`.

## Interpretation boundaries

The corrected discovery association is exploratory because its uniform re-audit occurred after initial outcome analysis. Cross-stratum attenuation is observational and does not identify rank as a causal moderator. D-VPF measures external configuration, not overall organizational security. The three sequential scans assess short-interval score repeatability only. Retrieval metrics are measured against study adjudication rather than an independent certification registry.
