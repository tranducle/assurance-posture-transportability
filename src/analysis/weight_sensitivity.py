#!/usr/bin/env python3
"""Sensitivity of discovery/replication conclusions to D-VPF pillar weights.

Weights are sampled independently of outcomes from a constrained simplex:
each pillar receives 10% to 40% of total weight and all four weights sum to 1.
The exercise is descriptive construct sensitivity, not a multiplicity-generating
set of hypothesis tests.
"""

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DISC = ROOT / "data/derived/discovery.csv"
REPL = ROOT / "data/derived/replication_complete_case.csv"
OUT = ROOT / "results"
SEED = 20260918
N_ACCEPT = 50000
PILLARS = [
    "score_tls_transport",
    "score_dns_email",
    "score_http_headers",
    "score_pki_cert",
]


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def matrix(rows):
    return np.asarray([[float(r[c]) for c in PILLARS] for r in rows], dtype=float)


def claims(rows):
    return np.asarray([int(r["total_claimed_attestations"]) > 0 for r in rows], dtype=bool)


def sample_weights(rng, n):
    accepted = []
    while sum(len(x) for x in accepted) < n:
        w = rng.dirichlet(np.ones(4), size=max(10000, n))
        mask = (w.min(axis=1) >= 0.10) & (w.max(axis=1) <= 0.40)
        accepted.append(w[mask])
    return np.vstack(accepted)[:n]


def weighted_scores(X, W):
    # Each pillar is 0..25. Convert to a 0..100 weighted index.
    return 100.0 * (X / 25.0) @ W.T


def gaps(scores, c):
    return scores[c].mean(axis=0) - scores[~c].mean(axis=0)


def summarize(x):
    return {
        "min": float(np.min(x)),
        "q025": float(np.quantile(x, 0.025)),
        "median": float(np.median(x)),
        "q975": float(np.quantile(x, 0.975)),
        "max": float(np.max(x)),
        "fraction_positive": float(np.mean(x > 0)),
        "fraction_negative": float(np.mean(x < 0)),
    }


def main():
    rng = np.random.default_rng(SEED)
    drows, rrows = load(DISC), load(REPL)
    Xd, Xr = matrix(drows), matrix(rrows)
    cd, cr = claims(drows), claims(rrows)

    W = sample_weights(rng, N_ACCEPT)
    dg = gaps(weighted_scores(Xd, W), cd)
    rg = gaps(weighted_scores(Xr, W), cr)
    attenuation = rg - dg

    equal = np.full((1, 4), 0.25)
    equal_d = float(gaps(weighted_scores(Xd, equal), cd)[0])
    equal_r = float(gaps(weighted_scores(Xr, equal), cr)[0])

    result = {
        "seed": SEED,
        "accepted_weight_vectors": N_ACCEPT,
        "constraint": "each pillar weight in [0.10, 0.40], weights sum to 1",
        "pillars": PILLARS,
        "equal_weight_reference": {
            "weights": [0.25, 0.25, 0.25, 0.25],
            "discovery_gap": equal_d,
            "replication_gap": equal_r,
            "replication_minus_discovery": equal_r - equal_d,
        },
        "discovery_gap_distribution": summarize(dg),
        "replication_gap_distribution": summarize(rg),
        "attenuation_distribution": summarize(attenuation),
        "claim_boundary": (
            "Weight perturbation tests dependence on the equal-weight construct. "
            "It does not validate any particular alternative weighting scheme."
        ),
    }

    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / "weight_sensitivity_summary.json"
    md = OUT / "weight_sensitivity_report.md"
    jp.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# D-VPF Weight Sensitivity",
        "",
        f"- Accepted constrained weight vectors: {N_ACCEPT:,}.",
        "- Constraint: each pillar receives 10% to 40%; weights sum to 100%.",
        f"- Equal-weight discovery gap: {equal_d:.2f}.",
        f"- Equal-weight replication gap: {equal_r:.2f}.",
        "",
        "## Discovery gap over admissible weights",
        f"- Range: {np.min(dg):.2f} to {np.max(dg):.2f}.",
        f"- 2.5% to 97.5% weight-sensitivity interval: {np.quantile(dg,.025):.2f} to {np.quantile(dg,.975):.2f}.",
        f"- Fraction positive: {np.mean(dg>0):.4f}.",
        "",
        "## Replication gap over admissible weights",
        f"- Range: {np.min(rg):.2f} to {np.max(rg):.2f}.",
        f"- 2.5% to 97.5% interval: {np.quantile(rg,.025):.2f} to {np.quantile(rg,.975):.2f}.",
        "",
        "## Cross-stratum attenuation over admissible weights",
        f"- Replication-minus-discovery range: {np.min(attenuation):.2f} to {np.max(attenuation):.2f}.",
        f"- 2.5% to 97.5% interval: {np.quantile(attenuation,.025):.2f} to {np.quantile(attenuation,.975):.2f}.",
        f"- Fraction negative: {np.mean(attenuation<0):.4f}.",
        "",
        "## Interpretation boundary",
        result["claim_boundary"],
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
