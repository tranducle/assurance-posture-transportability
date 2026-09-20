#!/usr/bin/env python3
"""Final corrected discovery-vs-replication transportability analysis.

Uses outcome-independent, manually adjudicated exposure labels:
- Discovery: corrected negative-label audit + Liftoff/Vungle alias deduplication.
- Replication: pre-outcome cohort and attestation adjudication.

Reports each cohort separately and tests whether the claim-posture association differs
between Tranco rank strata. No causal interpretation is implied.
"""

import csv
import json
import math
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
DISC = ROOT / "data/derived/discovery.csv"
REPL = ROOT / "data/derived/replication_complete_case.csv"
OUTDIR = ROOT / "results"
SEED = 20260918
PILLARS = [
    "score_tls_transport",
    "score_dns_email",
    "score_http_headers",
    "score_pki_cert",
]


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def vec(rows, key):
    return np.asarray([float(r[key]) for r in rows], dtype=float)


def claim(rows):
    return np.asarray([int(r["total_claimed_attestations"]) > 0 for r in rows], dtype=bool)


def cohen_d(x1, x0):
    pooled = math.sqrt(
        ((len(x1) - 1) * np.var(x1, ddof=1) + (len(x0) - 1) * np.var(x0, ddof=1))
        / (len(x1) + len(x0) - 2)
    )
    return float((np.mean(x1) - np.mean(x0)) / pooled)


def welch_ci(x1, x0, alpha=0.05):
    diff = float(np.mean(x1) - np.mean(x0))
    v1 = np.var(x1, ddof=1)
    v0 = np.var(x0, ddof=1)
    se = math.sqrt(v1 / len(x1) + v0 / len(x0))
    df = (v1 / len(x1) + v0 / len(x0)) ** 2 / (
        (v1 / len(x1)) ** 2 / (len(x1) - 1)
        + (v0 / len(x0)) ** 2 / (len(x0) - 1)
    )
    crit = stats.t.ppf(1 - alpha / 2, df)
    return diff, [diff - crit * se, diff + crit * se], float(df), float(se)


def permutation_p(y, c, rng, draws=100000):
    obs = float(np.mean(y[c]) - np.mean(y[~c]))
    exceed = 0
    for _ in range(draws):
        pc = rng.permutation(c)
        g = float(np.mean(y[pc]) - np.mean(y[~pc]))
        if abs(g) >= abs(obs) - 1e-12:
            exceed += 1
    return (exceed + 1) / (draws + 1)


def bootstrap_gap_ci(y, c, rng, draws=30000):
    a = y[c]
    b = y[~c]
    vals = np.empty(draws)
    for i in range(draws):
        vals[i] = np.mean(rng.choice(a, len(a), replace=True)) - np.mean(
            rng.choice(b, len(b), replace=True)
        )
    return [float(x) for x in np.quantile(vals, [0.025, 0.975])]


def hc3_rank_model(rows):
    y = vec(rows, "d_vpf_technical_score")
    c = claim(rows).astype(int)
    rank = np.log10(vec(rows, "rank"))
    X = sm.add_constant(np.column_stack([c, rank]))
    m = sm.OLS(y, X).fit(cov_type="HC3")
    ci = m.conf_int(alpha=0.05)
    return {
        "claim_beta": float(m.params[1]),
        "claim_se": float(m.bse[1]),
        "claim_p": float(m.pvalues[1]),
        "claim_ci95": [float(ci[1, 0]), float(ci[1, 1])],
        "log_rank_beta": float(m.params[2]),
        "log_rank_p": float(m.pvalues[2]),
        "r2": float(m.rsquared),
    }


def leave_one_out(rows):
    out = []
    for i, r in enumerate(rows):
        rr = rows[:i] + rows[i + 1 :]
        y = vec(rr, "d_vpf_technical_score")
        c = claim(rr)
        if c.all() or (~c).all():
            continue
        t = stats.ttest_ind(y[c], y[~c], equal_var=False)
        model = hc3_rank_model(rr)
        out.append(
            {
                "removed_domain": r["domain"],
                "gap": float(np.mean(y[c]) - np.mean(y[~c])),
                "welch_p": float(t.pvalue),
                "ols_beta": model["claim_beta"],
                "ols_p": model["claim_p"],
            }
        )
    return {
        "gap_range": [min(x["gap"] for x in out), max(x["gap"] for x in out)],
        "welch_p_range": [
            min(x["welch_p"] for x in out),
            max(x["welch_p"] for x in out),
        ],
        "ols_beta_range": [
            min(x["ols_beta"] for x in out),
            max(x["ols_beta"] for x in out),
        ],
        "ols_p_range": [
            min(x["ols_p"] for x in out),
            max(x["ols_p"] for x in out),
        ],
        "all_welch_p_below_005": all(x["welch_p"] < 0.05 for x in out),
        "all_ols_p_below_005": all(x["ols_p"] < 0.05 for x in out),
        "rows": out,
    }


