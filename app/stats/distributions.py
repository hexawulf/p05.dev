"""Unified 14-distribution engine backed by scipy.stats with sf/isf extreme-tail accuracy."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import stats

from .schemas import (
    DistEvaluateRequest,
    DistQuantileRequest,
    DistributionId,
    clean_float,
)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    kind: str  # "float" | "int"
    default: float
    min_val: float | None
    max_val: float | None
    min_inclusive: bool
    max_inclusive: bool
    step: float
    slider_min: float
    slider_max: float


@dataclass(frozen=True)
class DistMeta:
    id: DistributionId
    name: str
    family: str  # "continuous" | "discrete"
    notation: str
    support: str
    formula_latex: str
    note: str
    params: tuple[ParamSpec, ...]


_CATALOG: dict[DistributionId, DistMeta] = {
    "normal": DistMeta(
        id="normal",
        name="Normal (Gaussian)",
        family="continuous",
        notation="X ~ N(μ, σ²)",
        support="(-∞, +∞)",
        formula_latex=r"f(x) = \frac{1}{\sigma\sqrt{2\pi}}\exp\!\left(-\frac{(x-\mu)^2}{2\sigma^2}\right)",
        note="Standard parameterization by mean μ and standard deviation σ > 0.",
        params=(
            ParamSpec("mu", "Mean μ", "float", 0.0, -1e6, 1e6, True, True, 0.1, -5.0, 5.0),
            ParamSpec("sigma", "Std Dev σ", "float", 1.0, 0.0, 1e6, False, True, 0.05, 0.2, 5.0),
        ),
    ),
    "student_t": DistMeta(
        id="student_t",
        name="Student's t",
        family="continuous",
        notation="X ~ t(ν, μ, σ)",
        support="(-∞, +∞)",
        formula_latex=r"f(x) = \frac{\Gamma(\frac{\nu+1}{2})}{\sigma\sqrt{\nu\pi}\,\Gamma(\frac{\nu}{2})}\left(1 + \frac{(x-\mu)^2}{\nu\sigma^2}\right)^{-(\nu+1)/2}",
        note="Location-scale Student's t; standard Student's t uses μ = 0, σ = 1.",
        params=(
            ParamSpec("df", "Degrees of freedom ν", "float", 5.0, 0.0, 1e6, False, True, 0.5, 1.0, 50.0),
            ParamSpec("mu", "Location μ", "float", 0.0, -1e6, 1e6, True, True, 0.1, -5.0, 5.0),
            ParamSpec("sigma", "Scale σ", "float", 1.0, 0.0, 1e6, False, True, 0.05, 0.2, 5.0),
        ),
    ),
    "chi2": DistMeta(
        id="chi2",
        name="Chi-Squared (χ²)",
        family="continuous",
        notation="X ~ χ²(k)",
        support="[0, +∞)",
        formula_latex=r"f(x) = \frac{1}{2^{k/2}\Gamma(k/2)} x^{k/2 - 1} e^{-x/2}",
        note="Sum of k independent standard normal squares; k > 0.",
        params=(
            ParamSpec("df", "Degrees of freedom k", "float", 4.0, 0.0, 1e5, False, True, 1.0, 1.0, 30.0),
        ),
    ),
    "f": DistMeta(
        id="f",
        name="Fisher–Snedecor F",
        family="continuous",
        notation="X ~ F(d₁, d₂)",
        support="[0, +∞)",
        formula_latex=r"f(x) = \frac{\sqrt{\frac{(d_1 x)^{d_1} d_2^{d_2}}{(d_1 x + d_2)^{d_1+d_2}}}}{x\,B(d_1/2, d_2/2)}",
        note="Ratio of scaled χ² variates with numerator df d₁ and denominator df d₂.",
        params=(
            ParamSpec("dfn", "Numerator df d₁", "float", 5.0, 0.0, 1e5, False, True, 1.0, 1.0, 30.0),
            ParamSpec("dfd", "Denominator df d₂", "float", 20.0, 0.0, 1e5, False, True, 1.0, 2.0, 60.0),
        ),
    ),
    "exponential": DistMeta(
        id="exponential",
        name="Exponential",
        family="continuous",
        notation="X ~ Exp(λ)",
        support="[0, +∞)",
        formula_latex=r"f(x) = \lambda e^{-\lambda x}, \quad x \ge 0",
        note="Rate parameterization λ > 0 (mean = 1/λ; scipy scale = 1/λ).",
        params=(
            ParamSpec("lam", "Rate λ", "float", 1.0, 0.0, 1e6, False, True, 0.1, 0.1, 5.0),
        ),
    ),
    "uniform": DistMeta(
        id="uniform",
        name="Continuous Uniform",
        family="continuous",
        notation="X ~ Unif(a, b)",
        support="[a, b]",
        formula_latex=r"f(x) = \frac{1}{b-a}, \quad a \le x \le b",
        note="Requires strict lower < upper bound (a < b).",
        params=(
            ParamSpec("a", "Lower a", "float", 0.0, -1e6, 1e6, True, True, 0.5, -10.0, 10.0),
            ParamSpec("b", "Upper b", "float", 1.0, -1e6, 1e6, True, True, 0.5, -5.0, 15.0),
        ),
    ),
    "gamma": DistMeta(
        id="gamma",
        name="Gamma",
        family="continuous",
        notation="X ~ Gamma(α, β)",
        support="[0, +∞)",
        formula_latex=r"f(x) = \frac{\beta^\alpha}{\Gamma(\alpha)} x^{\alpha-1} e^{-\beta x}",
        note="Shape α > 0, rate β > 0 (mean = α/β; scipy scale = 1/β).",
        params=(
            ParamSpec("alpha", "Shape α", "float", 3.0, 0.0, 1e5, False, True, 0.25, 0.5, 15.0),
            ParamSpec("beta", "Rate β", "float", 1.0, 0.0, 1e5, False, True, 0.1, 0.2, 5.0),
        ),
    ),
    "beta": DistMeta(
        id="beta",
        name="Beta",
        family="continuous",
        notation="X ~ Beta(α, β)",
        support="[0, 1]",
        formula_latex=r"f(x) = \frac{x^{\alpha-1}(1-x)^{\beta-1}}{B(\alpha, \beta)}, \quad x \in (0,1)",
        note="Conjugate prior for Binomial/Bernoulli probabilities on [0, 1].",
        params=(
            ParamSpec("alpha", "Shape α", "float", 2.0, 0.0, 1e5, False, True, 0.25, 0.5, 20.0),
            ParamSpec("beta", "Shape β", "float", 5.0, 0.0, 1e5, False, True, 0.25, 0.5, 20.0),
        ),
    ),
    "lognormal": DistMeta(
        id="lognormal",
        name="Log-Normal",
        family="continuous",
        notation="X ~ LogNormal(μ, σ)",
        support="(0, +∞)",
        formula_latex=r"f(x) = \frac{1}{x\sigma\sqrt{2\pi}}\exp\!\left(-\frac{(\ln x - \mu)^2}{2\sigma^2}\right)",
        note="ln(X) ~ N(μ, σ²); scipy shape s = σ and scale = exp(μ).",
        params=(
            ParamSpec("mu", "Log-mean μ", "float", 0.0, -20.0, 20.0, True, True, 0.1, -2.0, 2.5),
            ParamSpec("sigma", "Log-sd σ", "float", 0.5, 0.0, 10.0, False, True, 0.05, 0.1, 2.0),
        ),
    ),
    "binomial": DistMeta(
        id="binomial",
        name="Binomial",
        family="discrete",
        notation="X ~ Bin(n, p)",
        support="{0, 1, …, n}",
        formula_latex=r"P(X=k) = \binom{n}{k} p^k (1-p)^{n-k}",
        note="Count of successes in n independent Bernoulli(p) trials.",
        params=(
            ParamSpec("n", "Trials n", "int", 20, 1, 10_000, True, True, 1, 1, 100),
            ParamSpec("p", "Success prob p", "float", 0.5, 0.0, 1.0, True, True, 0.02, 0.0, 1.0),
        ),
    ),
    "poisson": DistMeta(
        id="poisson",
        name="Poisson",
        family="discrete",
        notation="X ~ Pois(λ)",
        support="{0, 1, 2, …}",
        formula_latex=r"P(X=k) = \frac{\lambda^k e^{-\lambda}}{k!}",
        note="Count of independent events in a fixed interval with mean rate λ > 0.",
        params=(
            ParamSpec("lam", "Rate λ", "float", 4.0, 0.0, 10_000.0, False, True, 0.25, 0.5, 40.0),
        ),
    ),
    "geometric": DistMeta(
        id="geometric",
        name="Geometric (Failures)",
        family="discrete",
        notation="X ~ Geom₀(p)",
        support="{0, 1, 2, …}",
        formula_latex=r"P(X=k) = (1-p)^k p, \quad k \in \{0,1,2,\dots\}",
        note="0-indexed failures before 1st success (scipy.stats.geom(p, loc=-1)).",
        params=(
            ParamSpec("p", "Success prob p", "float", 0.3, 0.0, 1.0, False, True, 0.02, 0.05, 1.0),
        ),
    ),
    "negbinom": DistMeta(
        id="negbinom",
        name="Negative Binomial",
        family="discrete",
        notation="X ~ NB(r, p)",
        support="{0, 1, 2, …}",
        formula_latex=r"P(X=k) = \binom{k+r-1}{k} p^r (1-p)^k",
        note="Number of failures k before achieving r successes (each with prob p).",
        params=(
            ParamSpec("r", "Target successes r", "float", 5.0, 0.0, 10_000.0, False, True, 1.0, 1.0, 30.0),
            ParamSpec("p", "Success prob p", "float", 0.4, 0.0, 1.0, False, True, 0.02, 0.05, 1.0),
        ),
    ),
    "hypergeom": DistMeta(
        id="hypergeom",
        name="Hypergeometric",
        family="discrete",
        notation="X ~ Hypergeom(M, K, n)",
        support="{max(0, n+K-M), …, min(n, K)}",
        formula_latex=r"P(X=k) = \frac{\binom{K}{k}\binom{M-K}{n-k}}{\binom{M}{n}}",
        note="Successes k in n draws without replacement from population M with K successes.",
        params=(
            ParamSpec("M", "Population M", "int", 52, 1, 100_000, True, True, 1, 5, 200),
            ParamSpec("K", "Success states K", "int", 13, 0, 100_000, True, True, 1, 0, 100),
            ParamSpec("n", "Draws n", "int", 5, 1, 100_000, True, True, 1, 1, 100),
        ),
    ),
}


_PRESETS: list[dict[str, Any]] = [
    {
        "id": "p05-normal-95",
        "title": "p < 0.05: Standard Normal Two-Tailed",
        "subtitle": "N(0, 1) with |z| ≥ 1.96 (α = 0.05)",
        "dist": "normal",
        "params": {"mu": 0.0, "sigma": 1.0},
        "region": "two_tailed",
        "a": -1.959963984540054,
        "b": 1.959963984540054,
        "overlays": [],
    },
    {
        "id": "normal-95-ci",
        "title": "Standard Normal 95% CI",
        "subtitle": "P(-1.96 ≤ Z ≤ 1.96) = 0.9500",
        "dist": "normal",
        "params": {"mu": 0.0, "sigma": 1.0},
        "region": "interval",
        "a": -1.959963984540054,
        "b": 1.959963984540054,
        "overlays": [],
    },
    {
        "id": "heavy-tails-t2",
        "title": "Heavy Tails: t(df=2) vs t(df=10) vs Normal",
        "subtitle": "Compare tail thickness at 5% critical region",
        "dist": "student_t",
        "params": {"df": 2.0, "mu": 0.0, "sigma": 1.0},
        "region": "right",
        "a": -2.919985580355516,
        "b": 2.919985580355516,
        "overlays": [
            {"dist": "student_t", "params": {"df": 10.0, "mu": 0.0, "sigma": 1.0}, "label": "t(df=10)"},
            {"dist": "normal", "params": {"mu": 0.0, "sigma": 1.0}, "label": "N(0, 1)"},
        ],
    },
    {
        "id": "binom-poisson-limit",
        "title": "Binomial → Poisson Limit",
        "subtitle": "Bin(n=100, p=0.04) vs Pois(λ=4)",
        "dist": "binomial",
        "params": {"n": 100, "p": 0.04},
        "region": "right",
        "a": 2.0,
        "b": 7.0,
        "overlays": [
            {"dist": "poisson", "params": {"lam": 4.0}, "label": "Pois(λ=4)"},
        ],
    },
    {
        "id": "beta-bayes-update",
        "title": "Beta(1,1) vs Bayesian Update",
        "subtitle": "Posterior Beta(8, 4) after 7 heads / 3 tails",
        "dist": "beta",
        "params": {"alpha": 8.0, "beta": 4.0},
        "region": "interval",
        "a": 0.4,
        "b": 0.9,
        "overlays": [
            {"dist": "beta", "params": {"alpha": 1.0, "beta": 1.0}, "label": "Prior Beta(1, 1)"},
            {"dist": "beta", "params": {"alpha": 2.0, "beta": 2.0}, "label": "Beta(2, 2)"},
        ],
    },
]


def _validate_and_coerce_params(dist_id: DistributionId, raw_params: dict[str, float]) -> dict[str, float | int]:
    meta = _CATALOG[dist_id]
    coerced: dict[str, float | int] = {}
    allowed = {p.name for p in meta.params}
    unknown = set(raw_params.keys()) - allowed
    if unknown:
        raise ValueError(f"Unknown parameter(s) for {dist_id}: {', '.join(sorted(unknown))}")

    for spec in meta.params:
        val = float(raw_params.get(spec.name, spec.default))
        if not math.isfinite(val):
            raise ValueError(f"Parameter '{spec.name}' must be finite")
        if spec.kind == "int":
            if abs(val - round(val)) > 1e-9:
                raise ValueError(f"Parameter '{spec.name}' must be an integer")
            ival = int(round(val))
            if spec.min_val is not None and ival < spec.min_val:
                raise ValueError(f"Parameter '{spec.name}' must be >= {int(spec.min_val)}")
            if spec.max_val is not None and ival > spec.max_val:
                raise ValueError(f"Parameter '{spec.name}' must be <= {int(spec.max_val)}")
            coerced[spec.name] = ival
        else:
            if spec.min_val is not None:
                if spec.min_inclusive and val < spec.min_val:
                    raise ValueError(f"Parameter '{spec.name}' must be >= {spec.min_val:g}")
                if not spec.min_inclusive and val <= spec.min_val:
                    raise ValueError(f"Parameter '{spec.name}' must be > {spec.min_val:g}")
            if spec.max_val is not None:
                if spec.max_inclusive and val > spec.max_val:
                    raise ValueError(f"Parameter '{spec.name}' must be <= {spec.max_val:g}")
                if not spec.max_inclusive and val >= spec.max_val:
                    raise ValueError(f"Parameter '{spec.name}' must be < {spec.max_val:g}")
            coerced[spec.name] = val

    if dist_id == "uniform" and float(coerced["b"]) <= float(coerced["a"]):
        raise ValueError("Uniform distribution requires b > a")
    if dist_id == "hypergeom":
        M = int(coerced["M"])
        K = int(coerced["K"])
        n = int(coerced["n"])
        if K > M:
            raise ValueError(f"Hypergeometric requires K <= M (got K={K}, M={M})")
        if n > M:
            raise ValueError(f"Hypergeometric requires n <= M (got n={n}, M={M})")

    return coerced


def _build_frozen(dist_id: DistributionId, p: dict[str, float | int]) -> Any:
    if dist_id == "normal":
        return stats.norm(loc=p["mu"], scale=p["sigma"])
    if dist_id == "student_t":
        return stats.t(df=p["df"], loc=p["mu"], scale=p["sigma"])
    if dist_id == "chi2":
        return stats.chi2(df=p["df"])
    if dist_id == "f":
        return stats.f(dfn=p["dfn"], dfd=p["dfd"])
    if dist_id == "exponential":
        return stats.expon(scale=1.0 / float(p["lam"]))
    if dist_id == "uniform":
        return stats.uniform(loc=p["a"], scale=float(p["b"]) - float(p["a"]))
    if dist_id == "gamma":
        return stats.gamma(a=p["alpha"], scale=1.0 / float(p["beta"]))
    if dist_id == "beta":
        return stats.beta(a=p["alpha"], b=p["beta"])
    if dist_id == "lognormal":
        return stats.lognorm(s=p["sigma"], scale=math.exp(float(p["mu"])))
    if dist_id == "binomial":
        return stats.binom(n=p["n"], p=p["p"])
    if dist_id == "poisson":
        return stats.poisson(mu=p["lam"])
    if dist_id == "geometric":
        return stats.geom(p=p["p"], loc=-1)
    if dist_id == "negbinom":
        return stats.nbinom(n=p["r"], p=p["p"])
    if dist_id == "hypergeom":
        return stats.hypergeom(M=p["M"], n=p["K"], N=p["n"])
    raise ValueError(f"Unsupported distribution: {dist_id}")


def _support_bounds(dist_id: DistributionId, p: dict[str, float | int]) -> tuple[float | None, float | None]:
    if dist_id in ("normal", "student_t"):
        return (None, None)
    if dist_id in ("chi2", "f", "exponential", "gamma", "lognormal"):
        return (0.0, None)
    if dist_id == "uniform":
        return (float(p["a"]), float(p["b"]))
    if dist_id == "beta":
        return (0.0, 1.0)
    if dist_id == "binomial":
        return (0.0, float(p["n"]))
    if dist_id in ("poisson", "geometric", "negbinom"):
        return (0.0, None)
    if dist_id == "hypergeom":
        M, K, n = int(p["M"]), int(p["K"]), int(p["n"])
        return (float(max(0, n + K - M)), float(min(n, K)))
    return (None, None)


def _compute_mode(dist_id: DistributionId, p: dict[str, float | int]) -> tuple[float | None, str | None]:
    if dist_id in ("normal", "student_t"):
        return (float(p["mu"]), None)
    if dist_id == "chi2":
        df = float(p["df"])
        return (max(df - 2.0, 0.0), None)
    if dist_id == "f":
        d1, d2 = float(p["dfn"]), float(p["dfd"])
        if d1 > 2.0:
            return (((d1 - 2.0) / d1) * (d2 / (d2 + 2.0)), None)
        return (0.0 if d1 == 2.0 else None, "Asymptote at 0+" if d1 < 2.0 else None)
    if dist_id == "exponential":
        return (0.0, None)
    if dist_id == "uniform":
        return (None, f"Any x ∈ [{float(p['a']):g}, {float(p['b']):g}]")
    if dist_id == "gamma":
        a, b = float(p["alpha"]), float(p["beta"])
        return ((a - 1.0) / b if a >= 1.0 else None, "Asymptote at 0+" if a < 1.0 else None)
    if dist_id == "beta":
        a, b = float(p["alpha"]), float(p["beta"])
        if a > 1.0 and b > 1.0:
            return ((a - 1.0) / (a + b - 2.0), None)
        if a == 1.0 and b == 1.0:
            return (None, "Any x ∈ [0, 1]")
        if a < 1.0 and b < 1.0:
            return (None, "Bimodal {0, 1}")
        if a <= 1.0 and b > 1.0:
            return (0.0 if a == 1.0 else None, "Asymptote at 0+" if a < 1.0 else None)
        return (1.0 if b == 1.0 else None, "Asymptote at 1−" if b < 1.0 else None)
    if dist_id == "lognormal":
        mu, sigma = float(p["mu"]), float(p["sigma"])
        return (math.exp(mu - sigma * sigma), None)
    if dist_id == "binomial":
        return (float(math.floor((int(p["n"]) + 1) * float(p["p"]))), None)
    if dist_id == "poisson":
        return (float(math.floor(float(p["lam"]))), None)
    if dist_id == "geometric":
        return (0.0, None)
    if dist_id == "negbinom":
        r, prob = float(p["r"]), float(p["p"])
        return (float(math.floor((r - 1.0) * (1.0 - prob) / prob)) if r > 1.0 else 0.0, None)
    if dist_id == "hypergeom":
        M, K, n = int(p["M"]), int(p["K"]), int(p["n"])
        return (float(math.floor(((n + 1) * (K + 1)) / (M + 2))), None)
    return (None, None)


def _compute_summary(dist_id: DistributionId, p: dict[str, float | int], frozen: Any) -> dict[str, Any]:
    notes: dict[str, str] = {}
    mean_v, var_v, skew_v, kurt_v = frozen.stats(moments="mvsk")
    mean_f = clean_float(float(mean_v))
    var_f = clean_float(float(var_v))
    std_f = clean_float(math.sqrt(var_f)) if var_f is not None and var_f >= 0.0 else None
    skew_f = clean_float(float(skew_v))
    kurt_f = clean_float(float(kurt_v))
    median_f = clean_float(float(frozen.median()))
    mode_f, mode_label = _compute_mode(dist_id, p)

    try:
        ent_raw = float(frozen.entropy())
        entropy_f = clean_float(ent_raw)
    except (ValueError, ZeroDivisionError):
        entropy_f = None

    if dist_id == "student_t":
        df = float(p["df"])
        if df <= 1.0:
            mean_f = None
            notes["mean"] = "Undefined (requires ν > 1)"
        if df <= 2.0:
            var_f = None
            std_f = None
            notes["variance"] = "Infinite/undefined (requires ν > 2)"
        if df <= 3.0:
            skew_f = None
            notes["skewness"] = "Undefined (requires ν > 3)"
        if df <= 4.0:
            kurt_f = None
            notes["excess_kurtosis"] = "Infinite/undefined (requires ν > 4)"
    elif dist_id == "f":
        dfd = float(p["dfd"])
        if dfd <= 2.0:
            mean_f = None
            notes["mean"] = "Undefined (requires d₂ > 2)"
        if dfd <= 4.0:
            var_f = None
            std_f = None
            notes["variance"] = "Infinite/undefined (requires d₂ > 4)"
        if dfd <= 6.0:
            skew_f = None
            notes["skewness"] = "Undefined (requires d₂ > 6)"
        if dfd <= 8.0:
            kurt_f = None
            notes["excess_kurtosis"] = "Infinite/undefined (requires d₂ > 8)"

    if mode_label:
        notes["mode"] = mode_label

    return {
        "mean": mean_f,
        "variance": var_f,
        "std": std_f,
        "median": median_f,
        "mode": clean_float(mode_f),
        "mode_label": mode_label,
        "skewness": skew_f,
        "excess_kurtosis": kurt_f,
        "entropy": entropy_f,
        "moment_notes": notes,
    }


def _discrete_prob_le(frozen: Any, x: float, s_min: float) -> float:
    k = math.floor(x)
    if k < s_min:
        return 0.0
    return float(frozen.cdf(k))


def _discrete_prob_ge(frozen: Any, x: float, s_min: float, s_max: float | None) -> float:
    k = math.ceil(x)
    if k <= s_min:
        return 1.0
    if s_max is not None and k > s_max:
        return 0.0
    return float(frozen.sf(k - 1))


def _compute_region_prob(
    dist_id: DistributionId,
    p: dict[str, float | int],
    frozen: Any,
    region: str,
    a: float | None,
    b: float | None,
) -> dict[str, Any]:
    meta = _CATALOG[dist_id]
    is_discrete = meta.family == "discrete"
    s_min, s_max = _support_bounds(dist_id, p)
    med = float(frozen.median())

    if region == "none":
        return {"probability": None, "complement": None, "expression": "Density / Mass overview", "a": a, "b": b}

    if region == "left":
        if a is None:
            raise ValueError("Bound 'a' is required for left-tail region P(X ≤ a)")
        prob = _discrete_prob_le(frozen, a, s_min or 0.0) if is_discrete else float(frozen.cdf(a))
        comp = float(frozen.sf(math.floor(a))) if is_discrete else float(frozen.sf(a))
        expr = f"P(X ≤ {int(math.floor(a))})" if is_discrete else f"P(X ≤ {a:g})"
        return {"probability": min(1.0, max(0.0, prob)), "complement": min(1.0, max(0.0, comp)), "expression": expr, "a": a, "b": b}

    if region == "right":
        bound = b if b is not None else a
        if bound is None:
            raise ValueError("Bound 'b' is required for right-tail region P(X ≥ b)")
        if is_discrete:
            prob = _discrete_prob_ge(frozen, bound, s_min or 0.0, s_max)
            k = math.ceil(bound)
            comp = float(frozen.cdf(k - 1)) if k > (s_min or 0.0) else 0.0
            expr = f"P(X ≥ {int(k)})"
        else:
            prob = float(frozen.sf(bound))
            comp = float(frozen.cdf(bound))
            expr = f"P(X ≥ {bound:g})"
        return {"probability": min(1.0, max(0.0, prob)), "complement": min(1.0, max(0.0, comp)), "expression": expr, "a": a, "b": bound}

    if region == "interval":
        if a is None or b is None:
            raise ValueError("Both bounds 'a' and 'b' are required for interval region P(a ≤ X ≤ b)")
        lo, hi = (a, b) if a <= b else (b, a)
        if is_discrete:
            k_min = math.ceil(lo)
            k_max = math.floor(hi)
            if k_min > k_max:
                prob = 0.0
            elif k_min > med:
                prob = max(0.0, float(frozen.sf(k_min - 1) - frozen.sf(k_max)))
            else:
                cdf_hi = float(frozen.cdf(k_max))
                cdf_lo = float(frozen.cdf(k_min - 1)) if k_min > (s_min or 0.0) else 0.0
                prob = max(0.0, cdf_hi - cdf_lo)
            expr = f"P({int(k_min)} ≤ X ≤ {int(k_max)})"
        else:
            if lo > med:
                prob = max(0.0, float(frozen.sf(lo) - frozen.sf(hi)))
            else:
                prob = max(0.0, float(frozen.cdf(hi) - frozen.cdf(lo)))
            expr = f"P({lo:g} ≤ X ≤ {hi:g})"
        prob = min(1.0, max(0.0, prob))
        return {"probability": prob, "complement": max(0.0, 1.0 - prob), "expression": expr, "a": lo, "b": hi}

    if region == "two_tailed":
        if a is None or b is None:
            raise ValueError("Both bounds 'a' and 'b' are required for two-tailed region P(X ≤ a or X ≥ b)")
        lo, hi = (a, b) if a <= b else (b, a)
        if is_discrete:
            k_lo = math.floor(lo)
            k_hi = math.ceil(hi)
            p_left = _discrete_prob_le(frozen, k_lo, s_min or 0.0)
            p_right = _discrete_prob_ge(frozen, k_hi, s_min or 0.0, s_max)
            if k_lo >= k_hi:
                prob = 1.0
            else:
                prob = min(1.0, p_left + p_right)
            expr = f"P(X ≤ {int(k_lo)} or X ≥ {int(k_hi)})"
        else:
            p_left = float(frozen.cdf(lo))
            p_right = float(frozen.sf(hi))
            prob = min(1.0, p_left + p_right)
            expr = f"P(X ≤ {lo:g} or X ≥ {hi:g})"
        return {"probability": prob, "complement": max(0.0, 1.0 - prob), "expression": expr, "a": lo, "b": hi}

    raise ValueError(f"Unsupported region: {region}")


def _auto_x_range(
    dist_id: DistributionId,
    p: dict[str, float | int],
    frozen: Any,
    a: float | None,
    b: float | None,
) -> tuple[float, float]:
    meta = _CATALOG[dist_id]
    s_min, s_max = _support_bounds(dist_id, p)

    if dist_id == "beta":
        return (0.0, 1.0)
    if dist_id == "uniform":
        span = float(p["b"]) - float(p["a"])
        return (float(p["a"]) - 0.18 * span, float(p["b"]) + 0.18 * span)

    if meta.family == "discrete":
        q_lo = float(frozen.ppf(0.0005))
        q_hi = float(frozen.ppf(0.9995))
        if not math.isfinite(q_lo):
            q_lo = s_min if s_min is not None else 0.0
        if not math.isfinite(q_hi):
            q_hi = (s_min or 0.0) + 25.0
        lo = max(s_min, q_lo - 1.0) if s_min is not None else q_lo - 1.0
        hi = min(s_max, q_hi + 1.0) if s_max is not None else q_hi + 1.0
        if hi - lo < 6:
            hi = min(s_max, lo + 8) if s_max is not None else lo + 8
        if hi - lo > 160:
            mean_f, var_f = frozen.stats(moments="mv")
            sd = math.sqrt(max(float(var_f), 1.0))
            lo = max(s_min or 0.0, math.floor(float(mean_f) - 4.0 * sd))
            hi = min(s_max if s_max is not None else 1e9, math.ceil(float(mean_f) + 4.0 * sd))
        return (float(lo), float(hi))

    # Continuous
    q_lo = float(frozen.ppf(0.001))
    q_hi = float(frozen.ppf(0.999))
    if dist_id == "student_t":
        mu, sigma = float(p["mu"]), float(p["sigma"])
        q_lo = max(q_lo, mu - 10.0 * sigma)
        q_hi = min(q_hi, mu + 10.0 * sigma)
    elif dist_id == "f":
        q_lo = 0.0
        q_hi = min(q_hi, 18.0) if float(p["dfd"]) <= 4.0 else min(q_hi, 40.0)
    elif dist_id == "lognormal":
        q_lo = 0.0
        q_hi = min(q_hi, math.exp(float(p["mu"]) + 3.2 * float(p["sigma"])))

    if s_min is not None:
        q_lo = max(s_min, q_lo)
    if s_max is not None:
        q_hi = min(s_max, q_hi)
    if not math.isfinite(q_lo) or not math.isfinite(q_hi) or q_hi <= q_lo:
        q_lo, q_hi = (s_min or 0.0), (s_min or 0.0) + 10.0

    # Expand moderately for user bounds if reasonable
    span = q_hi - q_lo
    for bound in (a, b):
        if bound is not None and math.isfinite(bound):
            if s_min is None or bound >= s_min:
                q_lo = min(q_lo, max(bound - 0.15 * span, q_lo - 2.0 * span))
            if s_max is None or bound <= s_max:
                q_hi = max(q_hi, min(bound + 0.15 * span, q_hi + 2.0 * span))

    return (float(q_lo), float(q_hi))


def _sample_curve(
    dist_id: DistributionId,
    p: dict[str, float | int],
    frozen: Any,
    x_min: float,
    x_max: float,
    points: int,
    label: str,
) -> dict[str, Any]:
    meta = _CATALOG[dist_id]
    if meta.family == "discrete":
        s_min, s_max = _support_bounds(dist_id, p)
        k_lo = int(max(s_min if s_min is not None else -1e9, math.floor(x_min)))
        k_hi = int(min(s_max if s_max is not None else 1e9, math.ceil(x_max)))
        if k_hi - k_lo > 240:
            ks = np.unique(np.round(np.linspace(k_lo, k_hi, 180)).astype(int))
        else:
            ks = np.arange(k_lo, k_hi + 1, dtype=int)
        pmf = frozen.pmf(ks)
        cdf = frozen.cdf(ks)
        return {
            "dist": dist_id,
            "family": "discrete",
            "label": label,
            "x": [int(k) for k in ks],
            "density": [clean_float(float(v)) or 0.0 for v in pmf],
            "cdf": [clean_float(float(v)) or 0.0 for v in cdf],
        }

    s_min, s_max = _support_bounds(dist_id, p)
    lo = max(x_min, s_min) if s_min is not None else x_min
    hi = min(x_max, s_max) if s_max is not None else x_max
    if hi <= lo:
        hi = lo + 1.0
    xs = np.linspace(lo, hi, points)
    # Guard boundary asymptotes at x == 0 or x == 1
    eps = (hi - lo) * 1e-4
    if s_min is not None and abs(xs[0] - s_min) < eps:
        xs[0] = s_min + eps
    if s_max is not None and abs(xs[-1] - s_max) < eps:
        xs[-1] = s_max - eps

    pdf = frozen.pdf(xs)
    cdf = frozen.cdf(xs)
    # Cap extreme vertical asymptotes visually while preserving finite floats
    finite_vals = pdf[np.isfinite(pdf)]
    cap = float(np.percentile(finite_vals, 98) * 3.0) if finite_vals.size > 5 else 10.0
    cap = max(cap, 1.0)
    pdf_clean = [clean_float(min(float(v), cap)) if math.isfinite(float(v)) else cap for v in pdf]
    cdf_clean = [clean_float(float(v)) or 0.0 for v in cdf]
    return {
        "dist": dist_id,
        "family": "continuous",
        "label": label,
        "x": [float(v) for v in xs],
        "density": pdf_clean,
        "cdf": cdf_clean,
    }


def _format_label(dist_id: DistributionId, p: dict[str, float | int]) -> str:
    args = ", ".join(f"{k}={v:g}" if isinstance(v, float) else f"{k}={v}" for k, v in p.items())
    return f"{_CATALOG[dist_id].name} ({args})"


def get_catalog() -> dict[str, Any]:
    """Return metadata for all 14 supported distributions plus curated presets."""
    dists = []
    for meta in _CATALOG.values():
        dists.append(
            {
                "id": meta.id,
                "name": meta.name,
                "family": meta.family,
                "notation": meta.notation,
                "support": meta.support,
                "formula_latex": meta.formula_latex,
                "note": meta.note,
                "params": [
                    {
                        "name": ps.name,
                        "label": ps.label,
                        "kind": ps.kind,
                        "default": ps.default,
                        "min": ps.min_val,
                        "max": ps.max_val,
                        "min_inclusive": ps.min_inclusive,
                        "max_inclusive": ps.max_inclusive,
                        "step": ps.step,
                        "slider_min": ps.slider_min,
                        "slider_max": ps.slider_max,
                    }
                    for ps in meta.params
                ],
            }
        )
    return {"distributions": dists, "presets": _PRESETS}


def evaluate_distribution(req: DistEvaluateRequest) -> dict[str, Any]:
    """Evaluate moments, region probability (via sf/isf), and curves with overlays."""
    p = _validate_and_coerce_params(req.dist, req.params)
    frozen = _build_frozen(req.dist, p)
    summary = _compute_summary(req.dist, p, frozen)
    region_res = _compute_region_prob(req.dist, p, frozen, req.region, req.a, req.b)

    x_min, x_max = _auto_x_range(req.dist, p, frozen, region_res["a"], region_res["b"])

    overlay_specs: list[tuple[DistributionId, dict[str, float | int], Any, str]] = []
    for ov in req.overlays:
        ov_p = _validate_and_coerce_params(ov.dist, ov.params)
        ov_frozen = _build_frozen(ov.dist, ov_p)
        ov_lo, ov_hi = _auto_x_range(ov.dist, ov_p, ov_frozen, None, None)
        x_min = min(x_min, ov_lo)
        x_max = max(x_max, ov_hi)
        ov_label = ov.label or _format_label(ov.dist, ov_p)
        overlay_specs.append((ov.dist, ov_p, ov_frozen, ov_label))

    primary_curve = _sample_curve(
        req.dist, p, frozen, x_min, x_max, req.points, _format_label(req.dist, p)
    )
    overlay_curves = [
        _sample_curve(ov_id, ov_p, ov_frozen, x_min, x_max, req.points, ov_label)
        for ov_id, ov_p, ov_frozen, ov_label in overlay_specs
    ]

    meta = _CATALOG[req.dist]
    return {
        "dist": req.dist,
        "name": meta.name,
        "family": meta.family,
        "notation": meta.notation,
        "support": meta.support,
        "formula_latex": meta.formula_latex,
        "params": p,
        "view": req.view,
        "region": req.region,
        "a": clean_float(region_res["a"]),
        "b": clean_float(region_res["b"]),
        "probability": clean_float(region_res["probability"]),
        "complement": clean_float(region_res["complement"]),
        "expression": region_res["expression"],
        "summary": summary,
        "x_domain": [float(x_min), float(x_max)],
        "primary": primary_curve,
        "overlays": overlay_curves,
    }


def solve_quantile(req: DistQuantileRequest) -> dict[str, Any]:
    """Solve inverse quantile bounds (a, b) for a target probability using ppf/isf."""
    p = _validate_and_coerce_params(req.dist, req.params)
    frozen = _build_frozen(req.dist, p)
    meta = _CATALOG[req.dist]
    is_discrete = meta.family == "discrete"
    s_min, s_max = _support_bounds(req.dist, p)
    q = float(req.target_p)

    a: float | None = None
    b: float | None = None

    if req.region == "left":
        val = float(frozen.ppf(q))
        a = float(int(round(val))) if is_discrete else val
    elif req.region == "right":
        if is_discrete:
            k_raw = int(round(float(frozen.isf(q))))
            # isf(q) is smallest k with sf(k) <= q -> P(X >= k+1) <= q
            cand = k_raw if _discrete_prob_ge(frozen, k_raw, s_min or 0.0, s_max) <= q + 1e-12 else k_raw + 1
            if s_max is not None:
                cand = min(int(s_max), cand)
            b = float(cand)
        else:
            b = float(frozen.isf(q))
    elif req.region == "interval":
        tail = 0.5 * (1.0 - q)
        if is_discrete:
            a = float(int(round(float(frozen.ppf(tail)))))
            k_raw = int(round(float(frozen.isf(tail))))
            b = float(min(int(s_max), k_raw) if s_max is not None else k_raw)
            if b < a:
                b = a
        else:
            a = float(frozen.ppf(tail))
            b = float(frozen.isf(tail))
    elif req.region == "two_tailed":
        tail = 0.5 * q
        if is_discrete:
            a = float(int(round(float(frozen.ppf(tail)))))
            k_raw = int(round(float(frozen.isf(tail)))) + 1
            b = float(min(int(s_max), k_raw) if s_max is not None else k_raw)
        else:
            a = float(frozen.ppf(tail))
            b = float(frozen.isf(tail))

    reg = _compute_region_prob(req.dist, p, frozen, req.region, a, b)
    return {
        "dist": req.dist,
        "region": req.region,
        "target_p": q,
        "achieved_p": clean_float(reg["probability"]),
        "a": clean_float(reg["a"]),
        "b": clean_float(reg["b"]),
        "expression": reg["expression"],
    }
