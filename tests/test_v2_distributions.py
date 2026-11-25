"""Numerical accuracy tests for all 14 distributions in app.stats.distributions."""

import math

import pytest
from scipy import stats

from app.stats.distributions import evaluate_distribution, get_catalog, solve_quantile
from app.stats.schemas import DistEvaluateRequest, DistQuantileRequest


def test_catalog_completeness_and_hero_preset():
    cat = get_catalog()
    ids = {d["id"] for d in cat["distributions"]}
    expected = {
        "normal",
        "student_t",
        "chi2",
        "f",
        "exponential",
        "uniform",
        "gamma",
        "beta",
        "lognormal",
        "binomial",
        "poisson",
        "geometric",
        "negbinom",
        "hypergeom",
    }
    assert ids == expected
    assert cat["presets"][0]["id"] == "p05-normal-95"
    assert cat["presets"][0]["region"] == "two_tailed"


@pytest.mark.parametrize(
    ("dist_id", "params", "frozen", "region", "a", "b"),
    [
        ("normal", {"mu": 2.5, "sigma": 1.4}, stats.norm(loc=2.5, scale=1.4), "interval", 1.1, 4.2),
        ("student_t", {"df": 7.0, "mu": 1.0, "sigma": 2.0}, stats.t(df=7.0, loc=1.0, scale=2.0), "two_tailed", -2.5, 4.5),
        ("chi2", {"df": 6.0}, stats.chi2(df=6.0), "right", None, 12.591587243743977),
        ("f", {"dfn": 5.0, "dfd": 18.0}, stats.f(dfn=5.0, dfd=18.0), "right", None, 2.772853),
        ("exponential", {"lam": 0.4}, stats.expon(scale=2.5), "left", 3.0, None),
        ("uniform", {"a": -2.0, "b": 6.0}, stats.uniform(loc=-2.0, scale=8.0), "interval", 0.0, 3.0),
        ("gamma", {"alpha": 3.5, "beta": 1.5}, stats.gamma(a=3.5, scale=1.0 / 1.5), "right", None, 4.0),
        ("beta", {"alpha": 2.0, "beta": 5.0}, stats.beta(a=2.0, b=5.0), "interval", 0.1, 0.5),
        ("lognormal", {"mu": 0.2, "sigma": 0.6}, stats.lognorm(s=0.6, scale=math.exp(0.2)), "right", None, 2.5),
    ],
)
def test_continuous_distributions_match_scipy(dist_id, params, frozen, region, a, b):
    res = evaluate_distribution(
        DistEvaluateRequest(dist=dist_id, params=params, region=region, a=a, b=b)
    )
    mean, var, skew, kurt = frozen.stats(moments="mvsk")
    assert math.isclose(res["summary"]["mean"], float(mean), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["variance"], float(var), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["skewness"], float(skew), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["excess_kurtosis"], float(kurt), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["median"], float(frozen.median()), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["entropy"], float(frozen.entropy()), rel_tol=1e-10, abs_tol=1e-12)

    if region == "left":
        ref_p = float(frozen.cdf(a))
    elif region == "right":
        ref_p = float(frozen.sf(b))
    elif region == "interval":
        ref_p = float(frozen.cdf(b) - frozen.cdf(a))
    else:
        ref_p = float(frozen.cdf(a) + frozen.sf(b))
    assert math.isclose(res["probability"], ref_p, rel_tol=1e-10, abs_tol=1e-12)


@pytest.mark.parametrize(
    ("dist_id", "params", "frozen", "region", "a", "b"),
    [
        ("binomial", {"n": 25, "p": 0.35}, stats.binom(n=25, p=0.35), "interval", 6, 12),
        ("poisson", {"lam": 4.5}, stats.poisson(mu=4.5), "right", None, 7),
        ("geometric", {"p": 0.3}, stats.geom(p=0.3, loc=-1), "left", 2, None),
        ("negbinom", {"r": 5, "p": 0.4}, stats.nbinom(n=5, p=0.4), "right", None, 10),
        ("hypergeom", {"M": 52, "K": 13, "n": 5}, stats.hypergeom(M=52, n=13, N=5), "interval", 1, 3),
    ],
)
def test_discrete_distributions_match_scipy(dist_id, params, frozen, region, a, b):
    res = evaluate_distribution(
        DistEvaluateRequest(dist=dist_id, params=params, region=region, a=a, b=b)
    )
    mean, var, skew, kurt = frozen.stats(moments="mvsk")
    assert math.isclose(res["summary"]["mean"], float(mean), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["variance"], float(var), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["skewness"], float(skew), rel_tol=1e-10, abs_tol=1e-12)
    assert math.isclose(res["summary"]["excess_kurtosis"], float(kurt), rel_tol=1e-10, abs_tol=1e-12)

    if region == "left":
        ref_p = float(frozen.cdf(a))
    elif region == "right":
        ref_p = float(frozen.sf(b - 1))
    else:
        ref_p = float(frozen.cdf(b) - (frozen.cdf(a - 1) if a > 0 else 0.0))
    assert math.isclose(res["probability"], ref_p, rel_tol=1e-10, abs_tol=1e-12)


