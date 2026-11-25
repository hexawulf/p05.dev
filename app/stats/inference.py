"""Hypothesis testing, confidence intervals, power & sample-size calculations via scipy.stats."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import optimize, stats

from .fitting import parse_numeric_series
from .schemas import (
    AnovaTestRequest,
    ChiSqTestRequest,
    MeansTestRequest,
    PowerAnalysisRequest,
    ProportionsTestRequest,
    clean_float,
)


def _pvalue_and_crit(
    dist: Any, stat: float, alternative: str, alpha: float
) -> tuple[float, list[float], str]:
    """Compute exact sf-based p-value and critical value(s) without 1 - cdf cancellation."""
    if alternative == "two-sided":
        p_val = min(1.0, 2.0 * float(dist.sf(abs(stat))))
        c = float(dist.isf(alpha / 2.0))
        return p_val, [-c, c], "two_tailed"
    if alternative == "greater":
        p_val = float(dist.sf(stat))
        c = float(dist.isf(alpha))
        return p_val, [c], "right"
    if alternative == "less":
        p_val = float(dist.cdf(stat))
        c = float(dist.ppf(alpha))
        return p_val, [c], "left"
    raise ValueError(f"Unsupported alternative: {alternative}")


def _null_curve(
    dist: Any, stat: float, critical_values: list[float], tail_mode: str, x_min_floor: float | None = None
) -> dict[str, Any]:
    q_lo = float(dist.ppf(0.001))
    q_hi = float(dist.isf(0.001))
    if x_min_floor is not None:
        q_lo = max(x_min_floor, q_lo)
    vals = [stat, *critical_values]
    lo = min(q_lo, min(vals) - 0.5)
    hi = max(q_hi, max(vals) + 0.5)
    if x_min_floor is not None:
        lo = max(x_min_floor, lo)
    xs = np.linspace(lo, hi, 260)
    if x_min_floor is not None and xs[0] <= x_min_floor:
        xs[0] = x_min_floor + (hi - lo) * 1e-4
    ys = dist.pdf(xs)
    finite_y = ys[np.isfinite(ys)]
    cap = float(np.percentile(finite_y, 98) * 3.0) if finite_y.size > 5 else 10.0
    cap = max(cap, 1.0)
    return {
        "x": [float(x) for x in xs],
        "y": [clean_float(min(float(y), cap)) if math.isfinite(float(y)) else cap for y in ys],
        "stat": clean_float(stat),
        "critical_values": [clean_float(c) for c in critical_values],
        "tail_mode": tail_mode,
    }


def _wilson_ci(x: int, n: int, z: float) -> tuple[float, float]:
    phat = x / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (phat + z2 / (2.0 * n)) / denom
    half = (z / denom) * math.sqrt((phat * (1.0 - phat)) / n + z2 / (4.0 * n * n))
    return max(0.0, center - half), min(1.0, center + half)


# ---- 1. Means Tests ----


def run_means_test(req: MeansTestRequest) -> dict[str, Any]:
    """One-sample z/t and two-sample Student/Welch t-test from summary stats or raw data."""
    if req.input_mode == "raw":
        if not req.raw1:
            raise ValueError("Sample 1 raw observations are required")
        arr1 = np.asarray(parse_numeric_series(req.raw1, min_items=2), dtype=float)
        n1 = int(arr1.size)
        m1 = float(np.mean(arr1))
        s1 = float(np.std(arr1, ddof=1))
        if req.test_type in ("two_sample_t_equal", "two_sample_t_welch"):
            if not req.raw2:
                raise ValueError("Sample 2 raw observations are required for two-sample tests")
            arr2 = np.asarray(parse_numeric_series(req.raw2, min_items=2), dtype=float)
            n2 = int(arr2.size)
            m2 = float(np.mean(arr2))
            s2 = float(np.std(arr2, ddof=1))
        else:
            n2, m2, s2 = None, None, None
    else:
        if req.mean1 is None or req.n1 is None:
            raise ValueError("mean1 and n1 are required in summary mode")
        m1 = float(req.mean1)
        n1 = int(req.n1)
        s1 = float(req.sd1) if req.sd1 is not None else None
        if req.test_type == "one_sample_z":
            if req.pop_sigma is None:
                raise ValueError("Population σ (pop_sigma > 0) is required for one-sample z-test")
            s1 = float(req.pop_sigma)
        elif s1 is None:
            raise ValueError("Sample sd1 is required for t-test in summary mode")

        if req.test_type in ("two_sample_t_equal", "two_sample_t_welch"):
            if req.mean2 is None or req.sd2 is None or req.n2 is None:
                raise ValueError("mean2, sd2, and n2 are required for two-sample t-tests")
            m2, s2, n2 = float(req.mean2), float(req.sd2), int(req.n2)
        else:
            m2, s2, n2 = None, None, None

    alpha = float(req.alpha)
    if req.test_type == "one_sample_z":
        sigma = float(req.pop_sigma) if req.pop_sigma is not None else float(s1)
        if sigma <= 0.0:
            raise ValueError("Population σ must be > 0")
        se = sigma / math.sqrt(n1)
        diff = m1 - float(req.mu0)
        stat = diff / se
        dist = stats.norm(0.0, 1.0)
        df_val = None
        cohen_d = diff / sigma
        z_ci = float(dist.isf(alpha / 2.0))
        ci_low, ci_high = m1 - z_ci * se, m1 + z_ci * se
        dist_label = "N(0, 1)"
    elif req.test_type == "one_sample_t":
        assert s1 is not None
        if s1 <= 0.0:
            raise ValueError("Sample sd1 must be > 0")
        se = s1 / math.sqrt(n1)
        diff = m1 - float(req.mu0)
        stat = diff / se
        df_val = float(n1 - 1)
        dist = stats.t(df=df_val)
        cohen_d = diff / s1
        t_ci = float(dist.isf(alpha / 2.0))
        ci_low, ci_high = m1 - t_ci * se, m1 + t_ci * se
        dist_label = f"t(df={int(df_val)})"
    elif req.test_type == "two_sample_t_equal":
        assert m2 is not None and s2 is not None and n2 is not None and s1 is not None
        df_val = float(n1 + n2 - 2)
        sp2 = (((n1 - 1) * (s1 * s1)) + ((n2 - 1) * (s2 * s2))) / df_val
        if sp2 <= 0.0:
            raise ValueError("Pooled sample variance must be > 0")
        sp = math.sqrt(sp2)
        se = sp * math.sqrt(1.0 / n1 + 1.0 / n2)
        diff = m1 - m2
        stat = diff / se
        dist = stats.t(df=df_val)
        cohen_d = diff / sp
        t_ci = float(dist.isf(alpha / 2.0))
        ci_low, ci_high = diff - t_ci * se, diff + t_ci * se
        dist_label = f"t(df={int(df_val)})"
    else:  # two_sample_t_welch
        assert m2 is not None and s2 is not None and n2 is not None and s1 is not None
        v1 = (s1 * s1) / n1
        v2 = (s2 * s2) / n2
        se2 = v1 + v2
        if se2 <= 0.0:
            raise ValueError("Combined variance across samples must be > 0")
        se = math.sqrt(se2)
        df_val = (se2 * se2) / ((v1 * v1) / (n1 - 1) + (v2 * v2) / (n2 - 1))
        diff = m1 - m2
        stat = diff / se
        dist = stats.t(df=df_val)
        sd_avg = math.sqrt(0.5 * (s1 * s1 + s2 * s2))
        cohen_d = diff / sd_avg if sd_avg > 0 else 0.0
        t_ci = float(dist.isf(alpha / 2.0))
        ci_low, ci_high = diff - t_ci * se, diff + t_ci * se
        dist_label = f"t(df={df_val:.2f})"

    p_val, crit, tail_mode = _pvalue_and_crit(dist, stat, req.alternative, alpha)
    curve = _null_curve(dist, stat, crit, tail_mode)
    curve["label"] = dist_label

    return {
        "test_type": req.test_type,
        "alternative": req.alternative,
        "alpha": alpha,
        "statistic": clean_float(stat),
        "statistic_name": "z" if req.test_type == "one_sample_z" else "t",
        "df": clean_float(df_val),
        "p_value": clean_float(p_val),
        "reject_h0": bool(p_val <= alpha),
        "estimate": clean_float(diff if req.test_type.startswith("two") else m1),
        "se": clean_float(se),
        "ci_level": 1.0 - alpha,
        "ci": [clean_float(ci_low), clean_float(ci_high)],
        "cohens_d": clean_float(cohen_d),
        "critical_values": [clean_float(c) for c in crit],
        "summary": {
            "n1": n1,
            "mean1": clean_float(m1),
            "sd1": clean_float(s1),
            "n2": n2,
            "mean2": clean_float(m2),
            "sd2": clean_float(s2),
        },
        "plot": curve,
    }


# ---- 2. Proportions & A/B Tests ----


def run_proportions_test(req: ProportionsTestRequest) -> dict[str, Any]:
    """One-proportion and two-proportion z-test with Wilson score CIs and lift."""
    alpha = float(req.alpha)
    z_norm = stats.norm(0.0, 1.0)
    z_ci = float(z_norm.isf(alpha / 2.0))

    p1 = req.x1 / req.n1
    w1_lo, w1_hi = _wilson_ci(req.x1, req.n1, z_ci)

    if req.test_type == "one_prop":
        se0 = math.sqrt(req.p0 * (1.0 - req.p0) / req.n1)
        stat = (p1 - req.p0) / se0
        p_val, crit, tail_mode = _pvalue_and_crit(z_norm, stat, req.alternative, alpha)
        cohen_h = 2.0 * (math.asin(math.sqrt(p1)) - math.asin(math.sqrt(req.p0)))
        curve = _null_curve(z_norm, stat, crit, tail_mode)
        curve["label"] = "N(0, 1)"
        return {
            "test_type": "one_prop",
            "alternative": req.alternative,
            "alpha": alpha,
            "p1": clean_float(p1),
            "wilson_ci_1": [clean_float(w1_lo), clean_float(w1_hi)],
            "p0": clean_float(req.p0),
            "statistic": clean_float(stat),
            "p_value": clean_float(p_val),
            "reject_h0": bool(p_val <= alpha),
            "cohens_h": clean_float(cohen_h),
            "critical_values": [clean_float(c) for c in crit],
            "plot": curve,
        }

    assert req.x2 is not None and req.n2 is not None
    p2 = req.x2 / req.n2
    w2_lo, w2_hi = _wilson_ci(req.x2, req.n2, z_ci)
    p_pool = (req.x1 + req.x2) / (req.n1 + req.n2)
    se_pool = math.sqrt(p_pool * (1.0 - p_pool) * (1.0 / req.n1 + 1.0 / req.n2))
    if se_pool <= 0.0:
        raise ValueError("Pooled proportion variance is zero (all successes or all failures across both groups)")

    diff = p2 - p1
    stat = diff / se_pool
    p_val, crit, tail_mode = _pvalue_and_crit(z_norm, stat, req.alternative, alpha)

    # Newcombe-Wilson score interval for difference (p2 - p1)
    diff_ci_lo = diff - math.sqrt((p2 - w2_lo) ** 2 + (w1_hi - p1) ** 2)
    diff_ci_hi = diff + math.sqrt((w2_hi - p2) ** 2 + (p1 - w1_lo) ** 2)
    rel_lift = (diff / p1) if p1 > 0.0 else None
    cohen_h = 2.0 * (math.asin(math.sqrt(p2)) - math.asin(math.sqrt(p1)))

    curve = _null_curve(z_norm, stat, crit, tail_mode)
    curve["label"] = "N(0, 1)"
    return {
        "test_type": "two_prop",
        "alternative": req.alternative,
        "alpha": alpha,
        "p1": clean_float(p1),
        "p2": clean_float(p2),
        "wilson_ci_1": [clean_float(w1_lo), clean_float(w1_hi)],
        "wilson_ci_2": [clean_float(w2_lo), clean_float(w2_hi)],
        "lift_abs": clean_float(diff),
        "lift_rel": clean_float(rel_lift),
        "diff_ci": [clean_float(diff_ci_lo), clean_float(diff_ci_hi)],
        "ci_level": 1.0 - alpha,
        "statistic": clean_float(stat),
        "p_value": clean_float(p_val),
        "reject_h0": bool(p_val <= alpha),
        "cohens_h": clean_float(cohen_h),
        "critical_values": [clean_float(c) for c in crit],
        "plot": curve,
    }


# ---- 3. Statistical Power & Sample Size ----


def _power_two_prop(p1: float, p2: float, n: float, alpha: float, alternative: str) -> float:
    delta = abs(p2 - p1)
    if delta <= 0.0:
        return alpha
    p_bar = 0.5 * (p1 + p2)
    se0 = math.sqrt(2.0 * p_bar * (1.0 - p_bar) / n)
    se1 = math.sqrt((p1 * (1.0 - p1) + p2 * (1.0 - p2)) / n)
    if alternative == "two-sided":
        z_crit = float(stats.norm.isf(alpha / 2.0))
        upper = float(stats.norm.sf((z_crit * se0 - delta) / se1))
        lower = float(stats.norm.cdf((-z_crit * se0 - delta) / se1))
        return min(1.0, upper + lower)
    z_crit = float(stats.norm.isf(alpha))
    return float(stats.norm.sf((z_crit * se0 - delta) / se1))


def _power_means_t(mode: str, mean_diff: float, sd: float, n: float, alpha: float, alternative: str) -> float:
    d = abs(mean_diff) / sd
    if mode == "one_mean":
        df = max(1.0, n - 1.0)
        ncp = d * math.sqrt(n)
    else:
        df = max(2.0, 2.0 * n - 2.0)
        ncp = d * math.sqrt(n / 2.0)
    if d <= 0.0:
        return alpha
    nct_dist = stats.nct(df=df, nc=ncp)
    if alternative == "two-sided":
        t_crit = float(stats.t.isf(alpha / 2.0, df=df))
        return min(1.0, float(nct_dist.sf(t_crit) + nct_dist.cdf(-t_crit)))
    t_crit = float(stats.t.isf(alpha, df=df))
    return float(nct_dist.sf(t_crit))


def run_power_analysis(req: PowerAnalysisRequest) -> dict[str, Any]:
    """Sample size / power solver with Power vs. n and Power vs. MDE curve data."""
    alpha = float(req.alpha)
    if req.mode == "two_prop":
        mde = abs(req.p2 - req.p1)
        if mde <= 0.0:
            raise ValueError("Require p1 != p2 for two-proportion power analysis")
        eff_label = f"|p₂ − p₁| = {mde:.4g}"
        power_fn = lambda n_val: _power_two_prop(req.p1, req.p2, n_val, alpha, req.alternative)  # noqa: E731
    else:
        mde = abs(req.mean_diff)
        if mde <= 0.0:
            raise ValueError("Require non-zero mean_diff for means power analysis")
        eff_label = f"Cohen's d = {mde / req.sd:.4g}"
        power_fn = lambda n_val: _power_means_t(req.mode, mde, req.sd, n_val, alpha, req.alternative)  # noqa: E731

    if req.solve_for == "sample_size":
        target = float(req.target_power)
        lo_n, hi_n = 2.0, 4.0
        while power_fn(hi_n) < target and hi_n < 10_000_000:
            lo_n = hi_n
            hi_n *= 2.0
        if power_fn(hi_n) < target:
            raise ValueError("Required sample size exceeds 10,000,000 per group for these inputs")
        root_n = float(optimize.brentq(lambda x: power_fn(x) - target, lo_n, hi_n, xtol=1e-4))
        n_per_group = max(2, math.ceil(root_n))
        achieved_power = power_fn(float(n_per_group))
    else:
        n_per_group = int(req.n_per_group)
        achieved_power = power_fn(float(n_per_group))

    total_n = n_per_group if req.mode == "one_mean" else 2 * n_per_group

    n_max_curve = max(40, min(5_000_000, int(n_per_group * 2.2)))
    ns = np.unique(np.round(np.linspace(4, n_max_curve, 55)).astype(int))
    power_vs_n = [{"n": int(nv), "power": clean_float(power_fn(float(nv)))} for nv in ns]

    power_vs_mde: list[dict[str, float | None]] = []
    if req.mode == "two_prop":
        max_mde = min(0.95 - req.p1, max(mde * 2.5, 0.05))
        min_mde = max(0.002, mde * 0.2)
        if max_mde > min_mde:
            for d_val in np.linspace(min_mde, max_mde, 50):
                pw = _power_two_prop(req.p1, req.p1 + float(d_val), float(n_per_group), alpha, req.alternative)
                power_vs_mde.append({"mde": float(d_val), "power": clean_float(pw)})
    else:
        for d_val in np.linspace(max(0.05, mde * 0.2), max(0.5, mde * 2.5), 50):
            pw = _power_means_t(req.mode, float(d_val), req.sd, float(n_per_group), alpha, req.alternative)
            power_vs_mde.append({"mde": float(d_val), "power": clean_float(pw)})

    return {
        "mode": req.mode,
        "solve_for": req.solve_for,
        "alternative": req.alternative,
        "alpha": alpha,
        "n_per_group": n_per_group,
        "total_n": total_n,
        "achieved_power": clean_float(achieved_power),
        "mde": clean_float(mde),
        "effect_summary": eff_label,
        "power_vs_n": power_vs_n,
        "power_vs_mde": power_vs_mde,
    }


# ---- 4. Chi-Squared Tests ----


def run_chisq_test(req: ChiSqTestRequest) -> dict[str, Any]:
    """Chi-squared Goodness-of-Fit and R x C contingency table test of independence."""
    alpha = float(req.alpha)
    if req.mode == "gof":
        if not req.observed_1d:
            raise ValueError("observed_1d counts are required for goodness-of-fit test")
        obs = np.asarray(req.observed_1d, dtype=float)
        if np.any(obs < 0.0):
            raise ValueError("All observed counts must be >= 0")
        total = float(obs.sum())
        if total <= 0.0:
            raise ValueError("Sum of observed counts must be > 0")

        if req.expected_1d is not None:
            if len(req.expected_1d) != obs.size:
                raise ValueError("expected_1d must have the same length as observed_1d")
            exp_raw = np.asarray(req.expected_1d, dtype=float)
            if np.any(exp_raw <= 0.0):
                raise ValueError("All expected counts/proportions must be > 0")
            # Accept probabilities summing to 1 or expected counts summing to total
            exp = exp_raw * total if abs(float(exp_raw.sum()) - 1.0) <= 1e-6 else exp_raw * (total / float(exp_raw.sum()))
        else:
            exp = np.full_like(obs, total / float(obs.size))

        res = stats.chisquare(f_obs=obs, f_exp=exp)
        stat = float(res.statistic)
        p_val = float(res.pvalue)
        df_val = int(obs.size - 1)
        std_res = (obs - exp) / np.sqrt(exp)
        cohens_w = math.sqrt(stat / total)
        low_cells = int(np.sum(exp < 5.0))
        dist = stats.chi2(df=df_val)
        crit = [float(dist.isf(alpha))]
        curve = _null_curve(dist, stat, crit, "right", x_min_floor=0.0)
        curve["label"] = f"χ²(df={df_val})"
        return {
            "mode": "gof",
            "alpha": alpha,
            "statistic": clean_float(stat),
            "df": df_val,
            "p_value": clean_float(p_val),
            "reject_h0": bool(p_val <= alpha),
            "effect_size_name": "Cohen's w",
            "effect_size": clean_float(cohens_w),
            "observed": [float(v) for v in obs],
            "expected": [float(v) for v in exp],
            "standardized_residuals": [clean_float(float(v)) for v in std_res],
            "low_expected_warning": low_cells > 0,
            "low_expected_cells": low_cells,
            "critical_values": [clean_float(c) for c in crit],
            "plot": curve,
        }

    # Independence (R x C)
    if not req.table:
        raise ValueError("Contingency table is required for independence test")
    r_count = len(req.table)
    c_count = len(req.table[0])
    if c_count < 2:
        raise ValueError("Contingency table must have at least 2 columns")
    if any(len(row) != c_count for row in req.table):
        raise ValueError("All rows in contingency table must have equal length")
    mat = np.asarray(req.table, dtype=float)
    if np.any(mat < 0.0):
        raise ValueError("All cell counts must be >= 0")
    total = float(mat.sum())
    if total <= 0.0:
        raise ValueError("Contingency table sum must be > 0")
    if np.any(mat.sum(axis=1) <= 0.0) or np.any(mat.sum(axis=0) <= 0.0):
        raise ValueError("Every row and column total must be > 0")

    apply_yates = bool(req.yates and r_count == 2 and c_count == 2)
    chi2_res = stats.chi2_contingency(mat, correction=apply_yates)
    stat = float(chi2_res.statistic)
    p_val = float(chi2_res.pvalue)
    df_val = int(chi2_res.dof)
    exp_mat = np.asarray(chi2_res.expected_freq, dtype=float)

    row_prop = mat.sum(axis=1, keepdims=True) / total
    col_prop = mat.sum(axis=0, keepdims=True) / total
    denom = np.sqrt(exp_mat * (1.0 - row_prop) * (1.0 - col_prop))
    adj_res = np.where(denom > 0.0, (mat - exp_mat) / denom, 0.0)

    k_min = min(r_count - 1, c_count - 1)
    cramers_v = math.sqrt(stat / (total * k_min)) if k_min > 0 else 0.0
    low_cells = int(np.sum(exp_mat < 5.0))

    dist = stats.chi2(df=df_val)
    crit = [float(dist.isf(alpha))]
    curve = _null_curve(dist, stat, crit, "right", x_min_floor=0.0)
    curve["label"] = f"χ²(df={df_val})"

    return {
        "mode": "independence",
        "alpha": alpha,
        "yates_applied": apply_yates,
        "statistic": clean_float(stat),
        "df": df_val,
        "p_value": clean_float(p_val),
        "reject_h0": bool(p_val <= alpha),
        "effect_size_name": "Cramér's V",
        "effect_size": clean_float(cramers_v),
        "observed": mat.tolist(),
        "expected": [[float(v) for v in row] for row in exp_mat],
        "standardized_residuals": [[clean_float(float(v)) for v in row] for row in adj_res],
        "low_expected_warning": low_cells > 0,
        "low_expected_cells": low_cells,
        "critical_values": [clean_float(c) for c in crit],
        "plot": curve,
    }


# ---- 5. One-Way ANOVA ----


def run_anova_test(req: AnovaTestRequest) -> dict[str, Any]:
    """One-way ANOVA F-test accepting 2+ raw groups or summary statistics."""
    groups_info: list[tuple[str, int, float, float]] = []

    if req.input_mode == "raw":
        if not req.groups_raw or len(req.groups_raw) < 2:
            raise ValueError("At least 2 groups are required in raw mode")
        for idx, grp in enumerate(req.groups_raw, start=1):
            label = (grp.get("label") or f"Group {idx}").strip()
            vals = np.asarray(parse_numeric_series(grp.get("values", ""), min_items=2), dtype=float)
            groups_info.append((label, int(vals.size), float(np.mean(vals)), float(np.std(vals, ddof=1))))
    else:
        if not req.groups_summary or len(req.groups_summary) < 2:
            raise ValueError("At least 2 groups are required in summary mode")
        for grp in req.groups_summary:
            groups_info.append((grp.label, int(grp.n), float(grp.mean), float(grp.sd)))

    k = len(groups_info)
    total_n = sum(g[1] for g in groups_info)
    grand_mean = sum(g[1] * g[2] for g in groups_info) / float(total_n)

    ss_between = sum(g[1] * ((g[2] - grand_mean) ** 2) for g in groups_info)
    ss_within = sum((g[1] - 1) * (g[3] ** 2) for g in groups_info)
    if ss_within <= 0.0:
        raise ValueError("Within-group sum of squares (SS_W) must be > 0")
    ss_total = ss_between + ss_within
    df_between = k - 1
    df_within = total_n - k
    ms_between = ss_between / float(df_between)
    ms_within = ss_within / float(df_within)
    f_stat = ms_between / ms_within

    f_dist = stats.f(dfn=df_between, dfd=df_within)
    p_val = float(f_dist.sf(f_stat))
    eta_sq = ss_between / ss_total if ss_total > 0.0 else 0.0
    omega_sq = max(0.0, (ss_between - df_between * ms_within) / (ss_total + ms_within))
    crit = [float(f_dist.isf(req.alpha))]

    group_summaries = []
    for label, n_i, m_i, s_i in groups_info:
        se_i = s_i / math.sqrt(n_i)
        t_c = float(stats.t.isf(req.alpha / 2.0, df=n_i - 1))
        group_summaries.append(
            {
                "label": label,
                "n": n_i,
                "mean": clean_float(m_i),
                "sd": clean_float(s_i),
                "se": clean_float(se_i),
                "ci": [clean_float(m_i - t_c * se_i), clean_float(m_i + t_c * se_i)],
            }
        )

    curve = _null_curve(f_dist, f_stat, crit, "right", x_min_floor=0.0)
    curve["label"] = f"F({df_between}, {df_within})"

    return {
        "alpha": float(req.alpha),
        "f_stat": clean_float(f_stat),
        "df_between": df_between,
        "df_within": df_within,
        "df_total": total_n - 1,
        "p_value": clean_float(p_val),
        "reject_h0": bool(p_val <= req.alpha),
        "eta_squared": clean_float(eta_sq),
        "omega_squared": clean_float(omega_sq),
        "grand_mean": clean_float(grand_mean),
        "table": [
            {
                "source": "Between Groups",
                "ss": clean_float(ss_between),
                "df": df_between,
                "ms": clean_float(ms_between),
                "f": clean_float(f_stat),
                "p_value": clean_float(p_val),
            },
            {
                "source": "Within Groups",
                "ss": clean_float(ss_within),
                "df": df_within,
                "ms": clean_float(ms_within),
                "f": None,
                "p_value": None,
            },
            {
                "source": "Total",
                "ss": clean_float(ss_total),
                "df": total_n - 1,
                "ms": None,
                "f": None,
                "p_value": None,
            },
        ],
        "groups": group_summaries,
        "critical_values": [clean_float(c) for c in crit],
        "plot": curve,
    }
