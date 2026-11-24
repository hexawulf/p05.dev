"""Pure probability distribution and inequality helpers for probplots-web."""

import math

from scipy import stats


def _chk(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _chk_finite(val: float, name: str) -> None:
    _chk(math.isfinite(val), f"{name} must be finite")


# ---- Binomial ----


def binom_pmf(n: int, p: float, k: int) -> float:
    _chk(isinstance(n, int) and n >= 1, "n must be integer >= 1")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(k, int) and 0 <= k <= n, "k must be integer in [0,n]")
    return float(stats.binom.pmf(k, n, p))


def binom_cdf(n: int, p: float, k: int) -> float:
    _chk(isinstance(n, int) and n >= 1, "n must be integer >= 1")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(k, int) and 0 <= k <= n, "k must be integer in [0,n]")
    return float(stats.binom.cdf(k, n, p))


def binom_cdf_range(n: int, p: float, kmin: int, kmax: int) -> float:
    _chk(kmin <= kmax, "Require kmin <= kmax")
    return float(binom_cdf(n, p, kmax) - (binom_cdf(n, p, kmin - 1) if kmin > 0 else 0.0))


def binom_atmost(n: int, p: float, k: int) -> float:
    _chk(isinstance(n, int) and n >= 0, "n must be integer >= 0")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(stats.binom.cdf(k, n, p))


def binom_atleast(n: int, p: float, k: int) -> float:
    _chk(isinstance(n, int) and n >= 0, "n must be integer >= 0")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(stats.binom.sf(k - 1, n, p)) if k > 0 else 1.0


def binom_between(n: int, p: float, kmin: int, kmax: int) -> float:
    _chk(isinstance(n, int) and n >= 0, "n must be integer >= 0")
    _chk_finite(p, "p")
    _chk(0.0 <= p <= 1.0, "p must be in [0,1]")
    _chk(isinstance(kmin, int) and kmin >= 0, "kmin must be integer >= 0")
    _chk(isinstance(kmax, int) and kmax >= 0, "kmax must be integer >= 0")
    _chk(kmin <= kmax, "kmin must be <= kmax")
    left = float(stats.binom.cdf(kmax, n, p))
    right = float(stats.binom.cdf(kmin - 1, n, p)) if kmin > 0 else 0.0
    return max(0.0, left - right)


# ---- Poisson ----


def pois_pmf(lam: float, k: int) -> float:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(stats.poisson.pmf(k, lam))


def pois_cdf(lam: float, k: int) -> float:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(stats.poisson.cdf(k, lam))


def pois_atleast(lam: float, k: int) -> float:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(stats.poisson.sf(k - 1, lam)) if k > 0 else 1.0


def pois_between(lam: float, kmin: int, kmax: int) -> float:
    _chk_finite(lam, "lam")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(isinstance(kmin, int) and kmin >= 0, "kmin must be integer >= 0")
    _chk(isinstance(kmax, int) and kmax >= 0, "kmax must be integer >= 0")
    _chk(kmin <= kmax, "kmin must be <= kmax")
    left = float(stats.poisson.cdf(kmax, lam))
    right = float(stats.poisson.cdf(kmin - 1, lam)) if kmin > 0 else 0.0
    return max(0.0, left - right)


# ---- Geometric (k = failures before first success, support 0, 1, 2, ...) ----


def geom_pmf(p: float, k: int) -> float:
    _chk_finite(p, "p")
    _chk(0.0 < p <= 1.0, "p must be in (0,1]")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(((1.0 - p) ** k) * p)


def geom_cdf(p: float, k: int) -> float:
    _chk_finite(p, "p")
    _chk(0.0 < p <= 1.0, "p must be in (0,1]")
    _chk(isinstance(k, int) and k >= 0, "k must be integer >= 0")
    return float(1.0 - (1.0 - p) ** (k + 1))


# ---- Normal ----


def norm_pdf(x: float, mu: float, sigma: float) -> float:
    _chk_finite(x, "x")
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk(sigma > 0.0, "sigma must be > 0")
    return float(stats.norm.pdf(x, loc=mu, scale=sigma))


