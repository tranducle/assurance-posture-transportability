#!/bin/sh
set -eu

PYTHON="${PYTHON:-python3}"

$PYTHON 5_Experiments_Simulations/scripts/build_canonical_labels.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_cross_stratum.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_robustness.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_weight_sensitivity.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_repeatability.py
$PYTHON 5_Experiments_Simulations/scripts/audit_retrieval_labels.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_exposure_ablation.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_cross_stratum_permutation.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_retrieval_failure_taxonomy.py
$PYTHON 5_Experiments_Simulations/scripts/analyze_tradplus_timing_sensitivity.py
$PYTHON verify_results.py