def cohort_summary(rows, rng):
    y = vec(rows, "d_vpf_technical_score")
    c = claim(rows)
    a = y[c]
    b = y[~c]
    diff, ci, df, se = welch_ci(a, b)
    t = stats.ttest_ind(a, b, equal_var=False)
    u = stats.mannwhitneyu(a, b, alternative="two-sided")
    rank_model = hc3_rank_model(rows)
    pillars = {}
    for col in PILLARS:
        z = vec(rows, col)
        tt = stats.ttest_ind(z[c], z[~c], equal_var=False)
        pillars[col] = {
            "claimers_mean": float(np.mean(z[c])),
            "nonclaimers_mean": float(np.mean(z[~c])),
            "mean_difference": float(np.mean(z[c]) - np.mean(z[~c])),
            "welch_p": None if np.isnan(tt.pvalue) else float(tt.pvalue),
        }
    return {
        "n": len(rows),
        "claimers": int(c.sum()),
        "nonclaimers": int((~c).sum()),
        "claimers_mean": float(np.mean(a)),
        "claimers_sd": float(np.std(a, ddof=1)),
        "nonclaimers_mean": float(np.mean(b)),
        "nonclaimers_sd": float(np.std(b, ddof=1)),
        "mean_difference": diff,
        "mean_difference_se": se,
        "ci95": ci,
        "welch_t": float(t.statistic),
        "welch_df": df,
        "welch_p": float(t.pvalue),
        "mann_whitney_u": float(u.statistic),
        "mann_whitney_p": float(u.pvalue),
        "cohens_d": cohen_d(a, b),
        "permutation_p": permutation_p(y, c, rng),
        "bootstrap_ci95": bootstrap_gap_ci(y, c, rng),
        "rank_adjusted_hc3": rank_model,
        "pillars": pillars,
        "leave_one_service_out": leave_one_out(rows),
    }


