#!/usr/bin/env python3
"""Verify generated result summaries against the frozen expected metrics."""

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"
E = json.loads((Path(__file__).resolve().parent / "expected_results.json").read_text())

def load(name):
    return json.loads((R / name).read_text())

def close(label, actual, expected, tol=1e-8):
    if not math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol):
        raise SystemExit(f"FAIL {label}: actual={actual} expected={expected}")
    print(f"PASS {label}: {actual}")

cross = load("cross_stratum_summary.json")
perm = load("cross_stratum_permutation.json")
repeat = load("repeatability_summary.json")
retr = load("retrieval_validation.json")
weights = load("weight_sensitivity_summary.json")

d = cross["discovery"]
r = cross["replication"]
close("discovery_n", d["n"], E["discovery"]["n"])
close("discovery_claimers", d["claimers"], E["discovery"]["claimers"])
close("discovery_nonclaimers", d["nonclaimers"], E["discovery"]["nonclaimers"])
close("discovery_gap", d["mean_difference"], E["discovery"]["gap"])
close("discovery_welch_p", d["welch_p"], E["discovery"]["welch_p"])

close("replication_n", r["n"], E["replication_complete"]["n"])
close("replication_claimers", r["claimers"], E["replication_complete"]["claimers"])
close("replication_nonclaimers", r["nonclaimers"], E["replication_complete"]["nonclaimers"])
close("replication_gap", r["mean_difference"], E["replication_complete"]["gap"])
close("replication_welch_p", r["welch_p"], E["replication_complete"]["welch_p"])

ix = cross["stratum_interaction_local_rank_adjusted"]
close("interaction_beta", ix["claim_x_replication_beta"], E["cross_stratum"]["interaction_beta"])
close("interaction_p", ix["interaction_p"], E["cross_stratum"]["interaction_p"])
ed = cross["effect_difference_replication_minus_discovery"]["bootstrap_ci95"]
close("bootstrap_ci_low", ed[0], E["cross_stratum"]["bootstrap_ci_low"])
close("bootstrap_ci_high", ed[1], E["cross_stratum"]["bootstrap_ci_high"])

close("cross_stratum_permutation_p", perm["two_sided_permutation_p"], E["permutation"]["p"])

if bool(repeat["summary"]["all_score_fields_exact_across_all_pairs"]) != E["repeatability"]["exact"]:
    raise SystemExit("FAIL repeatability exact-agreement flag")
close("repeatability_n", repeat["n_domains"], E["repeatability"]["n"])

close("discovery_retrieval_precision", retr["discovery"]["precision"], E["retrieval"]["discovery_precision"])
close("discovery_retrieval_recall", retr["discovery"]["recall"], E["retrieval"]["discovery_recall"])
close("replication_retrieval_precision", retr["replication"]["precision"], E["retrieval"]["replication_precision"])
close("replication_retrieval_recall", retr["replication"]["recall"], E["retrieval"]["replication_recall"])

close("weight_draws", weights["accepted_weight_vectors"], E["weight_sensitivity"]["draws"])
close("weight_discovery_min_gap", weights["discovery_gap_distribution"]["min"], E["weight_sensitivity"]["discovery_min_gap"])
close("weight_replication_min_gap", weights["replication_gap_distribution"]["min"], E["weight_sensitivity"]["replication_min_gap"])
close("weight_attenuation_max", weights["attenuation_distribution"]["max"], E["weight_sensitivity"]["attenuation_max"])

print("\nALL EXPECTED RESULT CHECKS PASSED")
