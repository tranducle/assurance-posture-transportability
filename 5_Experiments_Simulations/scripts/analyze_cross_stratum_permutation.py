#!/usr/bin/env python3
"""Claim-stratified permutation test for the cross-stratum difference in D-VPF gaps.

Null: conditional on public-claim status, assignment to the discovery versus
replication rank stratum is exchangeable with respect to D-VPF. The test keeps
the observed number of claimers and non-claimers assigned to replication
(18 and 7) and recomputes replication-gap minus discovery-gap.
"""

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DISC = ROOT / "5_Experiments_Simulations/strengthening/canonical_v2/discovery_canonical_v2.csv"
REPL = ROOT / "5_Experiments_Simulations/strengthening/canonical_v2/replication_canonical_v2_complete.csv"
OUT_JSON = ROOT / "6_Analysis_Results/strengthening/canonical_v2_cross_stratum_permutation.json"
OUT_MD = ROOT / "6_Analysis_Results/strengthening/canonical_v2_cross_stratum_permutation.md"
SEED = 20260918
DRAWS = 200000


def load(path, stratum):
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["_stratum"] = stratum
    return rows


def gap(scores, claims, strata, target):
    m = strata == target
    a = scores[m & claims]
    b = scores[m & (~claims)]
    return float(np.mean(a) - np.mean(b))


def main():
    rows = load(DISC, 0) + load(REPL, 1)
    y = np.asarray([float(r["d_vpf_technical_score"]) for r in rows], dtype=float)
    c = np.asarray([int(r["total_claimed_attestations"]) > 0 for r in rows], dtype=bool)
    s = np.asarray([int(r["_stratum"]) for r in rows], dtype=int)

    observed_disc = gap(y, c, s, 0)
    observed_repl = gap(y, c, s, 1)
    observed_delta = observed_repl - observed_disc

    idx_claim = np.where(c)[0]
    idx_no = np.where(~c)[0]
    n_repl_claim = int(np.sum((s == 1) & c))
    n_repl_no = int(np.sum((s == 1) & (~c)))

    rng = np.random.default_rng(SEED)
    deltas = np.empty(DRAWS, dtype=float)
    exceed = 0
    for b in range(DRAWS):
        ps = np.zeros(len(rows), dtype=int)
        repl_claim = rng.choice(idx_claim, size=n_repl_claim, replace=False)
        repl_no = rng.choice(idx_no, size=n_repl_no, replace=False)
        ps[repl_claim] = 1
        ps[repl_no] = 1
        delta = gap(y, c, ps, 1) - gap(y, c, ps, 0)
        deltas[b] = delta
        if abs(delta) >= abs(observed_delta) - 1e-12:
            exceed += 1

    p_two = (exceed + 1) / (DRAWS + 1)
    result = {
        "seed": SEED,
        "draws": DRAWS,
        "n_total": len(rows),
        "n_discovery": int(np.sum(s == 0)),
        "n_replication": int(np.sum(s == 1)),
        "replication_claimers_fixed": n_repl_claim,
        "replication_nonclaimers_fixed": n_repl_no,
        "observed_discovery_gap": observed_disc,
        "observed_replication_gap": observed_repl,
        "observed_replication_minus_discovery": observed_delta,
        "two_sided_permutation_p": p_two,
        "null_distribution_quantiles": {
            "q025": float(np.quantile(deltas, 0.025)),
            "median": float(np.quantile(deltas, 0.5)),
            "q975": float(np.quantile(deltas, 0.975)),
        },
        "interpretation_boundary": (
            "This is an assumption-light exchangeability check for the difference in cohort-specific "
            "mean gaps. It does not identify rank as the causal source of attenuation."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "# Cross-Stratum Claim-Stratified Permutation Test\n\n"
        f"- Discovery gap: {observed_disc:.2f}\n"
        f"- Replication complete-case gap: {observed_repl:.2f}\n"
        f"- Replication minus discovery: {observed_delta:.2f}\n"
        f"- Two-sided permutation p ({DRAWS:,} draws): {p_two:.6f}\n"
        f"- Null 95% central range: [{result['null_distribution_quantiles']['q025']:.2f}, "
        f"{result['null_distribution_quantiles']['q975']:.2f}]\n\n"
        + result["interpretation_boundary"] + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
