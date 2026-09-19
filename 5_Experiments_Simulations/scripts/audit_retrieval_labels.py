#!/usr/bin/env python3
"""Audit automated claim retrieval against canonical-v2 adjudicated labels."""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISC_AUTO = ROOT / "5_Experiments_Simulations/data/final_empirical_dataset.csv"
DISC_FINAL = ROOT / "5_Experiments_Simulations/strengthening/canonical_v2/discovery_canonical_v2.csv"
REPL_AUTO = ROOT / "5_Experiments_Simulations/strengthening/replication/vendor_compliance_replication.csv"
REPL_FINAL = ROOT / "5_Experiments_Simulations/strengthening/canonical_v2/replication_canonical_v2.csv"
OUT_JSON = ROOT / "6_Analysis_Results/strengthening/canonical_v2_exposure_retrieval_audit.json"
OUT_MD = ROOT / "6_Analysis_Results/strengthening/canonical_v2_exposure_retrieval_audit.md"


def load(path):
    with path.open(encoding="utf-8") as fh:
        return {r["domain"]: r for r in csv.DictReader(fh)}


def positive(row):
    return int(row["total_claimed_attestations"]) > 0


def audit(auto, final):
    domains = sorted(set(auto).intersection(final))
    tp = fp = fn = tn = 0
    disagreements = []
    for d in domains:
        a = positive(auto[d])
        f = positive(final[d])
        if a and f:
            tp += 1
        elif a and not f:
            fp += 1
            disagreements.append({"domain": d, "auto": 1, "final": 0})
        elif (not a) and f:
            fn += 1
            disagreements.append({"domain": d, "auto": 0, "final": 1})
        else:
            tn += 1
    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    specificity = tn / (tn + fp) if tn + fp else None
    accuracy = (tp + tn) / n if n else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    return {
        "n": n, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": precision, "recall": recall,
        "specificity": specificity, "accuracy": accuracy, "f1": f1,
        "disagreements": disagreements,
    }


def main():
    d = audit(load(DISC_AUTO), load(DISC_FINAL))
    r = audit(load(REPL_AUTO), load(REPL_FINAL))
    result = {
        "reference_label": (
            "canonical-v2 first-party adjudicated observed public claim; "
            "this is a study reference, not an independent certification gold standard"
        ),
        "scope_rule": (
            "Positive when first-party target assurance evidence is attributable to the sampled "
            "brand/vendor or explicitly represented service/platform family."
        ),
        "discovery": d,
        "replication": r,
        "timing_note": (
            "Discovery negative-label re-audit occurred after preliminary retrieval validation; "
            "replication adjudication was performed before D-VPF outcome collection except for "
            "one later TradPlus ISO correction based on direct first-party evidence."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Canonical-v2 Exposure Retrieval Audit", "",
        result["reference_label"], "",
        "| Stratum | TP | FP | FN | TN | Precision | Recall | Specificity | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, x in [("Ranks 1-1000", d), ("Ranks 1001-2000", r)]:
        lines.append(
            f"| {name} | {x['tp']} | {x['fp']} | {x['fn']} | {x['tn']} | "
            f"{x['precision']:.3f} | {x['recall']:.3f} | {x['specificity']:.3f} | {x['f1']:.3f} |"
        )
    lines.extend(["", "## Timing note", result["timing_note"]])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
