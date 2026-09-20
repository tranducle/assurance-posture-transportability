#!/usr/bin/env python3
"""Classify canonical false-negative assurance sources by first-party URL path.

Taxonomy is deterministic and based only on URL/domain tokens:
- trust_compliance_audit
- documentation_support_faq
- blog_news_press
- other_first_party

The purpose is error analysis of retrieval location, not semantic certification validation.
"""

import csv
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DISC = ROOT / "data/discovery/negative_reaudit.csv"
REPL_PRE = ROOT / "data/replication/assurance_adjudication_pre_outcome.csv"
SCOPE = ROOT / "data/derived/scope_reconciliation.csv"
OUT_JSON = ROOT / "results/retrieval_failure_taxonomy.json"
OUT_MD = ROOT / "results/retrieval_failure_taxonomy.md"

TRUST_TOKENS = (
    "trust", "compliance", "certification", "certifications", "certificate",
    "repository", "audit", "audits", "transparency", "security-practices",
)
DOC_TOKENS = (
    "support", "docs", "documentation", "help", "faq", "experienceleague",
    "legal/contractingfaq",
)
NEWS_TOKENS = ("blog", "news", "press", "announcement")


def classify(url):
    low = url.lower()
    if any(t in low for t in TRUST_TOKENS):
        return "trust_compliance_audit"
    if any(t in low for t in DOC_TOKENS):
        return "documentation_support_faq"
    if any(t in low for t in NEWS_TOKENS):
        return "blog_news_press"
    return "other_first_party"


def main():
    misses = []

    with DISC.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if int(r["auto_iso"]) + int(r["auto_soc2"]) + int(r["auto_csa"]) == 0 and int(r["final_any"]) == 1:
                misses.append({
                    "cohort": "discovery",
                    "domain": r["domain"],
                    "source": r["source"],
                })

    # Replication false negatives in canonical v2 are Cloud, VMware, TradPlus.
    with REPL_PRE.open(encoding="utf-8") as fh:
        pre = {r["domain"]: r for r in csv.DictReader(fh)}
    with SCOPE.open(encoding="utf-8") as fh:
        scope = {r["domain"]: r for r in csv.DictReader(fh)}
    for domain in ("cloud.com", "vmware.com", "tradplusad.com"):
        if domain == "tradplusad.com":
            url = scope[domain]["source"]
        else:
            url = pre[domain]["source"].split(" ; ")[0]
        misses.append({"cohort": "replication", "domain": domain, "source": url})

    for x in misses:
        x["category"] = classify(x["source"])

    counts = Counter(x["category"] for x in misses)
    by_cohort = {
        c: Counter(x["category"] for x in misses if x["cohort"] == c)
        for c in ("discovery", "replication")
    }
    total = len(misses)
    result = {
        "n_false_negatives": total,
        "taxonomy_rule": {
            "trust_compliance_audit": list(TRUST_TOKENS),
            "documentation_support_faq": list(DOC_TOKENS),
            "blog_news_press": list(NEWS_TOKENS),
            "other_first_party": "no listed token matched",
        },
        "counts": dict(counts),
        "fractions": {k: v / total for k, v in counts.items()},
        "by_cohort": {k: dict(v) for k, v in by_cohort.items()},
        "rows": misses,
        "interpretation_boundary": (
            "Categories describe where missed first-party evidence was located. "
            "They do not independently validate assurance scope or certificate authenticity."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

    lines = [
        "# Analysis Retrieval Failure Taxonomy", "",
        f"- False negatives analyzed: {total}.",
        "",
        "| Source-location category | Count | Fraction |",
        "|---|---:|---:|",
    ]
    for cat in ("trust_compliance_audit", "documentation_support_faq", "blog_news_press", "other_first_party"):
        n = counts.get(cat, 0)
        lines.append(f"| {cat} | {n} | {n/total:.1%} |")
    lines.extend(["", result["interpretation_boundary"]])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
