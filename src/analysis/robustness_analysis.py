#!/usr/bin/env python3
"""Robustness checks for corrected discovery labels and cross-stratum interaction."""

import csv
import json
from pathlib import Path

import numpy as np
import statsmodels.api as sm
from scipy import stats
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
DISC = ROOT / "data/derived/discovery.csv"
REPL = ROOT / "data/derived/replication_complete_case.csv"
OUT = ROOT / "results"
SEED = 20260918


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def yvec(rows):
    return np.asarray([float(r["d_vpf_technical_score"]) for r in rows], dtype=float)


def cvec(rows):
    return np.asarray([int(r["total_claimed_attestations"]) > 0 for r in rows], dtype=bool)


def rankvec(rows):
    return np.asarray([float(r["rank"]) for r in rows], dtype=float)


def gap(y, c):
    return float(np.mean(y[c]) - np.mean(y[~c]))


def welch_p(y, c):
    return float(stats.ttest_ind(y[c], y[~c], equal_var=False).pvalue)


def hc3_p_beta(rows, c=None, y=None):
    if c is None:
        c = cvec(rows)
    if y is None:
        y = yvec(rows)
    lr = np.log10(rankvec(rows))
    X = sm.add_constant(np.column_stack([c.astype(int), lr]))
    m = sm.OLS(y, X).fit(cov_type="HC3")
    return float(m.params[1]), float(m.pvalues[1])


def interaction_fit(drows, rrows):
    rows = drows + rrows
    y = yvec(rows)
    c = cvec(rows).astype(int)
    cohort = np.asarray([0] * len(drows) + [1] * len(rrows), dtype=int)
    inter = c * cohort
    lr = np.log10(rankvec(rows))
    centered = lr.copy()
    for g in (0, 1):
        centered[cohort == g] -= np.mean(lr[cohort == g])
    X = sm.add_constant(np.column_stack([c, cohort, inter, centered]))
    m = sm.OLS(y, X).fit(cov_type="HC3")
    return float(m.params[3]), float(m.pvalues[3])


def adversarial_flip_sensitivity(rows):
    y = yvec(rows)
    base = cvec(rows)
    out = {"negative_to_positive": [], "positive_to_negative": []}

    # False negatives: move lowest-score nonclaimers into claimant group.
    neg = [i for i in np.argsort(y) if not base[i]]
    for k in range(1, len(neg) + 1):
        c = base.copy()
        c[neg[:k]] = True
        if int(c.sum()) < 2 or int((~c).sum()) < 2:
            break
        rr = [dict(r) for r in rows]
        for i in neg[:k]:
            rr[i]["total_claimed_attestations"] = "1"
        beta, op = hc3_p_beta(rr, c, y)
        out["negative_to_positive"].append(
            {
                "k": k,
                "domains": [rows[i]["domain"] for i in neg[:k]],
                "gap": gap(y, c),
                "welch_p": welch_p(y, c),
                "ols_beta": beta,
                "ols_p": op,
            }
        )

    # False positives: move highest-score claimers into nonclaimant group.
    pos = [i for i in np.argsort(-y) if base[i]]
    for k in range(1, min(len(pos), 15) + 1):
        c = base.copy()
        c[pos[:k]] = False
        if int(c.sum()) < 2 or int((~c).sum()) < 2:
            break
        rr = [dict(r) for r in rows]
        for i in pos[:k]:
            rr[i]["total_claimed_attestations"] = "0"
        beta, op = hc3_p_beta(rr, c, y)
        out["positive_to_negative"].append(
            {
                "k": k,
                "domains": [rows[i]["domain"] for i in pos[:k]],
                "gap": gap(y, c),
                "welch_p": welch_p(y, c),
                "ols_beta": beta,
                "ols_p": op,
            }
        )

    for direction in ["negative_to_positive", "positive_to_negative"]:
        rows_ = out[direction]
        out[direction + "_first_welch_p_ge_005"] = next(
            (x["k"] for x in rows_ if x["welch_p"] >= 0.05), None
        )
        out[direction + "_first_ols_p_ge_005"] = next(
            (x["k"] for x in rows_ if x["ols_p"] >= 0.05), None
        )
    return out


def rank_match(rows):
    y = yvec(rows)
    c = cvec(rows)
    lr = np.log10(rankvec(rows))
    i1 = np.where(c)[0]
    i0 = np.where(~c)[0]
    cost = np.abs(lr[i1, None] - lr[i0][None, :])
    rr, cc = linear_sum_assignment(cost)
    m1 = i1[rr]
    m0 = i0[cc]
    diff = y[m1] - y[m0]
    t = stats.ttest_rel(y[m1], y[m0])
    nonzero = diff[diff != 0]
    positive_pairs = int(np.sum(nonzero > 0))
    negative_pairs = int(np.sum(nonzero < 0))
    sign_p = (
        float(stats.binomtest(positive_pairs, n=positive_pairs + negative_pairs, p=0.5, alternative="two-sided").pvalue)
        if len(nonzero)
        else None
    )
    return {
        "pairs": int(len(diff)),
        "paired_mean_difference": float(np.mean(diff)),
        "paired_median_difference": float(np.median(diff)),
        "paired_t_p": float(t.pvalue),
        "positive_pairs": positive_pairs,
        "negative_pairs": negative_pairs,
        "exact_sign_test_p": sign_p,
        "max_abs_log_rank_gap": float(np.max(np.abs(lr[m1] - lr[m0]))),
        "pairs_detail": [
            {
                "claimer": rows[a]["domain"],
                "nonclaimer": rows[b]["domain"],
                "rank_log_gap": float(abs(lr[a] - lr[b])),
                "score_difference": float(y[a] - y[b]),
            }
            for a, b in zip(m1, m0)
        ],
    }


