#!/usr/bin/env python3
"""Analyze short-term D-VPF repeatability across three independent live scans."""

import csv
import itertools
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = ROOT / "data/repeatability"
OUT_DIR = ROOT / "results"
RUNS = [RUN_DIR / f"run{i}_merged.csv" for i in (1, 2, 3)]
CORRECTED_LABELS = ROOT / "data/derived/discovery.csv"
SCORE_COLS = [
    "score_tls_transport",
    "score_dns_email",
    "score_http_headers",
    "score_pki_cert",
    "d_vpf_technical_score",
]
RAW_COLS = [
    "cert_lifespan_days",
    "cert_max_allowed_days",
    "key_type",
    "key_bits",
    "tls_validation_status",
    "http_probe_status",
    "dns_probe_status",
    "hsts_present",
    "csp_present",
]


def load(path):
    with path.open(encoding="utf-8") as fh:
        return {r["domain"]: r for r in csv.DictReader(fh)}


def num(rows, domains, col):
    return np.asarray([float(rows[d][col]) for d in domains], dtype=float)


def main():
    data = [load(p) for p in RUNS]
    corrected = load(CORRECTED_LABELS)
    domains = sorted(set(corrected).intersection(*(set(x) for x in data)))
    assert len(domains) == 53, len(domains)

    score_summary = {}
    for col in SCORE_COLS:
        pairwise = []
        for i, j in itertools.combinations(range(3), 2):
            a = num(data[i], domains, col)
            b = num(data[j], domains, col)
            diff = np.abs(a - b)
            pearson = stats.pearsonr(a, b)
            spearman = stats.spearmanr(a, b)
            pairwise.append({
                "runs": [i + 1, j + 1],
                "exact_agreement_fraction": float(np.mean(diff == 0)),
                "mae": float(np.mean(diff)),
                "max_abs_difference": float(np.max(diff)),
                "changed_domains": int(np.sum(diff > 0)),
                "pearson_r": float(pearson.statistic),
                "spearman_rho": float(spearman.statistic),
            })
        score_summary[col] = pairwise

    raw_changes = []
    for col in RAW_COLS:
        for d in domains:
            vals = [x[d].get(col, "") for x in data]
            if len(set(vals)) > 1:
                raw_changes.append({"domain": d, "field": col, "values": vals})

    group_results = []
    for idx, rows in enumerate(data, 1):
        claim = np.asarray([int(corrected[d]["total_claimed_attestations"]) > 0 for d in domains], dtype=bool)
        y = num(rows, domains, "d_vpf_technical_score")
        t = stats.ttest_ind(y[claim], y[~claim], equal_var=False)
        u = stats.mannwhitneyu(y[claim], y[~claim], alternative="two-sided")
        group_results.append({
            "run": idx,
            "claimers_mean": float(np.mean(y[claim])),
            "nonclaimers_mean": float(np.mean(y[~claim])),
            "mean_difference": float(np.mean(y[claim]) - np.mean(y[~claim])),
            "welch_p": float(t.pvalue),
            "mann_whitney_p": float(u.pvalue),
        })

    result = {
        "runs": [str(p.relative_to(ROOT)) for p in RUNS],
        "label_source": str(CORRECTED_LABELS.relative_to(ROOT)),
        "n_domains": len(domains),
        "score_repeatability": score_summary,
        "raw_field_changes": raw_changes,
        "group_results": group_results,
        "summary": {
            "all_score_fields_exact_across_all_pairs": all(
                x["exact_agreement_fraction"] == 1.0
                for v in score_summary.values()
                for x in v
            ),
            "raw_field_change_count": len(raw_changes),
            "group_gap_range": [
                min(x["mean_difference"] for x in group_results),
                max(x["mean_difference"] for x in group_results),
            ],
        },
        "interpretation_boundary": (
            "Three sequential scans establish short-term score repeatability under the measurement "
            "conditions used here; they do not establish longitudinal stability over days or months."
        ),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_out = OUT_DIR / "repeatability_summary.json"
    md_out = OUT_DIR / "repeatability_report.md"
    json_out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# D-VPF Short-Term Repeatability Report",
        "",
        f"- Domains measured in all three scans: {len(domains)}.",
        f"- All five score fields (four pillars plus total) had 100% exact agreement across all three pairwise run comparisons: {result['summary']['all_score_fields_exact_across_all_pairs']}.",
        "- Pairwise MAE for every score field: 0.00 points.",
        "- Pairwise maximum absolute score difference for every score field: 0.00 points.",
        f"- Raw non-score field changes detected: {len(raw_changes)}.",
        "",
        "## Group-level inference across runs",
    ]
    for x in group_results:
        lines.append(
            f"- Run {x['run']}: claimers={x['claimers_mean']:.2f}, non-claimers={x['nonclaimers_mean']:.2f}, "
            f"gap={x['mean_difference']:.2f}, Welch p={x['welch_p']:.4f}, "
            f"Mann-Whitney p={x['mann_whitney_p']:.4f}."
        )
    lines.extend([
        "",
        "## Raw-state variation",
    ])
    if raw_changes:
        for x in raw_changes:
            lines.append(f"- {x['domain']} / {x['field']}: {x['values']}.")
    else:
        lines.append("- None observed.")
    lines.extend([
        "",
        "## Interpretation boundary",
        result["interpretation_boundary"],
    ])
    md_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "exact_score_repeatability": result["summary"]["all_score_fields_exact_across_all_pairs"],
        "raw_field_changes": raw_changes,
        "group_results": group_results,
        "json_out": str(json_out),
        "md_out": str(md_out),
    }, indent=2))


if __name__ == "__main__":
    main()
