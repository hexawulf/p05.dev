"""Empirical data parsing, descriptive statistics, Hist+KDE, MLE distribution fitting & Q-Q plots."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
from scipy import stats

from .schemas import FitAnalyzeRequest, clean_float

_TOKEN_SPLIT = re.compile(r"[\s,;]+")


def parse_numeric_series(raw_text: str, min_items: int = 2, max_items: int = 50_000) -> list[float]:
    """Parse comma/space/semicolon/tab/newline numbers, skipping an optional single header token."""
    tokens = [tok.strip() for tok in _TOKEN_SPLIT.split(raw_text.strip()) if tok.strip()]
    if not tokens:
        raise ValueError("No numeric values provided")
    values: list[float] = []
    for idx, tok in enumerate(tokens):
        try:
            val = float(tok)
        except ValueError as exc:
            if idx == 0 and len(tokens) > 1:
                continue
            raise ValueError(f"Non-numeric token '{tok}' at position {idx + 1}") from exc
        if not math.isfinite(val):
            raise ValueError(f"Non-finite number '{tok}' is not allowed")
        values.append(val)
    if len(values) < min_items:
        raise ValueError(f"At least {min_items} numeric observations are required (got {len(values)})")
    if len(values) > max_items:
        raise ValueError(f"At most {max_items} observations are supported (got {len(values)})")
    return values


def _compute_bin_count(arr: np.ndarray, rule: str, manual_bins: int) -> int:
    n = arr.size
    if rule == "manual":
        return int(max(3, min(150, manual_bins)))
    data_min = float(arr.min())
    data_max = float(arr.max())
    span = data_max - data_min
    if span <= 0.0:
        return 5
    if rule == "sturges":
        k = math.ceil(math.log2(n) + 1.0)
    elif rule == "scott":
        sd = float(np.std(arr, ddof=1))
        h = 3.5 * sd / (n ** (1.0 / 3.0)) if sd > 0.0 else span / 10.0
        k = math.ceil(span / h) if h > 0.0 else 10
    else:  # "fd" Freedman-Diaconis
        q1, q3 = np.percentile(arr, [25.0, 75.0])
        iqr = float(q3 - q1)
        if iqr > 0.0:
            h = 2.0 * iqr / (n ** (1.0 / 3.0))
            k = math.ceil(span / h)
        else:
            k = math.ceil(math.log2(n) + 1.0)
    return int(max(3, min(150, k)))


def _fit_candidate_distributions(arr: np.ndarray, x_grid: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    n = arr.size
    x_min = float(arr.min())
    x_max = float(arr.max())
    fits: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    candidates: list[tuple[str, str, int, bool, bool]] = [
        ("normal", "Normal", 2, False, False),
        ("lognormal", "Log-Normal", 2, True, False),
        ("exponential", "Exponential", 1, False, True),
        ("gamma", "Gamma", 2, True, False),
        ("uniform", "Uniform", 2, False, False),
    ]

    sample_sorted = np.sort(arr)
    probs = (np.arange(1, n + 1, dtype=float) - 0.5) / float(n)
    # Downsample Q-Q points safely if n > 400 so JSON stays compact
    if n > 400:
        idx = np.unique(np.round(np.linspace(0, n - 1, 400)).astype(int))
    else:
        idx = np.arange(n, dtype=int)
    sample_qq = sample_sorted[idx]
    probs_qq = probs[idx]

    for key, label, k_params, req_strict_pos, req_nonneg in candidates:
        if req_strict_pos and x_min <= 0.0:
            skipped.append({"id": key, "name": label, "reason": f"Requires x > 0 (min observed = {x_min:g})"})
            continue
        if req_nonneg and x_min < 0.0:
            skipped.append({"id": key, "name": label, "reason": f"Requires x ≥ 0 (min observed = {x_min:g})"})
            continue

        try:
            if key == "normal":
                mu_hat = float(np.mean(arr))
                sigma_hat = float(np.std(arr, ddof=0))
                if sigma_hat <= 0.0:
                    raise ValueError("Zero variance")
                frozen = stats.norm(loc=mu_hat, scale=sigma_hat)
                params_dict = {"mu": mu_hat, "sigma": sigma_hat}
                param_str = f"μ={mu_hat:.4g}, σ={sigma_hat:.4g}"
            elif key == "lognormal":
                log_x = np.log(arr)
                mu_hat = float(np.mean(log_x))
                sigma_hat = float(np.std(log_x, ddof=0))
                if sigma_hat <= 0.0:
                    raise ValueError("Zero log variance")
                frozen = stats.lognorm(s=sigma_hat, scale=math.exp(mu_hat))
                params_dict = {"mu": mu_hat, "sigma": sigma_hat}
                param_str = f"μ={mu_hat:.4g}, σ={sigma_hat:.4g}"
            elif key == "exponential":
                mean_hat = float(np.mean(arr))
                if mean_hat <= 0.0:
                    raise ValueError("Mean must be > 0")
                lam_hat = 1.0 / mean_hat
                frozen = stats.expon(scale=mean_hat)
                params_dict = {"lam": lam_hat}
                param_str = f"λ={lam_hat:.4g}"
            elif key == "gamma":
                shape_hat, _, scale_hat = stats.gamma.fit(arr, floc=0.0)
                if not (math.isfinite(shape_hat) and math.isfinite(scale_hat) and shape_hat > 0 and scale_hat > 0):
                    raise ValueError("Gamma MLE did not converge")
                beta_hat = 1.0 / float(scale_hat)
                frozen = stats.gamma(a=float(shape_hat), scale=float(scale_hat))
                params_dict = {"alpha": float(shape_hat), "beta": beta_hat}
                param_str = f"α={shape_hat:.4g}, β={beta_hat:.4g}"
            else:  # uniform
                if x_max <= x_min:
                    raise ValueError("Uniform requires max > min")
                frozen = stats.uniform(loc=x_min, scale=x_max - x_min)
                params_dict = {"a": x_min, "b": x_max}
                param_str = f"a={x_min:.4g}, b={x_max:.4g}"

            logpdf = frozen.logpdf(arr)
            if key == "uniform":
                # Account for endpoints cleanly
                loglik = -float(n) * math.log(x_max - x_min)
            else:
                if not np.all(np.isfinite(logpdf)):
                    raise ValueError("Non-finite log-likelihood")
                loglik = float(np.sum(logpdf))

            aic = 2.0 * float(k_params) - 2.0 * loglik
            bic = float(k_params) * math.log(float(n)) - 2.0 * loglik
            ks_res = stats.kstest(arr, frozen.cdf)

            y_grid = frozen.pdf(x_grid)
            y_clean = [clean_float(float(v)) or 0.0 for v in y_grid]
            theo_qq = frozen.ppf(probs_qq)
            theo_clean = [clean_float(float(v)) for v in theo_qq]

            fits.append(
                {
                    "id": key,
                    "name": label,
                    "params": {pk: clean_float(pv) for pk, pv in params_dict.items()},
                    "param_summary": param_str,
                    "loglik": clean_float(loglik),
                    "aic": clean_float(aic),
                    "bic": clean_float(bic),
                    "ks_stat": clean_float(float(ks_res.statistic)),
                    "ks_pvalue": clean_float(float(ks_res.pvalue)),
                    "pdf_y": y_clean,
                    "qq": {
                        "theoretical": theo_clean,
                        "sample": [float(v) for v in sample_qq],
                    },
                }
            )
        except (ValueError, ZeroDivisionError, FloatingPointError) as exc:
            skipped.append({"id": key, "name": label, "reason": str(exc)})

    fits.sort(key=lambda item: item["aic"] if item["aic"] is not None else float("inf"))
    for rank, item in enumerate(fits, start=1):
        item["rank"] = rank
    return fits, skipped


def analyze_empirical_data(req: FitAnalyzeRequest) -> dict[str, Any]:
    """Compute descriptive stats, histogram + KDE, MLE distribution ranking, and Q-Q plot data."""
    if req.data is not None:
        values = [float(v) for v in req.data]
    elif req.raw_text is not None:
        values = parse_numeric_series(req.raw_text, min_items=3, max_items=50_000)
    else:
        raise ValueError("Provide either 'raw_text' or 'data'")

    arr = np.asarray(values, dtype=float)
    n = int(arr.size)
    sd_sample = float(np.std(arr, ddof=1))
    if sd_sample <= 0.0:
        raise ValueError("Sample variance must be > 0 (all observations are identical)")

    mean_v = float(np.mean(arr))
    trimmed_v = float(stats.trim_mean(arr, proportiontocut=0.10))
    median_v = float(np.median(arr))
    sd_pop = float(np.std(arr, ddof=0))
    var_sample = float(np.var(arr, ddof=1))
    q1, q3 = (float(x) for x in np.percentile(arr, [25.0, 75.0]))
    iqr_v = q3 - q1
    x_min = float(arr.min())
    x_max = float(arr.max())
    skew_v = float(stats.skew(arr, bias=False)) if n >= 3 else 0.0
    kurt_v = float(stats.kurtosis(arr, fisher=True, bias=False)) if n >= 4 else 0.0

    se = sd_sample / math.sqrt(n)
    t_crit = float(stats.t.isf(0.025, df=n - 1))
    ci_low = mean_v - t_crit * se
    ci_high = mean_v + t_crit * se

    lower_fence = q1 - 1.5 * iqr_v
    upper_fence = q3 + 1.5 * iqr_v
    outlier_vals = sorted([float(x) for x in arr if x < lower_fence or x > upper_fence])

    bin_count = _compute_bin_count(arr, req.bin_rule, req.bins)
    counts, edges = np.histogram(arr, bins=bin_count, density=False)
    densities, _ = np.histogram(arr, bins=edges, density=True)

    pad = max((x_max - x_min) * 0.12, sd_sample * 0.4)
    grid_lo = x_min - pad
    grid_hi = x_max + pad
    x_grid = np.linspace(grid_lo, grid_hi, 240)
    kde = stats.gaussian_kde(arr)
    kde_y = kde(x_grid)

    fits, skipped = _fit_candidate_distributions(arr, x_grid)

    return {
        "n": n,
        "descriptives": {
            "n": n,
            "mean": clean_float(mean_v),
            "trimmed_mean_10": clean_float(trimmed_v),
            "median": clean_float(median_v),
            "std_sample": clean_float(sd_sample),
            "std_pop": clean_float(sd_pop),
            "var_sample": clean_float(var_sample),
            "q1": clean_float(q1),
            "q3": clean_float(q3),
            "iqr": clean_float(iqr_v),
            "min": clean_float(x_min),
            "max": clean_float(x_max),
            "skewness": clean_float(skew_v),
            "excess_kurtosis": clean_float(kurt_v),
            "mean_ci_95": [clean_float(ci_low), clean_float(ci_high)],
            "outliers_iqr": {
                "count": len(outlier_vals),
                "lower_fence": clean_float(lower_fence),
                "upper_fence": clean_float(upper_fence),
                "values": outlier_vals[:50],
                "truncated": len(outlier_vals) > 50,
            },
        },
        "histogram": {
            "bin_rule": req.bin_rule,
            "bin_count": bin_count,
            "edges": [float(e) for e in edges],
            "counts": [int(c) for c in counts],
            "densities": [float(d) for d in densities],
        },
        "x_grid": [float(x) for x in x_grid],
        "kde_y": [clean_float(float(y)) or 0.0 for y in kde_y],
        "fits": fits,
        "skipped_models": skipped,
    }