def main():
    rng = np.random.default_rng(SEED)
    drows = load(DISC)
    rrows = load(REPL)
    ds = cohort_summary(drows, rng)
    rs = cohort_summary(rrows, rng)

    rows = drows + rrows
    y = vec(rows, "d_vpf_technical_score")
    c = claim(rows).astype(int)
    cohort = np.asarray([0] * len(drows) + [1] * len(rrows), dtype=int)
    interaction = c * cohort
    log_rank = np.log10(vec(rows, "rank"))

    # Within-cohort centering removes the between-stratum rank shift from the
    # covariate. It therefore asks whether local rank position inside each
    # tranche changes the claim-by-stratum result.
    centered_log_rank = log_rank.copy()
    for g in (0, 1):
        centered_log_rank[cohort == g] -= np.mean(log_rank[cohort == g])

    # Unadjusted stratum interaction.
    X = sm.add_constant(np.column_stack([c, cohort, interaction]))
    m = sm.OLS(y, X).fit(cov_type="HC3")
    mci = m.conf_int(alpha=0.05)

    # Interaction plus within-stratum local-rank adjustment.
    Xa = sm.add_constant(np.column_stack([c, cohort, interaction, centered_log_rank]))
    ma = sm.OLS(y, Xa).fit(cov_type="HC3")
    maci = ma.conf_int(alpha=0.05)

    # Pooled common-effect descriptive model with cohort fixed effect and local rank.
    Xp = sm.add_constant(np.column_stack([c, cohort, centered_log_rank]))
    mp = sm.OLS(y, Xp).fit(cov_type="HC3")
    mpci = mp.conf_int(alpha=0.05)

    # Direct effect-difference CI from independent Welch-style group contrasts.
    effect_diff = rs["mean_difference"] - ds["mean_difference"]
    effect_diff_se = math.sqrt(
        rs["mean_difference_se"] ** 2 + ds["mean_difference_se"] ** 2
    )
    z = stats.norm.ppf(0.975)
    effect_diff_ci = [
        effect_diff - z * effect_diff_se,
        effect_diff + z * effect_diff_se,
    ]

    # Nonparametric bootstrap of the difference in cohort-specific claim gaps.
    # Resampling is performed independently within each cohort-by-claim cell so
    # observed group sizes remain fixed.
    dy = vec(drows, "d_vpf_technical_score")
    dc = claim(drows)
    ry = vec(rrows, "d_vpf_technical_score")
    rc = claim(rrows)
    boot_effect_diff = np.empty(30000)
    for b in range(len(boot_effect_diff)):
        d1 = rng.choice(dy[dc], size=int(dc.sum()), replace=True)
        d0 = rng.choice(dy[~dc], size=int((~dc).sum()), replace=True)
        r1 = rng.choice(ry[rc], size=int(rc.sum()), replace=True)
        r0 = rng.choice(ry[~rc], size=int((~rc).sum()), replace=True)
        boot_effect_diff[b] = (np.mean(r1) - np.mean(r0)) - (
            np.mean(d1) - np.mean(d0)
        )
    effect_diff_boot_ci = [
        float(x) for x in np.quantile(boot_effect_diff, [0.025, 0.975])
    ]

    result = {
        "seed": SEED,
        "inputs": {
            "corrected_discovery": str(DISC.relative_to(ROOT)),
            "independent_replication": str(REPL.relative_to(ROOT)),
        },
        "discovery": ds,
        "replication": rs,
        "effect_difference_replication_minus_discovery": {
            "estimate": effect_diff,
            "se": effect_diff_se,
            "ci95_normal_approx": effect_diff_ci,
            "bootstrap_ci95": effect_diff_boot_ci,
            "bootstrap_draws": len(boot_effect_diff),
        },
        "stratum_interaction_unadjusted": {
            "claim_discovery_beta": float(m.params[1]),
            "replication_main_beta": float(m.params[2]),
            "claim_x_replication_beta": float(m.params[3]),
            "interaction_se": float(m.bse[3]),
            "interaction_p": float(m.pvalues[3]),
            "interaction_ci95": [float(mci[3, 0]), float(mci[3, 1])],
            "r2": float(m.rsquared),
        },
        "stratum_interaction_local_rank_adjusted": {
            "claim_discovery_beta": float(ma.params[1]),
            "replication_main_beta": float(ma.params[2]),
            "claim_x_replication_beta": float(ma.params[3]),
            "interaction_se": float(ma.bse[3]),
            "interaction_p": float(ma.pvalues[3]),
            "interaction_ci95": [float(maci[3, 0]), float(maci[3, 1])],
            "within_stratum_log_rank_beta": float(ma.params[4]),
            "within_stratum_log_rank_p": float(ma.pvalues[4]),
            "r2": float(ma.rsquared),
        },
        "pooled_common_effect_descriptive": {
            "attestation_beta": float(mp.params[1]),
            "attestation_se": float(mp.bse[1]),
            "attestation_p": float(mp.pvalues[1]),
            "attestation_ci95": [float(mpci[1, 0]), float(mpci[1, 1])],
            "replication_stratum_beta": float(mp.params[2]),
            "within_stratum_log_rank_beta": float(mp.params[3]),
            "r2": float(mp.rsquared),
            "interpretation": (
                "Descriptive common-effect model only; cohort-specific estimates "
                "and the interaction remain primary for assessing transportability."
            ),
        },
        "claim_boundary": {
            "supported": [
                "A strong positive claim-posture association is present in the corrected Top-1000 discovery cohort.",
                "The same large effect is not reproduced in the independent ranks-1001-to-2000 cohort.",
                "Short-term D-VPF score repeatability is exact across three sequential scans for the corrected discovery cohort.",
            ],
            "not_supported": [
                "A universal or stable-magnitude signaling effect across Tranco rank strata.",
                "A causal effect of attestation on technical posture.",
                "A claim that lower-ranked services show meaningful decoupling; the replication interval is wide and includes both negative and positive effects.",
            ],
        },
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    jp = OUTDIR / "cross_stratum_summary.json"
    md = OUTDIR / "cross_stratum_report.md"
    jp.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Corrected Discovery and Independent Replication Analysis",
        "",
        "## Corrected discovery cohort",
        f"- N={ds['n']} ({ds['claimers']} claimers, {ds['nonclaimers']} non-claimers).",
        f"- Means: {ds['claimers_mean']:.2f} vs {ds['nonclaimers_mean']:.2f}; gap={ds['mean_difference']:.2f}.",
        f"- 95% CI: [{ds['ci95'][0]:.2f}, {ds['ci95'][1]:.2f}].",
        f"- Welch p={ds['welch_p']:.6f}; Mann-Whitney p={ds['mann_whitney_p']:.6f}; d={ds['cohens_d']:.3f}.",
        f"- Rank-adjusted HC3 beta={ds['rank_adjusted_hc3']['claim_beta']:.2f}, p={ds['rank_adjusted_hc3']['claim_p']:.6g}.",
        f"- Permutation p={ds['permutation_p']:.6f}; bootstrap CI=[{ds['bootstrap_ci95'][0]:.2f}, {ds['bootstrap_ci95'][1]:.2f}].",
        "",
        "## Independent replication cohort",
        f"- N={rs['n']} ({rs['claimers']} claimers, {rs['nonclaimers']} non-claimers).",
        f"- Means: {rs['claimers_mean']:.2f} vs {rs['nonclaimers_mean']:.2f}; gap={rs['mean_difference']:.2f}.",
        f"- 95% CI: [{rs['ci95'][0]:.2f}, {rs['ci95'][1]:.2f}].",
        f"- Welch p={rs['welch_p']:.4f}; Mann-Whitney p={rs['mann_whitney_p']:.4f}; d={rs['cohens_d']:.3f}.",
        f"- Rank-adjusted HC3 beta={rs['rank_adjusted_hc3']['claim_beta']:.2f}, p={rs['rank_adjusted_hc3']['claim_p']:.4f}.",
        f"- Permutation p={rs['permutation_p']:.4f}; bootstrap CI=[{rs['bootstrap_ci95'][0]:.2f}, {rs['bootstrap_ci95'][1]:.2f}].",
        "",
        "## Cross-stratum transportability",
        f"- Replication-minus-discovery effect difference={effect_diff:.2f}, approximate 95% CI [{effect_diff_ci[0]:.2f}, {effect_diff_ci[1]:.2f}].",
        f"- Stratified bootstrap 95% CI for the effect difference: [{effect_diff_boot_ci[0]:.2f}, {effect_diff_boot_ci[1]:.2f}].",
        f"- Claim-by-replication interaction={ma.params[3]:.2f}, 95% CI [{maci[3,0]:.2f}, {maci[3,1]:.2f}], p={ma.pvalues[3]:.4f} after within-stratum rank adjustment.",
        f"- Within-stratum log-rank term p={ma.pvalues[4]:.4f}.",
        "",
        "## Interpretation",
        "- The corrected Top-1000 cohort shows a large positive association.",
        "- The independent lower-rank cohort does not reproduce that magnitude; its estimate is near zero with a wide interval.",
        "- The cross-stratum interaction quantifies this attenuation and should replace any universal signaling claim.",
        "- Neither stratum supports causal inference.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "discovery": {
            "n": ds["n"],
            "gap": ds["mean_difference"],
            "ci95": ds["ci95"],
            "welch_p": ds["welch_p"],
            "d": ds["cohens_d"],
            "rank_adjusted_beta": ds["rank_adjusted_hc3"]["claim_beta"],
            "rank_adjusted_p": ds["rank_adjusted_hc3"]["claim_p"],
            "loo_all_welch_p_below_005": ds["leave_one_service_out"]["all_welch_p_below_005"],
        },
        "replication": {
            "n": rs["n"],
            "gap": rs["mean_difference"],
            "ci95": rs["ci95"],
            "welch_p": rs["welch_p"],
            "d": rs["cohens_d"],
            "rank_adjusted_beta": rs["rank_adjusted_hc3"]["claim_beta"],
            "rank_adjusted_p": rs["rank_adjusted_hc3"]["claim_p"],
        },
        "interaction_adjusted": result["stratum_interaction_local_rank_adjusted"],
        "pooled_descriptive": result["pooled_common_effect_descriptive"],
        "json_out": str(jp),
        "md_out": str(md),
    }, indent=2))


if __name__ == "__main__":
    main()
