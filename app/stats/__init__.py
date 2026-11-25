"""Modular statistical computing engine for p05.dev (probplots-web v2)."""

from .distributions import evaluate_distribution, get_catalog, solve_quantile
from .export_png import render_export_png
from .fitting import analyze_empirical_data
from .inference import (
    run_anova_test,
    run_chisq_test,
    run_means_test,
    run_power_analysis,
    run_proportions_test,
)
from .simulators import analyze_joint_matrix, simulate_clt

__all__ = [
    "analyze_empirical_data",
    "analyze_joint_matrix",
    "evaluate_distribution",
    "get_catalog",
    "render_export_png",
    "run_anova_test",
    "run_chisq_test",
    "run_means_test",
    "run_power_analysis",
    "run_proportions_test",
    "simulate_clt",
    "solve_quantile",
]
