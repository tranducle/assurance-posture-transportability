#!/usr/bin/env python3
"""Sensitivity of the public-assurance exposure to target-standard composition.

The primary exposure is any adjudicated ISO/IEC 27001, SOC 2, or CSA STAR claim.
This script reruns the cohort comparison after omitting each standard from the
binary exposure definition. It tests whether the primary association depends
entirely on one target assurance mechanism; it does not estimate causal effects
of individual standards.
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
OUT_JSON = ROOT / "results/exposure_definition_sensitivity.json"
OUT_MD = ROOT / "results/exposure_definition_sensitivity.md"

STANDARDS = {
    "ISO27001": "has_iso_27001",
    "SOC2": "has_soc_2",
    "CSASTAR": "has_csa_star",
}


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def compare(rows, active_cols):
    y = np.asarray([float(r["d_vpf_technical_score"]) for r in rows])
    z = np.asarray([any(int(r[c]) > 0 for c in active_cols) for r in rows], dtype=bool)
    n1, n0 = int(z.sum()), int((~z).sum())
    if n1 < 2 or n0 < 2:
        return {"valid": False, "n_positive": n1, "n_negative": n0}

    a, b = y[z], y[~z]
    mean1, mean0 = float(np.mean(a)), float(np.mean(b))
    sd1, sd0 = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
    gap = mean1 - mean0
    se = math.sqrt(sd1**2 / n1 + sd0**2 / n0)
    df = (sd1**2 / n1 + sd0**2 / n0) ** 2 / (
        (sd1**2 / n1) ** 2 / (n1 - 1) + (sd0**2 / n0) ** 2 / (n0 - 1)
    )
    tc = stats.t.ppf(0.975, df)
    t = stats.ttest_ind(a, b, equal_var=False)
    u = stats.mannwhitneyu(a, b, alternative="two-sided")
    pooled = math.sqrt(((n1 - 1) * sd1**2 + (n0 - 1) * sd0**2) / (n1 + n0 - 2))

    ranks = np.asarray([float(r["rank"]) for r in rows])
    X = sm.add_constant(np.column_stack([z.astype(int), np.log10(ranks)]))
    m = sm.OLS(y, X).fit(cov_type="HC3")
    ci = m.conf_int(alpha=0.05)

    return {
        "valid": True,
        "n_positive": n1,
        "n_negative": n0,
        "mean_positive": mean1,
        "mean_negative": mean0,
        "mean_difference": gap,
        "ci95": [float(gap - tc * se), float(gap + tc * se)],
        "welch_p": float(t.pvalue),
        "mann_whitney_p": float(u.pvalue),
        "cohens_d": float(gap / pooled),
        "hc3_beta": float(m.params[1]),
        "hc3_ci95": [float(ci[1, 0]), float(ci[1, 1])],
        "hc3_p": float(m.pvalues[1]),
    }


def main():
    disc = load(DISC)
    repl = load(REPL)
    all_cols = list(STANDARDS.values())

    definitions = {
        "all_three": all_cols,
        "without_ISO27001": [STANDARDS["SOC2"], STANDARDS["CSASTAR"]],
        "without_SOC2": [STANDARDS["ISO27001"], STANDARDS["CSASTAR"]],
        "without_CSASTAR": [STANDARDS["ISO27001"], STANDARDS["SOC2"]],
    }

    result = {
        "purpose": (
            "Leave-one-standard-out sensitivity of the pooled public-assurance exposure. "
            "This tests construct dependence, not causal effects of standards."
        ),
        "definitions": {},
    }
    for name, cols in definitions.items():
        result["definitions"][name] = {
            "active_columns": cols,
            "discovery": compare(disc, cols),
            "replication_complete_case": compare(repl, cols),
        }

    result["summary"] = {
        "discovery_positive_gap_all_definitions": all(
            x["discovery"].get("mean_difference", 0) > 0
            for x in result["definitions"].values()
            if x["discovery"].get("valid")
        ),
        "replication_positive_gap_all_definitions": all(
            x["replication_complete_case"].get("mean_difference", 0) > 0
            for x in result["definitions"].values()
            if x["replication_complete_case"].get("valid")
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Exposure Definition Sensitivity",
        "",
        result["purpose"],
        "",
        "| Exposure definition | Discovery n+/n- | Discovery gap | Welch p | HC3 beta (p) | Replication n+/n- | Replication gap | Welch p |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "all_three": "ISO or SOC2 or CSA",
        "without_ISO27001": "SOC2 or CSA (ISO omitted)",
        "without_SOC2": "ISO or CSA (SOC2 omitted)",
        "without_CSASTAR": "ISO or SOC2 (CSA omitted)",
    }
    for name, x in result["definitions"].items():
        d, r = x["discovery"], x["replication_complete_case"]
        lines.append(
            f"| {labels[name]} | {d['n_positive']}/{d['n_negative']} | {d['mean_difference']:.2f} | "
            f"{d['welch_p']:.4g} | {d['hc3_beta']:.2f} ({d['hc3_p']:.4g}) | "
            f"{r['n_positive']}/{r['n_negative']} | {r['mean_difference']:.2f} | {r['welch_p']:.4g} |"
        )
    lines.extend([
        "",
        "Interpretation boundary: a positive leave-one-standard-out gap shows that the pooled direction "
        "is not exclusively created by the omitted standard. It does not show that each remaining "
        "standard has an independent causal effect.",
    ])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
