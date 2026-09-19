# Assurance–Posture Transportability

This repository contains the reproducibility code for a study of public security-assurance claims, automated retrieval validity, and externally observable security posture.

The study compares an adjudicated public-assurance signal with the Deterministic Vendor Posture Framework (D-VPF), a transparent 0–100 external-configuration index. The corrected discovery association is treated as exploratory, and the central transportability result is bounded to two sampled rank strata.

## Repository contents

- `5_Experiments_Simulations/scripts/`: frozen canonical-v2 analysis and measurement scripts.
- `DVPF_SCORING_AND_ACQUISITION.md`: exact D-VPF scoring and acquisition specification.
- `expected_results.json`: frozen headline quantities used by the verifier.
- `verify_results.py`: deterministic result checker.
- `requirements.txt`: pinned Python dependencies.
- `DATA.md`: data-access and reconstruction notes.
- `REPRODUCIBILITY.md`: reproduction workflow and interpretation boundaries.

## Study design in brief

The frozen analysis uses a discovery cohort from one rank stratum and an independently screened adjacent rank stratum for transportability assessment. Public assurance is treated as an adjudicated observed claim, not independently authenticated certification ground truth. D-VPF measures only the specified externally observable DNS/email, HTTP, TLS/transport, and PKI configuration families.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The frozen CSV inputs are intentionally not included in this public-release staging package. See `DATA.md` for the expected data layers and availability boundary.

## Reproducibility notes

Canonical randomized analyses use the frozen seed `20260918`. Reproducibility-critical scoring rules, cohort rules, thresholds, and expected values are preserved unchanged from the verified supplementary artifact.

## Citation

A formal citation will be added after publication.
