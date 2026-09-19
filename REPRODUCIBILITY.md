# Reproducibility

## Environment

Python dependencies are pinned in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Frozen analysis

Place the authorized frozen CSV inputs in the paths described in `DATA.md`.

Then run:

```bash
./run_all_analysis.sh
```

The workflow rebuilds the canonical labels and reruns the cross-stratum, robustness, weight-sensitivity, repeatability, retrieval, exposure-definition, permutation, failure-taxonomy, and TradPlus timing analyses before running `verify_results.py`.

A successful verification ends with:

```text
ALL CANONICAL-V2 RESULT CHECKS PASSED
```

## Frozen constants

The verified release preserves:

- randomized-analysis seed: `20260918`;
- exact D-VPF scoring and acquisition rules in `DVPF_SCORING_AND_ACQUISITION.md`;
- complete-case handling for the primary second-stratum posture analysis;
- the frozen expected values in `expected_results.json`;
- the original code paths used by the verified supplementary artifact.

Some directory names such as `5_Experiments_Simulations`, `6_Analysis_Results`, and `strengthening` are retained because the scripts use them as frozen relative paths. Renaming them without a full equivalence rerun would change the verified execution contract.

## Interpretation boundaries

- The corrected discovery association is exploratory because the uniform re-audit was post-collection.
- Cross-stratum attenuation is observational and does not identify rank as a causal moderator.
- D-VPF is an external-configuration index, not a holistic organizational-security score.
- Three sequential scans support short-interval score repeatability only.
- Retrieval metrics are relative to study adjudication, not an independent certification registry.
