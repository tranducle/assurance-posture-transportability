#!/bin/sh
set -eu

PYTHON="${PYTHON:-python3}"

$PYTHON src/analysis/build_analysis_cohorts.py
$PYTHON src/analysis/cross_stratum_analysis.py
$PYTHON src/analysis/robustness_analysis.py
$PYTHON src/analysis/weight_sensitivity.py
$PYTHON src/analysis/repeatability_analysis.py
$PYTHON src/analysis/retrieval_validation.py
$PYTHON src/analysis/exposure_definition_sensitivity.py
$PYTHON src/analysis/cross_stratum_permutation.py
$PYTHON src/analysis/retrieval_failure_analysis.py
$PYTHON src/analysis/label_timing_sensitivity.py
$PYTHON tests/verify_expected_results.py
