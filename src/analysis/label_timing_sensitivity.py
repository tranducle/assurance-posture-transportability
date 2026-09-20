#!/usr/bin/env python3
"""Sensitivity analysis for the timing of one post-outcome label correction."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
DISCOVERY = ROOT / "data/derived/discovery.csv"
REPLICATION = ROOT / "data/derived/replication_complete_case.csv"
OUTPUT = ROOT / "results/label_timing_sensitivity.json"

SEED = 20260918
DRAWS = 200000
TARGET_DOMAIN = "tradplusad.com"


def finalize_claim(df):
    return (
        df[["has_iso_27001", "has_soc_2", "has_csa_star"]].sum(axis=1) > 0
    ).astype(int)


def gap(df):
    claims = df["claim"].to_numpy(bool)
    scores = df.d_vpf_technical_score.to_numpy(float)
    observed = scores[claims]
    unobserved = scores[~claims]

    difference = float(observed.mean() - unobserved.mean())
    v1 = np.var(observed, ddof=1)
    v0 = np.var(unobserved, ddof=1)
    se = np.sqrt(v1 / len(observed) + v0 / len(unobserved))
    dof = (v1 / len(observed) + v0 / len(unobserved)) ** 2 / (
        (v1 / len(observed)) ** 2 / (len(observed) - 1)
        + (v0 / len(unobserved)) ** 2 / (len(unobserved) - 1)
    )
    critical = stats.t.ppf(0.975, dof)
    ci = [
        float(difference - critical * se),
        float(difference + critical * se),
    ]
    p_value = float(
        stats.ttest_ind(observed, unobserved, equal_var=False).pvalue
    )
    return difference, ci, p_value


def interaction(discovery, replication):
    d = discovery.copy()
    r = replication.copy()
    d["claim"] = finalize_claim(d)

    combined = pd.concat(
        [d.assign(stratum=0), r.assign(stratum=1)],
        ignore_index=True,
    )
    y = combined.d_vpf_technical_score.to_numpy(float)
    claim = combined.claim.to_numpy(int)
    stratum = combined.stratum.to_numpy(int)
    interaction_term = claim * stratum

    log_rank = np.log10(combined["rank"].to_numpy(float))
    centered_log_rank = log_rank.copy()
    for group in (0, 1):
        centered_log_rank[stratum == group] -= log_rank[stratum == group].mean()

    design = sm.add_constant(
        np.column_stack([claim, stratum, interaction_term, centered_log_rank])
    )
    model = sm.OLS(y, design).fit(cov_type="HC3")
    ci = model.conf_int()
    return (
        float(model.params[3]),
        [float(ci[3, 0]), float(ci[3, 1])],
        float(model.pvalues[3]),
    )


def permutation(discovery, replication, draws=DRAWS):
    d = discovery.copy()
    d["claim"] = finalize_claim(d)
    rows = pd.concat(
        [d.assign(stratum=0), replication.assign(stratum=1)],
        ignore_index=True,
    )

    y = rows.d_vpf_technical_score.to_numpy(float)
    claim = rows.claim.to_numpy(bool)
    stratum = rows.stratum.to_numpy(int)

    def cohort_gap(labels, target):
        mask = labels == target
        return float(y[mask & claim].mean() - y[mask & ~claim].mean())

    observed = cohort_gap(stratum, 1) - cohort_gap(stratum, 0)
    claimant_idx = np.where(claim)[0]
    nonclaimant_idx = np.where(~claim)[0]
    n_rep_claim = int(((stratum == 1) & claim).sum())
    n_rep_no_claim = int(((stratum == 1) & ~claim).sum())

    rng = np.random.default_rng(SEED)
    exceed = 0
    for _ in range(draws):
        permuted = np.zeros(len(rows), int)
        permuted[rng.choice(claimant_idx, size=n_rep_claim, replace=False)] = 1
        permuted[
            rng.choice(nonclaimant_idx, size=n_rep_no_claim, replace=False)
        ] = 1
        delta = cohort_gap(permuted, 1) - cohort_gap(permuted, 0)
        if abs(delta) >= abs(observed) - 1e-12:
            exceed += 1

    return float(observed), (exceed + 1) / (draws + 1)


def main():
    discovery = pd.read_csv(DISCOVERY)
    replication_base = pd.read_csv(REPLICATION)

    if TARGET_DOMAIN not in set(replication_base.domain):
        raise ValueError(f"Expected domain not found: {TARGET_DOMAIN}")

    scenarios = {}
    for name in ("original_negative", "final_positive", "removed"):
        replication = replication_base.copy()

        if name == "original_negative":
            replication["claim"] = finalize_claim(replication)
            replication.loc[replication.domain == TARGET_DOMAIN, "claim"] = 0
        elif name == "final_positive":
            replication["claim"] = finalize_claim(replication)
        else:
            replication = replication[
                replication.domain != TARGET_DOMAIN
            ].copy()
            replication["claim"] = finalize_claim(replication)

        second_gap, second_ci, second_p = gap(replication)
        beta, beta_ci, interaction_p = interaction(discovery, replication)
        delta, permutation_p = permutation(discovery, replication)

        scenarios[name] = {
            "n_second": len(replication),
            "claimers": int(replication.claim.sum()),
            "nonclaimers": int((1 - replication.claim).sum()),
            "second_gap": second_gap,
            "second_gap_ci95": second_ci,
            "second_welch_p": second_p,
            "claim_x_stratum_beta": beta,
            "claim_x_stratum_ci95": beta_ci,
            "interaction_p": interaction_p,
            "second_minus_discovery_gap": delta,
            "claim_stratified_permutation_p": permutation_p,
            "permutation_draws": DRAWS,
        }

    result = {
        "seed": SEED,
        "target_domain": TARGET_DOMAIN,
        "scenarios": scenarios,
        "interpretation": (
            "Sensitivity analysis only. The scenarios test the timing of the "
            "post-outcome label correction and do not independently adjudicate "
            "the correct label."
        ),
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