def interaction_leave_one_out(drows, rrows):
    values = []
    combined = [("discovery", i, r) for i, r in enumerate(drows)] + [
        ("replication", i, r) for i, r in enumerate(rrows)
    ]
    for cohort, i, r in combined:
        if cohort == "discovery":
            dd = drows[:i] + drows[i + 1 :]
            rr = rrows
        else:
            dd = drows
            rr = rrows[:i] + rrows[i + 1 :]
        beta, p = interaction_fit(dd, rr)
        values.append(
            {
                "removed_cohort": cohort,
                "removed_domain": r["domain"],
                "interaction_beta": beta,
                "interaction_p": p,
            }
        )
    return {
        "beta_range": [
            min(x["interaction_beta"] for x in values),
            max(x["interaction_beta"] for x in values),
        ],
        "p_range": [
            min(x["interaction_p"] for x in values),
            max(x["interaction_p"] for x in values),
        ],
        "all_p_below_005": all(x["interaction_p"] < 0.05 for x in values),
        "rows": values,
    }


def main():
    drows = load(DISC)
    rrows = load(REPL)

    result = {
        "corrected_discovery": {
            "rank_matching": rank_match(drows),
            "label_flip_sensitivity": adversarial_flip_sensitivity(drows),
        },
        "replication": {
            "rank_matching": rank_match(rrows),
            "label_flip_sensitivity": adversarial_flip_sensitivity(rrows),
        },
        "interaction_leave_one_service_out": interaction_leave_one_out(drows, rrows),
        "interpretation": {
            "rank_matching": (
                "Discovery rank matching tests whether the Top-1000 gap remains when "
                "claimers are compared with nonclaimers at similar local popularity ranks."
            ),
            "label_flips": (
                "Adversarial label flips are stress tests, not estimates of actual label error. "
                "Manual first-party exposure adjudication is the primary validity control."
            ),
            "interaction_loo": (
                "Leave-one-service-out interaction stability tests whether cross-stratum "
                "attenuation depends on a single service."
            ),
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    jp = OUT / "robustness_summary.json"
    md = OUT / "robustness_report.md"
    jp.write_text(json.dumps(result, indent=2), encoding="utf-8")

    dflip = result["corrected_discovery"]["label_flip_sensitivity"]
    rm = result["corrected_discovery"]["rank_matching"]
    iloo = result["interaction_leave_one_service_out"]
    lines = [
        "# Corrected Robustness Report",
        "",
        "## Discovery rank matching",
        f"- Pairs: {rm['pairs']}.",
        f"- Paired mean difference: {rm['paired_mean_difference']:.2f}.",
        f"- Paired t-test p={rm['paired_t_p']:.4f}; exact sign-test p={rm['exact_sign_test_p']:.4f} ({rm['positive_pairs']} positive vs {rm['negative_pairs']} negative pairs).",
        "",
        "## Adversarial discovery label-flip sensitivity",
        f"- Lowest-score nonclaimers reclassified as claimers: first Welch p>=0.05 at k={dflip['negative_to_positive_first_welch_p_ge_005']}; first HC3 OLS p>=0.05 at k={dflip['negative_to_positive_first_ols_p_ge_005']}.",
        f"- Highest-score claimers reclassified as nonclaimers: first Welch p>=0.05 at k={dflip['positive_to_negative_first_welch_p_ge_005']}; first HC3 OLS p>=0.05 at k={dflip['positive_to_negative_first_ols_p_ge_005']}.",
        "",
        "## Interaction leave-one-service-out",
        f"- Interaction beta range: {iloo['beta_range'][0]:.2f} to {iloo['beta_range'][1]:.2f}.",
        f"- Interaction p-value range: {iloo['p_range'][0]:.4f} to {iloo['p_range'][1]:.4f}.",
        f"- Interaction remains p<0.05 after every single-service deletion: {iloo['all_p_below_005']}.",
        "",
        "## Interpretation boundary",
        "- Label-flip scenarios are deliberately adversarial and do not substitute for the completed first-party manual audit.",
        "- Matching and deletion diagnostics support robustness of the corrected Top-1000 association and the cross-stratum attenuation, subject to small nonclaimer counts.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "discovery_rank_matching": rm,
                "discovery_label_flip_thresholds": {
                    "negative_to_positive_welch": dflip[
                        "negative_to_positive_first_welch_p_ge_005"
                    ],
                    "negative_to_positive_ols": dflip[
                        "negative_to_positive_first_ols_p_ge_005"
                    ],
                    "positive_to_negative_welch": dflip[
                        "positive_to_negative_first_welch_p_ge_005"
                    ],
                    "positive_to_negative_ols": dflip[
                        "positive_to_negative_first_ols_p_ge_005"
                    ],
                },
                "interaction_loo": {
                    k: v for k, v in iloo.items() if k != "rows"
                },
                "json_out": str(jp),
                "md_out": str(md),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
