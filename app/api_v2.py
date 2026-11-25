"""FastAPI v2 router (/api/v2/*) for p05.dev interactive probability & statistics workbench."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Response

from .stats import (
    analyze_empirical_data,
    analyze_joint_matrix,
    evaluate_distribution,
    get_catalog,
    render_export_png,
    run_anova_test,
    run_chisq_test,
    run_means_test,
    run_power_analysis,
    run_proportions_test,
    simulate_clt,
    solve_quantile,
)
from .stats.schemas import (
    AnovaTestRequest,
    ChiSqTestRequest,
    CltSimRequest,
    DistEvaluateRequest,
    DistQuantileRequest,
    FitAnalyzeRequest,
    JointMatrixRequest,
    MeansTestRequest,
    PngExportRequest,
    PowerAnalysisRequest,
    ProportionsTestRequest,
)

router = APIRouter(prefix="/api/v2")


def _run_stat(fn: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
    try:
        return fn(*args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---- v2 Distributions ----


@router.get("/dist/catalog", tags=["v2 Distributions"], summary="Distribution catalog & presets")
def api_v2_dist_catalog() -> dict[str, Any]:
    """Return parameter metadata, support, LaTeX density, and presets for all 14 distributions."""
    return get_catalog()


@router.post("/dist/evaluate", tags=["v2 Distributions"], summary="Evaluate PDF/PMF, CDF, moments & overlays")
def api_v2_dist_evaluate(req: DistEvaluateRequest) -> dict[str, Any]:
    """Compute exact moments, survival-function tail probabilities, and curve coordinates."""
    return _run_stat(evaluate_distribution, req)


@router.post("/dist/quantile", tags=["v2 Distributions"], summary="Solve critical bounds from target probability")
def api_v2_dist_quantile(req: DistQuantileRequest) -> dict[str, Any]:
    """Invert CDF / survival function (ppf/isf) to snap bounds to a target probability."""
    return _run_stat(solve_quantile, req)


# ---- v2 Hypothesis Tests ----


@router.post("/inference/means", tags=["v2 Hypothesis Tests"], summary="1/2-sample z, Student t & Welch t tests")
def api_v2_inference_means(req: MeansTestRequest) -> dict[str, Any]:
    """Run one-sample z/t or two-sample Student/Welch t-test from summary stats or raw arrays."""
    return _run_stat(run_means_test, req)


@router.post("/inference/proportions", tags=["v2 Hypothesis Tests"], summary="1/2-proportion z-tests & Wilson CIs")
def api_v2_inference_proportions(req: ProportionsTestRequest) -> dict[str, Any]:
    """Run 1- or 2-proportion z-test with Wilson score intervals, lift, and Cohen's h."""
    return _run_stat(run_proportions_test, req)


@router.post("/inference/power", tags=["v2 Hypothesis Tests"], summary="Sample size & statistical power curves")
def api_v2_inference_power(req: PowerAnalysisRequest) -> dict[str, Any]:
    """Solve required sample size or achieved power and generate Power vs. n / MDE curves."""
    return _run_stat(run_power_analysis, req)


@router.post("/inference/chisq", tags=["v2 Hypothesis Tests"], summary="Chi-squared GOF & R×C independence")
def api_v2_inference_chisq(req: ChiSqTestRequest) -> dict[str, Any]:
    """Compute chi-squared test, expected counts, standardized residuals, and Cramér's V."""
    return _run_stat(run_chisq_test, req)


@router.post("/inference/anova", tags=["v2 Hypothesis Tests"], summary="One-way ANOVA F-test & effect size")
def api_v2_inference_anova(req: AnovaTestRequest) -> dict[str, Any]:
    """Run one-way ANOVA from raw groups or summary stats with ANOVA table and η²."""
    return _run_stat(run_anova_test, req)


# ---- v2 Data & Fitting ----


@router.post("/fit/analyze", tags=["v2 Data & Fitting"], summary="Descriptives, KDE, MLE auto-fit & Q-Q plot")
def api_v2_fit_analyze(req: FitAnalyzeRequest) -> dict[str, Any]:
    """Parse raw data, compute descriptives/outliers, Hist+KDE, MLE AIC/KS ranking & Q-Q data."""
    return _run_stat(analyze_empirical_data, req)


# ---- v2 Simulators ----


@router.post("/sim/clt", tags=["v2 Simulators"], summary="Central Limit Theorem sampling simulator")
def api_v2_sim_clt(req: CltSimRequest) -> dict[str, Any]:
    """Simulate N sample means of size n and compare against theoretical N(μ, σ²/n)."""
    return _run_stat(simulate_clt, req)


@router.post("/sim/joint", tags=["v2 Simulators"], summary="Discrete joint (X, Y) matrix analyzer")
def api_v2_sim_joint(req: JointMatrixRequest) -> dict[str, Any]:
    """Analyze discrete R×C joint PMF for marginals, conditionals, independence, Cov & Corr."""
    return _run_stat(analyze_joint_matrix, req)


# ---- High-Res PNG Export ----


@router.post("/export/png", tags=["System"], summary="Export 2x Retina PNG of active workbench plot")
def api_v2_export_png(req: PngExportRequest) -> Response:
    """Render a CSP-safe 2x Retina PNG using Matplotlib Agg in light or dark theme."""
    try:
        png = render_export_png(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(
        content=png,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="p05-plot.png"'},
    )
