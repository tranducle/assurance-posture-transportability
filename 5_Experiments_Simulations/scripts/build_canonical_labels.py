#!/usr/bin/env python3
"""Build canonical v2 discovery and replication cohorts after scope-rule reconciliation.

Scope rule:
A target public attestation claim is positive when first-party evidence is
attributable to the sampled brand/vendor or to an explicitly represented
service/platform family. Claims only about unrelated sibling products,
customers, hosting providers, or an ultimate parent without sampled-brand
attribution are excluded.

Discovery uses the existing uniform negative re-audit and alias-deduplicated
dataset. Replication uses the pre-outcome adjudication ledger, plus one later
first-party correction for TradPlus ISO/IEC 27001 that was missed in that
pre-outcome audit. Technical scores are never changed here.
"""

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DISC_SRC = ROOT / "5_Experiments_Simulations/strengthening/discovery_corrected_empirical.csv"
REPL_TECH_SRC = ROOT / "5_Experiments_Simulations/strengthening/replication/final_empirical_replication.csv"
REPL_PRE = ROOT / "5_Experiments_Simulations/strengthening/replication/attestation_adjudication_pre_outcome.csv"

OUT_DIR = ROOT / "5_Experiments_Simulations/strengthening/canonical_v2"
DISC_OUT = OUT_DIR / "discovery_canonical_v2.csv"
REPL_OUT = OUT_DIR / "replication_canonical_v2.csv"
REPL_COMPLETE_OUT = OUT_DIR / "replication_canonical_v2_complete.csv"
LEDGER = OUT_DIR / "scope_reconciliation_ledger.csv"
SUMMARY = ROOT / "6_Analysis_Results/strengthening/canonical_v2_build_summary.json"

TRADPLUS = {
    "iso": 1,
    "soc2": 0,
    "csa": 0,
    "url": "https://www.tradplusad.com/news/45",
    "reason": (
        "First-party TradPlus announcement states that TradPlus formally obtained "
        "an ISO/IEC 27001:2013 information-security management certificate."
    ),
}

DISPUTED_SCOPE = [
    {
        "domain": "adobe.io",
        "decision": "positive",
        "source": "https://blog.adobe.com/en/publish/2016/12/06/soc-2-availability-across-clouds",
        "reason": (
            "Sampled adobe.io is an Adobe developer/platform domain. Adobe first-party "
            "material states SOC 2 Type 2 and ISO 27001 coverage across Adobe enterprise "
            "cloud offerings. Counted as a vendor/platform-associated public assurance signal; "
            "not treated as proof that the exact endpoint is within certificate scope."
        ),
    },
    {
        "domain": "visma.com",
        "decision": "positive",
        "source": "https://www.visma.com/trust-centre/vismaclouddelivery",
        "reason": (
            "Sampled visma.com is the Visma group domain. Visma describes VCDM as a "
            "group-wide cloud delivery framework with an ISO 27001-certified ISMS. "
            "Counted as a vendor/group-associated public assurance signal."
        ),
    },
    {
        "domain": "vmware.com",
        "decision": "positive",
        "source": "https://blogs.vmware.com/tanzu/vmware-tanzu-mission-control-iso-iec-27001-soc-2-type-1-csa-star-certifications/",
        "reason": (
            "Sampled vmware.com represents the VMware enterprise technology vendor. "
            "VMware first-party material documents ISO 27001, SOC 2, and CSA STAR for "
            "Tanzu Mission Control, an explicitly represented VMware SaaS platform. "
            "Counted as vendor/platform-associated signal under the frozen scope rule."
        ),
    },
    {
        "domain": "tradplusad.com",
        "decision": "positive",
        "source": TRADPLUS["url"],
        "reason": TRADPLUS["reason"],
    },
]