def norm_cdf(x: float, mu: float, sigma: float) -> float:
    _chk_finite(x, "x")
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk(sigma > 0.0, "sigma must be > 0")
    return float(stats.norm.cdf(x, loc=mu, scale=sigma))


def norm_interval(lower: float, upper: float, mu: float, sigma: float) -> float:
    _chk_finite(lower, "lower")
    _chk_finite(upper, "upper")
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk(sigma > 0.0, "sigma must be > 0")
    if lower > upper:
        lower, upper = upper, lower
    return float(stats.norm.cdf(upper, loc=mu, scale=sigma) - stats.norm.cdf(lower, loc=mu, scale=sigma))


def norm_inv(p: float, mu: float, sigma: float) -> float:
    _chk_finite(p, "p")
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk(0.0 < p < 1.0, "p must be in (0,1)")
    _chk(sigma > 0.0, "sigma must be > 0")
    return float(stats.norm.ppf(p, loc=mu, scale=sigma))


# ---- Exponential ----


def exp_pdf(lam: float, x: float) -> float:
    _chk_finite(lam, "lam")
    _chk_finite(x, "x")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(x >= 0.0, "x must be >= 0")
    return float(stats.expon(scale=1.0 / lam).pdf(x))


def exp_cdf(lam: float, x: float) -> float:
    _chk_finite(lam, "lam")
    _chk_finite(x, "x")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(x >= 0.0, "x must be >= 0")
    return float(stats.expon(scale=1.0 / lam).cdf(x))


def exp_inv(lam: float, p: float) -> float:
    _chk_finite(lam, "lam")
    _chk_finite(p, "p")
    _chk(lam > 0.0, "lambda must be > 0")
    _chk(0.0 < p < 1.0, "p must be in (0,1)")
    return float(-math.log1p(-p) / lam)


# ---- Uniform ----


def unif_pdf(a: float, b: float, x: float) -> float:
    _chk_finite(a, "a")
    _chk_finite(b, "b")
    _chk_finite(x, "x")
    _chk(b > a, "require b > a")
    return float(1.0 / (b - a)) if a <= x <= b else 0.0


def unif_cdf(a: float, b: float, x: float) -> float:
    _chk_finite(a, "a")
    _chk_finite(b, "b")
    _chk_finite(x, "x")
    _chk(b > a, "require b > a")
    return float(stats.uniform(loc=a, scale=b - a).cdf(x))


# ---- CLT & Inequalities ----


def clt(mu: float, sigma: float, n: int, lower: float, upper: float) -> float:
    _chk_finite(mu, "mu")
    _chk_finite(sigma, "sigma")
    _chk_finite(lower, "lower")
    _chk_finite(upper, "upper")
    _chk(sigma > 0.0, "sigma must be > 0")
    _chk(isinstance(n, int) and n >= 1, "n must be integer >= 1")
    if lower > upper:
        lower, upper = upper, lower
    s = sigma / math.sqrt(n)
    return float(stats.norm.cdf(upper, loc=mu, scale=s) - stats.norm.cdf(lower, loc=mu, scale=s))


def markov_bound(mean: float, t: float) -> dict[str, float | bool]:
    _chk_finite(mean, "mean")
    _chk_finite(t, "t")
    _chk(mean >= 0.0, "E[X] must be >= 0 (non-negative random variable)")
    _chk(t > 0.0, "t must be > 0")
    raw = mean / t
    return {"bound": min(1.0, raw), "raw_ratio": raw, "trivial": raw >= 1.0}


def chebyshev_bound(sigma: float, t: float) -> dict[str, float | bool | None]:
    _chk_finite(sigma, "sigma")
    _chk_finite(t, "t")
    _chk(sigma >= 0.0, "sigma must be >= 0")
    _chk(t > 0.0, "t must be > 0")
    raw_outer = (sigma * sigma) / (t * t)
    outer = min(1.0, raw_outer)
    inner = max(0.0, 1.0 - raw_outer)
    k = (t / sigma) if sigma > 0.0 else None
    return {
        "outer_bound": outer,
        "inner_bound": inner,
        "k_sigmas": k,
        "trivial": raw_outer >= 1.0,
    }