def test_geometric_zero_indexed_failures_contract():
    # P(X=0) = p, P(X<=2) = 1 - (1-p)^3
    res = evaluate_distribution(
        DistEvaluateRequest(dist="geometric", params={"p": 0.3}, region="left", a=2, b=None)
    )
    assert math.isclose(res["primary"]["density"][0], 0.3, rel_tol=1e-12)
    assert math.isclose(res["probability"], 1.0 - 0.7**3, rel_tol=1e-12)


def test_extreme_tail_sf_precision_no_cancellation():
    # Naive 1 - cdf(9) underflows to 0.0 in IEEE 754 float64; sf stays exact!
    for z in (9.0, 15.0, 30.0):
        res = evaluate_distribution(
            DistEvaluateRequest(dist="normal", params={"mu": 0.0, "sigma": 1.0}, region="right", a=None, b=z)
        )
        ref = float(stats.norm.sf(z))
        assert res["probability"] > 0.0
        assert math.isclose(res["probability"], ref, rel_tol=1e-12)

    # Upper-half interval P(9 <= Z <= 10) must not collapse to 0.0
    res_int = evaluate_distribution(
        DistEvaluateRequest(dist="normal", params={"mu": 0.0, "sigma": 1.0}, region="interval", a=9.0, b=10.0)
    )
    ref_int = float(stats.norm.sf(9.0) - stats.norm.sf(10.0))
    assert res_int["probability"] > 0.0
    assert math.isclose(res_int["probability"], ref_int, rel_tol=1e-12)

    # Discrete deep upper tail: Binomial(n=100, p=0.5), P(X >= 90)
    res_bin = evaluate_distribution(
        DistEvaluateRequest(dist="binomial", params={"n": 100, "p": 0.5}, region="right", a=None, b=90)
    )
    assert res_bin["probability"] > 0.0
    assert math.isclose(res_bin["probability"], float(stats.binom.sf(89, 100, 0.5)), rel_tol=1e-12)


def test_undefined_moments_json_safe():
    # Student's t(df=1) Cauchy has undefined mean/var/skew/kurt; F(2, 2) has undefined mean/var
    res_t = evaluate_distribution(
        DistEvaluateRequest(dist="student_t", params={"df": 1.0, "mu": 0.0, "sigma": 1.0}, region="two_tailed", a=-12.706, b=12.706)
    )
    assert res_t["summary"]["mean"] is None
    assert res_t["summary"]["variance"] is None
    assert "mean" in res_t["summary"]["moment_notes"]

    res_f = evaluate_distribution(
        DistEvaluateRequest(dist="f", params={"dfn": 2.0, "dfd": 2.0}, region="right", a=None, b=19.0)
    )
    assert res_f["summary"]["mean"] is None
    assert res_f["summary"]["variance"] is None


def test_quantile_round_trip_and_overlays():
    q = solve_quantile(
        DistQuantileRequest(dist="normal", params={"mu": 0.0, "sigma": 1.0}, target_p=0.05, region="two_tailed")
    )
    assert math.isclose(q["a"], -1.959963984540054, rel_tol=1e-9)
    assert math.isclose(q["b"], 1.959963984540054, rel_tol=1e-9)
    assert math.isclose(q["achieved_p"], 0.05, rel_tol=1e-9)

    # Extreme quantile via isf
    q_ext = solve_quantile(
        DistQuantileRequest(dist="normal", params={"mu": 0.0, "sigma": 1.0}, target_p=1e-20, region="right")
    )
    assert math.isclose(q_ext["b"], float(stats.norm.isf(1e-20)), rel_tol=1e-10)

    # Overlays (up to 3 curves total)
    ov = evaluate_distribution(
        DistEvaluateRequest(
            dist="student_t",
            params={"df": 3.0, "mu": 0.0, "sigma": 1.0},
            region="right",
            b=2.0,
            overlays=[
                {"dist": "student_t", "params": {"df": 10.0, "mu": 0.0, "sigma": 1.0}},
                {"dist": "normal", "params": {"mu": 0.0, "sigma": 1.0}},
            ],
        )
    )
    assert len(ov["overlays"]) == 2
