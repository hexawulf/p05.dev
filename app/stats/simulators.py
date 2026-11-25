"""CLT sampling distribution simulator and standalone discrete joint (X, Y) matrix engine."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy import stats

from .schemas import CltSimRequest, JointMatrixRequest, clean_float


def _population_moments_and_curve(pop: str) -> tuple[float, float, str, list[float], list[float], str]:
    if pop == "uniform":
        mu, var = 0.5, 1.0 / 12.0
        xs = np.linspace(-0.08, 1.08, 160)
        ys = np.where((xs >= 0.0) & (xs <= 1.0), 1.0, 0.0)
        return mu, math.sqrt(var), "Uniform(0, 1)", xs.tolist(), ys.tolist(), "continuous"
    if pop == "exponential":
        mu, sigma = 1.0, 1.0
        xs = np.linspace(0.0, 5.5, 160)
        ys = np.exp(-xs)
        return mu, sigma, "Exponential(λ = 1)", xs.tolist(), ys.tolist(), "continuous"
    if pop == "skewed_beta":
        a, b = 0.7, 3.0
        dist = stats.beta(a=a, b=b)
        mu = float(dist.mean())
        sigma = float(dist.std())
        xs = np.linspace(0.01, 0.99, 160)
        ys = np.minimum(dist.pdf(xs), 6.0)
        return mu, sigma, "Skewed Beta(0.7, 3)", xs.tolist(), ys.tolist(), "continuous"
    if pop == "bimodal":
        # 50/50 mixture of N(-2, 0.7^2) and N(+2, 0.7^2)
        mu = 0.0
        sigma = math.sqrt(0.49 + 4.0)
        xs = np.linspace(-4.5, 4.5, 180)
        ys = 0.5 * stats.norm.pdf(xs, -2.0, 0.7) + 0.5 * stats.norm.pdf(xs, 2.0, 0.7)
        return mu, sigma, "Bimodal Mixture ½N(−2,0.7²)+½N(2,0.7²)", xs.tolist(), ys.tolist(), "continuous"
    if pop == "bernoulli":
        p = 0.25
        mu, sigma = p, math.sqrt(p * (1.0 - p))
        return mu, sigma, "Bernoulli(p = 0.25)", [0.0, 1.0], [1.0 - p, p], "discrete"
    if pop == "poisson":
        lam = 1.5
        mu, sigma = lam, math.sqrt(lam)
        ks = np.arange(0, 10)
        ys = stats.poisson.pmf(ks, lam)
        return mu, sigma, "Poisson(λ = 1.5)", ks.astype(float).tolist(), ys.tolist(), "discrete"
    raise ValueError(f"Unsupported population: {pop}")


def simulate_clt(req: CltSimRequest) -> dict[str, Any]:
    """Simulate N sample means of size n and compare against N(μ, σ²/n)."""
    pop = req.population
    n = int(req.n)
    trials = int(req.trials)
    rng = np.random.default_rng(req.seed)

    mu_pop, sigma_pop, pop_label, pop_x, pop_y, pop_family = _population_moments_and_curve(pop)
    se_theo = sigma_pop / math.sqrt(n)

    # Chunk draws at 5,000 trials per batch to cap memory on Pi hosts
    sample_means = np.empty(trials, dtype=float)
    batch_size = 5000
    pos = 0
    while pos < trials:
        m = min(batch_size, trials - pos)
        if pop == "uniform":
            chunk = rng.uniform(0.0, 1.0, size=(m, n))
        elif pop == "exponential":
            chunk = rng.exponential(1.0, size=(m, n))
        elif pop == "skewed_beta":
            chunk = rng.beta(0.7, 3.0, size=(m, n))
        elif pop == "bimodal":
            comp = rng.integers(0, 2, size=(m, n))
            chunk = np.where(comp == 0, -2.0, 2.0) + rng.normal(0.0, 0.7, size=(m, n))
        elif pop == "bernoulli":
            chunk = rng.binomial(1, 0.25, size=(m, n)).astype(float)
        else:  # poisson
            chunk = rng.poisson(1.5, size=(m, n)).astype(float)
        sample_means[pos : pos + m] = np.mean(chunk, axis=1)
        pos += m

    emp_mean = float(np.mean(sample_means))
    emp_sd = float(np.std(sample_means, ddof=1))
    emp_skew = float(stats.skew(sample_means, bias=False))
    emp_kurt = float(stats.kurtosis(sample_means, fisher=True, bias=False))
    cov_95 = float(np.mean(np.abs(sample_means - mu_pop) <= 1.959963984540054 * se_theo))

    densities, edges = np.histogram(sample_means, bins=req.bins, density=True)
    counts, _ = np.histogram(sample_means, bins=edges, density=False)

    lo = min(float(edges[0]), mu_pop - 3.8 * se_theo)
    hi = max(float(edges[-1]), mu_pop + 3.8 * se_theo)
    xs = np.linspace(lo, hi, 240)
    normal_y = stats.norm.pdf(xs, loc=mu_pop, scale=se_theo)

    return {
        "population": pop,
        "population_label": pop_label,
        "population_family": pop_family,
        "n": n,
        "trials": trials,
        "seed": req.seed,
        "theoretical": {
            "pop_mean": clean_float(mu_pop),
            "pop_sd": clean_float(sigma_pop),
            "se": clean_float(se_theo),
        },
        "empirical": {
            "mean": clean_float(emp_mean),
            "sd": clean_float(emp_sd),
            "skewness": clean_float(emp_skew),
            "excess_kurtosis": clean_float(emp_kurt),
            "ci95_coverage": clean_float(cov_95),
        },
        "histogram": {
            "edges": [float(e) for e in edges],
            "counts": [int(c) for c in counts],
            "densities": [float(d) for d in densities],
        },
        "normal_overlay": {
            "x": [float(x) for x in xs],
            "y": [float(y) for y in normal_y],
        },
        "population_curve": {
            "x": pop_x,
            "y": pop_y,
        },
    }


def analyze_joint_matrix(req: JointMatrixRequest) -> dict[str, Any]:
    """Analyze discrete joint distribution (X, Y) matrix: marginals, conditionals, independence, moments."""
    xs = np.asarray(req.x_values, dtype=float)
    ys = np.asarray(req.y_values, dtype=float)
    mat = np.asarray(req.matrix, dtype=float)

    total = float(mat.sum())
    if total <= 0.0:
        raise ValueError("Joint probability sum must be > 0")
    if req.auto_normalize:
        mat = mat / total
        total = 1.0
    elif abs(total - 1.0) > 1e-9:
        raise ValueError(f"Joint probabilities must sum to 1 within 1e-9 (got {total:.12g})")

    marg_x = mat.sum(axis=1)  # P(X = x_i)
    marg_y = mat.sum(axis=0)  # P(Y = y_j)

    ex = float(np.sum(xs * marg_x))
    ey = float(np.sum(ys * marg_y))
    ex2 = float(np.sum((xs * xs) * marg_x))
    ey2 = float(np.sum((ys * ys) * marg_y))
    var_x = max(0.0, ex2 - ex * ex)
    var_y = max(0.0, ey2 - ey * ey)
    sd_x = math.sqrt(var_x)
    sd_y = math.sqrt(var_y)

    exy = float(np.sum(np.outer(xs, ys) * mat))
    cov = exy - ex * ey
    corr = (cov / (sd_x * sd_y)) if (sd_x > 1e-12 and sd_y > 1e-12) else None

    prod_marginals = np.outer(marg_x, marg_y)
    max_indep_diff = float(np.max(np.abs(mat - prod_marginals)))
    independent = bool(max_indep_diff <= 1e-9)

    # Mutual information I(X; Y) and joint entropy H(X, Y) in nats
    nz = mat > 0.0
    entropy_joint = float(-np.sum(mat[nz] * np.log(mat[nz])))
    mi = float(np.sum(mat[nz] * np.log(mat[nz] / prod_marginals[nz])))
    mi = max(0.0, mi)

    y_given_x: dict[str, dict[str, float]] = {}
    for i, xv in enumerate(xs):
        px = float(marg_x[i])
        if px > 1e-12:
            y_given_x[f"{xv:g}"] = {f"{yv:g}": float(mat[i, j] / px) for j, yv in enumerate(ys)}

    x_given_y: dict[str, dict[str, float]] = {}
    for j, yv in enumerate(ys):
        py = float(marg_y[j])
        if py > 1e-12:
            x_given_y[f"{yv:g}"] = {f"{xv:g}": float(mat[i, j] / py) for i, xv in enumerate(xs)}

    return {
        "x_values": [float(v) for v in xs],
        "y_values": [float(v) for v in ys],
        "matrix": [[float(v) for v in row] for row in mat],
        "sum_p": clean_float(total),
        "marginal_x": [float(v) for v in marg_x],
        "marginal_y": [float(v) for v in marg_y],
        "independent": independent,
        "max_indep_diff": clean_float(max_indep_diff),
        "ex": clean_float(ex),
        "ey": clean_float(ey),
        "exy": clean_float(exy),
        "var_x": clean_float(var_x),
        "var_y": clean_float(var_y),
        "sd_x": clean_float(sd_x),
        "sd_y": clean_float(sd_y),
        "cov": clean_float(cov),
        "corr": clean_float(corr),
        "entropy_joint": clean_float(entropy_joint),
        "mutual_information": clean_float(mi),
        "y_given_x": y_given_x,
        "x_given_y": x_given_y,
    }