def load(path):
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    # Discovery branch is already the uniform negative re-audit + alias-deduplicated file.
    shutil.copy2(DISC_SRC, DISC_OUT)
    discovery = load(DISC_OUT)

    # Replication: technical values from the measured file, labels from the
    # pre-outcome adjudication ledger, with the documented TradPlus correction.
    tech_rows = {r["domain"]: r for r in load(REPL_TECH_SRC)}
    pre_rows = {r["domain"]: r for r in load(REPL_PRE)}
    if set(tech_rows) != set(pre_rows):
        raise RuntimeError("Replication technical and adjudication domain sets differ.")

    replication = []
    for domain in sorted(tech_rows, key=lambda d: int(tech_rows[d]["rank"])):
        r = dict(tech_rows[domain])
        p = pre_rows[domain]
        iso = int(p["final_iso"])
        soc = int(p["final_soc2"])
        csa = int(p["final_csa"])
        evidence = r.get("attestation_evidence", "")
        if domain == "tradplusad.com":
            iso, soc, csa = TRADPLUS["iso"], TRADPLUS["soc2"], TRADPLUS["csa"]
            evidence = f"HIGH_RECALL: {TRADPLUS['url']} :: {TRADPLUS['reason']}"
        r["has_iso_27001"] = str(iso)
        r["has_soc_2"] = str(soc)
        r["has_csa_star"] = str(csa)
        r["total_claimed_attestations"] = str(iso + soc + csa)
        r["attestation_evidence"] = evidence
        replication.append(r)

    with REPL_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=replication[0].keys())
        w.writeheader()
        w.writerows(replication)

    ledger_rows = []
    for item in DISPUTED_SCOPE:
        ledger_rows.append(item)
    ledger_rows.extend([
        {
            "domain": "trustarc.com",
            "decision": "SOC2_only",
            "source": "https://trustarc.com/resource/onetrust-competitors-trustarc/",
            "reason": (
                "Retain vendor-specific SOC 2 signal; do not count generic ISO navigation "
                "as a TrustArc ISO 27001 claim."
            ),
        },
        {
            "domain": "nextcloud.com",
            "decision": "negative",
            "source": "https://nextcloud.com/partners/",
            "reason": (
                "Automated ISO hit described a partner rather than Nextcloud; no direct "
                "target Nextcloud ISO/SOC2/CSA STAR claim was established."
            ),
        },
        {
            "domain": "sun.com",
            "decision": "negative",
            "source": "",
            "reason": (
                "Oracle parent/cloud certifications are not assigned to the legacy Sun-branded "
                "sampled endpoint without sampled-brand/service attribution."
            ),
        },
    ])
    complete_replication = [
        r for r in replication
        if r.get("tls_validation_status") in ("verified", "unverified")
        and r.get("http_probe_status") == "observed"
        and r.get("dns_probe_status") == "observed"
    ]
    with REPL_COMPLETE_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=replication[0].keys())
        w.writeheader()
        w.writerows(complete_replication)

    with LEDGER.open("w", newline="", encoding="utf-8") as fh:
        fields = ["domain", "decision", "source", "reason"]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(ledger_rows)

    result = {
        "scope_rule": (
            "Positive if first-party target assurance evidence is attributable to the sampled "
            "brand/vendor or explicitly represented service/platform family; unrelated sibling, "
            "customer, hosting-provider, or unsupported parent-only claims are excluded."
        ),
        "discovery": {
            "path": str(DISC_OUT.relative_to(ROOT)),
            "n": len(discovery),
            "claimers": sum(int(r["total_claimed_attestations"]) > 0 for r in discovery),
            "nonclaimers": sum(int(r["total_claimed_attestations"]) == 0 for r in discovery),
        },
        "replication": {
            "path": str(REPL_OUT.relative_to(ROOT)),
            "n": len(replication),
            "claimers": sum(int(r["total_claimed_attestations"]) > 0 for r in replication),
            "nonclaimers": sum(int(r["total_claimed_attestations"]) == 0 for r in replication),
            "tradplus_late_correction": True,
            "complete_case_path": str(REPL_COMPLETE_OUT.relative_to(ROOT)),
            "complete_case_n": len(complete_replication),
            "incomplete_technical_domains": sorted(set(r["domain"] for r in replication) - set(r["domain"] for r in complete_replication)),
        },
        "scope_ledger": str(LEDGER.relative_to(ROOT)),
    }
    SUMMARY.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
