#!/usr/bin/env python3
"""
Statistical analysis for the D-VPF measurement study.

Primary exposure:
    any high-precision public third-party security attestation claim
    (ISO/IEC 27001, SOC 2, or CSA STAR), observed on a reachable first-party
    vendor page or trust/security/compliance page.

Primary outcome:
    D-VPF external technical posture score (0-100).

Analyses:
1. Descriptive group statistics with a Welch 95% CI for the mean difference.
2. Welch two-sample t-test and two-sided Mann-Whitney U test.
3. Cohen's d.
4. Pearson/Spearman association with attestation count.
5. Pillar-level comparisons.
6. OLS adjustment for log10 Tranco rank with HC3 robust standard errors.
7. Missingness/probe-status accounting.

This script intentionally does not interpret a non-significant p-value as proof
of equivalence or as confirmation of an organizational mechanism.
"""

import argparse
import csv
import json
import math
import os

import numpy as np
import statsmodels.api as sm
from scipy import stats

INPUT_FILE = "5_Experiments_Simulations/data/final_empirical_dataset.csv"
OUTPUT_REPORT = "6_Analysis_Results/statistical_summary.json"


def f(x):
    return float(x)


def i(x):
    return int(x)


def main():
    parser = argparse.ArgumentParser(description="Analyze D-VPF attestation/posture data")
    parser.add_argument("--input", default=INPUT_FILE, help="Merged empirical CSV")
    parser.add_argument("--output", default=OUTPUT_REPORT, help="JSON result path")
    args = parser.parse_args()

    with open(args.input, mode="r", encoding="utf-8") as fh:
        all_rows = list(csv.DictReader(fh))

    # Vendors for which the public-attestation crawler observed at least one page.
    rows = [
        r for r in all_rows
        if r.get("attestation_audit_status", "observed") == "observed"
    ]
    excluded_attestation_unknown = len(all_rows) - len(rows)

    claim = np.array([
        1 if i(r.get("total_claimed_attestations", 0)) > 0 else 0
        for r in rows
    ])
    scores = np.array([f(r["d_vpf_technical_score"]) for r in rows])
    ranks = np.array([f(r["rank"]) for r in rows])
    claim_counts = np.array([f(r.get("total_claimed_attestations", 0)) for r in rows])

    claimers = scores[claim == 1]
    non_claimers = scores[claim == 0]
    n1, n0 = len(claimers), len(non_claimers)
    if n1 < 2 or n0 < 2:
        raise RuntimeError("Both attestation groups need at least two observed vendors.")

    mean1, sd1 = np.mean(claimers), np.std(claimers, ddof=1)
    mean0, sd0 = np.mean(non_claimers), np.std(non_claimers, ddof=1)
    diff = mean1 - mean0

    t_stat, p_val = stats.ttest_ind(claimers, non_claimers, equal_var=False)
    u_stat, u_pval = stats.mannwhitneyu(
        claimers, non_claimers, alternative="two-sided"
    )

    se_diff = math.sqrt(sd1**2 / n1 + sd0**2 / n0)
    welch_df = (sd1**2 / n1 + sd0**2 / n0) ** 2 / (
        (sd1**2 / n1) ** 2 / (n1 - 1)
        + (sd0**2 / n0) ** 2 / (n0 - 1)
    )
    tcrit = stats.t.ppf(0.975, welch_df)
    diff_ci = (diff - tcrit * se_diff, diff + tcrit * se_diff)

    pooled = math.sqrt(
        ((n1 - 1) * sd1**2 + (n0 - 1) * sd0**2) / (n1 + n0 - 2)
    )
    cohen_d = diff / pooled

    pearson_r, pearson_p = stats.pearsonr(claim_counts, scores)
    spearman_rho, spearman_p = stats.spearmanr(claim_counts, scores)

    pillars = [
        "score_tls_transport",
        "score_dns_email",
        "score_http_headers",
        "score_pki_cert",
    ]
    pillar_summary = {}
    for name in pillars:
        p1 = np.array([f(r[name]) for idx, r in enumerate(rows) if claim[idx] == 1])
        p0 = np.array([f(r[name]) for idx, r in enumerate(rows) if claim[idx] == 0])
        pm1, ps1 = np.mean(p1), np.std(p1, ddof=1)
        pm0, ps0 = np.mean(p0), np.std(p0, ddof=1)
        pt, pp = stats.ttest_ind(p1, p0, equal_var=False)
        pillar_summary[name] = {
            "claimers_mean": round(float(pm1), 2),
            "claimers_std": round(float(ps1), 2),
            "non_claimers_mean": round(float(pm0), 2),
            "non_claimers_std": round(float(ps0), 2),
            "difference": round(float(pm1 - pm0), 2),
            "welch_t": round(float(pt), 3),
            "p_value": round(float(pp), 4),
        }

    # Robustness to the equal-weight composite: recompute the group comparison
    # after omitting each pillar in turn. This is not an alternative primary
    # endpoint; it checks whether the direction of the primary result is driven
    # entirely by one pillar.
    leave_one_pillar_out = {}
    for omitted in pillars:
        retained = [name for name in pillars if name != omitted]
        reduced_scores = np.array([
            sum(f(r[name]) for name in retained)
            for r in rows
        ])
        r1 = reduced_scores[claim == 1]
        r0 = reduced_scores[claim == 0]
        rt, rp = stats.ttest_ind(r1, r0, equal_var=False)
        ru, rup = stats.mannwhitneyu(r1, r0, alternative="two-sided")
        leave_one_pillar_out[omitted] = {
            "retained_pillars": retained,
            "claimers_mean": round(float(np.mean(r1)), 2),
            "non_claimers_mean": round(float(np.mean(r0)), 2),
            "mean_difference": round(float(np.mean(r1) - np.mean(r0)), 2),
            "welch_t": round(float(rt), 3),
            "welch_p_value": round(float(rp), 4),
            "mann_whitney_u": round(float(ru), 1),
            "mann_whitney_p_value": round(float(rup), 4),
        }

    # Sensitivity to the single diagnostic/unverified TLS fallback. The primary
    # analysis keeps all completed service observations; this secondary check
    # repeats the core tests on services with a verified TLS chain only.
    verified_rows = [r for r in rows if r.get("tls_validation_status") == "verified"]
    verified_claim = np.array([
        1 if i(r.get("total_claimed_attestations", 0)) > 0 else 0
        for r in verified_rows
    ])
    verified_scores = np.array([f(r["d_vpf_technical_score"]) for r in verified_rows])
    verified_ranks = np.array([f(r["rank"]) for r in verified_rows])
    v1 = verified_scores[verified_claim == 1]
    v0 = verified_scores[verified_claim == 0]
    vt, vtp = stats.ttest_ind(v1, v0, equal_var=False)
    vu, vup = stats.mannwhitneyu(v1, v0, alternative="two-sided")
    vX = sm.add_constant(np.column_stack([verified_claim, np.log10(verified_ranks)]))
    vmodel = sm.OLS(verified_scores, vX).fit(cov_type="HC3")
    verified_tls_sensitivity = {
        "n": len(verified_rows),
        "claimers": len(v1),
        "non_claimers": len(v0),
        "mean_difference": round(float(np.mean(v1) - np.mean(v0)), 2),
        "welch_t": round(float(vt), 3),
        "welch_p_value": round(float(vtp), 4),
        "mann_whitney_u": round(float(vu), 1),
        "mann_whitney_p_value": round(float(vup), 4),
        "ols_attestation_beta": round(float(vmodel.params[1]), 3),
        "ols_attestation_p_value": round(float(vmodel.pvalues[1]), 4),
    }

    X = sm.add_constant(np.column_stack([claim, np.log10(ranks)]))
    model = sm.OLS(scores, X).fit(cov_type="HC3")
    ci = model.conf_int(alpha=0.05)
    ols = {
        "n": int(model.nobs),
        "r_squared": round(float(model.rsquared), 4),
        "covariance": "HC3",
        "intercept": {
            "beta": round(float(model.params[0]), 3),
            "se": round(float(model.bse[0]), 3),
            "ci95": [round(float(ci[0, 0]), 3), round(float(ci[0, 1]), 3)],
            "p_value": round(float(model.pvalues[0]), 4),
        },
        "has_public_attestation_claim": {
            "beta": round(float(model.params[1]), 3),
            "se": round(float(model.bse[1]), 3),
            "ci95": [round(float(ci[1, 0]), 3), round(float(ci[1, 1]), 3)],
            "p_value": round(float(model.pvalues[1]), 4),
        },
        "log10_tranco_rank": {
            "beta": round(float(model.params[2]), 3),
            "se": round(float(model.bse[2]), 3),
            "ci95": [round(float(ci[2, 0]), 3), round(float(ci[2, 1]), 3)],
            "p_value": round(float(model.pvalues[2]), 4),
        },
    }

    status_counts = {
        "attestation_audit": {},
        "tls_validation": {},
        "http_probe": {},
        "dns_probe": {},
    }
    for r in all_rows:
        for key, col in [
            ("attestation_audit", "attestation_audit_status"),
            ("tls_validation", "tls_validation_status"),
            ("http_probe", "http_probe_status"),
            ("dns_probe", "dns_probe_status"),
        ]:
            val = r.get(col, "not_recorded")
            status_counts[key][val] = status_counts[key].get(val, 0) + 1

    results = {
        "analysis_population": {
            "cohort_rows_total": len(all_rows),
            "attestation_observed_rows": len(rows),
            "excluded_attestation_unknown": excluded_attestation_unknown,
            "claimers": n1,
            "non_claimers": n0,
            "claimers_pct": round(n1 / len(rows) * 100, 1),
            "non_claimers_pct": round(n0 / len(rows) * 100, 1),
            "exposure_definition": "Observed first-party public claim of ISO/IEC 27001, SOC 2, or CSA STAR",
        },
        "primary_comparison": {
            "claimers_mean": round(float(mean1), 2),
            "claimers_std": round(float(sd1), 2),
            "non_claimers_mean": round(float(mean0), 2),
            "non_claimers_std": round(float(sd0), 2),
            "mean_difference": round(float(diff), 2),
            "mean_difference_ci95": [
                round(float(diff_ci[0]), 2),
                round(float(diff_ci[1]), 2),
            ],
            "welch_t": round(float(t_stat), 3),
            "welch_df": round(float(welch_df), 2),
            "welch_p_value": round(float(p_val), 4),
            "mann_whitney_u": round(float(u_stat), 1),
            "mann_whitney_p_value": round(float(u_pval), 4),
            "cohens_d": round(float(cohen_d), 3),
        },
        "attestation_count_association": {
            "pearson_r": round(float(pearson_r), 3),
            "pearson_p": round(float(pearson_p), 4),
            "spearman_rho": round(float(spearman_rho), 3),
            "spearman_p": round(float(spearman_p), 4),
        },
        "pillar_breakdown": pillar_summary,
        "leave_one_pillar_out_sensitivity": leave_one_pillar_out,
        "verified_tls_only_sensitivity": verified_tls_sensitivity,
        "ols_adjusted_for_tranco_rank": ols,
        "measurement_status": status_counts,
        "interpretation_guardrail": (
            "Association estimates are observational. Failure to reject a null "
            "difference is not evidence of equivalence and does not establish "
            "institutional decoupling as a causal organizational mechanism."
        ),
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)

    print("=" * 72)
    print("D-VPF ATTESTATION-POSTURE ANALYSIS")
    print("=" * 72)
    print(f"Rows: {len(rows)}/{len(all_rows)} with observable attestation audit")
    print(f"Claimers: n={n1}, mean={mean1:.2f}, SD={sd1:.2f}")
    print(f"Non-claimers: n={n0}, mean={mean0:.2f}, SD={sd0:.2f}")
    print(
        f"Mean difference={diff:+.2f}, 95% CI "
        f"[{diff_ci[0]:.2f}, {diff_ci[1]:.2f}]"
    )
    print(f"Welch t={t_stat:.3f}, p={p_val:.4f}; MW U={u_stat:.1f}, p={u_pval:.4f}")
    print(f"Cohen d={cohen_d:.3f}")
    print(
        "OLS attestation coefficient="
        f"{model.params[1]:+.3f} (HC3 SE={model.bse[1]:.3f}, p={model.pvalues[1]:.4f})"
    )
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
